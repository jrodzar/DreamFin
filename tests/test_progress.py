# -*- coding: utf-8 -*-
"""Phase 3 progress/watched reporting: the POST bodies must carry ticks
(ms * 10000) exactly, the pause flag, and never raise on a dead server."""

import unittest

from tests import helpers
from tests.embymock import MockEmby

helpers.setup_environment()

from src.DP_EmbyLibrary import msToTicks  # noqa: E402

MOVIE_ID = "104906"
SESSIONS_START = "/Sessions/Playing"
SESSIONS_PROGRESS = "/Sessions/Playing/Progress"
SESSIONS_STOPPED = "/Sessions/Playing/Stopped"
POSITION_MS = 1234567


def wire_auth(mock):
	mock.add_json("/Users/AuthenticateByName", helpers.fixture_json("auth_ok_emby.json"), method="POST")
	mock.add_json("/System/Info/Public", helpers.fixture_json("system_info_public_emby.json"))


class ProgressBase(unittest.TestCase):

	def setUp(self):
		self.mock = MockEmby().start()
		wire_auth(self.mock)
		for path in (SESSIONS_START, SESSIONS_PROGRESS, SESSIONS_STOPPED):
			self.mock.add_json(path, {}, method="POST")

	def tearDown(self):
		self.mock.stop()

	def _lib(self):
		lib = helpers.make_emby_instance(self.mock)
		self.assertTrue(lib.authenticate())
		return lib

	def _last_body(self, path):
		reqs = self.mock.requests_for(path)
		self.assertTrue(reqs, "expected a request to " + path)
		return reqs[-1]["body"]


class TestProgressReporting(ProgressBase):

	def test_start_body_is_directstream_with_session(self):
		lib = self._lib()
		self.assertTrue(lib.reportPlaybackStart(MOVIE_ID, 0, isPaused=False))

		body = self._last_body(SESSIONS_START)
		self.assertEqual(body["ItemId"], MOVIE_ID)
		self.assertEqual(body["PositionTicks"], 0)
		self.assertEqual(body["PlayMethod"], "DirectStream")
		self.assertTrue(body["PlaySessionId"])
		self.assertIn("MediaSourceId", body)

	def test_progress_body_ticks_are_exact(self):
		lib = self._lib()
		self.assertTrue(lib.reportProgress(MOVIE_ID, POSITION_MS, isPaused=False))

		body = self._last_body(SESSIONS_PROGRESS)
		self.assertEqual(body["PositionTicks"], msToTicks(POSITION_MS))
		self.assertEqual(body["PositionTicks"], 12345670000)
		self.assertIs(body["IsPaused"], False)
		self.assertEqual(body["ItemId"], MOVIE_ID)
		self.assertIn("MediaSourceId", body)

	def test_progress_paused_flag_is_true(self):
		lib = self._lib()
		self.assertTrue(lib.reportProgress(MOVIE_ID, POSITION_MS, isPaused=True))
		self.assertIs(self._last_body(SESSIONS_PROGRESS)["IsPaused"], True)

	def test_stopped_body_carries_final_position(self):
		lib = self._lib()
		self.assertTrue(lib.reportStopped(MOVIE_ID, POSITION_MS))

		body = self._last_body(SESSIONS_STOPPED)
		self.assertEqual(body["PositionTicks"], POSITION_MS * 10000)
		self.assertEqual(body["ItemId"], MOVIE_ID)

	def test_mediasourceid_override_is_honoured(self):
		lib = self._lib()
		lib.reportProgress(MOVIE_ID, POSITION_MS, mediaSourceId="explicit-source")
		self.assertEqual(self._last_body(SESSIONS_PROGRESS)["MediaSourceId"], "explicit-source")


class TestProgressRobustness(unittest.TestCase):

	def test_dead_server_reports_return_falsy_without_raising(self):
		mock = MockEmby().start()
		wire_auth(mock)
		lib = helpers.make_emby_instance(mock)
		self.assertTrue(lib.authenticate())
		mock.stop()  # server gone before any report

		self.assertFalse(lib.reportPlaybackStart(MOVIE_ID, 0))
		self.assertFalse(lib.reportProgress(MOVIE_ID, POSITION_MS))
		self.assertFalse(lib.reportStopped(MOVIE_ID, POSITION_MS))
		self.assertTrue(lib.getLastErrorMessage())


if __name__ == "__main__":
	unittest.main()
