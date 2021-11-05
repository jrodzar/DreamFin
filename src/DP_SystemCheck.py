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
import sys
import time
#import httplib
import ssl

from os import system, popen
from Screens.Standby import TryQuitMainloop

from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.config import config
from Components.Label import Label

from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Screens.Console import Console as SConsole

from .__common__ import printl2 as printl, revokeCacheFiles

from .__init__ import _ # _ is translation

#===============================================================================
#
#===============================================================================


class DPS_SystemCheck(Screen):

	archVersion = None
	check = None
	latestVersion = None

	def __init__(self, session):
		printl("", self, "S")

		Screen.__init__(self, session)

		self["actions"] = ActionMap(["ColorActions", "SetupActions"],
		{
		"ok": self.startSelection,
		"cancel": self.cancel,
		"red": self.cancel,
		}, -1)

		vlist = []

#		self.archVersion = getBoxArch()

#		if self.archVersion == "mipsel":
#			vlist.append((_("Check for gst-plugin-fragmented"), "gst-plugin-fragmented"))

#		elif self.archVersion == "mips32el":
		vlist.append((_("Check for gst-plugins-bad-fragmented"), "gst-plugins-bad-fragmented"))

#		else:
#			printl("unknown oe version", self, "W")
#			vlist.append((_("Check for gst-plugin-fragmented if you are using OE16."), "gst-plugin-fragmented"))
#			vlist.append((_("Check for gst-plugins-bad-fragmented if you are using OE20."), "gst-plugins-bad-fragmented"))

		if sys.version_info[0] == 2:
			vlist.append((_("Check openSSL installation data."), "python-pyopenssl"))
			vlist.append((_("Check python imaging installation data."), "python-imaging"))
			vlist.append((_("Check python textutils installation data."), "python-textutils"))
		else:
			vlist.append((_("Check openSSL installation data."), "python3-pyopenssl"))
			vlist.append((_("Check python imaging installation data."), "python3-pillow"))
			vlist.append((_("Check python textutils installation data."), "python3-textutils"))
		vlist.append((_("Check mjpegtools intallation data."), "mjpegtools"))
		vlist.append((_("Check curl installation data."), "curl"))

		vlist.append((_("Revoke cache files manually"), "revoke_cache"))

		self["header"] = Label()
		self["content"] = MenuList(vlist)

		self.onLayoutFinish.append(self.finishLayout)

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def finishLayout(self):
		printl("", self, "S")

		self.setTitle(_("System - Systemcheck"))

		self["header"].setText(_("Functions List:"))

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def startSelection(self):
		printl("", self, "S")

		selection = self["content"].getCurrent()

		# set package name for object
		content = selection[1]

		if content == "revoke_cache":
			revokeCacheFiles()
			self.session.openWithCallback(self.close, MessageBox, _("Cache files successfully deleted."), MessageBox.TYPE_INFO)
		else:
			self.package = content

			# first we check the state
			self.checkInstallationState()

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def checkIfBetaVersion(self, foundVersion):
		printl("", self, "S")

		isBeta = foundVersion.find("beta")
		if isBeta != -1:

			printl("", self, "C")
			return True
		else:

			printl("", self, "C")
			return False

	#===========================================================================
	#
	#===========================================================================s
	def searchLatestStable(self):
		printl("", self, "S")

		isStable = False
		latestStabel = ""
		leftLimiter = 0

		while not isStable:
			starter = self.response.find('},', leftLimiter)
			printl("starter: " + str(starter), self, "D")
			end = starter + 50
			closer = self.response.find('",', starter, end)
			printl("closer: " + str(closer), self, "D")
			# is a bit dirty but better than forcing users to install simplejson
			start = (self.response.find('": "', starter, end)) + 4 # we correct the string here right away => : "1.09-beta.9 becomes 1.09.beta.9
			latestStabel = self.response[start:closer]
			printl("found version: " + str(latestStabel), self, "D")
			isBeta = self.checkIfBetaVersion(latestStabel)
			if not isBeta:
				isStable = True
			else:
				leftLimiter = closer

		printl("latestStable: " + str(latestStabel), self, "D")

		printl("", self, "C")
		return latestStabel

	#===========================================================================
	# override is used to get bool as answer and not the plugin information
	#===========================================================================
	def checkInstallationState(self, override=False):
		printl("", self, "S")

		command = "opkg status " + str(self.package)

		state = self.executeStateCheck(command, override)

		printl("", self, "C")
		return state

	#===============================================================================
	#
	#===============================================================================
	def executeStateCheck(self, command, override=False):
		printl("", self, "S")

		pipe = popen(command)

		if pipe:
			data = pipe.read(8192)
			pipe.close()
			if data is not None and data != "":
				if override:
					return True
				# plugin is installed
				self.session.open(MessageBox, _("Information:\n") + data, MessageBox.TYPE_INFO)
			else:
				if override:
					return False

				# if plugin is not installed
				self.session.openWithCallback(self.installPackage, MessageBox, _("The selected lib/package/plugin is not installed!\n Do you want to proceed to install?"), MessageBox.TYPE_YESNO)

		printl("", self, "C")

	#===============================================================================
	#
	#===============================================================================
	def installPackage(self, confirm):
		printl("", self, "S")

		command = ""

		if confirm:
			# User said 'Yes'

			command = "opkg update; opkg install " + str(self.package)

			self.executeInstallationCommand(command)
		else:
			# User said 'no'
			self.cancel()

		printl("", self, "C")

	#===============================================================================
	#
	#===============================================================================
	def executeInstallationCommand(self, command):
		printl("", self, "S")

		self.session.open(SConsole, "Excecuting command:", [command], self.finishupdate)

		printl("", self, "C")

	#===================================================================
	#
	#===================================================================
	def cancel(self):
		printl("", self, "S")

		self.close(False, self.session)

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def finishupdate(self):
		printl("", self, "S")

		time.sleep(2)
		self.session.openWithCallback(self.e2restart, MessageBox, _("Enigma2 must be restarted!\nShould Enigma2 now restart?"), MessageBox.TYPE_YESNO)

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def e2restart(self, answer):
		printl("", self, "S")

		if answer is True:
			try:
				self.session.open(TryQuitMainloop, 3)
			except Exception as ex:
				printl("Exception: " + str(ex), self, "W")
				data = "TryQuitMainLoop is not implemented in your OS.\n Please restart your box manually."
				self.session.open(MessageBox, _("Information:\n") + data, MessageBox.TYPE_INFO)
		else:
			self.close()

		printl("", self, "C")
