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
from .DP_LibMain import DP_LibMain

from .__common__ import printl2 as printl

#===============================================================================
#
#===============================================================================


class DP_LibShows(DP_LibMain):

	#===========================================================================
	#
	#===========================================================================
	def __init__(self, session, initalEntryData):
		printl("", self, "S")

		self.initalEntryData = initalEntryData
		printl("initalEntryData: " + str(self.initalEntryData), self, "D")

		libraryName = "shows"
		DP_LibMain.__init__(self, session, libraryName)

		printl("", self, "C")

	#===============================================================================
	#
	#===============================================================================
	def loadLibrary(self, entryData=None, forceUpdate=False):
		printl("", self, "S")

		if entryData is None:
			entryData = self.initalEntryData

		# The episode-based lists (onDeck/recentlyViewed/newest) render as a flat,
		# directly-playable episode list. Recently-added is deliberately NOT here:
		# the backend now returns Series grouped by show (DateLastContentAdded), so
		# it falls back to the section type (show) and browses like the full show
		# list - clicking a series opens its seasons instead of playing an episode.
		if str(entryData.get('key')) in ("onDeck", "recentlyViewed", "newest"):
			entryData["nextViewMode"] = "ShowEpisodesDirect"
			entryData["currentViewMode"] = "ShowEpisodesDirect"
		self.currentViewMode = "ShowEpisodesDirect"

		printl("", self, "C")
		return self.loadLibraryData(entryData, forceUpdate)
