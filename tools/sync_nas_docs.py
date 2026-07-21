#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Sync the project docs with the shared NAS hub.

Two classes of docs, with different canonical homes:

* INTERNAL (PLAN, CLAUDE, doc/JOURNAL) - working docs that are NOT in git
  (they are .gitignore'd, so the repo can be published without leaking the
  work log, the box's LAN address or the NAS paths). The **NAS is canonical**
  for these: pull them onto a fresh PC, push them back at the end of a session.
* PUBLIC (README, CHANGES, RELEASENOTES) - shipped with the repo, so **git
  stays canonical**; they are mirrored to the NAS only for convenience, so the
  whole doc set can be read from one folder.

Run with:
	py -3 tools/sync_nas_docs.py           # push repo -> NAS (end of session)
	py -3 tools/sync_nas_docs.py --pull    # pull internal docs NAS -> repo

The NAS folder can be overridden with $DREAMFIN_NAS.
"""

from __future__ import print_function

import os
import shutil
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

NAS_ROOT = os.environ.get("DREAMFIN_NAS", r"<NAS-HUB>")

# not in git - the NAS copy is the canonical one
INTERNAL = ["PLAN.md", "CLAUDE.md", os.path.join("doc", "JOURNAL.md")]
# in git - mirrored to the NAS for convenience only
PUBLIC = ["README.md", "CHANGES.md", "RELEASENOTES.md"]


def copyOne(src, dst):
	dstDir = os.path.dirname(dst)
	if dstDir and not os.path.isdir(dstDir):
		os.makedirs(dstDir)
	shutil.copy2(src, dst)


def push():
	copied = 0
	for rel in INTERNAL + PUBLIC:
		src = os.path.join(REPO_ROOT, rel)
		if not os.path.isfile(src):
			print("skip (missing locally): %s" % rel.replace(os.sep, "/"))
			continue
		copyOne(src, os.path.join(NAS_ROOT, rel))
		print("pushed %s" % rel.replace(os.sep, "/"))
		copied += 1
	print("done: %d docs pushed to %s" % (copied, NAS_ROOT))
	return 0


def pull():
	"""Bring the internal (non-git) docs onto this PC - e.g. after a fresh clone."""
	copied = 0
	missing = 0
	for rel in INTERNAL:
		src = os.path.join(NAS_ROOT, rel)
		if not os.path.isfile(src):
			print("MISSING on the NAS: %s" % rel.replace(os.sep, "/"))
			missing += 1
			continue
		copyOne(src, os.path.join(REPO_ROOT, rel))
		print("pulled %s" % rel.replace(os.sep, "/"))
		copied += 1
	print("done: %d internal docs pulled from %s" % (copied, NAS_ROOT))
	return 1 if missing else 0


def main():
	if not os.path.isdir(NAS_ROOT):
		print("NAS hub not reachable: %s" % NAS_ROOT)
		print("(mount the NAS or set $DREAMFIN_NAS)")
		return 2
	if "--pull" in sys.argv[1:]:
		return pull()
	return push()


if __name__ == "__main__":
	sys.exit(main())
