# -*- coding: utf-8 -*-
"""Robustness: async I/O delivery, multi-version media offering and
graceful failure of the whole playback surface against a dead server.

Redirect following, container pagination and token handling are exercised
in test_auth/test_browse (embymock covers them for every request). Transcode,
trailers/extras and audio/subtitle preselection land in phase 4.
"""

import threading
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


class _FakeReactor(object):
	"""twisted's reactor as the box has it, minus the main loop: there,
	callFromThread hands the call to the main loop; here it runs it straight
	away. It records every call, so a test can tell the result came back
	through it."""

	def __init__(self):
		self.calls = 0

	def callFromThread(self, function, *args, **kwargs):
		self.calls += 1
		function(*args, **kwargs)


class TestRunInThread(unittest.TestCase):
	"""Network I/O must be delivered back through a callback so it can run
	off the enigma2 main loop (a long block there kills enigma2).

	runInThread has two branches, picked by whether twisted's reactor
	imported: synchronous without one (these offline tests) and, on the box,
	a worker thread that hands the result back with reactor.callFromThread.
	Which one a test took used to depend on what the sys.path offered: at
	DreamPlex a twisted stub added to tests/stubs for another fix moved these
	tests onto the thread branch without anyone noticing, and since they read
	the result on the next line, py2.7 lost the race now and then (56 in
	20,000). Here no twisted is on the path, so the box's branch was simply
	never tested. Each branch is now forced, and the thread one is waited
	for."""

	def setUp(self):
		import src.__common__ as common
		self.common = common
		self.savedReactor = common.reactor

	def tearDown(self):
		self.common.reactor = self.savedReactor

	def _run(self, work):
		seen = {}
		done = threading.Event()

		def onDone(result, error):
			seen["result"], seen["error"] = result, error
			seen["thread"] = threading.current_thread()
			done.set()

		self.common.runInThread(work, onDone)  # must not raise
		self.assertTrue(done.wait(5), "the callback never came")
		return seen

	@staticmethod
	def _failing():
		raise IOError("boom")

	# without a reactor: the offline branch, synchronous

	def test_result_is_delivered_without_a_reactor(self):
		self.common.reactor = None
		seen = self._run(lambda: 21 * 2)
		self.assertEqual(seen["result"], 42)
		self.assertIsNone(seen["error"])
		self.assertIs(seen["thread"], threading.current_thread(),
			"without a reactor the call must stay on the calling thread")

	def test_exception_is_delivered_not_raised_without_a_reactor(self):
		self.common.reactor = None
		seen = self._run(self._failing)
		self.assertIsNone(seen["result"])
		self.assertIsInstance(seen["error"], IOError)

	# with a reactor: the branch the box runs

	def test_result_is_delivered_through_the_reactor(self):
		reactor = self.common.reactor = _FakeReactor()
		worker = {}

		def work():
			worker["thread"] = threading.current_thread()
			return 21 * 2

		seen = self._run(work)
		self.assertEqual(seen["result"], 42)
		self.assertIsNone(seen["error"])
		self.assertIsNot(worker["thread"], threading.current_thread(),
			"the work did not run off the calling thread")
		self.assertEqual(reactor.calls, 1, "the result did not come back through reactor.callFromThread")

	def test_exception_is_delivered_through_the_reactor_not_raised(self):
		reactor = self.common.reactor = _FakeReactor()
		seen = self._run(self._failing)
		self.assertIsNone(seen["result"])
		self.assertIsInstance(seen["error"], IOError)
		self.assertEqual(reactor.calls, 1, "the error did not come back through reactor.callFromThread")


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
