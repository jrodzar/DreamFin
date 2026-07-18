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
from Components.Label import Label

from Screens.Screen import Screen

from .__common__ import printl2 as printl, getVersion, getSkinAuthors
from .__init__ import _  # _ is translation

#===============================================================================
#
#===============================================================================


class DPS_About(Screen):

	#===========================================================================
	#
	#===========================================================================
	def __init__(self, session):
		printl("", self, "S")

		Screen.__init__(self, session)

		self["leftText"] = Label()
		self["rightText"] = Label()

		self["setupActions"] = ActionMap(["SetupActions", "ColorActions"],
		{
			"cancel": self.keyCancel,
		}, -2)

		self.onLayoutFinish.append(self.finishLayout)

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def finishLayout(self):
		printl("", self, "S")

		self.setTitle(_("About"))

		self["leftText"].setText(self.getLeftText())
		self["rightText"].setText(self.getRightText())

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def keyCancel(self):
		printl("", self, "S")

		self.close()

		printl("", self, "C")

	#===========================================================================
	#
	#===========================================================================
	def getLeftText(self):
		printl("", self, "S")

		content = ""
		content += "Information\n\n"
		content += "DreamFin - an Emby/Jellyfin client for Enigma2 \n"
		content += "Version: \t" + getVersion() + "\n\n"
		content += "Emby/Jellyfin backend & theme:\n"
		content += "\t Claude (Anthropic), directed by jrodzar\n"
		content += "\n"
		content += "Based on DreamPlex by:\n"
		content += "\t DonDavici, jbleyel\n"
		content += "\t oe-alliance / OpenViX\n"
		content += "\n"
		content += "Skin: \t" + getSkinAuthors() + "\n"
		content += "Contributors: \t wezhunter, andyblac, rossi2000"

		printl("", self, "C")
		return content

		#===========================================================================
	#
	#===========================================================================
	def getRightText(self):
		printl("", self, "S")

		content = "Emby/Jellyfin client for Enigma2,"
		content += "\nforked from DreamPlex."
		content += "\n\n\nFind the git repository here!"
		content += "\n\n   https://github.com/jrodzar/DreamFin"
		content += "\n\n\nLicense: GPL-2.0-or-later"

		printl("", self, "C")
		return content
