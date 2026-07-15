#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Refresh the .md doc mirror on the shared NAS hub.

git stays canonical for the docs; this copies the current .md files
(PLAN, CLAUDE, README, CHANGES, RELEASENOTES, doc/JOURNAL) to the NAS
folder so they are readable/editable from any PC next to the
credentials. Run at the end of a session, after committing the docs.

Run with:  py -3 tools/sync_nas_docs.py
The NAS folder can be overridden with $DREAMFIN_NAS.
"""

from __future__ import print_function

import os
import shutil
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

NAS_ROOT = os.environ.get("DREAMFIN_NAS", r"<NAS-HUB>")

DOCS = ["PLAN.md", "CLAUDE.md", "README.md", "CHANGES.md", "RELEASENOTES.md",
		os.path.join("doc", "JOURNAL.md")]


def main():
	if not os.path.isdir(NAS_ROOT):
		print("NAS hub not reachable: %s" % NAS_ROOT)
		print("(mount the NAS or set $DREAMFIN_NAS)")
		return 2

	copied = 0
	for rel in DOCS:
		src = os.path.join(REPO_ROOT, rel)
		if not os.path.isfile(src):
			print("skip (missing in repo): %s" % rel)
			continue
		dst = os.path.join(NAS_ROOT, rel)
		dstDir = os.path.dirname(dst)
		if dstDir and not os.path.isdir(dstDir):
			os.makedirs(dstDir)
		shutil.copy2(src, dst)
		print("mirrored %s" % rel.replace(os.sep, "/"))
		copied += 1

	print("done: %d docs mirrored to %s" % (copied, NAS_ROOT))
	return 0


if __name__ == "__main__":
	sys.exit(main())
