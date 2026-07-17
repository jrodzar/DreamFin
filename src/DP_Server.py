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
from Components.ActionMap import ActionMap
from Components.ConfigList import ConfigListScreen
from Components.Sources.StaticText import StaticText
from Components.Sources.List import List
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.config import config, getConfigListEntry, configfile

from Screens.MessageBox import MessageBox
from Screens.Screen import Screen

from .__common__ import printl2 as printl
from .__init__ import initServerEntryConfig, _  # _ is translation

from .DP_Mappings import DPS_Mappings
from .DPH_ScreenHelper import DPH_PlexScreen
from .DP_ViewFactory import getGuiElements
#===============================================================================
#
#===============================================================================


class DPS_Server(Screen, DPH_PlexScreen):

	def __init__(self, session, what=None):
		printl("", self, "S")

		Screen.__init__(self, session)
		DPH_PlexScreen.__init__(self)

		self.guiElements = getGuiElements()

		self["Title"] = Label(_("System Server"))

		self["entryList"] = List(self.builEntryList(), True)
		self["header"] = Label()
		self["columnHeader"] = Label()

		self["btn_redText"] = Label()
		self["btn_red"] = Pixmap()

		self["btn_greenText"] = Label()
		self["btn_green"] = Pixmap()

		self["btn_yellowText"] = Label()
		self["btn_yellow"] = Pixmap()

		self["btn_blueText"] = Label()
		self["btn_blue"] = Pixmap()

		self["actions"] = ActionMap(["WizardActions", "MenuActions", "ShortcutActions"],
			{
			 "ok": self.keyOk,
			 "back": self.keyClose,
			 "red": self.keyRed,
			 "green": self.keyGreen,
			 }, -1)
		self.what = what

		self.onLayoutFinish.append(self.finishLayout)

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def finishLayout(self):
		printl("", self, "S")

		# first we set the pics for buttons
		self.setColorFunctionIcons()

		self["header"].setText(_("Server List:"))

		if self.skinResolution == "FHD":  # FHD is used for FULL HD Boxes with new framebuffer
			self["columnHeader"].setText(_("Name                                         IP/DNS                                                Port                                              Active"))
		else:
			self["columnHeader"].setText(_("Name                                         IP/DNS                                     Port                                        Active"))

		self["btn_redText"].setText(_("Delete"))
		self["btn_greenText"].setText(_("Add"))
		self["btn_yellowText"].hide()
		self["btn_yellow"].hide()
		self["btn_blueText"].hide()
		self["btn_blue"].hide()

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def builEntryList(self):
		printl("", self, "S")

		self.myEntryList = []

		for serverConfig in config.plugins.dreamfin.Entries:

			name = serverConfig.name.value

			if serverConfig.connectionType.value == "1":
				text1 = serverConfig.dns.value
			else:
				text1 = "%d.%d.%d.%d" % tuple(serverConfig.ip.value)
			text2 = "%d" % serverConfig.port.value

			active = str(serverConfig.state.value)

			self.myEntryList.append((name, text1, text2, active, serverConfig))

		printl("", self, "C")
		return self.myEntryList

	#===========================================================================
	#
	#===========================================================================
	def updateList(self):
		printl("", self, "S")

		self["entryList"].setList(self.builEntryList())

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def keyClose(self):
		printl("", self, "S")

		self.close(self.session, self.what, None)

		printl("", self, "C")

	#=======================================================================
	#
	#=======================================================================
	def keyGreen(self):
		printl("", self, "S")

		self.session.openWithCallback(self.updateList, DPS_ServerConfig, None)

		printl("", self, "C")

	#=======================================================================
	#
	#=======================================================================
	def keyRed(self):
		printl("", self, "S")

		try:
			sel = self["entryList"].getCurrent()[4]

		except Exception as ex:
			printl("Exception: " + str(ex), self, "W")
			sel = None

		if sel is None:
			return

		self.session.openWithCallback(self.deleteConfirm, MessageBox, _("Really delete this Server Entry?"))

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def keyOk(self):
		printl("", self, "S")

		try:
			sel = self["entryList"].getCurrent()[4]

		except Exception as ex:
			printl("Exception: " + str(ex), self, "W")
			sel = None

		if sel is None:
			return

		printl("config selction: " + str(sel), self, "D")
		self.session.openWithCallback(self.updateList, DPS_ServerConfig, sel)

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def deleteConfirm(self, result):
		printl("", self, "S")

		if not result:
			return

		sel = self["entryList"].getCurrent()[4]
		config.plugins.dreamfin.entriescount.value -= 1
		config.plugins.dreamfin.entriescount.save()
		config.plugins.dreamfin.Entries.remove(sel)
		config.plugins.dreamfin.Entries.save()
		config.plugins.dreamfin.save()
		configfile.save()
		self.updateList()

		printl("", self, "C")

#===============================================================================
#
#===============================================================================


class DPS_ServerConfig(ConfigListScreen, Screen, DPH_PlexScreen):

	useMappings = False

	def __init__(self, session, entry):
		printl("", self, "S")

		Screen.__init__(self, session)

		self.guiElements = getGuiElements()

		self["actions"] = ActionMap(["DPS_ServerConfig", "ColorActions"],
		{
			"green": self.keySave,
			"cancel": self.keyCancel,
		    "exit": self.keyCancel,
			"yellow": self.keyYellow,
			"left": self.keyLeft,
			"right": self.keyRight,
		}, -2)

		self["help"] = StaticText()

		self["Title"] = Label(_("Server Config"))

		self["btn_redText"] = Label()
		self["btn_red"] = Pixmap()

		self["btn_greenText"] = Label()
		self["btn_green"] = Pixmap()

		self["btn_yellowText"] = Label()
		self["btn_yellow"] = Pixmap()

		self["btn_blueText"] = Label()
		self["btn_blue"] = Pixmap()

		if entry is None:
			self.newmode = 1
			self.current = initServerEntryConfig()

		else:
			self.newmode = 0
			self.current = entry
			self.currentId = self.current.id.value
			printl("currentId: " + str(self.currentId), self, "D")

		self.cfglist = []
		ConfigListScreen.__init__(self, self.cfglist, session)

		self["config"].onSelectionChanged.append(self.updateHelp)

		self.onLayoutFinish.append(self.finishLayout)

		self.onShown.append(self.showSetup)

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def finishLayout(self):
		printl("", self, "S")

		# first we set the pics for buttons
		self.setColorFunctionIcons()

		self.setKeyNames()

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def showSetup(self):
		printl("", self, "S")

		self.onShown = []
		self.createSetup()

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def createSetup(self):
		printl("", self, "S")

		separator = "".ljust(250, "_")

		self.cfglist = []
		##
		self.cfglist.append(getConfigListEntry(_("General Settings ") + separator, config.plugins.dreamfin.about, _("-")))
		##
		self.cfglist.append(getConfigListEntry(_(" > State"), self.current.state, _("Toggle state to on/off to show this server in the list or not.")))
		self.cfglist.append(getConfigListEntry(_(" > Autostart"), self.current.autostart, _("Enter this server automatically on startup.")))
		self.cfglist.append(getConfigListEntry(_(" > Name"), self.current.name, _("Simply a name for better overview")))
		self.cfglist.append(getConfigListEntry(_(" > Trailer"), self.current.loadExtraData, _("Enable trailer function. Only works with PlexPass or YYTrailer plugin.")))

		##
		self.cfglist.append(getConfigListEntry(_("Connection Settings ") + separator, config.plugins.dreamfin.about, _(" ")))
		##
		self.cfglist.append(getConfigListEntry(_(" > Connection Type"), self.current.connectionType, _("Select your type how the box is reachable.")))

		if self.current.connectionType.value == "0":  # IP
			self.addIpSettings()
		else:  # DNS
			self.cfglist.append(getConfigListEntry(_(" >> DNS"), self.current.dns, _("Host name of your Emby/Jellyfin server, e.g. jellyfin.example.com")))
			self.cfglist.append(getConfigListEntry(_(" >> Port"), self.current.port, _("8096 is the default port. 443 and 8920 imply https.")))

		self.cfglist.append(getConfigListEntry(_(" > Server Type"), self.current.serverType, _("Auto detects Emby vs Jellyfin on first contact and sets the color theme.")))
		self.cfglist.append(getConfigListEntry(_(" > Username"), self.current.username, _("User to log in with. Not needed when an API key is set.")))
		self.cfglist.append(getConfigListEntry(_(" > Password"), self.current.password, _("Stored as plain text in the enigma2 settings; prefer an API key if that worries you.")))
		self.cfglist.append(getConfigListEntry(_(" > API key (optional)"), self.current.accessToken, _("Emby/Jellyfin API key. When set it wins over username/password.")))

		##
		self.cfglist.append(getConfigListEntry(_("Playback Settings ") + separator, config.plugins.dreamfin.about, _(" ")))
		##

		self.cfglist.append(getConfigListEntry(_(" > Playback Type"), self.current.playbackType, _(" ")))
		if self.current.playbackType.value == "0":
			self.useMappings = False

		elif self.current.playbackType.value == "1":
			self.useMappings = False
			self.cfglist.append(getConfigListEntry(_(" >> Transcoding quality"), self.current.uniQuality, _("Requested transcode resolution/bitrate.")))
			self.cfglist.append(getConfigListEntry(_(" >> Transcode video codec"), self.current.transcodeVideoCodec, _("H.264 for maximum compatibility (older gstreamer / OpenATV 6.4). HEVC gives better quality at a lower bitrate on boxes that decode it, if the server can encode HEVC.")))
			self.cfglist.append(getConfigListEntry(_(" >> Progressive stream (HLS fallback)"), self.current.progressiveTranscode, _("Enable only if HLS playback stutters/fails: streams a single .ts instead of the m3u8.")))

		elif self.current.playbackType.value == "2":
			self.useMappings = True
			self.cfglist.append(getConfigListEntry(_("> Search and use forced subtitles"), self.current.useForcedSubtitles, _("Monitor playback to activate subtitles automatically if needed. You have to enable subtitles with the 'Text' button first.")))

		elif self.current.playbackType.value == "3":
			self.useMappings = False
			#self.cfglist.append(getConfigListEntry(_(">> Username"), self.current.smbUser))
			#self.cfglist.append(getConfigListEntry(_(">> Password"), self.current.smbPassword))
			#self.cfglist.append(getConfigListEntry(_(">> Server override IP"), self.current.nasOverrideIp))
			#self.cfglist.append(getConfigListEntry(_(">> Servers root"), self.current.nasRoot))

		if self.current.playbackType.value == "2":
			##
			self.cfglist.append(getConfigListEntry(_("Subtitle Settings ") + separator, config.plugins.dreamfin.about, _(" ")))
			##
			self.cfglist.append(getConfigListEntry(_(" >> Enable Subtitle renaming in direct local mode"), self.current.srtRenamingForDirectLocal, _("Renames filename.eng.srt automatically to filename.srt so e2 is able to read them.")))
			if self.current.srtRenamingForDirectLocal.value:
				self.cfglist.append(getConfigListEntry(_(" >> Target subtitle language"), self.current.subtitlesLanguage, _("Search string that should be removed from srt file.")))

		##
		self.cfglist.append(getConfigListEntry(_("Wake On Lan Settings ") + separator, config.plugins.dreamfin.about, _(" ")))
		##
		self.cfglist.append(getConfigListEntry(_(" > Use Wake on Lan (WoL)"), self.current.wol, _(" ")))

		if self.current.wol.value:
			self.cfglist.append(getConfigListEntry(_(" >> Mac address (Size: 12 alphanumeric no seperator) only for WoL"), self.current.wol_mac, _(" ")))
			self.cfglist.append(getConfigListEntry(_(" >> Wait for server delay (max 180 seconds) only for WoL"), self.current.wol_delay, _(" ")))

		self["config"].list = self.cfglist
		self["config"].l.setList(self.cfglist)

		self.setKeyNames()

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def addIpSettings(self):
		printl("", self, "S")

		self.cfglist.append(getConfigListEntry(_(" >> IP"), self.current.ip, _(" ")))
		self.cfglist.append(getConfigListEntry(_(" >> Port"), self.current.port, _(" ")))

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def updateHelp(self):
		printl("", self, "S")

		cur = self["config"].getCurrent()
		printl("cur: " + str(cur), self, "D")
		self["help"].setText(cur[2])  # = cur and cur[2] or ""

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def setKeyNames(self):
		printl("", self, "S")

		self["btn_greenText"].setText(_("Save"))

		if self.useMappings and self.newmode == 0:
			self["btn_yellowText"].setText(_("Mappings"))
			self["btn_yellowText"].show()
			self["btn_yellow"].show()
		else:
			self["btn_yellowText"].hide()
			self["btn_yellow"].hide()

		self["btn_redText"].hide()
		self["btn_red"].hide()
		self["btn_blueText"].hide()
		self["btn_blue"].hide()

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
	def keySave(self):
		printl("", self, "S")

		if self.newmode == 1:
			config.plugins.dreamfin.entriescount.value += 1
			config.plugins.dreamfin.entriescount.save()

		# connection or account details may have changed: drop the cached
		# session so the next request logs in freshly against this config
		self.current.accessTokenCache.value = ""
		self.current.userIdCache.value = ""

		self.saveNow()

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def saveNow(self, retval=None):
		printl("", self, "S")

		config.plugins.dreamfin.entriescount.save()
		config.plugins.dreamfin.Entries.save()
		config.plugins.dreamfin.save()
		configfile.save()

		self.close()

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def keyCancel(self):
		printl("", self, "S")

		if self.newmode == 1:
			config.plugins.dreamfin.Entries.remove(self.current)
		ConfigListScreen.cancelConfirm(self, True)

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def keyYellow(self):
		printl("", self, "S")

		if self.useMappings:
			serverID = self.currentId
			serverpaths = []  # section paths for Direct Local come back in phase 2
			self.session.open(DPS_Mappings, serverID, serverpaths)

		printl("", self, "C")
