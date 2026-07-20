# -*- coding: utf-8 -*-
"""Watched/started/unseen marker: it must follow UserData.Played, NOT
PlayCount. Emby bumps PlayCount on every stop (even one a few seconds in,
zeroing the resume position), so PlayCount>0 does not mean watched -
otherwise briefly-sampled movies show up as fully seen (deco regression)."""

import calendar
import time
import unittest

from tests import helpers

helpers.setup_environment()

NOW = calendar.timegm((2026, 7, 20, 12, 0, 0, 0, 0, 0))


def _ago(days):
	return time.strftime("%Y-%m-%dT%H:%M:%S.0000000Z", time.gmtime(NOW - int(days * 86400)))


def _dated(dateCreated=None, dateLastMediaAdded=None, itemType="Series"):
	item = {"Id": "1", "Name": "x", "Type": itemType, "UserData": {}}
	if dateCreated:
		item["DateCreated"] = dateCreated
	if dateLastMediaAdded:
		item["DateLastMediaAdded"] = dateLastMediaAdded
	return item


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


class TestIsNewFlag(unittest.TestCase):
	"""isNew marks content ADDED to the library recently (DateCreated, or
	DateLastMediaAdded for containers), never the premiere date. Window and
	'now' are patched so the assertion is deterministic."""

	def setUp(self):
		self.lib = helpers.make_emby_instance(mock=None)
		self.lib._nowEpoch = lambda: NOW
		self.lib._newContentDays = lambda: 7

	def test_recently_added_leaf_is_new(self):
		self.assertEqual(self.lib.itemToEntryData(_dated(dateCreated=_ago(2)))["isNew"], "1")

	def test_old_leaf_is_not_new(self):
		self.assertEqual(self.lib.itemToEntryData(_dated(dateCreated=_ago(30)))["isNew"], "0")

	def test_media_added_bubbles_an_old_series(self):
		item = _dated(dateCreated=_ago(400), dateLastMediaAdded=_ago(1))
		self.assertEqual(self.lib.itemToEntryData(item)["isNew"], "1")

	def test_premiere_date_never_makes_it_new(self):
		# added long ago, but "aired" yesterday -> still NOT new
		item = _dated(dateCreated=_ago(400))
		item["PremiereDate"] = _ago(1)
		self.assertEqual(self.lib.itemToEntryData(item)["isNew"], "0")

	def test_zero_days_setting_turns_it_off(self):
		self.lib._newContentDays = lambda: 0
		self.assertEqual(self.lib.itemToEntryData(_dated(dateCreated=_ago(0)))["isNew"], "0")

	def test_flag_is_always_present(self):
		# the view reads entryData['isNew'] unconditionally, so it must exist
		self.assertIn("isNew", self.lib.itemToEntryData(_dated()))


if __name__ == "__main__":
	unittest.main()
