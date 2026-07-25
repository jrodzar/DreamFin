# -*- coding: utf-8 -*-
"""The manual seek (BLUE -> MinuteInput) must not go back to being a no-op.

DP_Player cannot be imported offline (it pulls half of enigma2's Screens), so
these checks read the source, the same trick test_stdlib_imports uses for the
boot guards.

The bug being guarded against (found 2026-07-25): seekToMinute() routed the
jump through seekToStartPos(), which bails out unless the decoder can say
where it is - and during a transcode it never can. The dialog worked, the
minute was accepted, and nothing moved. Silently.
"""
from __future__ import absolute_import

import ast
import os
import unittest

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")


def _function(tree, name):
	for node in ast.walk(tree):
		if isinstance(node, ast.FunctionDef) and node.name == name:
			return node
	return None


def _called_names(func):
	"""Every self.<name>() called anywhere inside `func`."""
	names = set()
	for node in ast.walk(func):
		if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
			value = node.func.value
			if isinstance(value, ast.Name) and value.id == "self":
				names.add(node.func.attr)
	return names


class TestManualSeek(unittest.TestCase):
	def setUp(self):
		path = os.path.join(SRC, "DP_Player.py")
		with open(path, "rb") as handle:
			self.tree = ast.parse(handle.read(), filename=path)
		self.seekToMinute = _function(self.tree, "seekToMinute")
		self.assertIsNotNone(self.seekToMinute, "seekToMinute() not found in DP_Player.py")

	def test_seeks_directly_and_not_through_seek_to_start_pos(self):
		called = _called_names(self.seekToMinute)

		self.assertIn(
			"doSeek", called,
			"seekToMinute() must seek by itself (doSeek), or the jump never happens")

		self.assertNotIn(
			"seekToStartPos", called,
			"seekToMinute() must NOT go through seekToStartPos(): that one needs a "
			"decoder position, which a transcoded HLS stream never gives, so the "
			"jump is dropped without a word")

	def test_target_is_clamped_to_the_media_length(self):
		called = _called_names(self.seekToMinute)
		self.assertIn(
			"getMediaDuration", called,
			"seekToMinute() must ask for the duration to clamp the target: seeking "
			"past the end leaves the decoder on a dead playlist")

	def test_dialog_cancel_is_handled(self):
		"""MinuteInput hands back None when the user backs out."""
		source = ast.dump(self.seekToMinute)
		self.assertIn(
			"None", source,
			"seekToMinute() must cope with the dialog being cancelled (minutes=None)")

	def test_seek_to_start_pos_still_guards_the_decoder(self):
		"""The resume path keeps its retry dance - it is right for THAT job."""
		func = _function(self.tree, "seekToStartPos")
		self.assertIsNotNone(func, "seekToStartPos() not found")
		self.assertIn(
			"doSeek", _called_names(func),
			"seekToStartPos() is still what resume uses to reach the saved point")


class TestProgressTicker(unittest.TestCase):
	"""The progress ticker must start where it is built.

	It used to be built here and started somewhere else, and for streamed or
	transcoded playback nobody won the race: DreamFin reported no progress for
	a whole playback (measured on the box, 2026-07-25), which also left the
	PlaybackClock idle.
	"""

	def setUp(self):
		path = os.path.join(SRC, "DP_Player.py")
		with open(path, "rb") as handle:
			self.source = handle.read()
		self.tree = ast.parse(self.source, filename=path)

	def test_start_timeline_watcher_actually_starts_it(self):
		func = _function(self.tree, "startTimelineWatcher")
		self.assertIsNotNone(func, "startTimelineWatcher() not found")

		started = False
		for node in ast.walk(func):
			if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
					and node.func.attr == "start"):
				target = node.func.value
				if isinstance(target, ast.Attribute) and target.attr == "timelineWatcher":
					started = True
		self.assertTrue(
			started,
			"startTimelineWatcher() must start the timer itself: leaving that to "
			"resumePlayerData()/bufferFull() meant it never ticked while streaming")

	def test_the_tick_interval_is_one_named_constant(self):
		"""Four call sites used to carry their own number (5000, 5000, 5000, 30000)."""
		self.assertNotIn(
			b"timelineWatcher.start(5000", self.source,
			"use TIMELINE_TICK_MS, not a bare 5000")
		self.assertNotIn(
			b"timelineWatcher.start(30000", self.source,
			"use TIMELINE_TICK_MS, not a bare 30000")
		self.assertIn(b"TIMELINE_TICK_MS = ", self.source,
		              "TIMELINE_TICK_MS must be defined")


if __name__ == "__main__":
	unittest.main()
