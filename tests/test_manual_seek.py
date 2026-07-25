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


class TestResumeWatcher(unittest.TestCase):
	"""The resume watcher must never block the enigma2 main loop.

	seekwatcherThread is an eTimer, NOT a thread despite the name, so its
	callback runs on the main loop. It used to hold a `while resumeStamp is not
	None: seekToStartPos(); sleep(1)` loop in there, which froze the whole GUI
	for as long as the resume took - about 5 seconds in the normal case, and
	with a decoder that never reports a position the loop had no exit at all.

	Verified on the box with the fix in (2026-07-25): BLUE was accepted 1.4s
	before the resume finished, which the old loop made impossible.

	Found on the DreamPlex side, 2026-07-25.
	"""

	def setUp(self):
		path = os.path.join(SRC, "DP_Player.py")
		with open(path, "rb") as handle:
			self.tree = ast.parse(handle.read(), filename=path)
		self.watcher = _function(self.tree, "seekWatcher")
		self.assertIsNotNone(self.watcher, "seekWatcher() not found")

	def _stops_the_watcher(self, func):
		for node in ast.walk(func):
			if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
					and node.func.attr == "stop"):
				target = node.func.value
				if isinstance(target, ast.Attribute) and target.attr == "seekwatcherThread":
					return True
		return False

	def test_the_watcher_does_not_loop_or_sleep(self):
		"""One attempt per tick: the eTimer already repeats every 900ms."""
		self.assertFalse(
			[n for n in ast.walk(self.watcher) if isinstance(n, ast.While)],
			"seekWatcher() must not loop: it runs on the main loop, so a loop in "
			"there freezes the GUI for the whole resume")

		slept = [n for n in ast.walk(self.watcher)
		         if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
		         and n.func.id == "sleep"]
		self.assertFalse(
			slept,
			"seekWatcher() must not sleep(): that blocks the enigma2 main loop "
			"and swallows every key press while it does")

	def test_the_watcher_still_tries_to_resume(self):
		self.assertIn(
			"seekToStartPos", _called_names(self.watcher),
			"seekWatcher() is what drives the resume - it must still attempt it")

	def test_the_watcher_stops_itself_when_there_is_nothing_to_resume(self):
		self.assertTrue(
			self._stops_the_watcher(self.watcher),
			"seekWatcher() must stop its own timer once resumeStamp is cleared, "
			"or it keeps firing for the whole playback")

	def test_leaving_the_player_stops_the_watcher(self):
		func = _function(self.tree, "leavePlayerConfirmed")
		self.assertIsNotNone(func, "leavePlayerConfirmed() not found")
		self.assertTrue(
			self._stops_the_watcher(func),
			"nobody used to stop seekwatcherThread: with a resume still pending "
			"it went on firing after the player was gone")

	def test_the_timer_is_a_class_attribute(self):
		"""Every other timer is declared up there; this one was not, so the
		guards below would raise AttributeError before the first playback."""
		attributes = set()
		for node in ast.walk(self.tree):
			if isinstance(node, ast.ClassDef) and node.name == "DP_Player":
				for stmt in node.body:
					if isinstance(stmt, ast.Assign):
						for target in stmt.targets:
							if isinstance(target, ast.Name):
								attributes.add(target.id)
		self.assertIn(
			"seekwatcherThread", attributes,
			"declare seekwatcherThread = None on the class, like timelineWatcher "
			"and subtitleWatcher")

	def test_only_one_watcher_is_ever_built(self):
		"""evUpdatedInfo fires over and over; it used to build a NEW eTimer on
		each one and drop the previous without stopping it - and enigma2
		dispatches service events synchronously, so the timer being replaced can
		be the one whose callback is on the stack."""
		func = _function(self.tree, "__evUpdatedInfo")
		self.assertIsNotNone(func, "__evUpdatedInfo() not found")

		def timers(node):
			return [n for n in ast.walk(node)
			        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
			        and n.func.id == "eTimer"]

		built = timers(func)
		self.assertTrue(built, "__evUpdatedInfo() is where the resume watcher is built")

		guarded = []
		for node in ast.walk(func):
			if isinstance(node, ast.If) and "seekwatcherThread" in ast.dump(node.test):
				for stmt in node.body:
					guarded.extend(timers(stmt))

		self.assertEqual(
			len(guarded), len(built),
			"the eTimer must only be built when there is not one already: guard "
			"it with `if self.seekwatcherThread is None`")


if __name__ == "__main__":
	unittest.main()
