# -*- coding: utf-8 -*-
"""
DreamPlex Plugin by DonDavici, 2012
and jbleyel 2021

Original -> https://github.com/oe-alliance/DreamPlex
Fork -> https://github.com/oe-alliance/DreamPlex

Some of the code is from other plugins:
all credits to the coders :-)

DreamPlex Plugin is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 2 of the License, or
(at your option) any later version.

DreamPlex Plugin is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
"""
#=================================
#IMPORT
#=================================
from Components.ActionMap import HelpableActionMap
from Components.Input import Input
from Components.Sources.List import List
from Components.Sources.StaticText import StaticText
from Components.config import config
from Components.Pixmap import Pixmap, MultiPixmap
from Components.Label import Label

from Screens.MessageBox import MessageBox

from .DPH_Singleton import Singleton
from .DPH_MovingLabel import DPH_HorizontalMenu
from .DP_HelperScreens import DPS_InputBox
from .DPH_ScreenHelper import DPH_ScreenHelper, DPH_Screen, DPH_Filter, DPH_PlexScreen
from .DP_ViewFactory import getGuiElements

from .__common__ import printl2 as printl, getLiveTv, runInThread
from .__plugin__ import Plugin
from .__init__ import _  # _ is translation

#===============================================================================
#
#===============================================================================

# Subclass of List to support horizontal menu


class DPS_List(List):
	def __init__(self):
		List.__init__(self)

	def selectPrevious(self):
		if self.getIndex() - 1 < 0:
			self.index = self.count() - 1
		else:
			self.index -= 1
		self.setIndex(self.index)

	def selectNext(self):
		if self.getIndex() + 1 >= self.count():
			self.index = 0
		else:
			self.index += 1
		self.setIndex(self.index)


class DPS_ServerMenu(DPH_Screen, DPH_HorizontalMenu, DPH_ScreenHelper, DPH_Filter, DPH_PlexScreen):

	g_horizontal_menu = False

	selectedEntry = None
	g_serverConfig = None

	g_serverDataMenu = None
	currentService = None
	plexInstance = None
	selectionOverride = None
	secondRun = False
	menuStep = 0  # vaule how many steps we made to restore navigation data
	currentMenuDataDict = {}
	currentIndexDict = {}

	#===========================================================================
	#
	#===========================================================================
	def __init__(self, session, g_serverConfig):
		printl("", self, "S")
		DPH_Screen.__init__(self, session)
		DPH_ScreenHelper.__init__(self)
		DPH_Filter.__init__(self)
		DPH_PlexScreen.__init__(self)

		self.selectionOverride = None
		printl("selectionOverride:" + str(self.selectionOverride), self, "D")
		self.session = session

		self.g_serverConfig = g_serverConfig
		self.plexInstance = Singleton().getBackendInstance()
		self.guiElements = getGuiElements()

		self.initScreen("server_menu")
		self.initMenu()

		if self.g_horizontal_menu:
			self.setHorMenuElements(depth=2)
			self.translateNames()

		self["title"] = StaticText()

		self["menu"] = DPS_List()

		self["actions"] = HelpableActionMap(self, "DP_MainMenuActions",
			{
				"ok": (self.okbuttonClick, ""),
				"left": (self.left, ""),
				"right": (self.right, ""),
				"up": (self.up, ""),
				"down": (self.down, ""),
				"cancel": (self.cancel, ""),
			}, -2)

		self["btn_green"] = Pixmap()
		self["btn_green"].hide()
		self["btn_greenText"] = Label()

		# rotating busy spinner, shown while sections/filters load in the
		# background (see startBusy/stopBusy in DPH_ScreenHelper)
		self["busy"] = MultiPixmap()
		self["busy"].hide()

		self["text_HomeUserLabel"] = Label()
		self["text_HomeUser"] = Label()

		# stop the busy spinner timer if the screen is closed mid-load
		self.onClose.append(self.stopBusy)

		self.onLayoutFinish.append(self.finishLayout)
		# getInitialData loads asynchronously now; the steps that need the
		# data (menu_main_list, selection override) run in its callback
		self.onLayoutFinish.append(self.getInitialData)

		printl("", self, "C")

	#===============================================================================
	#
	#===============================================================================
	def finishLayout(self):
		printl("", self, "S")

		self.setTitle(_("Server Menu"))

		# first we set the pics for buttons
		self.setColorFunctionIcons()

		if self.miniTv:
			self.initMiniTv()

		printl("", self, "C")

	#===============================================================================
	#
	#===============================================================================
	def getInitialData(self):
		printl("", self, "S")

		# the follow-up steps need the data, so they run in the callback
		self.getServerData(initialLoad=True)

		printl("", self, "C")

	#===============================================================================
	#
	#===============================================================================
	def finishInitialData(self):
		printl("", self, "S")

		# save the mainMenuList for later usage
		self.menu_main_list = self["menu"].list

		if self.g_horizontal_menu:
			# init horizontal menu
			self.refreshOrientationHorMenu(0)

		self.checkSelectionOverride()

		printl("", self, "C")

	#===============================================================================
	#
	#===============================================================================
	def checkSelectionOverride(self):
		printl("", self, "S")
		printl("self.selectionOverride: " + str(self.selectionOverride), self, "D")

		if self.selectionOverride is not None:
			self.okbuttonClick()

		printl("", self, "C")

#===============================================================================
# KEYSTROKES
#===============================================================================

	#===============================================================
	#
	#===============================================================
	def okbuttonClick(self):
		printl("", self, "S")

		self.currentMenuDataDict[self.menuStep] = self.g_serverDataMenu
		printl("currentMenuDataDict: " + str(self.currentMenuDataDict), self, "D")

		# first of all we save the data from the current step
		self.currentIndexDict[self.menuStep] = self["menu"].getIndex()

		# now we increase the step value because we go to the next step
		self.menuStep += 1
		printl("menuStep: " + str(self.menuStep), self, "D")

		# this is used to step in directly into a server when there is only one entry in the serverlist
		if self.selectionOverride is not None:
			selection = self.selectionOverride

			# because we change the screen we have to unset the information to be able to return to main menu
			self.selectionOverride = None
		else:
			selection = self["menu"].getCurrent()

		printl("selection = " + str(selection), self, "D")

		if selection is not None and selection:

			self.selectedEntry = selection[1]
			printl("selected entry " + str(self.selectedEntry), self, "D")

			if type(self.selectedEntry) is int:
				printl("selected entry is int", self, "D")

				if self.selectedEntry == Plugin.MENU_MOVIES:
					printl("found Plugin.MENU_MOVIES", self, "D")
					self.getServerData("movies")

				elif self.selectedEntry == Plugin.MENU_TVSHOWS:
					printl("found Plugin.MENU_TVSHOWS", self, "D")
					self.getServerData("tvshow")

				elif self.selectedEntry == Plugin.MENU_MUSIC:
					printl("found Plugin.MENU_MUSIC", self, "D")
					self.getServerData("music")

				elif self.selectedEntry == Plugin.MENU_FILTER:
					printl("found Plugin.MENU_FILTER", self, "D")
					self.getFilterData(selection[3])

				elif self.selectedEntry == Plugin.MENU_SERVERFILTER:
					self.getServerData(filterBy=selection[3]['myCurrentFilterData'], serverFilterActive=selection[3]['serverName'])

			else:
				printl("selected entry is executable", self, "D")
				self.mediaType = selection[2]
				printl("mediaType: " + str(self.mediaType), self, "D")

				entryData = selection[3]
				printl("entryData: " + str(entryData), self, "D")

				hasPromptTag = entryData.get('hasPromptTag', False)
				printl("hasPromptTag: " + str(hasPromptTag), self, "D")
				if hasPromptTag:
					self.session.openWithCallback(self.addSearchString, DPS_InputBox, entryData, title=_("Please enter your search string: "), text=" " * 55, maxSize=55, type=Input.TEXT)
				else:
					self.menuStep -= 1
					self.executeSelectedEntry(entryData)

			self.refreshMenu()
		else:
			printl("no data, leaving ...", self, "D")
			self.cancel()

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def addSearchString(self, entryData, searchString=None):
		printl("", self, "S")
		printl("entryData: " + str(entryData), self, "D")

		if searchString is not None:
			if "origContentUrl" in entryData[0]:
				searchUrl = entryData[0]["origContentUrl"] + "&SearchTerm=" + searchString
			else:
				searchUrl = entryData[0]["contentUrl"] + "&SearchTerm=" + searchString
				entryData[0]["origContentUrl"] = entryData[0]["contentUrl"]

			printl("searchUrl: " + str(searchUrl), self, "D")

			entryData[0]["contentUrl"] = searchUrl

		self.executeSelectedEntry(entryData[0])

		printl("", self, "C")

	#===========================================================================
	# this function starts DP_Lib...
	#===========================================================================
	def executeSelectedEntry(self, entryData):
		printl("", self, "S")

		if self.selectedEntry.start is not None:
			printl("we are startable ...", self, "D")
			self.session.openWithCallback(self.myCallback, self.selectedEntry.start, entryData)

		elif self.selectedEntry.fnc is not None:
			printl("we are a function ...", self, "D")
			self.selectedEntry.fnc(self.session)

		if config.plugins.dreamfin.showFilter.value:
			self.selectedEntry = Plugin.MENU_FILTER  # we overwrite this now to handle correct menu jumps with exit/cancel button

		printl("", self, "C")

	#==========================================================================
	#
	#==========================================================================
	def myCallback(self):
		printl("", self, "S")

		if not config.plugins.dreamfin.stopLiveTvOnStartup.value:
			self.session.nav.playService(getLiveTv(), forceRestart=True)

		printl("", self, "C")

	#==========================================================================
	#
	#==========================================================================
	def up(self):
		printl("", self, "S")

		if self.g_horizontal_menu:
			self.left()
		else:
			self["menu"].selectPrevious()

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def down(self):
		printl("", self, "S")

		if self.g_horizontal_menu:
			self.right()
		else:
			self["menu"].selectNext()

		printl("", self, "C")

	#===============================================================================
	#
	#===============================================================================
	def right(self):
		printl("", self, "S")

		try:
			if self.g_horizontal_menu:
				self.refreshOrientationHorMenu(+1)
			else:
				self["menu"].pageDown()
		except Exception as ex:
			printl("Exception(" + str(type(ex)) + "): " + str(ex), self, "W")
			self["menu"].selectNext()

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def left(self):
		printl("", self, "S")

		try:
			if self.g_horizontal_menu:
				self.refreshOrientationHorMenu(-1)
			else:
				self["menu"].pageUp()
		except Exception as ex:
			printl("Exception(" + str(type(ex)) + "): " + str(ex), self, "W")
			self["menu"].selectPrevious()

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def exit(self):
		printl("", self, "S")

		self.close((True,))

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def cancel(self):
		printl("", self, "S")
		self.menuStep -= 1
		printl("menuStep: " + str(self.menuStep), self, "D")

		if self.menuStep >= 0:
			self.g_serverDataMenu = self.currentMenuDataDict[self.menuStep]
			self["menu"].setList(self.g_serverDataMenu)
			self.beforeFilterListViewList = self.g_serverDataMenu
			self["menu"].setIndex(self.currentIndexDict[self.menuStep])
			self.refreshMenu()
		else:
			self.exit()

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def refreshMenu(self):
		printl("", self, "S")

		if self.g_horizontal_menu:
			self.refreshOrientationHorMenu(0)

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def getServerData(self, filterBy=None, serverFilterActive=False, initialLoad=False):
		printl("", self, "S")

		# the request can take seconds (or hang on an unreachable plex.tv):
		# do it off the main loop so the GUI stays alive
		def work():
			if config.plugins.dreamfin.summerizeSections.value and filterBy is None:
				return self.plexInstance.getSectionTypes()
			return self.plexInstance.getAllSections(myFilter=filterBy, serverFilterActive=serverFilterActive)

		def onDone(serverData, error):
			self.onServerDataReady(serverData, error, initialLoad)

		self.startBusy()
		runInThread(work, onDone)

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def onServerDataReady(self, serverData, error, initialLoad=False):
		printl("", self, "S")

		self.stopBusy()

		if error is not None:
			printl("error while loading server data: " + str(error), self, "E")

		if not serverData:
			self.showNoDataMessage()
		else:
			self.g_serverDataMenu = serverData  # lets save the menu to call it when cancel is pressed

			self["menu"].setList(serverData)
			self.beforeFilterListViewList = self.g_serverDataMenu
			self.refreshMenu()
			try:
				self["menu"].top()
			except:
				try:
					self["menu"].setIndex(0)
				except:
					pass

		if initialLoad:
			self.finishInitialData()

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def getFilterData(self, entryData):
		printl("", self, "S")

		self.startBusy()
		runInThread(lambda: self.plexInstance.getSectionFilter(entryData), self.onFilterDataReady)

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def onFilterDataReady(self, menuData, error):
		printl("", self, "S")

		self.stopBusy()

		if error is not None:
			printl("error while loading filter data: " + str(error), self, "E")

		if not menuData:
			self.showNoDataMessage()
			self.menuStep -= 1
			printl("menuStep: " + str(self.menuStep), self, "D")

		else:
			self["menu"].setList(menuData)
			self.g_serverDataMenu = menuData  # lets save the menu to call it when cancel is pressed
			self.beforeFilterListViewList = self.g_serverDataMenu
			self.refreshMenu()

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def showNoDataMessage(self):
		printl("", self, "S")

		text = self.plexInstance.getLastErrorMessage()
		self.session.open(MessageBox, _("\n%s") % text, MessageBox.TYPE_INFO)

		printl("", self, "C")
