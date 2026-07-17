#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate the per-server skin variants (Phase 5).

For each skin, read its (amber) skin.xml and emit skin_emby.xml / skin_jellyfin.xml:
  - the named `accent` colour is swapped to the server accent, and
  - every accent PNG path is repointed at that skin's accent_<accent>/ dir
    (distinct paths per accent dodge enigma2's path-indexed pixmap cache).
The accent PNGs themselves come from tools/retint_pngs.py build --write.
The skin reloads on every plugin open, so the runtime just picks the right file
(loadPlexSkin) - no runtime templating. skin.xml stays the maintained source.

Run:  py -3 tools/build_skins.py
"""
from __future__ import print_function

import io
import os
import xml.dom.minidom as minidom

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKINS = os.path.join(REPO, "src", "skins")

BASE_ACCENT = "#00f0a30a"                 # amber accent value in the base skins
ACCENT_HEX = {                            # enigma2 #AARRGGBB, AA=00 opaque
    "emby": "#0052b54b",                  # green
    "jellyfin": "#00aa5cc3",              # lilac
}


def read(p):
    with io.open(p, encoding="utf-8") as f:
        return f.read()


def write(p, s):
    with io.open(p, "w", encoding="utf-8", newline="") as f:
        f.write(s)


def accent_relpaths(sdir):
    """PNG paths (posix, relative to the skin dir) under accent_emby/."""
    root = os.path.join(sdir, "accent_emby")
    rels = []
    for dp, _dn, fn in os.walk(root):
        for f in fn:
            if f.lower().endswith(".png"):
                rel = os.path.relpath(os.path.join(dp, f), root).replace("\\", "/")
                rels.append(rel)
    return sorted(rels)


def build_skin(skin):
    sdir = os.path.join(SKINS, skin)
    xmlpath = os.path.join(sdir, "skin.xml")
    if not os.path.isfile(xmlpath) or not os.path.isdir(os.path.join(sdir, "accent_emby")):
        return
    src = read(xmlpath)
    rels = accent_relpaths(sdir)
    col_from = 'name="accent" value="%s"' % BASE_ACCENT

    for accent, hexv in sorted(ACCENT_HEX.items()):
        out = src
        col_n = out.count(col_from)
        out = out.replace(col_from, 'name="accent" value="%s"' % hexv)
        path_n = 0
        for rel in rels:
            frm = "/skins/%s/%s" % (skin, rel)
            to = "/skins/%s/accent_%s/%s" % (skin, accent, rel)
            c = out.count(frm)
            if c:
                out = out.replace(frm, to)
                path_n += c
        try:
            minidom.parseString(out.encode("utf-8"))
            valid = "XML OK"
        except Exception as ex:
            valid = "XML BROKEN: %s" % ex
        write(os.path.join(sdir, "skin_%s.xml" % accent), out)
        print("  %-14s skin_%s.xml: accent col x%d, png paths x%d | %s" % (
            skin, accent, col_n, path_n, valid))


def main():
    print("=== building per-accent skin variants ===")
    for skin in sorted(os.listdir(SKINS)):
        if os.path.isdir(os.path.join(SKINS, skin)):
            build_skin(skin)


if __name__ == "__main__":
    main()
