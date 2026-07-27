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


if __name__ == "__main__":
	unittest.main()
