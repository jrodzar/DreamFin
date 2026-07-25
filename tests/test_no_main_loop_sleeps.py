# -*- coding: utf-8 -*-
"""No sleeping on the enigma2 main loop.

enigma2 is single threaded: the same loop draws the screen, spins the spinner
and reads the remote. Anything that sleeps in a GUI callback freezes ALL of
that, and the keys pressed meanwhile are not lost - there is simply nobody
reading them until it is over.

Two of these were live (2026-07-25, both found on the DreamPlex side):

  * DP_Player::seekWatcher - `while resumeStamp: seekToStartPos(); sleep(1)`
    inside an eTimer callback (seekwatcherThread is NOT a thread despite the
    name). Blocked the GUI for the whole resume - about 5 seconds measured on
    the box - and forever when the decoder never reported a position.
  * DP_MainMenu::sleepNow - time.sleep(wol_delay) in a MessageBox callback.
    wol_delay defaults to 60 here and goes up to 180, so the GUI froze for a
    minute out of the box, three at worst.

Both are now eTimers. This guard is repo-wide so the pattern cannot come back
somewhere else: waiting is what eTimer is for.

The exceptions below are inherited DEAD code (kept on purpose for diffability
against the dreamplex remote). Their sleeps never run - audioTrackWatcher has
no caller at all, and it is the only caller of setAudioTrack, which is the only
caller of tryAudioEnable. If a future change wires that chain up, this test
starts failing, which is exactly what should happen.
"""
from __future__ import absolute_import

import ast
import os
import unittest

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")

# function name -> why a sleep() in there is tolerated
ALLOWED = {
	"audioTrackWatcher": "dead code: no caller anywhere in src/",
	"tryAudioEnable": "dead code: only reached through audioTrackWatcher",
}


def _is_sleep(node):
	"""sleep(...) or time.sleep(...)"""
	if not isinstance(node, ast.Call):
		return False
	if isinstance(node.func, ast.Name):
		return node.func.id == "sleep"
	if isinstance(node.func, ast.Attribute):
		return node.func.attr == "sleep"
	return False


def _sleeps_by_function(tree):
	"""[(function name, line)] for every sleep call, blamed on the INNERMOST
	function that contains it - a sleep inside a nested worker function is not
	the enclosing method's fault."""
	found = []

	def visit(node, owner):
		for child in ast.iter_child_nodes(node):
			if isinstance(child, ast.FunctionDef):
				visit(child, child.name)
				continue
			if _is_sleep(child):
				found.append((owner, getattr(child, "lineno", -1)))
			visit(child, owner)

	visit(tree, "<module>")
	return found


class TestNoMainLoopSleeps(unittest.TestCase):
	def test_nothing_sleeps_outside_the_known_dead_code(self):
		offenders = []

		for name in sorted(os.listdir(SRC)):
			if not name.endswith(".py"):
				continue
			path = os.path.join(SRC, name)
			with open(path, "rb") as handle:
				tree = ast.parse(handle.read(), filename=path)

			for owner, line in _sleeps_by_function(tree):
				if owner in ALLOWED:
					continue
				offenders.append("%s:%d in %s()" % (name, line, owner))

		self.assertEqual(
			[], offenders,
			"sleep() on what is very probably the enigma2 main loop: " +
			", ".join(offenders) +
			". enigma2 is single threaded - a sleep in a GUI callback freezes "
			"the screen and swallows every key press until it returns. Use an "
			"eTimer (see DP_Player::seekWatcher or DP_MainMenu::sleepNow), or "
			"push the wait into a worker with runInThread().")

	def test_the_dead_chain_is_still_dead(self):
		"""The exceptions above are only safe while nothing calls into them."""
		callers = {"audioTrackWatcher": [], "setAudioTrack": [], "tryAudioEnable": []}

		for name in sorted(os.listdir(SRC)):
			if not name.endswith(".py"):
				continue
			path = os.path.join(SRC, name)
			with open(path, "rb") as handle:
				tree = ast.parse(handle.read(), filename=path)

			for node in ast.walk(tree):
				if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
					continue
				if node.func.attr in callers:
					callers[node.func.attr].append("%s:%d" % (name, node.lineno))

		self.assertEqual(
			[], callers["audioTrackWatcher"],
			"audioTrackWatcher() has a caller now (%s), so its `while ... "
			"sleep(1)` is live and blocks the main loop. Convert it to an "
			"eTimer before wiring it up." % ", ".join(callers["audioTrackWatcher"]))

		# setAudioTrack/tryAudioEnable are only reachable through it: whoever
		# calls them from anywhere else drags the sleep(2) per track along
		for name in ("setAudioTrack", "tryAudioEnable"):
			self.assertTrue(
				all(c.startswith("DP_Player.py") for c in callers[name]),
				"%s() is called from outside DP_Player.py (%s) - it carries a "
				"sleep() with it" % (name, ", ".join(callers[name])))


if __name__ == "__main__":
	unittest.main()
