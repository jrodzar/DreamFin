#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""One-shot mechanical rename of the DreamPlex fork into DreamFin.

Rewrites only the externally visible identity so DreamFin can coexist
with an installed DreamPlex on the same box:

- install path        Plugins/Extensions/DreamPlex -> Extensions/DreamFin
- config namespace    config.plugins.dreamplex     -> config.plugins.dreamfin
- gettext domain      "DreamPlex"                  -> "DreamFin" (+ .mo name)
- opkg package        enigma2-plugin-extensions-dreamplex -> ...-dreamfin
- data directory      /hdd/dreamplex               -> /hdd/dreamfin
- enigma2 skin file   skin_dreamplex.xml           -> skin_dreamfin.xml
- plugin descriptor   name/description/menu key
- CONTROL scripts, maintainer.info, CI workflow, plugin version

Internal DP_* module names and the original DreamPlex copyright and
license notices are intentionally NOT touched: keeping them makes
future diffs against upstream DreamPlex readable and honours the
GPL-2.0-or-later requirement to preserve existing notices.

Idempotent: running it twice is a no-op. Patterns are pure ASCII and
files are patched at byte level, so encodings and line endings are
preserved exactly.
"""

from __future__ import print_function

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# files/dirs never touched by the global pass: history and docs describe
# the DreamPlex past (phase 6 rewrites them), po/ msgids get refreshed in
# phase 6 too, and this script must not rewrite itself
GLOBAL_EXCLUDE_DIRS = (".git", "po", "doc", ".github")
GLOBAL_EXCLUDE_FILES = (
    "CHANGES.md",
    "README.md",
    "RELEASENOTES.md",
    os.path.join("tools", "rename_fork.py"),
)

BINARY_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".mo", ".pyc", ".pyo", ".ttf", ".otf")

# order matters: most specific first
GLOBAL_REPLACEMENTS = [
    (b"enigma2-plugin-extensions-dreamplex", b"enigma2-plugin-extensions-dreamfin"),
    (b"Extensions/DreamPlex", b"Extensions/DreamFin"),
    (b"config.plugins.dreamplex", b"config.plugins.dreamfin"),
    (b"/hdd/dreamplex", b"/hdd/dreamfin"),
    (b"skin_dreamplex.xml", b"skin_dreamfin.xml"),
    (b'bindtextdomain("DreamPlex"', b'bindtextdomain("DreamFin"'),
    (b'dgettext("DreamPlex"', b'dgettext("DreamFin"'),
    (b"DreamPlex.mo", b"DreamFin.mo"),
]

# per-file surgical replacements (path relative to repo root, old, new)
TARGETED_REPLACEMENTS = [
    # plugin descriptor: the identity the user sees in the plugin browser
    ("src/plugin.py", b'name="DreamPlex"', b'name="DreamFin"'),
    ("src/plugin.py", b'description="plex client for enigma2"', b'description="Emby/Jellyfin client for enigma2"'),
    ("src/plugin.py", b'description=_("plex client for enigma2")', b'description=_("Emby/Jellyfin client for enigma2")'),
    ("src/plugin.py", b'[(_("DreamPlex"), main, "dreamplex", 47)]', b'[(_("DreamFin"), main, "dreamfin", 47)]'),
    ("src/plugin.py", b"menu_dreamplex", b"menu_dreamfin"),
    # device name reported to the media server
    ("src/__init__.py", b'boxName = ConfigText(default="DreamPlex"', b'boxName = ConfigText(default="DreamFin"'),
    # fork starts its own versioning
    ("src/__common__.py", b'version = "2.3.2"', b'version = "0.1.0"'),
    ("tools/build_ipk.py", b'default="+pms" + time.strftime("%Y%m%d")', b'default="+dev" + time.strftime("%Y%m%d")'),
    ("tools/build_ipk.py", b'help="appended to the plugin version (default: +pmsYYYYMMDD)")', b'help="appended to the plugin version (default: +devYYYYMMDD)")'),
    # opkg metadata
    ("CONTROL/control", b"Version: 2.3.1", b"Version: 0.1.0"),
    ("CONTROL/control", b"Description: Plex client for Enigma2 - fork with modern Plex Media Server fixes", b"Description: Emby/Jellyfin client for Enigma2, derived from DreamPlex"),
    ("CONTROL/control", b"Maintainer: DonDavici, jbleyel, oe-alliance", b"Maintainer: jrodzar"),
    ("CONTROL/control", b"Homepage: https://github.com/oe-alliance/DreamPlex", b"Homepage: https://github.com/jrodzar/DreamFin"),
    ("CONTROL/control", b"Source: https://github.com/oe-alliance/DreamPlex", b"Source: https://github.com/jrodzar/DreamFin"),
    # install-time console messages
    ("CONTROL/preinst", b"echo Starting installation of DreamPlex ...", b"echo Starting installation of DreamFin ..."),
    ("CONTROL/postinst", b"'# DreamPlex (modern PMS fork) installed.            #'", b"'# DreamFin (Emby/Jellyfin client) installed.        #'"),
    # feed maintainer contact for this fork
    ("src/maintainer.info", b"dondavici@gmail.com", b"jrodzar@gmail.com"),
    ("src/maintainer.info", b"DreamPlex", b"DreamFin"),
]

# leftovers that must NOT survive in the tree the global pass covers
FORBIDDEN_AFTER = (
    b"Extensions/DreamPlex",
    b"config.plugins.dreamplex",
    b"/hdd/dreamplex",
    b"enigma2-plugin-extensions-dreamplex",
    b"skin_dreamplex",
    b"DreamPlex.mo",
)


def iter_global_files():
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        rel_dir = os.path.relpath(dirpath, REPO_ROOT)
        parts = [] if rel_dir == "." else rel_dir.split(os.sep)
        if parts and parts[0] in GLOBAL_EXCLUDE_DIRS:
            dirnames[:] = []
            continue
        # never descend into excluded dirs found deeper
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__")]
        for name in filenames:
            rel = os.path.join(rel_dir, name) if parts else name
            if rel.replace(os.sep, "/") in [f.replace(os.sep, "/") for f in GLOBAL_EXCLUDE_FILES]:
                continue
            if name.lower().endswith(BINARY_EXTENSIONS):
                continue
            yield os.path.join(dirpath, name), rel


def patch_bytes(data, pairs, counter):
    for old, new in pairs:
        n = data.count(old)
        if n:
            data = data.replace(old, new)
            counter[old] = counter.get(old, 0) + n
    return data


def main():
    counter = {}

    # global pass
    for path, rel in iter_global_files():
        with open(path, "rb") as f:
            data = f.read()
        if b"\0" in data:
            continue  # binary safety net
        patched = patch_bytes(data, GLOBAL_REPLACEMENTS, counter)
        if patched != data:
            with open(path, "wb") as f:
                f.write(patched)

    # targeted pass
    for rel, old, new in TARGETED_REPLACEMENTS:
        path = os.path.join(REPO_ROOT, rel)
        with open(path, "rb") as f:
            data = f.read()
        n = data.count(old)
        if n:
            with open(path, "wb") as f:
                f.write(data.replace(old, new))
            counter[old] = counter.get(old, 0) + n

    for old, _new in GLOBAL_REPLACEMENTS:
        print("%-55s %d" % (old.decode("ascii"), counter.get(old, 0)))
    targeted_total = sum(counter.get(old, 0) for _rel, old, _new in TARGETED_REPLACEMENTS)
    print("%-55s %d" % ("targeted replacements", targeted_total))

    # verify nothing forbidden survived in global-pass files
    leftovers = []
    for path, rel in iter_global_files():
        with open(path, "rb") as f:
            data = f.read()
        if b"\0" in data:
            continue
        for pat in FORBIDDEN_AFTER:
            if pat in data:
                leftovers.append((rel, pat.decode("ascii")))
    if leftovers:
        for rel, pat in leftovers:
            print("LEFTOVER: %s still contains %s" % (rel, pat))
        return 1
    print("no forbidden leftovers - rename complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
