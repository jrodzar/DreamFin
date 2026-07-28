# -*- coding: utf-8 -*-
"""Nothing may be pasted into a msgid before gettext sees it.

`_("text " + value + "'")` concatenates BEFORE the lookup, so the key carried
to the catalogue changes with the value and never matches an entry. The string
is untranslatable by construction - and the damage is invisible, because
gettext just hands the key back and the text still reads fine in English.

Two of these shipped for a long time here, both found on 2026-07-25, and both
had a FINISHED Spanish translation sitting in po/es.po that had never once been
displayed:

  * DP_MainMenu, the Wake on Lan dialog (fixed in 0.1.11).
  * DP_View, the blue-button label. It showed as "playback mode
    'Transcodificado'" - English wrapper, translated value, because the mode
    names are marked separately. That mixed-language label is the tell.

The right shape is _("... %s ...") % value: one msgid, the value substituted
after the lookup.

Only that shape is rejected here. `_(someVariable)` is left alone on purpose:
it is a no-op when the value is not in the catalogue, and this codebase uses it
on server-supplied names inherited from DreamPlex.
"""
from __future__ import absolute_import

import ast
import os
import unittest

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")


# ast.Str is gone in py3.12+, ast.Constant does not exist in py2.7, and
# ast.JoinedStr (f-strings) only exists from py3.6. This test has to parse the
# same sources under both interpreters the project supports, so every node type
# is looked up defensively - isinstance(x, ()) is simply always False.
_STR_NODE = getattr(ast, "Str", None) or ast.Constant
_FSTRING_NODE = getattr(ast, "JoinedStr", ())
try:
	_TEXT_TYPES = (str, unicode)          # noqa: F821 - py2.7 only
except NameError:
	_TEXT_TYPES = (str,)


def _docstringIds(tree):
	"""ids of the string nodes that are docstrings.

	They are never display text, but they ARE string literals, so they turned up
	as false 'loose' uses and pushed junk into the exception lists below. Since a
	long exception list is what hides the next real finding, it is worth removing
	the noise at the source rather than excusing it.
	"""
	found = set()
	for node in ast.walk(tree):
		body = getattr(node, "body", None)
		if not isinstance(body, list) or not body:
			continue
		if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)):
			continue
		first = body[0]
		if isinstance(first, ast.Expr) and isinstance(first.value, _STR_NODE):
			found.add(id(first.value))
	return found


def _hasStringLiteral(node):
	"""A string literal anywhere in an expression tree."""
	for child in ast.walk(node):
		if isinstance(child, _STR_NODE):
			value = getattr(child, "s", getattr(child, "value", None))
			if isinstance(value, _TEXT_TYPES):
				return True
	return False


class TestGettextMsgids(unittest.TestCase):
	def test_no_literal_is_concatenated_into_a_msgid(self):
		offenders = []
		inspected = 0

		for name in sorted(os.listdir(SRC)):
			if not name.endswith(".py"):
				continue
			path = os.path.join(SRC, name)
			with open(path, "rb") as handle:
				tree = ast.parse(handle.read(), filename=path)

			for node in ast.walk(tree):
				if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
					continue
				if node.func.id != "_" or not node.args:
					continue
				inspected += 1
				arg = node.args[0]
				# a bare name/attribute is a no-op, not a broken msgid; what
				# breaks it is building the key out of a literal plus something
				if isinstance(arg, ast.BinOp) and _hasStringLiteral(arg):
					offenders.append("%s:%d" % (name, node.lineno))
				elif isinstance(arg, _FSTRING_NODE):
					offenders.append("%s:%d (f-string)" % (name, node.lineno))

		self.assertEqual(
			[], offenders,
			"a msgid is being built at runtime: " + ", ".join(offenders) +
			". gettext looks up the WHOLE string, so pasting a value into it "
			"means the key never matches the catalogue and the text can never "
			"be translated - silently, because the lookup just returns the key. "
			"Use _(\"... %s ...\") % value instead.")

		# a guard that stops seeing anything passes exactly like one that works
		self.assertTrue(
			inspected >= 50,
			"only %d _() calls were inspected - the walk has stopped matching "
			"them, so the assertion above proves nothing" % inspected)


class TestNoUnmarkedTwin(unittest.TestCase):
	"""A label marked for translation in one place and written bare in another.

	The AST guard above cannot see these: there is no _() to inspect. They are
	found by the text being marked SOMEWHERE, which is the giveaway - if a
	string is worth translating when the screen is painted, it is worth
	translating when a keypress rewrites it.

	Four shipped here, all button labels, all the same shape: one method paints
	the label with _() and its twin rewrites it without. The label came up in
	Spanish and turned back to English on the first press. DreamPlex found the
	first pair by reading around ours (2026-07-25); this test found the second.
	"""

	# marked somewhere, but legitimately used bare elsewhere: these are
	# identifiers, paths and stored data, not text anybody reads off the screen.
	#
	# THIS LIST IS THE WEAK POINT OF THIS TEST, and it has already cost a real
	# bug: "<unknown>" sat here as "just a fallback value" while it was being
	# compared against a TRANSLATED copy of itself, which is the fault
	# TestNoTranslatedSentinel below now catches. An exception added to quieten a
	# report is an exception that hides the next one. Add only identifiers, and
	# say why.
	# Matched EXACTLY, never by prefix. An earlier version excused these by
	# prefix and "DreamFin" quietly swallowed "DreamFin crashed due to a skin
	# error!..." - a real untranslated MessageBox - along with the product name.
	#
	# Each reason must name WHAT is used bare and WHERE IT GOES, so it can be
	# checked. "looks like a fallback value" is what let "<unknown>" hide here.
	NOT_DISPLAY_TEXT = {
		"DreamFin":
			"the product name. Bare uses are PluginDescriptor(name=) in "
			"plugin.py, a ConfigText default in __init__.py, and the About "
			"header. A proper noun, and translating it would be wrong",
		"Continue watching":
			"the bare copy goes into entryData['title'] as stored data; the "
			"copy that reaches the screen, two lines below, is marked",
		"Recently added":
			"idem, DP_EmbyLibrary",
	}

	def test_no_marked_label_is_also_written_bare(self):
		marked, loose = {}, []

		for name in sorted(os.listdir(SRC)):
			if not name.endswith(".py"):
				continue
			path = os.path.join(SRC, name)
			with open(path, "rb") as handle:
				tree = ast.parse(handle.read(), filename=path)

			inside = _docstringIds(tree)
			for node in ast.walk(tree):
				if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
						and node.func.id == "_" and node.args):
					arg = node.args[0]
					if isinstance(arg, _STR_NODE):
						value = getattr(arg, "s", getattr(arg, "value", None))
						if isinstance(value, _TEXT_TYPES):
							inside.add(id(arg))
							# up to the first placeholder: the fixed part is what
							# the bare twin repeats
							marked.setdefault(value.split("%")[0], (name, node.lineno))

			for node in ast.walk(tree):
				if isinstance(node, _STR_NODE) and id(node) not in inside:
					value = getattr(node, "s", getattr(node, "value", None))
					if isinstance(value, _TEXT_TYPES):
						loose.append((name, node.lineno, value))

		offenders = set()
		for name, line, value in loose:
			# EXACT match, not prefix. Matching by prefix caught the real twins
			# but also flagged the About page, whose text merely starts with the
			# product name - and DreamPlex measured the same rule giving 86
			# candidates on their tree, where nobody would keep the list honest.
			# The twins repeat the fixed part verbatim, so equality is enough.
			# and long enough to be a phrase: " ", "-" and "\n" are marked
			# somewhere (padding in a settings label) and appear bare all over
			# the view builders. Exact matching alone gave 87 candidates, nearly
			# all of them those.
			if len(value.strip()) < 8:
				continue
			if value in self.NOT_DISPLAY_TEXT or value not in marked:
				continue
			markedIn, markedLine = marked[value]
			offenders.add("%s:%d %r (marked at %s:%d)"
			              % (name, line, value[:40], markedIn, markedLine))

		self.assertEqual(
			[], sorted(offenders),
			"this text is marked for translation elsewhere but written bare "
			"here: " + ", ".join(sorted(offenders)) + ". A label worth "
			"translating when the screen is painted is worth translating when a "
			"keypress rewrites it - otherwise it reverts to English on the "
			"first press. Wrap it in _(), or add it to NOT_DISPLAY_TEXT if it "
			"is an identifier rather than something a user reads.")

		self.assertTrue(
			len(marked) >= 50 and len(loose) >= 100,
			"the walk collected %d marked and %d bare literals - too few to be "
			"real, so it has stopped matching and the assertion above proves "
			"nothing" % (len(marked), len(loose)))


class TestNoTranslatedSentinel(unittest.TestCase):
	"""A translated string must never be what a comparison depends on.

	`myLanguage = _("<unknown>")` and later `if myLanguage == "<unknown>"`. The
	label is translated for the screen, so the test only ever matches in
	English: es.po makes it "<desconocido>", fr.po "<inconnu>". External forced
	subtitles stopped auto-enabling in exactly those languages, and nowhere
	else - which is why testing in English pronounced it fine.

	This is the sharp end of the family. The other two tests here are about text
	looking wrong; this one is about the plugin BEHAVING differently depending on
	the language it is running in, silently.

	The rule that finds it, from the DreamPlex side (2026-07-25): a literal that
	is marked for translation somewhere AND appears as a comparison operand.
	They measured the alternatives on their tree - matching by prefix gave 86
	candidates and matching by equality 38, both unmaintainable, while this one
	gave 9 candidates and the one real bug. Here it gives five, all identifiers.

	Carry the fact in a flag instead. A boolean has no catalogue.
	"""

	# compared against, and legitimately so: none of these is a message
	NOT_A_MESSAGE = (
		" ",        # separator; marked because it pads a settings label
		"Series",   # item type from the server API
		"LiveTv",   # data key, stored next to its own translated label
	)

	def test_no_marked_string_is_used_as_a_sentinel(self):
		marked, compared = {}, []

		for name in sorted(os.listdir(SRC)):
			if not name.endswith(".py"):
				continue
			path = os.path.join(SRC, name)
			with open(path, "rb") as handle:
				tree = ast.parse(handle.read(), filename=path)

			for node in ast.walk(tree):
				if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
						and node.func.id == "_" and node.args):
					arg = node.args[0]
					if isinstance(arg, _STR_NODE):
						value = getattr(arg, "s", getattr(arg, "value", None))
						if isinstance(value, _TEXT_TYPES):
							marked.setdefault(value, (name, node.lineno))

			for node in ast.walk(tree):
				if not isinstance(node, ast.Compare):
					continue
				for side in [node.left] + list(node.comparators):
					if isinstance(side, _STR_NODE):
						value = getattr(side, "s", getattr(side, "value", None))
						if isinstance(value, _TEXT_TYPES):
							compared.append((name, node.lineno, value))

		offenders = sorted(set(
			"%s:%d compares %r (marked at %s:%d)" % (name, line, value,
			                                         marked[value][0], marked[value][1])
			for name, line, value in compared
			if value in marked and value not in self.NOT_A_MESSAGE))

		self.assertEqual(
			[], offenders,
			"a comparison depends on a string that gets translated: " +
			", ".join(offenders) + ". The catalogue rewrites it, so the test "
			"only holds in English and the plugin quietly behaves differently "
			"in every other language. Keep a boolean beside the label and "
			"compare that.")

		self.assertTrue(
			len(marked) >= 50 and len(compared) >= 20,
			"the walk collected %d marked strings and %d compared literals - "
			"too few to be real, so it has stopped matching and the assertion "
			"above proves nothing" % (len(marked), len(compared)))


if __name__ == "__main__":
	unittest.main()
