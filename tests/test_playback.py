# -*- coding: utf-8 -*-
"""Phase 3 direct playback: media options, versions, playerData, resume,
context-menu verbs, series theme and the single-item detail wrap."""

import unittest

from tests import helpers
from tests.embymock import MockEmby

helpers.setup_environment()

from src.DP_EmbyLibrary import ticksToMs  # noqa: E402

EMBY_UID = "user0000000000000000000000000001"
MOVIE_ID = "104906"
MOVIE_SRC0 = "mediasource_104906"
MOVIE_SRC1 = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
DETAIL_PATH = "/Users/%s/Items/%s" % (EMBY_UID, MOVIE_ID)
PLAYED_PATH = "/Users/%s/PlayedItems/%s" % (EMBY_UID, MOVIE_ID)


def wire_auth(mock):
	mock.add_json("/Users/AuthenticateByName", helpers.fixture_json("auth_ok_emby.json"), method="POST")
	mock.add_json("/System/Info/Public", helpers.fixture_json("system_info_public_emby.json"))


class PlaybackBase(unittest.TestCase):

	def setUp(self):
		self.mock = MockEmby().start()
		wire_auth(self.mock)

	def tearDown(self):
		self.mock.stop()

	def _lib(self):
		lib = helpers.make_emby_instance(self.mock)
		self.assertTrue(lib.authenticate())
		self.assertTrue(lib.g_accessToken, "auth must yield a token so api_key can be appended")
		return lib

	def _serve_detail(self, fixture_name):
		self.mock.add_json(DETAIL_PATH, helpers.fixture_json(fixture_name))


class TestSingleItemDetailWrap(PlaybackBase):

	def test_getItemUrl_single_item_wraps_into_one_entry(self):
		# the post-playback view-state refresh fetches one item and expects
		# exactly one list entry back (regression for _itemsFromAnswer)
		self._serve_detail("item_detail_emby.json")
		lib = self._lib()

		fullList, _mc = lib.getMoviesFromSection(lib.getItemUrl(MOVIE_ID))
		self.assertEqual(len(fullList), 1)
		self.assertEqual(fullList[0][1]["ratingKey"], MOVIE_ID)

	def test_getItemUrl_targets_the_detail_endpoint(self):
		lib = self._lib()
		url = lib.getItemUrl(MOVIE_ID)
		self.assertIn("/Users/%s/Items/%s" % (EMBY_UID, MOVIE_ID), url)
		self.assertIn("Fields=", url)


class TestGetMediaOptions(PlaybackBase):

	def test_single_version_one_eight_tuple(self):
		self._serve_detail("item_detail_emby.json")
		lib = self._lib()

		count, options, server = lib.getMediaOptionsToPlay(MOVIE_ID, lib.g_address)
		self.assertEqual(count, 1)
		self.assertEqual(len(options), 1)
		part = options[0]
		self.assertEqual(len(part), 8)
		key, path, container, size, duration, resolution, codec, mediaIndex = part
		self.assertIn("/Videos/%s/stream" % MOVIE_ID, key)
		self.assertIn("static=true", key)
		self.assertIn("MediaSourceId=%s" % MOVIE_SRC0, key)
		self.assertEqual(mediaIndex, 0)
		self.assertEqual(server, lib.g_address)

	def test_multiversion_two_parts_with_indices(self):
		self._serve_detail("item_detail_multiversion_emby.json")
		lib = self._lib()

		count, options, _server = lib.getMediaOptionsToPlay(MOVIE_ID, lib.g_address)
		self.assertEqual(count, 2)
		self.assertEqual(options[0][7], 0)
		self.assertEqual(options[1][7], 1)
		self.assertIn("MediaSourceId=%s" % MOVIE_SRC0, options[0][0])
		self.assertIn("MediaSourceId=%s" % MOVIE_SRC1, options[1][0])

	def test_parts_types_follow_the_golden_rule(self):
		# seven leading strings + an int mediaIndex; the version dialog
		# str()s [5]/[6] and int()s [3], the player list-indexes [7]
		self._serve_detail("item_detail_multiversion_emby.json")
		lib = self._lib()

		_count, options, _server = lib.getMediaOptionsToPlay(MOVIE_ID, lib.g_address)
		for part in options:
			for i in range(7):
				self.assertIsInstance(part[i], str, "part[%d] must be str" % i)
			self.assertIsInstance(part[7], int)

	def test_dead_server_returns_zero_without_raising(self):
		lib = self._lib()
		self.mock.stop()  # kill the server mid-flight

		count, options, server = lib.getMediaOptionsToPlay(MOVIE_ID, lib.g_address)
		self.assertEqual(count, 0)
		self.assertEqual(options, [])
		self.assertEqual(server, lib.g_address)
		self.assertTrue(lib.getLastErrorMessage())


class TestDirectPlay(PlaybackBase):

	def _play(self, fixture_name="item_detail_emby.json", index=0):
		self._serve_detail(fixture_name)
		lib = self._lib()
		_count, options, server = lib.getMediaOptionsToPlay(MOVIE_ID, lib.g_address)
		lib.setSelectedVersion(options[index][7])
		lib.setPlaybackType("0")
		mediaUrl = lib.mediaType({"key": options[index][0], "file": options[index][1]}, server)
		return lib, lib.playLibraryMedia(MOVIE_ID, mediaUrl)

	def test_direct_url_has_static_mediasource_and_apikey(self):
		lib, playerData = self._play()
		playUrl = playerData["playUrl"]
		self.assertIn("/Videos/%s/stream" % MOVIE_ID, playUrl)
		self.assertIn("static=true", playUrl)
		self.assertIn("MediaSourceId=%s" % MOVIE_SRC0, playUrl)
		self.assertIn("api_key=", playUrl)

	def test_playerData_has_every_key_setPlayerData_reads(self):
		_lib, playerData = self._play()
		for key in ("playUrl", "resumeStamp", "server", "id", "multiUserServer",
					"playbackType", "connectionType", "localAuth", "transcodingSession",
					"universalTranscoder", "videoData", "mediaData", "fallback", "locations"):
			self.assertIn(key, playerData)
		self.assertIs(playerData["multiUserServer"], True)
		self.assertIs(playerData["fallback"], False)
		self.assertEqual(playerData["id"], MOVIE_ID)

	def test_resume_roundtrips_in_milliseconds(self):
		# fixture UserData.PlaybackPositionTicks = 12345670000 (100ns units)
		_lib, playerData = self._play()
		self.assertEqual(playerData["resumeStamp"], ticksToMs(12345670000))
		self.assertEqual(playerData["resumeStamp"], 1234567)
		self.assertEqual(playerData["videoData"]["viewOffset"], "1234567")

	def test_videoData_values_are_strings(self):
		_lib, playerData = self._play()
		for key, value in playerData["videoData"].items():
			self.assertIsInstance(value, str, "videoData[%r] must be str" % key)

	def test_version_selector_picks_the_right_mediasourceid(self):
		_lib, playerData = self._play("item_detail_multiversion_emby.json", index=1)
		self.assertEqual(playerData["mediaSourceId"], MOVIE_SRC1)
		self.assertIn("MediaSourceId=%s" % MOVIE_SRC1, playerData["playUrl"])


class TestContextActions(PlaybackBase):

	def test_markWatched_uses_POST(self):
		self.mock.add_json(PLAYED_PATH, {}, method="POST")
		lib = self._lib()
		self.assertTrue(lib.markWatched(MOVIE_ID))
		reqs = self.mock.requests_for(PLAYED_PATH)
		self.assertEqual(reqs[-1]["method"], "POST")

	def test_markUnwatched_uses_DELETE(self):
		self.mock.add_json(PLAYED_PATH, {}, method="DELETE")
		lib = self._lib()
		self.assertTrue(lib.markUnwatched(MOVIE_ID))
		reqs = self.mock.requests_for(PLAYED_PATH)
		self.assertEqual(reqs[-1]["method"], "DELETE")

	def test_deleteItem_uses_DELETE(self):
		path = "/Items/%s" % MOVIE_ID
		self.mock.add_json(path, {}, method="DELETE")
		lib = self._lib()
		self.assertTrue(lib.deleteItem(MOVIE_ID))
		self.assertEqual(self.mock.requests_for(path)[-1]["method"], "DELETE")

	def test_refreshItem_uses_POST(self):
		path = "/Items/%s/Refresh" % MOVIE_ID
		self.mock.add_json(path, {}, method="POST")
		lib = self._lib()
		self.assertTrue(lib.refreshItem(MOVIE_ID))
		self.assertEqual(self.mock.requests_for(path)[-1]["method"], "POST")

	def test_dead_server_action_is_falsy_without_raising(self):
		lib = self._lib()
		self.mock.stop()
		self.assertFalse(lib.markWatched(MOVIE_ID))
		self.assertTrue(lib.getLastErrorMessage())


class TestSeriesTheme(PlaybackBase):

	def test_theme_url_points_at_audio_stream_with_apikey(self):
		series_id = "series001"
		self.mock.add_json("/Items/%s/ThemeSongs" % series_id, helpers.fixture_json("theme_songs_emby.json"))
		lib = self._lib()

		url = lib.getThemeUrl(series_id)
		self.assertIn("/Audio/themeaudio00000000000000000000001/stream", url)
		self.assertIn("static=true", url)
		self.assertIn("api_key=", url)

	def test_theme_url_empty_when_no_theme(self):
		series_id = "series002"
		self.mock.add_json("/Items/%s/ThemeSongs" % series_id, {"Items": [], "TotalRecordCount": 0})
		lib = self._lib()
		self.assertEqual(lib.getThemeUrl(series_id), "")


if __name__ == "__main__":
	unittest.main()
