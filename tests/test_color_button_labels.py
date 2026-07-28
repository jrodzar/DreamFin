# -*- coding: utf-8 -*-
"""Every colour-button label must go through _().

setColorFunction() exists to put text under a coloured button, so there is no
argument to be had about whether the string is on screen - which is exactly
where the exception lists of the other i18n guards kept going wrong. The label
is the first element of functionList=. If it is a literal and does not pass
through _(), it can never be translated.

Three of them survived for years here: "refresh Library", "Server Settings" and
"General Settings". They lasted because their NEIGHBOURS on the same row were
marked, so the button bar came up half in Spanish and half in English - which
reads like a translation somebody has not got round to, rather than a string
that was never offered to the catalogue at all. Found on the DreamPlex side
(2026-07-25), and present here in the same three places.

An empty label is legal and means the caller fills it in later (the comment in
the source says so). functionList=None is legal too - that button is unused at
that level.
"""
from __future__ import absolute_import

import ast
import os
import unittest

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")

_STR_NODE = getattr(ast, "Str", None) or ast.Constant
try:
	_TEXT_TYPES = (str, unicode)          # noqa: F821 - py2.7 only
except NameError:
	_TEXT_TYPES = (str,)


def _labelOf(call):
	"""First element of the functionList= keyword, or None if there is none."""
	for kw in call.keywords:
		if kw.arg != "functionList":
			continue
		if isinstance(kw.value, ast.Tuple) and kw.value.elts:
			return kw.value.elts[0]
	return None


def _isMarked(node):
	"""_( ... ) anywhere in the expression that produces the label."""
	for child in ast.walk(node):
		if (isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
				and child.func.id == "_"):
			return True
	return False


class TestColourButtonLabels(unittest.TestCase):
	def test_every_literal_label_is_translatable(self):
		offenders, marked, empty = [], 0, 0

		for name in sorted(os.listdir(SRC)):
			if not name.endswith(".py"):
				continue
			path = os.path.join(SRC, name)
			with open(path, "rb") as handle:
				tree = ast.parse(handle.read(), filename=path)

			for node in ast.walk(tree):
				if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
					continue
				if node.func.attr != "setColorFunction":
					continue

				label = _labelOf(node)
				if label is None:                      # functionList=None
					continue

				if _isMarked(label):
					marked += 1
					continue

				if isinstance(label, _STR_NODE):
					value = getattr(label, "s", getattr(label, "value", None))
					if isinstance(value, _TEXT_TYPES):
						if not value:                  # filled in by the caller
							empty += 1
							continue
						offenders.append("%s:%d %r" % (name, node.lineno, value))

		self.assertEqual(
			[], offenders,
			"colour-button label that can never be translated: " +
			", ".join(offenders) + ". setColorFunction() puts this text under a "
			"button on screen, so wrap it in _(). If it should be blank and "
			"filled in later, pass an empty string.")

		# a guard that stops seeing anything is a guard nobody notices breaking
		self.assertTrue(
			marked >= 5 and empty >= 3,
			"expected to find marked and deliberately-empty labels too "
			"(marked=%d, empty=%d) - if these drop to zero the walk has stopped "
			"matching setColorFunction and the test above proves nothing"
			% (marked, empty))


if __name__ == "__main__":
	unittest.main()
