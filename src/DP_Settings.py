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
from enigma import eListboxPythonMultiContent, gFont, RT_HALIGN_LEFT, RT_VALIGN_CENTER

from Components.ActionMap import ActionMap
from Components.ConfigList import ConfigListScreen
from Components.MenuList import MenuList
from Components.Sources.StaticText import StaticText
from Components.config import config, getConfigListEntry, configfile
from Components.Label import Label
from Components.Pixmap import Pixmap

from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen

from .__common__ import printl2 as printl
from .__init__ import _  # _ is translation

from .DP_PathSelector import DPS_PathSelector
from .DPH_ScreenHelper import DPH_PlexScreen
from .DP_ViewFactory import getGuiElements

#===============================================================================
#
#===============================================================================


class DPS_Settings(Screen, ConfigListScreen, HelpableScreen, DPH_PlexScreen):

	_hasChanged = False
	_session = None
	skins = None

	def __init__(self, session):
		printl("", self, "S")

		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		DPH_PlexScreen.__init__(self)

		self.guiElements = getGuiElements()

		self.cfglist = []
		ConfigListScreen.__init__(self, self.cfglist, session, on_change=self._changed)

		self._hasChanged = False

		self["Title"] = Label(_("System Settings"))
		self["btn_greenText"] = Label()
		self["btn_green"] = Pixmap()

		self["help"] = StaticText()

		self["setupActions"] = ActionMap(["SetupActions", "ColorActions", "DPS_Settings"],
		{
			"green": self.keySave,
			"red": self.keyCancel,
			"cancel": self.keyCancel,
			"ok": self.ok,
			"left": self.keyLeft,
			"right": self.keyRight,
			"bouquet_up": self.keyBouquetUp,
			"bouquet_down": self.keyBouquetDown,
		}, -2)

		self.createSetup()

		self["config"].onSelectionChanged.append(self.updateHelp)
		self.onLayoutFinish.append(self.finishLayout)

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def finishLayout(self):
		printl("", self, "S")

		# first we set the pics for buttons
		self.setColorFunctionIcons()

		self["btn_greenText"].hide()
		self["btn_green"].hide()

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def createSetup(self):
		printl("", self, "S")

		separator = "".ljust(240, "_")

		self.cfglist = []

		# GENERAL SETTINGS
		self.cfglist.append(getConfigListEntry(_("General Settings ") + separator, config.plugins.dreamfin.about, _(" ")))
		self.cfglist.append(getConfigListEntry(_("> Boxname"), config.plugins.dreamfin.boxName, _("Enter the name of your box, e.g. Livingroom.")))
		self.cfglist.append(getConfigListEntry(_("> Used Skin"), config.plugins.dreamfin.skin, _("If you change the skin you have to restart at least the GUI!")))
		self.cfglist.append(getConfigListEntry(_("> Show Plugin in Main Menu"), config.plugins.dreamfin.showInMainMenu, _("Use this to start the plugin direct in the main menu.")))
		self.cfglist.append(getConfigListEntry(_("> Use Cache for Sections"), config.plugins.dreamfin.useCache, _("Save server answers in cache to speed up a bit.")))
		self.cfglist.append(getConfigListEntry(_("> Use Picture Cache"), config.plugins.dreamfin.usePicCache, _("Use this only if you do have enough space on your hdd drive or flash.")))
		self.cfglist.append(getConfigListEntry(_("> Show Player Poster on external LCD"), config.plugins.dreamfin.lcd4linux, _("e.g. lcd4linux")))

		# USERINTERFACE SETTINGS
		self.cfglist.append(getConfigListEntry(_("Userinterface Settings ") + separator, config.plugins.dreamfin.about, _(" ")))
		self.cfglist.append(getConfigListEntry(_("> Summerize Servers"), config.plugins.dreamfin.summerizeServers, _("Summarize servers in an additional menu step.")))
		self.cfglist.append(getConfigListEntry(_("> Summerize Sections"), config.plugins.dreamfin.summerizeSections, _("Summerize sections in an additional menu step.")))
		self.cfglist.append(getConfigListEntry(_("> Show Filter for Section"), config.plugins.dreamfin.showFilter, _("Show additional filter in an additional menu step e.g. OnDeck")))
		self.cfglist.append(getConfigListEntry(_("> Show Seen/Unseen count in TvShows"), config.plugins.dreamfin.showUnSeenCounts, _("Calculate and show them for tv shows.")))
		self.cfglist.append(getConfigListEntry(_("> Mark recently added content (days)"), config.plugins.dreamfin.newContentDays, _("Badge content added within this many days. 'Off' disables it. Uses the library add date, not the release date.")))
		self.cfglist.append(getConfigListEntry(_("> Start with Filtermode"), config.plugins.dreamfin.startWithFilterMode, _("Start with filtermode in any media view.")))
		self.cfglist.append(getConfigListEntry(_("> Exit function in Player"), config.plugins.dreamfin.exitFunction, _("Specifiy what the exit button in the player should do.")))

		self.cfglist.append(getConfigListEntry(_("> Show Backdrops as Videos"), config.plugins.dreamfin.useBackdropVideos, _("Use this if you have m1v videos as backdrops")))
		self.cfglist.append(getConfigListEntry(_("> Stop Live TV on startup"), config.plugins.dreamfin.stopLiveTvOnStartup, _("Stop live TV. Enables 'play themes', 'use backdrop videos'")))

		# playing themes stops live tv for this reason we enable this only if live stops on startup is set
		# also backdrops as video needs to turn of live tv
		if config.plugins.dreamfin.stopLiveTvOnStartup.value:
			# if backdrop videos are active we have to turn off theme playback
			if config.plugins.dreamfin.useBackdropVideos.value:
				config.plugins.dreamfin.playTheme.value = False
			else:
				self.cfglist.append(getConfigListEntry(_(">> Play Themes in TV Shows"), config.plugins.dreamfin.playTheme, _("Plays tv show themes automatically.")))
		else:
			# if the live startup stops is not set we have to turn of playtheme automatically
			config.plugins.dreamfin.playTheme.value = False
			#config.plugins.dreamfin.useBackdropVideos.value = False

		if config.plugins.dreamfin.useBackdropVideos.value:
			config.plugins.dreamfin.fastScroll.value = False
			config.plugins.dreamfin.liveTvInViews.value = False
		else:
			self.cfglist.append(getConfigListEntry(_("> Use fastScroll as default"), config.plugins.dreamfin.fastScroll, _("No update for addiontal informations in media views to speed up.")))
			if not config.plugins.dreamfin.stopLiveTvOnStartup.value:
				self.cfglist.append(getConfigListEntry(_("> Show liveTv in Views instead of backdrops"), config.plugins.dreamfin.liveTvInViews, _("Show live tv while you are navigating through your libs.")))

		self.cfglist.append(getConfigListEntry(_("> Show additional data for sections"), config.plugins.dreamfin.showDetailsInList, _("If server summerize is off you can here add additional information for better overview.")))
		if config.plugins.dreamfin.showDetailsInList.value:
			self.cfglist.append(getConfigListEntry(_("> Detail type for additional data"), config.plugins.dreamfin.showDetailsInListDetailType, _("Specifiy the type of additional data.")))

		# VIEW SETTINGS
		self.cfglist.append(getConfigListEntry(_("Path Settings ") + separator, config.plugins.dreamfin.about, _(" ")))
		self.cfglist.append(getConfigListEntry(_("> Default View for Movies"), config.plugins.dreamfin.defaultMovieView, _("Specify what view type should start automatically.")))
		self.cfglist.append(getConfigListEntry(_("> Default View for Shows"), config.plugins.dreamfin.defaultShowView, _("Specify what view type should start automatically.")))
		self.cfglist.append(getConfigListEntry(_("> Default View for Music"), config.plugins.dreamfin.defaultMusicView, _("Specify what view type should start automatically.")))

		# PATH SETTINGS
		self.cfglist.append(getConfigListEntry(_("Path Settings ") + separator, config.plugins.dreamfin.about, _(" ")))

		self.mediafolderpath = getConfigListEntry(_("> Media Folder Path"), config.plugins.dreamfin.mediafolderpath, _("/hdd/dreamfin/medias"))
		self.cfglist.append(self.mediafolderpath)

		self.configfolderpath = getConfigListEntry(_("> Config Folder Path"), config.plugins.dreamfin.configfolderpath, _("/hdd/dreamfin/config"))
		self.cfglist.append(self.configfolderpath)

		self.cachefolderpath = getConfigListEntry(_("> Cache Folder Path"), config.plugins.dreamfin.cachefolderpath, _("/hdd/dreamfin/cache"))
		self.cfglist.append(self.cachefolderpath)

		self.playerTempPath = getConfigListEntry(_("> Player Temp Path"), config.plugins.dreamfin.playerTempPath, _("/tmp"))
		self.cfglist.append(self.playerTempPath)

		self.logfolderpath = getConfigListEntry(_("> Log Folder Path"), config.plugins.dreamfin.logfolderpath, _("/tmp"))
		self.cfglist.append(self.logfolderpath)

		# MISC
		self.cfglist.append(getConfigListEntry(_("Misc Settings ") + separator, config.plugins.dreamfin.about, _(" ")))
		self.cfglist.append(getConfigListEntry(_("> Debug Mode"), config.plugins.dreamfin.debugMode, _("Enable only if needed. Slows down rapidly.")))

		if config.plugins.dreamfin.debugMode.value:
			self.cfglist.append(getConfigListEntry(_("> Write debugfile"), config.plugins.dreamfin.writeDebugFile, _("Without this option we just print to console.")))

		self["config"].list = self.cfglist
		self["config"].l.setList(self.cfglist)

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def _changed(self):
		printl("", self, "S")

		self._hasChanged = True

		self["btn_greenText"].show()
		self["btn_greenText"].setText(_("Save"))
		self["btn_green"].show()

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def updateHelp(self):
		printl("", self, "S")

		cur = self["config"].getCurrent()
		printl("cur: " + str(cur), self, "D")
		self["help"].text = cur and cur[2] or "empty"

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def ok(self):
		printl("", self, "S")

		cur = self["config"].getCurrent()

		if cur == self.mediafolderpath:
			self.session.openWithCallback(self.savePathConfig, DPS_PathSelector, self.mediafolderpath[1].value, "media")

		elif cur == self.configfolderpath:
			self.session.openWithCallback(self.savePathConfig, DPS_PathSelector, self.configfolderpath[1].value, "config")

		elif cur == self.playerTempPath:
			self.session.openWithCallback(self.savePathConfig, DPS_PathSelector, self.playerTempPath[1].value, "player")

		elif cur == self.logfolderpath:
			self.session.openWithCallback(self.savePathConfig, DPS_PathSelector, self.logfolderpath[1].value, "log")

		elif cur == self.cachefolderpath:
			self.session.openWithCallback(self.savePathConfig, DPS_PathSelector, self.cachefolderpath[1].value, "cache")

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def savePathConfig(self, pathValue, myType):
		printl("", self, "S")

		printl("pathValue: " + str(pathValue), self, "D")
		printl("type: " + str(myType), self, "D")

		if pathValue is not None:

			if myType == "media":
				self.mediafolderpath[1].value = pathValue

			elif myType == "config":
				self.configfolderpath[1].value = pathValue

			elif myType == "player":
				self.playerTempPath[1].value = pathValue

			elif myType == "log":
				self.logfolderpath[1].value = pathValue

			elif myType == "cache":
				self.cachefolderpath[1].value = pathValue

		config.plugins.dreamfin.save()

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def keySave(self):
		printl("", self, "S")

		config.plugins.dreamfin.entriescount.save()
		config.plugins.dreamfin.Entries.save()
		config.plugins.dreamfin.save()
		configfile.save()
		self.close(None)

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def keyLeft(self):
		printl("", self, "S")

		ConfigListScreen.keyLeft(self)
		self.createSetup()

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def keyRight(self):
		printl("", self, "S")

		ConfigListScreen.keyRight(self)
		self.createSetup()

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def keyBouquetUp(self):
		printl("", self, "S")

		self["config"].instance.moveSelection(self["config"].instance.pageUp)

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def keyBouquetDown(self):
		printl("", self, "S")

		self["config"].instance.moveSelection(self["config"].instance.pageDown)

		printl("", self, "C")


#===============================================================================
#
#===============================================================================
class DPS_ServerEntryList(MenuList):

	def __init__(self, menuList, enableWrapAround=True):
		printl("", self, "S")

		MenuList.__init__(self, menuList, enableWrapAround, eListboxPythonMultiContent)
		self.l.setFont(0, gFont("Regular", 20))
		self.l.setFont(1, gFont("Regular", 18))

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def postWidgetCreate(self, instance):
		printl("", self, "S")

		MenuList.postWidgetCreate(self, instance)
		instance.setItemHeight(20)

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def buildList(self):
		printl("", self, "S")

		self.list = []

		for entry in config.plugins.dreamfin.Entries:
			res = [entry]
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 55, 0, 200, 20, 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, str(entry.name.value)))

			if entry.connectionType.value == "1":
				text1 = entry.dns.value
			else:
				text1 = "%d.%d.%d.%d" % tuple(entry.ip.value)
			text2 = "%d" % entry.port.value

			res.append((eListboxPythonMultiContent.TYPE_TEXT, 260, 0, 150, 20, 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, str(text1)))
			res.append((eListboxPythonMultiContent.TYPE_TEXT, 450, 0, 80, 20, 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, str(text2)))
			self.list.append(res)

		self.l.setList(self.list)
		self.moveToIndex(0)

		printl("", self, "C")
