# -*- coding: utf-8 -*-
"""Watched/started/unseen marker: it must follow UserData.Played, NOT
PlayCount. Emby bumps PlayCount on every stop (even one a few seconds in,
zeroing the resume position), so PlayCount>0 does not mean watched -
otherwise briefly-sampled movies show up as fully seen (deco regression)."""

import unittest

from tests import helpers

helpers.setup_environment()


def _item(played=False, playCount=0, posTicks=0):
	return {
		"Id": "1", "Name": "movie", "Type": "Movie", "RunTimeTicks": 60000000000,
		"UserData": {"Played": played, "PlayCount": playCount, "PlaybackPositionTicks": posTicks},
	}


class TestViewStateFromPlayed(unittest.TestCase):

	def setUp(self):
		self.lib = helpers.make_emby_instance(mock=None)

	def _state(self, **kwargs):
		entryData = self.lib.itemToEntryData(_item(**kwargs))
		return self.lib.getViewStatefromViewCount(entryData)

	def test_barely_watched_is_unseen(self):
		# the deco bug: stop a movie seconds in -> Emby returns PlayCount=1,
		# Played=False, position 0. This must be UNSEEN, not seen.
		self.assertEqual(self._state(played=False, playCount=1, posTicks=0), "unseen")

	def test_played_is_seen(self):
		self.assertEqual(self._state(played=True, playCount=1, posTicks=0), "seen")

	def test_partial_position_is_started(self):
		self.assertEqual(self._state(played=False, playCount=0, posTicks=15300000000), "started")

	def test_played_wins_over_leftover_position(self):
		self.assertEqual(self._state(played=True, playCount=2, posTicks=15300000000), "seen")

	def test_untouched_is_unseen(self):
		self.assertEqual(self._state(played=False, playCount=0, posTicks=0), "unseen")

	def test_played_flag_is_string_boolean(self):
		self.assertEqual(self.lib.itemToEntryData(_item(played=True))["played"], "1")
		self.assertEqual(self.lib.itemToEntryData(_item(played=False))["played"], "0")

	def test_playcount_alone_never_marks_seen(self):
		# even a high PlayCount with no Played flag is not "seen"
		self.assertEqual(self._state(played=False, playCount=9, posTicks=0), "unseen")


if __name__ == "__main__":
	unittest.main()
