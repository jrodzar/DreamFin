# -*- coding: utf-8 -*-
"""AUDIO during playback must open the audio selection on every image.

Found on a box with OpenATV 8.0.1 (2026-10-04): AUDIO while a film was
playing brought up the crash window. The player's audioSelection() handed the
screen self.audioSelected as its callback - a method it borrowed from the
image's InfoBarAudioSelection. OpenATV 7.0 to 7.5 define it; 7.6, 8.0 and
master turned it into a local function, so on those the key raised
AttributeError before the screen even opened.

DP_Player cannot be imported offline (it pulls half of enigma2's Screens), so
these tests compile the real class out of the source on top of a stand-in
for the image's InfoBarAudioSelection, modelled on each shape it has had.
"""
from __future__ import absolute_import

import ast
import os
import sys
import unittest

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
PLAYER = os.path.join(SRC, "DP_Player.py")


def _compile_class(path, name, namespace):
	"""The class `name` from the source, compiled against the stand-in
	globals in namespace."""
	with open(path, "rb") as handle:
		tree = ast.parse(handle.read(), filename=path)
	for node in tree.body:
		if isinstance(node, ast.ClassDef) and node.name == name:
			if sys.version_info >= (3, 8):
				module = ast.Module(body=[node], type_ignores=[])
			else:
				module = ast.Module(body=[node])
			scope = dict(namespace)
			exec(compile(module, path, "exec"), scope)
			return scope[name]
	raise AssertionError("class %s not found in %s" % (name, os.path.basename(path)))


# --- the image's InfoBarAudioSelection, in the two shapes it has had ---------

class _ImageUpTo75(object):
	"""OpenATV 7.0 to 7.5: the screen's callback is a method, audioSelected."""

	def __init__(self):
		pass

	def audioSelection(self):
		self.session.openWithCallback(self.audioSelected, "AudioSelection", infobar=self)

	def audioSelected(self, ret=None):
		pass


class _ImageFrom76(object):
	"""OpenATV 7.6, 8.0 and master: the callback is a local function, and
	audioSelected is gone."""

	def __init__(self):
		pass

	def audioSelection(self):
		def audioSelectionCallback(result=None):
			pass

		self.session.openWithCallback(audioSelectionCallback, "AudioSelection", infobar=self)


# --- stand-ins for the rest --------------------------------------------------

MY_AUDIO_SELECTION = object()  # DreamFin's own screen, myAudioSelection


def _printl(string, parent=None, dmode="U", *args, **kwargs):
	pass


class _Session(object):
	infobar = None

	def __init__(self):
		self.opened = []

	def openWithCallback(self, callback, screen, *args, **kwargs):
		self.opened.append((callback, screen))


class _AudioKeyTest(object):
	IMAGE = None

	def player(self):
		cls = _compile_class(PLAYER, "InfobarAudioSelectionExtended", {
			"InfoBarAudioSelection": self.IMAGE,
			"myAudioSelection": MY_AUDIO_SELECTION,
			"printl": _printl,
		})
		player = cls()
		player.session = _Session()
		return player

	def test_audio_opens_the_audio_selection(self):
		player = self.player()

		player.audioSelection()  # AUDIO, while playing

		self.assertEqual(len(player.session.opened), 1, "AUDIO opened nothing")
		self.assertIs(player.session.opened[0][1], MY_AUDIO_SELECTION)

	def test_closing_the_audio_selection_is_handled(self):
		player = self.player()
		player.audioSelection()
		callback = player.session.opened[0][0]

		callback(0)  # how AudioSelection closes, with OK and with EXIT alike
		callback()


class TestAudioKeyOnOpenATV76AndLater(_AudioKeyTest, unittest.TestCase):
	IMAGE = _ImageFrom76


class TestAudioKeyOnOpenATV70To75(_AudioKeyTest, unittest.TestCase):
	IMAGE = _ImageUpTo75

	def test_the_callback_is_the_players_own(self):
		"""The rule, not only the 7.6 symptom: on these images the borrowed
		audioSelected still existed, so the old code worked here by luck.
		(Suggested by DreamPlex.)"""
		player = self.player()
		player.audioSelection()
		callback = player.session.opened[0][0]

		self.assertIn(callback.__name__, vars(type(player)),
			"AUDIO hands the screen a callback borrowed from the image's InfoBarAudioSelection")


if __name__ == "__main__":
	unittest.main()
