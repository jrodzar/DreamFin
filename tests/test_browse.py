# -*- coding: utf-8 -*-
"""Navigation: item parsing, list tuples and the golden string rule."""

import json
import unittest

from tests import helpers
from tests.embymock import MockEmby

helpers.setup_environment()

from src.DP_EmbyLibrary import EmbyLibrary, ticksToMs, msToTicks  # noqa: E402
from src.__common__ import IMAGE_SIZE_PLACEHOLDER  # noqa: E402

AUTH_PATH = "/Users/AuthenticateByName"
EMBY_UID = "user0000000000000000000000000001"
ITEMS_PATH = "/Users/%s/Items" % EMBY_UID


def wire_auth(mock):
	mock.add_json(AUTH_PATH, helpers.fixture_json("auth_ok_emby.json"), method="POST")
	mock.add_json("/System/Info/Public", helpers.fixture_json("system_info_public_emby.json"))


def assert_all_strings(test, mapping, context):
	"""Golden rule: every scalar an entryData carries must be native str."""
	for key, value in mapping.items():
		if isinstance(value, (dict, list)) or value is None:
			continue
		test.assertIsInstance(value, str, "%s[%r] is %s (%r)" % (context, key, type(value).__name__, value))


class TestTicksAndMappings(unittest.TestCase):

	def test_ticks_are_hundred_nanosecond_units(self):
		self.assertEqual(ticksToMs(64735560000), 6473556)
		self.assertEqual(ticksToMs(10000), 1)
		self.assertEqual(msToTicks(1), 10000)
		self.assertEqual(msToTicks(6473556), 64735560000)
		self.assertEqual(ticksToMs(msToTicks(123456)), 123456)

	def test_aspect_ratio_matrix(self):
		mapAspect = EmbyLibrary._mapAspect
		self.assertEqual(mapAspect("2.40:1"), "2.35")
		self.assertEqual(mapAspect("2.35:1"), "2.35")
		self.assertEqual(mapAspect("16:9"), "1.78")
		self.assertEqual(mapAspect("1.33:1"), "1.33")
		self.assertEqual(mapAspect("4:3"), "1.33")
		self.assertEqual(mapAspect(2.35), "2.35")
		self.assertEqual(mapAspect("1.78"), "1.78")
		self.assertEqual(mapAspect(None), "")
		self.assertEqual(mapAspect(""), "")
		self.assertEqual(mapAspect("garbage"), "")

	def test_resolution_buckets(self):
		mapResolution = EmbyLibrary._mapResolution
		self.assertEqual(mapResolution(3840, 2160), "4K")
		self.assertEqual(mapResolution(1920, 1080), "1080")
		self.assertEqual(mapResolution(1920, 800), "1080")  # scope crop still 1080p wide
		self.assertEqual(mapResolution(1280, 720), "720")
		self.assertEqual(mapResolution(720, 576), "SD")
		self.assertEqual(mapResolution(None, None), "SD")


class TestBrowseMovies(unittest.TestCase):

	def setUp(self):
		self.mock = MockEmby().start()
		wire_auth(self.mock)
		self.fixture = helpers.fixture_json("movies_page_emby.json")
		# the live capture used Limit=2, so the envelope carries the full
		# section count; clamp it so the mock serves a single page
		self.fixture["TotalRecordCount"] = len(self.fixture["Items"])
		self.mock.add_json(ITEMS_PATH, self.fixture)

	def tearDown(self):
		self.mock.stop()

	def _lib(self):
		lib = helpers.make_emby_instance(self.mock)
		self.assertTrue(lib.authenticate())
		return lib

	def test_five_tuples_with_string_typed_entrydata(self):
		lib = self._lib()
		fullList, mediaContainer = lib.getMoviesFromSection(lib.getContentUrl(ITEMS_PATH + "?IncludeItemTypes=Movie"))

		self.assertEqual(len(fullList), len(self.fixture["Items"]))
		self.assertIsInstance(mediaContainer, dict)

		for entry in fullList:
			self.assertEqual(len(entry), 5)
			title, entryData, contextMenu, viewState, nextUrl = entry
			self.assertIsInstance(title, str)
			self.assertIsInstance(entryData, dict)
			self.assertIn(viewState, ("seen", "started", "unseen"))
			self.assertIsInstance(nextUrl, str)
			assert_all_strings(self, entryData, "entryData")
			for mediaData in entryData["mediaDataArr"]:
				assert_all_strings(self, mediaData, "mediaData")
				for part in mediaData["Parts"]:
					assert_all_strings(self, part, "part")

	def test_movie_entrydata_matches_fixture_values(self):
		lib = self._lib()
		fullList, _mc = lib.getMoviesFromSection(lib.getContentUrl(ITEMS_PATH))

		item = self.fixture["Items"][0]
		entryData = fullList[0][1]

		self.assertEqual(entryData["type"], "movie")
		self.assertEqual(entryData["ratingKey"], str(item["Id"]))
		self.assertEqual(entryData["title"], helpers.nat(item["Name"]))
		self.assertEqual(entryData["year"], str(item.get("ProductionYear", "")))
		self.assertEqual(entryData["duration"], str(item["RunTimeTicks"] // 10000))
		self.assertEqual(entryData["currentViewMode"], "ShowMovies")
		self.assertEqual(entryData["nextViewMode"], "play")
		self.assertEqual(entryData["tagType"], "Video")
		self.assertEqual(entryData["viewCount"], str(item["UserData"].get("PlayCount", 0)))

		source = item["MediaSources"][0]
		videoStreams = [s for s in source["MediaStreams"] if s["Type"] == "Video"]
		mediaData = entryData["mediaDataArr"][0]
		self.assertEqual(mediaData["videoCodec"], videoStreams[0]["Codec"])
		self.assertEqual(mediaData["container"], source["Container"])
		self.assertEqual(mediaData["Parts"][0]["size"], str(source["Size"]))
		self.assertEqual(mediaData["Parts"][0]["file"], helpers.nat(source["Path"]))

	def test_context_menu_shape(self):
		lib = self._lib()
		fullList, _mc = lib.getMoviesFromSection(lib.getContentUrl(ITEMS_PATH))

		contextMenu = fullList[0][2]
		itemId = fullList[0][1]["ratingKey"]
		for key in ("libraryRefreshURL", "unwatchURL", "watchedURL", "deleteURL", "itemId"):
			self.assertIn(key, contextMenu)
		self.assertEqual(contextMenu["itemId"], itemId)
		self.assertIn("/Users/%s/PlayedItems/%s" % (EMBY_UID, itemId), contextMenu["watchedURL"])
		self.assertIn("/Items/%s/Refresh" % itemId, contextMenu["libraryRefreshURL"])

	def test_images_carry_the_shared_placeholder_and_api_key(self):
		lib = self._lib()
		fullList, _mc = lib.getMoviesFromSection(lib.getContentUrl(ITEMS_PATH))

		entryData = fullList[0][1]
		# the placeholder must be present VERBATIM (leading '&' included)
		# so the UI's download_url.replace(IMAGE_SIZE_PLACEHOLDER, ...) hits
		self.assertIn(IMAGE_SIZE_PLACEHOLDER, entryData["thumb"])
		self.assertIn("api_key=", entryData["thumb"])
		self.assertIn("/Images/Primary", entryData["thumb"])

		# emulate DP_View.downloadPoster resizing to real skin dimensions
		resized = entryData["thumb"].replace(IMAGE_SIZE_PLACEHOLDER, "&maxWidth=195&maxHeight=268")
		self.assertNotEqual(resized, entryData["thumb"])  # the replace fired
		self.assertIn("maxWidth=195&maxHeight=268", resized)
		self.assertNotIn("maxWidth=999", resized)

	def test_item_without_artwork_gets_empty_strings(self):
		bare = {"Items": [{"Type": "Movie", "Id": "77", "Name": "NoArt",
						"UserData": {"PlayCount": 0}}], "TotalRecordCount": 1}
		self.mock.add_json(ITEMS_PATH, bare)
		lib = self._lib()
		fullList, _mc = lib.getMoviesFromSection(lib.getContentUrl(ITEMS_PATH))

		entryData = fullList[0][1]
		self.assertEqual(entryData["thumb"], "")
		self.assertEqual(entryData["art"], "")
		self.assertEqual(entryData["mediaDataArr"], [])

	def test_multi_source_item_yields_one_mediadata_per_source(self):
		twoSources = {"Items": [{
			"Type": "Movie", "Id": "88", "Name": "Dual", "RunTimeTicks": 60000000,
			"UserData": {"PlayCount": 1},
			"MediaSources": [
				{"Id": "src1", "Container": "mkv", "Size": 1000, "Bitrate": 8000000,
				"MediaStreams": [{"Type": "Video", "Codec": "hevc", "Width": 3840, "Height": 2160, "AspectRatio": "16:9"},
								{"Type": "Audio", "Codec": "eac3", "Channels": 6}]},
				{"Id": "src2", "Container": "mp4", "Size": 500, "Bitrate": 2000000,
				"MediaStreams": [{"Type": "Video", "Codec": "h264", "Width": 1280, "Height": 720, "AspectRatio": "2.40:1"},
								{"Type": "Audio", "Codec": "aac", "Channels": 2}]},
			]}], "TotalRecordCount": 1}
		self.mock.add_json(ITEMS_PATH, twoSources)
		lib = self._lib()
		fullList, _mc = lib.getMoviesFromSection(lib.getContentUrl(ITEMS_PATH))

		mediaDataArr = fullList[0][1]["mediaDataArr"]
		self.assertEqual(len(mediaDataArr), 2)
		self.assertEqual(mediaDataArr[0]["id"], "src1")
		self.assertEqual(mediaDataArr[0]["videoResolution"], "4K")
		self.assertEqual(mediaDataArr[0]["aspectRatio"], "1.78")
		self.assertEqual(mediaDataArr[0]["audioChannels"], "6")
		self.assertEqual(mediaDataArr[1]["videoResolution"], "720")
		self.assertEqual(mediaDataArr[1]["aspectRatio"], "2.35")

	def test_pagination_merges_all_pages(self):
		manyItems = [{"Type": "Movie", "Id": str(i), "Name": "M%03d" % i,
					"UserData": {"PlayCount": 0}} for i in range(250)]
		self.mock.add_paged(ITEMS_PATH, manyItems)
		lib = self._lib()
		fullList, _mc = lib.getMoviesFromSection(lib.getContentUrl(ITEMS_PATH))

		self.assertEqual(len(fullList), 250)
		requests = self.mock.requests_for(ITEMS_PATH)
		self.assertEqual(len(requests), 2)
		self.assertEqual(requests[1]["query"].get("StartIndex"), ["200"])

	def test_dead_server_returns_empty_tuple_without_raising(self):
		lib = helpers.make_emby_instance(host="127.0.0.1", port=1)
		fullList, mediaContainer = lib.getMoviesFromSection("http://127.0.0.1:1/Users/x/Items")
		self.assertEqual(fullList, [])
		self.assertTrue(lib.getLastErrorMessage())


class TestBrowseShows(unittest.TestCase):

	def setUp(self):
		self.mock = MockEmby().start()
		wire_auth(self.mock)

	def tearDown(self):
		self.mock.stop()

	def _lib(self):
		lib = helpers.make_emby_instance(self.mock)
		self.assertTrue(lib.authenticate())
		return lib

	def test_series_counters_and_drill_in(self):
		fixture = helpers.fixture_json("series_page_emby.json")
		fixture["TotalRecordCount"] = len(fixture["Items"])
		self.mock.add_json(ITEMS_PATH, fixture)
		lib = self._lib()
		fullList, _mc = lib.getShowsFromSection(lib.getContentUrl(ITEMS_PATH + "?IncludeItemTypes=Series"))

		item = fixture["Items"][0]
		title, entryData, contextMenu, viewState, nextUrl = fullList[0]

		self.assertEqual(entryData["type"], "show")
		self.assertEqual(entryData["tagType"], "Show")
		self.assertEqual(entryData["nextViewMode"], "ShowSeasons")
		self.assertEqual(entryData["leafCount"], str(item["RecursiveItemCount"]))
		expectedViewed = item["RecursiveItemCount"] - item["UserData"]["UnplayedItemCount"]
		self.assertEqual(entryData["viewedLeafCount"], str(expectedViewed))
		self.assertIn("/Shows/%s/Seasons" % item["Id"], nextUrl)
		self.assertIn(viewState, ("seen", "started", "unseen"))
		assert_all_strings(self, entryData, "series entryData")

	def test_seasons_route_to_episodes_of_their_series(self):
		fixture = helpers.fixture_json("seasons_emby.json")
		seasonsPath = "/Shows/129110/Seasons"
		self.mock.add_json(seasonsPath, fixture)
		lib = self._lib()
		fullList, _mc = lib.getSeasonsOfShow(lib.getContentUrl(seasonsPath + "?UserId=x"))

		item = fixture["Items"][0]
		entryData = fullList[0][1]
		nextUrl = fullList[0][4]

		self.assertEqual(entryData["tagType"], "Episodes")
		self.assertEqual(entryData["nextViewMode"], "ShowEpisodes")
		self.assertIn("/Shows/%s/Episodes?SeasonId=%s" % (item["SeriesId"], item["Id"]), nextUrl)

	def test_episodes_switch_artwork_and_number_titles(self):
		fixture = helpers.fixture_json("episodes_emby.json")
		fixture["TotalRecordCount"] = len(fixture["Items"])
		episodesPath = "/Shows/129110/Episodes"
		self.mock.add_json(episodesPath, fixture)
		lib = self._lib()
		fullList, _mc = lib.getEpisodesOfSeason(lib.getContentUrl(episodesPath + "?SeasonId=129111"))

		item = fixture["Items"][0]
		title, entryData, _cm, viewState, _nextUrl = fullList[0]

		self.assertEqual(entryData["currentViewMode"], "ShowEpisodes")
		self.assertEqual(entryData["nextViewMode"], "play")
		self.assertTrue(entryData["title"].startswith(str(item["IndexNumber"]) + ". "))
		# list artwork comes from the series backdrop, detail art is the still
		self.assertIn(str(item["ParentBackdropItemId"]), entryData["thumb"])
		self.assertIn("/Images/Backdrop", entryData["thumb"])
		self.assertIn("/Images/Primary", entryData["art"])
		assert_all_strings(self, entryData, "episode entryData")

	def test_direct_mode_marks_the_view(self):
		fixture = helpers.fixture_json("episodes_emby.json")
		fixture["TotalRecordCount"] = len(fixture["Items"])
		self.mock.add_json("/Shows/NextUp", fixture)
		lib = self._lib()
		fullList, _mc = lib.getEpisodesOfSeason(lib.getContentUrl("/Shows/NextUp?ParentId=1"), directMode=True)

		self.assertEqual(fullList[0][1]["currentViewMode"], "ShowEpisodesDirect")


class TestBrowseMixedAndMusic(unittest.TestCase):

	def setUp(self):
		self.mock = MockEmby().start()
		wire_auth(self.mock)

	def tearDown(self):
		self.mock.stop()

	def _lib(self):
		lib = helpers.make_emby_instance(self.mock)
		self.assertTrue(lib.authenticate())
		return lib

	def test_latest_bare_array_parses(self):
		bare = helpers.fixture_json("latest_bare_emby.json")
		latestPath = "/Users/%s/Items/Latest" % EMBY_UID
		self.mock.add_json(latestPath, bare)
		lib = self._lib()
		fullList, _mc = lib.getMixedContentFromSection(lib.getContentUrl(latestPath + "?Limit=3"))

		self.assertEqual(len(fullList), len(bare))
		for entry in fullList:
			self.assertEqual(len(entry), 5)
			assert_all_strings(self, entry[1], "latest entryData")

	def test_mixed_container_routes_each_type(self):
		mixed = {"Items": [
			{"Type": "Movie", "Id": "1", "Name": "A Movie", "UserData": {"PlayCount": 0}},
			{"Type": "Series", "Id": "2", "Name": "A Show", "RecursiveItemCount": 5,
			"UserData": {"UnplayedItemCount": 5}},
			{"Type": "BoxSet", "Id": "3", "Name": "A Collection", "UserData": {}},
		], "TotalRecordCount": 3}
		self.mock.add_json(ITEMS_PATH, mixed)
		lib = self._lib()
		fullList, _mc = lib.getMixedContentFromSection(lib.getContentUrl(ITEMS_PATH))

		byTitle = dict((e[0], e) for e in fullList)
		self.assertEqual(byTitle["A Movie"][1]["nextViewMode"], "play")
		self.assertEqual(byTitle["A Show"][1]["nextViewMode"], "ShowSeasons")
		self.assertIn("/Shows/2/Seasons", byTitle["A Show"][4])
		self.assertEqual(byTitle["A Collection"][1]["nextViewMode"], "mixed")
		self.assertEqual(byTitle["A Collection"][1]["tagType"], "Directory")
		self.assertIn("ParentId=3", byTitle["A Collection"][4])

	def test_music_chain_artist_album_track(self):
		artists = {"Items": [{"Type": "MusicArtist", "Id": "a1", "Name": "Artist", "UserData": {}}], "TotalRecordCount": 1}
		albums = {"Items": [{"Type": "MusicAlbum", "Id": "b1", "Name": "Album", "ProductionYear": 1999, "UserData": {}}], "TotalRecordCount": 1}
		tracks = {"Items": [{"Type": "Audio", "Id": "t1", "Name": "Track", "IndexNumber": 3,
						"RunTimeTicks": 1800000000, "UserData": {"PlayCount": 2, "Played": True},
						"MediaSources": [{"Id": "ms1", "Container": "flac", "Size": 999,
										"MediaStreams": [{"Type": "Audio", "Codec": "flac", "Channels": 2}]}]}], "TotalRecordCount": 1}
		self.mock.add_json("/Artists/AlbumArtists", artists)
		self.mock.add_json(ITEMS_PATH, albums)
		lib = self._lib()

		artistList, _mc = lib.getMusicByArtist(lib.getContentUrl("/Artists/AlbumArtists?ParentId=7"))
		artistEntry = artistList[0]
		self.assertEqual(artistEntry[1]["nextViewMode"], "ShowAlbums")
		self.assertEqual(artistEntry[1]["tagType"], "Directory")
		self.assertIn("AlbumArtistIds=a1", artistEntry[4])

		albumList, _mc = lib.getMusicByAlbum(artistEntry[4])
		albumEntry = albumList[0]
		self.assertEqual(albumEntry[1]["nextViewMode"], "ShowTracks")
		self.assertIn("ParentId=b1", albumEntry[4])
		self.assertIn("IncludeItemTypes=Audio", albumEntry[4])

		self.mock.add_json(ITEMS_PATH, tracks)
		trackList, _mc = lib.getMusicTracks(albumEntry[4])
		trackEntry = trackList[0]
		self.assertEqual(trackEntry[1]["tagType"], "Track")
		self.assertEqual(trackEntry[1]["nextViewMode"], "play")
		self.assertEqual(trackEntry[1]["duration"], "180000")
		self.assertEqual(trackEntry[3], "seen")  # Played=True (not just PlayCount)
		assert_all_strings(self, trackEntry[1], "track entryData")


if __name__ == "__main__":
	unittest.main()
