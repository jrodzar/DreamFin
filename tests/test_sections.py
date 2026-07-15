# -*- coding: utf-8 -*-
"""Section listing and the synthesized filter menu against the Emby mock."""

import unittest

from tests import helpers
from tests.embymock import MockEmby

helpers.setup_environment()

from src.__plugin__ import Plugin  # noqa: E402

AUTH_PATH = "/Users/AuthenticateByName"
EMBY_UID = "user0000000000000000000000000001"
VIEWS_PATH = "/Users/%s/Views" % EMBY_UID


def wire_auth(mock, infoFixture="system_info_public_emby.json"):
	mock.add_json(AUTH_PATH, helpers.fixture_json("auth_ok_emby.json"), method="POST")
	mock.add_json("/System/Info/Public", helpers.fixture_json(infoFixture))


def section_root(sectionType="movie", sectionId="40"):
	return {
		"title": "Section",
		"type": sectionType,
		"key": sectionId,
		"section": sectionId,
		"address": "127.0.0.1:1",
		"server": "127.0.0.1:1",
		"isSectionRoot": True,
	}


class TestGetAllSections(unittest.TestCase):

	def setUp(self):
		self.mock = MockEmby().start()
		wire_auth(self.mock)

	def tearDown(self):
		self.mock.stop()

	def test_views_become_the_section_menu(self):
		self.mock.add_json(VIEWS_PATH, helpers.fixture_json("views_emby.json"))
		lib = helpers.make_emby_instance(self.mock)

		sections = lib.getAllSections()

		# 2 synthesized entries + Pel·lícules/Sèries/Documentals/Infantils/
		# Sèries infantils; boxsets, livetv and playlists are skipped
		self.assertEqual(len(sections), 7)

		for entry in sections:
			self.assertEqual(len(entry), 4)
			self.assertIsInstance(entry[3], dict)

		self.assertEqual(sections[0][3]["key"], "onDeck")
		self.assertEqual(sections[0][2], "mixedEntry")
		self.assertIn("/Items/Resume", sections[0][3]["contentUrl"])
		self.assertEqual(sections[1][3]["key"], "recentlyAdded")
		self.assertIn("/Items/Latest", sections[1][3]["contentUrl"])

		titles = [e[0] for e in sections[2:]]
		expected = [u"Pel·lícules", u"Sèries", u"Documentals",
					u"Infantils", u"Sèries infantils i juvenils"]
		self.assertEqual(titles, [helpers.nat(t) for t in expected])

		byTitle = dict((e[0], e) for e in sections)

		movies = byTitle[helpers.nat(u"Pel·lícules")]
		self.assertEqual(movies[1], Plugin.MENU_FILTER)
		self.assertEqual(movies[2], "movieEntry")
		self.assertTrue(movies[3]["isSectionRoot"])
		self.assertEqual(movies[3]["type"], "movie")
		self.assertIn("IncludeItemTypes=Movie", movies[3]["contentUrl"])
		self.assertIn("ParentId=40", movies[3]["contentUrl"])

		shows = byTitle[helpers.nat(u"Sèries")]
		self.assertEqual(shows[1], Plugin.MENU_FILTER)
		self.assertEqual(shows[2], "showEntry")
		self.assertIn("IncludeItemTypes=Series", shows[3]["contentUrl"])

		mixed = byTitle[helpers.nat(u"Documentals")]  # CollectionType None -> direct mixed browser
		self.assertEqual(mixed[2], "mixedEntry")
		self.assertEqual(mixed[3]["nextViewMode"], "mixed")

	def test_jellyfin_views_parse_identically(self):
		self.mock.add_json(AUTH_PATH, helpers.fixture_json("auth_ok_jellyfin.json"), method="POST")
		self.mock.add_json("/System/Info/Public", helpers.fixture_json("system_info_public_jellyfin.json"))
		jfViews = "/Users/user0000000000000000000000000002/Views"
		self.mock.add_json(jfViews, helpers.fixture_json("views_jellyfin.json"))

		lib = helpers.make_emby_instance(self.mock)
		sections = lib.getAllSections()

		# 2 synthesized + Documentals/Infantils/Pel·lícules/Sèries/Sèries inf.
		self.assertEqual(len(sections), 7)
		self.assertEqual(lib.getServerType(), "jellyfin")

	def test_movie_filter_keeps_only_movie_sections(self):
		self.mock.add_json(VIEWS_PATH, helpers.fixture_json("views_emby.json"))
		lib = helpers.make_emby_instance(self.mock)

		sections = lib.getAllSections(myFilter="movies")

		titles = [e[0] for e in sections]
		self.assertEqual(titles, [helpers.nat(u"Pel·lícules"), u"Infantils"])
		for entry in sections:
			self.assertEqual(entry[2], "movieEntry")

	def test_server_error_returns_empty_with_lasterror(self):
		self.mock.add_error(VIEWS_PATH, 500)
		lib = helpers.make_emby_instance(self.mock)

		self.assertEqual(lib.getAllSections(), [])
		self.assertTrue(lib.getLastErrorMessage())

	def test_section_types_are_static(self):
		lib = helpers.make_emby_instance(self.mock)
		types = lib.getSectionTypes()

		self.assertEqual([t[1] for t in types],
						[Plugin.MENU_MOVIES, Plugin.MENU_TVSHOWS, Plugin.MENU_MUSIC])


class TestSynthesizedFilter(unittest.TestCase):
	"""The synthesized menu must keep the exact key literals the UI
	routes by (DP_LibShows checks entryData['key'] against onDeck/
	recentlyAdded/newest) while pointing contentUrl at Emby requests."""

	def setUp(self):
		self.mock = MockEmby().start()
		wire_auth(self.mock)

	def tearDown(self):
		self.mock.stop()

	def _lib(self):
		lib = helpers.make_emby_instance(self.mock)
		self.assertTrue(lib.authenticate())
		return lib

	def test_movie_menu_keys_and_urls(self):
		lib = self._lib()
		menu = lib.getSectionFilter(section_root("movie"))

		keys = [e[3]["key"] for e in menu]
		self.assertEqual(keys, ["all", "all?unwatched=1", "recentlyAdded", "newest",
								"onDeck", "genre", "year", "decade", "search?type=1"])

		byKey = dict((e[3]["key"], e) for e in menu)

		self.assertIn("IncludeItemTypes=Movie", byKey["all"][3]["contentUrl"])
		self.assertIn("SortBy=SortName", byKey["all"][3]["contentUrl"])
		self.assertIn("Filters=IsUnplayed", byKey["all?unwatched=1"][3]["contentUrl"])
		self.assertIn("SortBy=DateCreated", byKey["recentlyAdded"][3]["contentUrl"])
		self.assertIn("SortBy=PremiereDate", byKey["newest"][3]["contentUrl"])
		self.assertIn("/Items/Resume", byKey["onDeck"][3]["contentUrl"])

		# secondaries route back into the filter machinery
		for key in ("genre", "year", "decade"):
			self.assertEqual(byKey[key][1], Plugin.MENU_FILTER)
			self.assertEqual(byKey[key][2], "showFilter")
			self.assertTrue(byKey[key][3]["hasSecondaryTag"])

		search = byKey["search?type=1"]
		self.assertTrue(search[3]["hasPromptTag"])
		self.assertIn("IncludeItemTypes=Movie", search[3]["contentUrl"])

		# content entries carry the section plugin route
		self.assertEqual(byKey["all"][2], "movieEntry")

	def test_show_menu_keys_and_urls(self):
		lib = self._lib()
		menu = lib.getSectionFilter(section_root("show", "54436"))

		keys = [e[3]["key"] for e in menu]
		self.assertEqual(keys, ["all", "all?unwatched=1", "recentlyAdded",
								"onDeck", "genre", "year", "search?type=2"])

		byKey = dict((e[3]["key"], e) for e in menu)
		self.assertIn("IncludeItemTypes=Series", byKey["all"][3]["contentUrl"])
		self.assertIn("/Shows/NextUp", byKey["onDeck"][3]["contentUrl"])
		self.assertIn("IncludeItemTypes=Episode", byKey["recentlyAdded"][3]["contentUrl"])
		self.assertEqual(byKey["all"][2], "showEntry")

	def test_music_menu_keys_and_urls(self):
		lib = self._lib()
		menu = lib.getSectionFilter(section_root("artist", "777"))

		keys = [e[3]["key"] for e in menu]
		self.assertEqual(keys, ["all", "recentlyAdded", "genre", "search?type=8"])

		byKey = dict((e[3]["key"], e) for e in menu)
		self.assertIn("/Artists/AlbumArtists", byKey["all"][3]["contentUrl"])
		self.assertEqual(byKey["recentlyAdded"][3]["nextViewMode"], "ShowAlbums")
		self.assertIn("IncludeItemTypes=MusicAlbum", byKey["recentlyAdded"][3]["contentUrl"])

	def test_genre_secondary_lists_the_genres(self):
		lib = self._lib()
		self.mock.add_paged("/Genres", [
			{"Name": u"Acción", "Id": "g1"},
			{"Name": "Drama", "Id": "g2"},
		])

		root = section_root("movie")
		root["key"] = "genre"
		root["hasSecondaryTag"] = True
		menu = lib.getSectionFilter(root)

		self.assertEqual(len(menu), 2)
		self.assertEqual(menu[0][0], helpers.nat(u"Acción"))
		self.assertEqual(menu[0][2], "movieEntry")
		self.assertIn("GenreIds=g1", menu[0][3]["contentUrl"])
		self.assertFalse(menu[0][3]["hasSecondaryTag"])

		request = self.mock.requests_for("/Genres")[0]
		self.assertEqual(request["query"].get("ParentId"), ["40"])

	def test_music_genres_use_the_music_endpoint(self):
		lib = self._lib()
		self.mock.add_paged("/MusicGenres", [{"Name": "Jazz", "Id": "mg1"}])

		root = section_root("artist", "777")
		root["key"] = "genre"
		menu = lib.getSectionFilter(root)

		self.assertEqual(len(menu), 1)
		self.assertIn("/Artists/AlbumArtists", menu[0][3]["contentUrl"])
		self.assertIn("GenreIds=mg1", menu[0][3]["contentUrl"])

	def test_year_secondary_sorts_descending(self):
		lib = self._lib()
		self.mock.add_paged("/Years", [
			{"Name": "1994", "Id": "y1"},
			{"Name": "2002", "Id": "y2"},
			{"Name": "1999", "Id": "y3"},
		])

		root = section_root("movie")
		root["key"] = "year"
		menu = lib.getSectionFilter(root)

		self.assertEqual([e[0] for e in menu], ["2002", "1999", "1994"])
		self.assertIn("Years=2002", menu[0][3]["contentUrl"])

	def test_decade_secondary_groups_years(self):
		lib = self._lib()
		self.mock.add_paged("/Years", [
			{"Name": "1994", "Id": "y1"},
			{"Name": "2002", "Id": "y2"},
			{"Name": "1999", "Id": "y3"},
		])

		root = section_root("movie")
		root["key"] = "decade"
		menu = lib.getSectionFilter(root)

		self.assertEqual([e[0] for e in menu], ["2000s", "1990s"])
		self.assertIn("Years=2002", menu[0][3]["contentUrl"])
		self.assertIn("Years=1994,1999", menu[1][3]["contentUrl"])

	def test_paged_secondary_is_merged(self):
		lib = self._lib()
		# 250 genres force two StartIndex/Limit pages with the default 200
		genres = [{"Name": "Genre %03d" % i, "Id": "g%d" % i} for i in range(250)]
		self.mock.add_paged("/Genres", genres)

		root = section_root("movie")
		root["key"] = "genre"
		menu = lib.getSectionFilter(root)

		self.assertEqual(len(menu), 250)
		requests = self.mock.requests_for("/Genres")
		self.assertEqual(len(requests), 2)
		self.assertEqual(requests[0]["query"].get("StartIndex"), ["0"])
		self.assertEqual(requests[1]["query"].get("StartIndex"), ["200"])


if __name__ == "__main__":
	unittest.main()
