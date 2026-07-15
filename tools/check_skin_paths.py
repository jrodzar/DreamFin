#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Static lint: every plugin file referenced from the skins exists.

Scans each skin's ``skin.xml`` and ``params`` for paths below
``Extensions/DreamFin/`` (with or without the absolute
``/usr/lib/enigma2/python/Plugins/`` prefix), maps them onto the
repository ``src/`` tree and fails when the target file is missing.
Catches renames/deletions that leave dangling skin references, which
on the box would only show up as missing pixmaps or a GSOD at runtime.

Run with:  py -3 tools/check_skin_paths.py [skin.xml paths...]

Without arguments all committed skins are checked. Extra arguments may
name specific skin.xml files (used by the phase-5 accent variants).
"""

from __future__ import print_function

import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, "src")
SKINS_DIR = os.path.join(SRC_DIR, "skins")

PLUGIN_PREFIX = "Extensions/DreamFin/"

# a path reference is the plugin prefix followed by anything up to a
# quote or a comma (enigma2 "pixmaps" attributes hold comma-separated
# lists); only entries whose last segment has an extension are files
PATH_PATTERN = re.compile(r"Extensions/DreamFin/[^\"'<>,]+")


def referenced_paths(text):
	found = []
	for match in PATH_PATTERN.finditer(text):
		raw = match.group(0)
		relative = raw[len(PLUGIN_PREFIX):]
		last = relative.rstrip("/").rsplit("/", 1)[-1]
		if "." not in last:
			continue  # directory-ish reference, nothing to stat
		found.append(relative)
	return found


def check_file(path, failures):
	fd = open(path, "rb")
	try:
		text = fd.read().decode("utf-8", "replace")
	finally:
		fd.close()
	count = 0
	for relative in referenced_paths(text):
		count += 1
		target = os.path.join(SRC_DIR, relative.replace("/", os.sep))
		if not os.path.isfile(target):
			failures.append("%s -> missing src/%s" % (os.path.relpath(path, REPO_ROOT), relative))
	return count


def default_targets():
	targets = []
	for name in sorted(os.listdir(SKINS_DIR)):
		skinDir = os.path.join(SKINS_DIR, name)
		if not os.path.isdir(skinDir):
			continue
		for base in ("skin.xml", "params"):
			candidate = os.path.join(skinDir, base)
			if os.path.isfile(candidate):
				targets.append(candidate)
	return targets


def main(argv=None):
	argv = argv if argv is not None else sys.argv[1:]
	targets = [os.path.abspath(a) for a in argv] or default_targets()

	failures = []
	total = 0
	for path in targets:
		total += check_file(path, failures)

	print("checked %d skin path references in %d files" % (total, len(targets)))
	if failures:
		print("\nDANGLING SKIN REFERENCES:")
		for failure in failures:
			print("  " + failure)
		return 1
	print("all skin paths resolve")
	return 0


if __name__ == "__main__":
	sys.exit(main())
