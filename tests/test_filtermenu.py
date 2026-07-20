# -*- coding: utf-8 -*-
"""Contract: the synthesized menu key literals the UI routes by."""

import io
import os
import unittest

from tests import helpers
from tests.embymock import MockEmby

helpers.setup_environment()

AUTH_PATH = "/Users/AuthenticateByName"

# DP_LibShows switches these keys into the direct episode browser; the
# synthesized menu must keep producing them verbatim. "recentlyAdded" is NOT
# here on purpose - it is grouped by series and browses like the show list
# (see test_recently_added_shows_group_by_series).
ROUTED_KEYS = ("onDeck", "newest", "recentlyViewed")


def section_root(sectionType, sectionId="40"):
	return {
		"title": "Section",
		"type": sectionType,
		"key": sectionId,
		"section": sectionId,
		"address": "127.0.0.1:1",
		"server": "127.0.0.1:1",
		"isSectionRoot": True,
	}


class TestFilterMenuContract(unittest.TestCase):

	def setUp(self):
		self.mock = MockEmby().start()
		self.mock.add_json(AUTH_PATH, helpers.fixture_json("auth_ok_emby.json"), method="POST")
		self.mock.add_json("/System/Info/Public", helpers.fixture_json("system_info_public_emby.json"))

	def tearDown(self):
		self.mock.stop()

	def _lib(self):
		lib = helpers.make_emby_instance(self.mock)
		self.assertTrue(lib.authenticate())
		return lib

	def test_the_ui_router_still_checks_the_same_literals(self):
		"""If upstream ever renames the special-cased keys in
		DP_LibShows.loadLibrary, this contract must be revisited."""
		path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "DP_LibShows.py")
		with io.open(path, encoding="utf-8") as fd:
			source = fd.read()
		for literal in ROUTED_KEYS:
			self.assertIn('"%s"' % literal, source)

	def test_recently_added_shows_group_by_series(self):
		"""recentlyAdded for series must NOT be routed into the direct episode
		browser: the backend returns Series (grouped by show), so DP_LibShows
		lets it fall back to the "show" view and browse like the full list.
		If it were special-cased to ShowEpisodesDirect the Series items would be
		rendered as (unplayable) episodes."""
		path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "DP_LibShows.py")
		with io.open(path, encoding="utf-8") as fd:
			source = fd.read()
		self.assertNotIn('"recentlyAdded"', source)

	def test_movie_menu_keeps_the_routed_literals(self):
		lib = self._lib()
		keys = [e[3]["key"] for e in lib.getSectionFilter(section_root("movie"))]
		for literal in ("onDeck", "recentlyAdded", "newest"):
			self.assertIn(literal, keys)

	def test_show_menu_keeps_the_routed_literals(self):
		lib = self._lib()
		keys = [e[3]["key"] for e in lib.getSectionFilter(section_root("show"))]
		for literal in ("onDeck", "recentlyAdded"):
			self.assertIn(literal, keys)

	def test_global_entries_reuse_the_literals(self):
		self.mock.add_json("/Users/user0000000000000000000000000001/Views",
						helpers.fixture_json("views_emby.json"))
		lib = self._lib()
		sections = lib.getAllSections()

		self.assertEqual(sections[0][3]["key"], "onDeck")
		self.assertEqual(sections[1][3]["key"], "recentlyAdded")


if __name__ == "__main__":
	unittest.main()
