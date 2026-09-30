# -*- coding: utf-8 -*-
"""The letter filter of the library views, driven the way the remote drives it.

Both faults were confirmed on a real box (SF8008, OpenATV 7.0, 2026-09-30):

1. Marking an entry seen/unseen while a letter filter was active changed its
   marker only in the filtered list. Clearing the filter brought back the
   unfiltered list with the OLD marker, while the data and the server said
   the opposite - and YELLOW offered "set 'Unseen'" on a row that looked
   unseen. The marker refresh after playback had the same hole, and on top
   of it patched by a list index taken before its request went out, so a
   list that changed in the meantime got the marker - and the resume
   position - on another row.
2. Getting the whole list back needed a space, which on OpenATV 7.0 is the
   SECOND press of key 1 (key 0 types "0"). A "0" matched nothing and left
   an EMPTY list ("no data retrieved"), and RED "turn filter mode off" left
   the list filtered. The section menu filters on the same keys through the
   base class, and emptied itself the same way.

DP_View cannot be imported offline (it pulls half of enigma2's Screens), so
these tests compile the real methods out of the source and run them on a
small stand-in for the screen. They check what the user would see - which
marker the whole list shows, which list is on screen - and not how the fix
is written: the same tests fail on the code from before it and pass on the
code after it.
"""
from __future__ import absolute_import

import ast
import os
import sys
import unittest

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
VIEW = os.path.join(SRC, "DP_View.py")
HELPER = os.path.join(SRC, "DPH_ScreenHelper.py")

SEEN, UNSEEN, STARTED = "pic:seen", "pic:unseen", "pic:started"

# a mixed level like "Recently added" on the box: three titles with a U
TITLES = ("Un hijo propio", "Hokum", "Un talento unico", "Jumbo", "Un altre home")
U_TITLES = ["Un hijo propio", "Un talento unico", "Un altre home"]


def _literal(node):
	"""A string literal across py2.7 (Str) and py3 (Constant)."""
	for attr in ("value", "s"):
		value = getattr(node, attr, None)
		if isinstance(value, str):
			return value
	return None


def _class_node(path, name):
	with open(path, "rb") as handle:
		tree = ast.parse(handle.read(), filename=path)
	for node in tree.body:
		if isinstance(node, ast.ClassDef) and node.name == name:
			return node
	raise AssertionError("class %s not found in %s" % (name, os.path.basename(path)))


def _compile_methods(path, cls, namespace):
	"""Every method of cls as a plain function, compiled from the source
	against the stand-in globals in namespace (one copy per method, so a
	method called like a builtin - DP_View.filter - shadows nothing)."""
	methods = {}
	for node in cls.body:
		if not isinstance(node, ast.FunctionDef):
			continue
		if sys.version_info >= (3, 8):
			module = ast.Module(body=[node], type_ignores=[])
		else:
			module = ast.Module(body=[node])
		scope = dict(namespace)
		exec(compile(module, path, "exec"), scope)
		methods[node.name] = scope[node.name]
	return methods


def _red_in_filter_mode(cls):
	"""Name of the method DP_View puts on RED at level 4 - the filter mode."""
	for node in ast.walk(cls):
		if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
				and node.func.attr == "setColorFunction"):
			continue
		keywords = dict((kw.arg, kw.value) for kw in node.keywords)
		if _literal(keywords.get("color")) == "red" and _literal(keywords.get("level")) == "4":
			return keywords["functionList"].elts[1].attr
	raise AssertionError("no setColorFunction(color=\"red\", level=\"4\") in DP_View.py")


# --- stand-ins for the globals the methods reach for -------------------------

PENDING = []  # (fetch, callback) pairs handed to runInThread, still "out"
FRESH = {}  # item url -> what the server answers for it


def _run_in_thread(fetch, callback):
	PENDING.append((fetch, callback))


def _answer_pending_requests():
	while PENDING:
		fetch, callback = PENDING.pop(0)
		callback(fetch(), None)


class _Backend(object):

	def getItemUrl(self, ratingKey):
		return "item:" + ratingKey

	def getMoviesFromSection(self, url):
		return FRESH[url]


class _Singleton(object):

	def getBackendInstance(self):
		return _Backend()


class _Timer(object):

	def __init__(self):
		self.callback = []

	def start(self, *args):
		pass

	def stop(self):
		pass


class _MessageBox(object):
	TYPE_INFO = 0


NAMESPACE = {
	"printl": lambda *args, **kwargs: None,
	"_": lambda text: text,
	"fireAndForget": lambda job: None,
	"runInThread": _run_in_thread,
	"Singleton": _Singleton,
	"eTimer": _Timer,
	"MessageBox": _MessageBox,
}


# --- a stand-in for the screen ----------------------------------------------

class _Listbox(object):
	"""The widget: what the user sees and moves the cursor over. A new list
	puts the cursor back on top, so nothing passes by keeping an old one."""

	def __init__(self):
		self.list = []
		self.index = 0

	def setList(self, entries):
		self.list = entries
		self.index = 0

	def setIndex(self, index):
		self.index = index

	def getIndex(self):
		return self.index

	def getCurrent(self):
		if 0 <= self.index < len(self.list):
			return self.list[self.index]
		return None


class _Widget(object):

	def show(self):
		pass

	def hide(self):
		pass

	def setText(self, text):
		self.text = text


class _Screen(object):

	def __init__(self, entries, listName):
		self.widgets = {listName: _Listbox()}
		self.seenPic, self.unseenPic, self.startedPic = SEEN, UNSEEN, STARTED
		self.filterMode = False
		self.keyOneDisabled = False
		self.onNumberKeyLastChar = "#"
		self.viewStep = 0
		self.forceUpdate = False
		self.contextItemId = "item"
		# the level as the load flow leaves it: the list on screen, the
		# unfiltered list and the list saved for onLeave are one object
		self.listViewList = entries
		self.beforeFilterListViewList = entries
		self.currentEntryDataDict = {0: entries}
		self[listName].setList(entries)

	def __getitem__(self, name):
		return self.widgets.setdefault(name, _Widget())

	# the UI work around the lists, which these tests do not look at
	def refresh(self):
		pass

	def refreshMenu(self):
		pass

	def refreshFunctionName(self, noInit=False):
		pass

	def processSubViewElements(self, myType=None):
		pass

	def onKey1(self, initial=False):
		pass

	def onKey2(self):
		pass

	def setLevelActive(self, currentLevel=None):
		pass

	def alterColorFunctionNames(self, level=None):
		pass


_STUBBED = ("__init__", "refresh", "refreshMenu", "refreshFunctionName", "processSubViewElements",
		"onKey1", "onKey2", "setLevelActive", "alterColorFunctionNames")


def _screen_class(path, className):
	cls = _class_node(path, className)
	methods = _compile_methods(path, cls, NAMESPACE)
	body = dict((name, func) for name, func in methods.items() if name not in _STUBBED)
	return cls, type(className + "UnderTest", (_Screen,), body)


VIEW_NODE, View = _screen_class(VIEW, "DP_View")
RED_IN_FILTER_MODE = _red_in_filter_mode(VIEW_NODE)
_, ServerMenuFilter = _screen_class(HELPER, "DPH_Filter")


def _rows(seen=()):
	rows = []
	for number, title in enumerate(TITLES):
		played = "1" if title in seen else "0"
		data = {"title": title, "ratingKey": str(100 + number), "server": "emby",
				"currentViewMode": "movie", "viewCount": played, "played": played}
		rows.append((title, data, None, SEEN if played == "1" else UNSEEN, "next:" + title))
	return rows


def _view(seen=()):
	del PENDING[:]
	FRESH.clear()
	return View(_rows(seen), "listview")


def _type(view, char):
	"""A character from the number keys, applied when their timeout fires."""
	view.onNumberKeyLastChar = char
	view.filter()


def _on_screen(view, listName="listview"):
	return [entry[0] for entry in view[listName].list]


def _markers(view):
	return dict((entry[0], entry[3]) for entry in view["listview"].list)


def _select(view, title):
	view["listview"].setIndex(_on_screen(view).index(title))


class TestMarkerSurvivesTheFilter(unittest.TestCase):

	def test_seen_marker_survives_clearing_the_filter(self):
		view = _view()
		_type(view, "U")
		self.assertEqual(_on_screen(view), U_TITLES)
		_select(view, "Un talento unico")
		view.markWatched()
		self.assertEqual(_markers(view)["Un talento unico"], SEEN)

		_type(view, " ")
		markers = _markers(view)
		self.assertEqual(markers["Un talento unico"], SEEN,
			"marked seen with the filter on, the whole list shows it unseen again")
		for title in TITLES:
			if title != "Un talento unico":
				self.assertEqual(markers[title], UNSEEN, "%s changed marker" % title)

	def test_unseen_marker_survives_clearing_the_filter(self):
		view = _view(seen=("Un altre home",))
		_type(view, "U")
		_select(view, "Un altre home")
		view.markUnwatched()

		_type(view, " ")
		self.assertEqual(_markers(view)["Un altre home"], UNSEEN,
			"marked unseen with the filter on, the whole list shows it seen again")

	def test_the_level_saved_for_going_back_keeps_the_marker(self):
		# onLeave restores this level from currentEntryDataDict
		view = _view()
		_type(view, "U")
		_select(view, "Un hijo propio")
		view.markWatched()
		saved = dict((entry[0], entry[3]) for entry in view.currentEntryDataDict[0])
		self.assertEqual(saved["Un hijo propio"], SEEN)

	def _play_and_answer_later(self, view, title):
		"""Stop a playback of title: the marker refresh asks the server, and
		the answer comes back later."""
		_select(view, title)
		ratingKey = [e[1]["ratingKey"] for e in view.listViewList if e[0] == title][0]
		FRESH["item:" + ratingKey] = [[(title, {"viewCount": "1", "played": "1", "viewOffset": "0"},
				None, "seen", "next:" + title)]]
		view.refreshEntryViewState(view["listview"].getIndex())
		self.assertTrue(PENDING, "the marker refresh sent no request")

	def test_refresh_after_playback_marks_the_played_row_when_the_filter_is_cleared_meanwhile(self):
		view = _view()
		_type(view, "U")
		self._play_and_answer_later(view, "Un altre home")
		_type(view, " ")  # cleared before the answer came back
		_answer_pending_requests()

		markers = _markers(view)
		self.assertEqual(markers["Un altre home"], SEEN, "the played entry did not get its marker")
		for title in TITLES:
			if title != "Un altre home":
				self.assertEqual(markers[title], UNSEEN,
					"%s got the marker of the entry that was played" % title)
				self.assertEqual([e[1]["played"] for e in view.listViewList if e[0] == title], ["0"],
					"%s got the watch state of the entry that was played" % title)

	def test_refresh_after_playback_reaches_a_row_filtered_out_meanwhile(self):
		view = _view()
		_type(view, "U")
		self._play_and_answer_later(view, "Un altre home")
		_type(view, "J")  # another letter before the answer came back
		_answer_pending_requests()
		self.assertEqual(_markers(view), {"Jumbo": UNSEEN}, "a row on screen got another entry's marker")

		_type(view, " ")
		self.assertEqual(_markers(view)["Un altre home"], SEEN,
			"the played entry lost its marker because it was filtered out when the answer came")


class TestGettingTheWholeListBack(unittest.TestCase):

	def test_red_in_filter_mode_brings_the_whole_list_back(self):
		view = _view()
		view.onKey4()
		self.assertTrue(view.filterMode)
		_type(view, "U")
		_select(view, "Un talento unico")

		getattr(view, RED_IN_FILTER_MODE)()

		self.assertFalse(view.filterMode)
		self.assertEqual(_on_screen(view), list(TITLES),
			"RED \"turn filter mode off\" left the list filtered")
		self.assertIs(view.listViewList, view["listview"].list,
			"the list on screen is not the one OK hands to the player")
		self.assertEqual(view["listview"].getCurrent()[0], "Un talento unico",
			"the cursor left the entry it was on")

	def test_ok_in_filter_mode_does_not_swap_the_list_under_the_player(self):
		# onEnter leaves the filter mode on every OK, right before handing
		# self.listViewList and the cursor index to DP_Player: that path must
		# keep the filtered list, or OK plays another entry
		view = _view()
		view.onKey4()
		_type(view, "U")
		_select(view, "Un altre home")
		view.toggleFilterMode(quit=True)
		self.assertEqual(_on_screen(view), U_TITLES)
		self.assertIs(view.listViewList, view["listview"].list)
		self.assertEqual(view.listViewList[view["listview"].getIndex()][0], "Un altre home")

	def test_a_character_nothing_starts_with_keeps_the_whole_list(self):
		view = _view()
		_type(view, "0")  # key 0 on OpenATV 7.0
		self.assertEqual(_on_screen(view), list(TITLES), "a \"0\" emptied the list")
		self.assertIs(view.listViewList, view["listview"].list)

	def test_a_character_nothing_starts_with_keeps_the_filtered_list(self):
		view = _view()
		_type(view, "U")
		_type(view, "0")
		self.assertEqual(_on_screen(view), U_TITLES, "a \"0\" emptied the filtered list")
		self.assertIs(view.listViewList, view["listview"].list)

	def test_the_section_menu_keeps_its_list_on_a_character_nothing_starts_with(self):
		# DPS_ServerMenu filters on the number keys through DPH_Filter.filter
		menu = ServerMenuFilter([(title,) for title in TITLES], "menu")
		menu.onNumberKeyLastChar = "0"
		menu.filter()
		self.assertEqual(_on_screen(menu, "menu"), list(TITLES), "a \"0\" emptied the section menu")
		menu.onNumberKeyLastChar = "U"
		menu.filter()
		self.assertEqual(_on_screen(menu, "menu"), U_TITLES)


if __name__ == "__main__":
	unittest.main()
