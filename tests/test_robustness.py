# -*- coding: utf-8 -*-
"""Robustness: async I/O delivery, multi-version media offering and
graceful failure of the whole playback surface against a dead server.

Redirect following, container pagination and token handling are exercised
in test_auth/test_browse (embymock covers them for every request). Transcode,
trailers/extras and audio/subtitle preselection land in phase 4.
"""

import unittest

from tests import helpers
from tests.embymock import MockEmby

helpers.setup_environment()

EMBY_UID = "user0000000000000000000000000001"
MOVIE_ID = "104906"
MOVIE_SRC0 = "mediasource_104906"
MOVIE_SRC1 = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
DETAIL_PATH = "/Users/%s/Items/%s" % (EMBY_UID, MOVIE_ID)


def wire_auth(mock):
	mock.add_json("/Users/AuthenticateByName", helpers.fixture_json("auth_ok_emby.json"), method="POST")
	mock.add_json("/System/Info/Public", helpers.fixture_json("system_info_public_emby.json"))


class TestRunInThread(unittest.TestCase):
	"""Network I/O must be delivered back through a callback so it can run
	off the enigma2 main loop (a long block there kills enigma2)."""

	def test_result_is_delivered(self):
		from src.__common__ import runInThread
		seen = {}

		def onDone(result, error):
			seen["result"], seen["error"] = result, error

		runInThread(lambda: 21 * 2, onDone)

		self.assertEqual(seen["result"], 42)
		self.assertIsNone(seen["error"])

	def test_exception_is_delivered_not_raised(self):
		from src.__common__ import runInThread
		seen = {}

		def work():
			raise IOError("boom")

		def onDone(result, error):
			seen["result"], seen["error"] = result, error

		runInThread(work, onDone)  # must not raise

		self.assertIsNone(seen["result"])
		self.assertIsInstance(seen["error"], IOError)


class TestMultiVersionMedia(unittest.TestCase):
	"""An item with several MediaSources (versions) must expose ALL of them,
	labelled with resolution/codec and carrying their media index, and the
	picked one must drive the playback MediaSourceId."""

	def setUp(self):
		self.mock = MockEmby().start()
		self.addCleanup(self.mock.stop)
		wire_auth(self.mock)
		self.mock.add_json(DETAIL_PATH, helpers.fixture_json("item_detail_multiversion_emby.json"))

	def _lib(self):
		lib = helpers.make_emby_instance(self.mock)
		self.assertTrue(lib.authenticate())
		return lib

	def test_all_versions_are_offered_with_media_index(self):
		lib = self._lib()
		count, options, _server = lib.getMediaOptionsToPlay(MOVIE_ID, lib.g_address, False, myType="Video")

		self.assertEqual(count, 2)
		self.assertEqual(options[0][7], 0)
		self.assertEqual(options[1][7], 1)
		self.assertIn("MediaSourceId=%s" % MOVIE_SRC0, options[0][0])
		self.assertIn("MediaSourceId=%s" % MOVIE_SRC1, options[1][0])

	def test_chosen_version_drives_the_playback_source(self):
		lib = self._lib()
		_count, options, server = lib.getMediaOptionsToPlay(MOVIE_ID, lib.g_address, False, myType="Video")

		lib.setSelectedVersion(options[1][7])  # what DP_Player does on choice
		url = lib.mediaType({"key": options[1][0], "file": options[1][1]}, server)
		playerData = lib.playLibraryMedia(MOVIE_ID, url)

		self.assertEqual(playerData["mediaSourceId"], MOVIE_SRC1)
		self.assertIn("MediaSourceId=%s" % MOVIE_SRC1, playerData["playUrl"])


class TestPlaybackRobustness(unittest.TestCase):
	"""Every UI-facing playback method must fail soft against a dead server:
	falsy/zero return, a lastError set, and never an exception (the runInThread
	model turns a raise here into an unhandled callback error)."""

	def setUp(self):
		self.mock = MockEmby().start()
		wire_auth(self.mock)
		self.lib = helpers.make_emby_instance(self.mock)
		self.assertTrue(self.lib.authenticate())
		self.mock.stop()  # server dies; every call below hits a closed port

	def test_getMediaOptions_returns_zero(self):
		count, options, _server = self.lib.getMediaOptionsToPlay(MOVIE_ID, self.lib.g_address)
		self.assertEqual(count, 0)
		self.assertEqual(options, [])
		self.assertTrue(self.lib.getLastErrorMessage())

	def test_playLibraryMedia_never_raises(self):
		# no versions were fetched; building playerData must still not blow up
		playerData = self.lib.playLibraryMedia(MOVIE_ID, "http://dead/Videos/1/stream")
		self.assertIsInstance(playerData, dict)
		self.assertIn("playUrl", playerData)

	def test_reports_are_falsy(self):
		self.assertFalse(self.lib.reportPlaybackStart(MOVIE_ID, 0))
		self.assertFalse(self.lib.reportProgress(MOVIE_ID, 1000))
		self.assertFalse(self.lib.reportStopped(MOVIE_ID, 1000))

	def test_context_actions_are_falsy(self):
		self.assertFalse(self.lib.markWatched(MOVIE_ID))
		self.assertFalse(self.lib.markUnwatched(MOVIE_ID))
		self.assertFalse(self.lib.deleteItem(MOVIE_ID))
		self.assertFalse(self.lib.refreshItem(MOVIE_ID))

	def test_theme_url_is_empty(self):
		self.assertEqual(self.lib.getThemeUrl("series001"), "")


if __name__ == "__main__":
	unittest.main()
