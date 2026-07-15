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
#===============================================================================
# IMPORT
#===============================================================================
from Plugins.Plugin import PluginDescriptor

from Components.config import config, configfile

from .__init__ import prepareEnvironment, startEnvironment, _ # _ is translation
from .__common__ import getUUID, getBoxResolution

#===============================================================================
# GLOBALS
#===============================================================================


class GlobalVars:
	def __init__(self):
		self.global_session = None


globalvars = GlobalVars()

#===============================================================================
# main
# Actions to take place when starting the plugin over extensions
#===============================================================================
#noinspection PyUnusedLocal


def main(session, **kwargs):
	session.open(DPS_MainMenu)

#===========================================================================
#
#===========================================================================


def DPS_MainMenu(*args, **kwargs):
	from . import DP_MainMenu

 	# this loads the skin
	startEnvironment()

	return DP_MainMenu.DPS_MainMenu(*args, **kwargs)

#===========================================================================
#
#===========================================================================
#noinspection PyUnusedLocal


def menu_dreamplex(menuid, **kwargs):
	if menuid == "mainmenu":
		return [(_("DreamPlex"), main, "dreamplex", 47)]
	return []

#===========================================================================
#
#===========================================================================
#noinspection PyUnusedLocal


def Autostart(reason, session=None, **kwargs):

	if reason == 0:
		prepareEnvironment()
		getUUID()

	else:
		config.plugins.dreamplex.entriescount.save()
		config.plugins.dreamplex.Entries.save()
		config.plugins.dreamplex.save()
		configfile.save()

#===========================================================================
#
#===========================================================================


def sessionStart(reason, **kwargs):

	if "session" in kwargs:
		globalvars.global_session = kwargs["session"]

		# load skin data here as well
		startEnvironment()

#===============================================================================
# plugins
# Actions to take place in Plugins
#===============================================================================
#noinspection PyUnusedLocal


def Plugins(**kwargs):
	myList = []
	boxResolution = getBoxResolution()

	if boxResolution == "FHD":
		myList.append(PluginDescriptor(name="DreamPlex", description="plex client for enigma2", where=[PluginDescriptor.WHERE_PLUGINMENU], icon="pluginLogoHD.png", fnc=main))
	else:
		myList.append(PluginDescriptor(name="DreamPlex", description="plex client for enigma2", where=[PluginDescriptor.WHERE_PLUGINMENU], icon="pluginLogo.png", fnc=main))
	myList.append(PluginDescriptor(where=PluginDescriptor.WHERE_AUTOSTART, fnc=Autostart))
	myList.append(PluginDescriptor(where=PluginDescriptor.WHERE_SESSIONSTART, fnc=sessionStart))

	if config.plugins.dreamplex.showInMainMenu.value:
		myList.append(PluginDescriptor(name="DreamPlex", description=_("plex client for enigma2"), where=[PluginDescriptor.WHERE_MENU], fnc=menu_dreamplex))

	return myList
