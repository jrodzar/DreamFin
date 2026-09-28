# -*- coding: utf-8 -*-
"""The list on screen and the list the view acts on must never diverge.

DP_View keeps the entries of the current level twice: in the Listbox widget
(what the user sees and moves the cursor over) and in self.listViewList (what
the code works with). onEnter hands self.listViewList to DP_Player together
with the WIDGET's cursor index, and marking seen/unseen, the view-state
refresh and the letter filter all index self.listViewList with that same
widget index.

The bug being guarded against (found on a fleet box, 2026-09-28): onLeave put
the parent level's list back into the widget but left self.listViewList on the
level it came from. Pressing OK on a playable entry of the parent level (a
movie in a mixed "recently added" view, after backing out of a series) either
crashed enigma2 with IndexError in DP_Player.playMedia, or - when the index
happened to fit - silently played a different entry.

DP_View cannot be imported offline (it pulls half of enigma2's Screens), so
the source is read instead, like test_manual_seek does for DP_Player.
"""
from __future__ import absolute_import

import ast
import os
import unittest

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")


def _methods(tree):
	"""Every method defined directly in a class body, as (name, node)."""
	for node in tree.body:
		if isinstance(node, ast.ClassDef):
			for item in node.body:
				if isinstance(item, ast.FunctionDef):
					yield item.name, item


def _subscript_key(node):
	"""The literal key of a subscript, across py2.7 (Index/Str), py3.8
	(Index/Constant) and py3.9+ (bare Constant)."""
	key = node.slice
	if key.__class__.__name__ == "Index":
		key = key.value
	for attr in ("value", "s"):
		value = getattr(key, attr, None)
		if isinstance(value, str):
			return value
	return None


def _is_listview_setlist(node):
	"""self["listview"].setList(...)"""
	if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
		return False
	if node.func.attr != "setList" or not isinstance(node.func.value, ast.Subscript):
		return False
	target = node.func.value
	return (isinstance(target.value, ast.Name) and target.value.id == "self"
			and _subscript_key(target) == "listview")


def _is_self_attr(node, attr):
	return (isinstance(node, ast.Attribute) and node.attr == attr
			and isinstance(node.value, ast.Name) and node.value.id == "self")


def _assigned_to(func, attr):
	"""ast.dump of every value assigned to self.<attr> inside func."""
	values = []
	for node in ast.walk(func):
		if isinstance(node, ast.Assign) and any(_is_self_attr(t, attr) for t in node.targets):
			values.append(ast.dump(node.value))
	return values


class TestViewListsStayInSync(unittest.TestCase):

	def setUp(self):
		path = os.path.join(SRC, "DP_View.py")
		with open(path, "rb") as handle:
			self.tree = ast.parse(handle.read(), filename=path)
		self.methods = dict(_methods(self.tree))

	def test_every_widget_list_is_also_the_working_list(self):
		seen = []
		for name, func in sorted(self.methods.items()):
			for node in ast.walk(func):
				if not _is_listview_setlist(node):
					continue
				seen.append(name)
				arg = node.args[0]
				if _is_self_attr(arg, "listViewList"):
					continue
				self.assertIn(
					ast.dump(arg), _assigned_to(func, "listViewList"),
					"%s() gives the widget a list without making it self.listViewList: "
					"onEnter would then play by a cursor index into a different list" % name)

		# a guard that silently stops finding the calls passes like one that works
		self.assertGreaterEqual(
			len(seen), 4,
			"expected at least 4 self[\"listview\"].setList() calls in DP_View.py, "
			"saw %d (%s) - the matcher no longer sees the code" % (len(seen), ", ".join(seen)))

	def test_on_leave_restores_both_lists_it_restores_on_screen(self):
		self.assertIn("onLeave", self.methods, "onLeave() not found in DP_View.py")
		func = self.methods["onLeave"]
		args = [ast.dump(n.args[0]) for n in ast.walk(func) if _is_listview_setlist(n)]
		self.assertEqual(len(args), 1, "onLeave() should restore the widget exactly once, saw %d" % len(args))

		self.assertIn(args[0], _assigned_to(func, "listViewList"),
					"onLeave() restores the widget but not self.listViewList")
		self.assertIn(args[0], _assigned_to(func, "beforeFilterListViewList"),
					"onLeave() restores the widget but not self.beforeFilterListViewList: "
					"the letter filter would then filter the level we just left")


if __name__ == "__main__":
	unittest.main()
