#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Exercise EmbyLibrary against the real test servers, from the PC.

Reads the server list from local/servers.json (machine-local, never
committed - see CLAUDE.md for the format), boots the offline harness
stubs and runs the phase-1 surface against each server: authenticate,
detectServerType, getAllSections, the synthesized filter menu, the
genre/decade secondaries and a wrong-password robustness probe.

Run with:  py -3 tools/verify_real_servers.py
      or:  <py2.7> tools/verify_real_servers.py
"""

from __future__ import print_function

import io
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

CREDENTIALS = os.path.join(REPO_ROOT, "local", "servers.json")

from tests import helpers  # noqa: E402
helpers.setup_environment()

import src  # noqa: E402
from src.DP_EmbyLibrary import EmbyLibrary  # noqa: E402
from src.__plugin__ import Plugin  # noqa: E402

if sys.version_info[0] == 2:
	out = io.open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False)
else:
	out = sys.stdout


def say(text):
	out.write(text + u"\n")
	out.flush()


def to_text(value):
	if isinstance(value, bytes):
		return value.decode("utf-8")
	return value


def make_lib(server, password=None):
	serverConfig = src.initServerEntryConfig()
	serverConfig.name.value = server["dns"]
	serverConfig.connectionType.value = "1"
	serverConfig.dns.value = server["dns"]
	serverConfig.port.value = int(server.get("port", 8096))
	serverConfig.username.value = server.get("username", "")
	serverConfig.password.value = password if password is not None else server.get("password", "")
	serverConfig.accessToken.value = server.get("apiKey", "")
	serverConfig.serverType.value = server.get("serverType", "auto")
	return EmbyLibrary(session=None, serverConfig=serverConfig)


def main():
	if not os.path.isfile(CREDENTIALS):
		say(u"missing %s - create it first (format documented in CLAUDE.md)" % CREDENTIALS)
		return 2

	with io.open(CREDENTIALS, encoding="utf-8") as fd:
		servers = json.load(fd)

	failures = []

	for server in servers:
		label = server.get("label", server["dns"])
		say(u"=== %s (%s) ===" % (label, server["dns"]))
		lib = make_lib(server)

		ok = lib.authenticate()
		say(u"  authenticate: %s (userId %s...)" % (ok, lib.g_userId[:8]))
		if not ok:
			failures.append("%s: auth failed: %s" % (label, lib.getLastErrorMessage()))
			continue

		detected = lib.detectServerType()
		say(u"  detectServerType: %s" % detected)
		expectedType = server.get("expectType")
		if expectedType and detected != expectedType:
			failures.append("%s: detected %s, expected %s" % (label, detected, expectedType))

		sections = lib.getAllSections()
		say(u"  getAllSections: %d entries" % len(sections))
		for entry in sections:
			say(u"    - %-35s %s" % (to_text(entry[0]), entry[2]))
		if len(sections) < 3:
			failures.append("%s: too few sections" % label)

		movieRoot = None
		for entry in sections:
			if entry[2] == "movieEntry" and entry[3].get("isSectionRoot"):
				movieRoot = entry[3]
				break

		if movieRoot is None:
			failures.append("%s: no movie section found" % label)
			continue

		menu = lib.getSectionFilter(movieRoot)
		keys = [e[3]["key"] for e in menu]
		say(u"  filter menu keys: %s" % u", ".join(keys))
		if "onDeck" not in keys or "genre" not in keys:
			failures.append("%s: unexpected filter menu %s" % (label, keys))

		genreRoot = dict(movieRoot)
		genreRoot["key"] = "genre"
		genres = lib.getSectionFilter(genreRoot)
		say(u"  genres: %d (first: %s)" % (len(genres), to_text(genres[0][0]) if genres else u"-"))
		if not genres:
			failures.append("%s: no genres came back" % label)

		decadeRoot = dict(movieRoot)
		decadeRoot["key"] = "decade"
		decades = lib.getSectionFilter(decadeRoot)
		say(u"  decades: %s" % u", ".join(to_text(e[0]) for e in decades[:6]))

		# phase 2: real navigation - movies, then a show down to episodes
		allEntry = None
		for entry in menu:
			if entry[3]["key"] == "all":
				allEntry = entry[3]
				break
		movies, _mc = lib.getMoviesFromSection(allEntry["contentUrl"])
		say(u"  movies: %d (first: %s)" % (len(movies), to_text(movies[0][0]) if movies else u"-"))
		if movies:
			first = movies[0]
			if len(first) != 5 or first[3] not in ("seen", "started", "unseen"):
				failures.append("%s: malformed movie list entry" % label)
			if "mediaDataArr" not in first[1] or not first[1]["mediaDataArr"]:
				failures.append("%s: first movie has no mediaDataArr" % label)
		else:
			failures.append("%s: no movies came back" % label)

		showRoot = None
		for entry in sections:
			if entry[2] == "showEntry" and entry[3].get("isSectionRoot"):
				showRoot = entry[3]
				break
		if showRoot is not None:
			shows, _mc = lib.getShowsFromSection(showRoot["contentUrl"])
			say(u"  shows: %d (first: %s)" % (len(shows), to_text(shows[0][0]) if shows else u"-"))
			if shows:
				seasons, _mc = lib.getSeasonsOfShow(shows[0][4])
				say(u"  seasons of first show: %d" % len(seasons))
				if seasons:
					episodes, _mc = lib.getEpisodesOfSeason(seasons[0][4])
					say(u"  episodes of first season: %d (first: %s)" % (
						len(episodes), to_text(episodes[0][0]) if episodes else u"-"))
					if not episodes:
						failures.append("%s: no episodes came back" % label)
				else:
					failures.append("%s: no seasons came back" % label)
			else:
				failures.append("%s: no shows came back" % label)

		if server.get("username"):
			bad = make_lib(server, password="definitely-wrong")
			badResult = bad.authenticate()
			say(u"  wrong password -> %s / %s" % (badResult, to_text(bad.getLastErrorMessage() or u"")))
			if badResult is not False:
				failures.append("%s: wrong password did not fail" % label)

	say(u"")
	if failures:
		say(u"FAILURES:")
		for failure in failures:
			say(u"  - " + failure)
		return 1

	say(u"ALL REAL-SERVER CHECKS PASSED")
	return 0


if __name__ == "__main__":
	sys.exit(main())
