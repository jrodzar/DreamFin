#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Recolour the amber accent of skin PNGs to the per-server accent
(green Emby / lilac Jellyfin), preserving each pixel's brightness (shading)
and alpha. Only amber pixels (hue ~28-52 deg, the #f0a30a / #FF8C00 / #e69405
accent) are touched; neutral art (white/grey codec icons, colour buttons,
star outlines) is left untouched.

Technique: for an amber pixel, output = target_rgb scaled by the pixel's own
value (HSV V), so an amber gradient becomes the same gradient in the target
hue. This is the amber->green/lilac tint used for the DreamPlex-derived art.

CLI:
  python tools/retint_pngs.py test <in.png>   # write <in>__emby/__jellyfin.png next to it
  python tools/retint_pngs.py build           # retint all accent PNGs into accent_*/ dirs
"""
from __future__ import print_function

import colorsys
import os
import sys

from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKINS = os.path.join(REPO, "src", "skins")

ACCENTS = {
    "emby": (0x52, 0xb5, 0x4b),      # #52b54b green
    "jellyfin": (0xaa, 0x5c, 0xc3),  # #aa5cc3 lilac
}

AMBER_LO, AMBER_HI = 22.0, 60.0   # degrees (covers the gold rim highlights too)
MIN_SAT = 0.33


def retint(im, target):
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    tr, tg, tb = target
    touched = 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            hh, ss, vv = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
            if AMBER_LO <= hh * 360.0 <= AMBER_HI and ss >= MIN_SAT:
                px[x, y] = (int(tr * vv), int(tg * vv), int(tb * vv), a)
                touched += 1
    return im, touched


def amber_ratio(im):
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    opaque = amber = 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 24:
                continue
            opaque += 1
            hh, ss, _v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
            if AMBER_LO <= hh * 360.0 <= AMBER_HI and ss >= MIN_SAT:
                amber += 1
    return (amber / float(opaque)) if opaque else 0.0


def do_test(inp):
    base = os.path.splitext(inp)[0]
    for name, target in ACCENTS.items():
        out, n = retint(Image.open(inp), target)
        out.save("%s__%s.png" % (base, name))
        print("wrote %s__%s.png (%d px retinted)" % (base, name, n))


def do_build(write=False):
    """Retint every amber accent PNG of every skin into per-accent dirs
    (accent_emby/ , accent_jellyfin/) mirroring the source sub-path, so the
    generated skins can point at distinct paths (dodging enigma2's pixmap
    cache). Dry-run by default; pass --write to actually generate."""
    made = 0
    for skin in sorted(os.listdir(SKINS)):
        sdir = os.path.join(SKINS, skin)
        if not os.path.isdir(sdir):
            continue
        for dp, _dn, fn in os.walk(sdir):
            if os.sep + "accent_" in dp:  # never re-process generated dirs
                continue
            for f in sorted(fn):
                if not f.lower().endswith(".png"):
                    continue
                p = os.path.join(dp, f)
                if amber_ratio(Image.open(p)) < 0.05:
                    continue
                rel = os.path.relpath(p, sdir)
                for name, target in ACCENTS.items():
                    outp = os.path.join(sdir, "accent_" + name, rel)
                    made += 1
                    if write:
                        d = os.path.dirname(outp)
                        if not os.path.isdir(d):
                            os.makedirs(d)
                        out, _n = retint(Image.open(p), target)
                        out.save(outp)
                    else:
                        print("would write %s" % os.path.relpath(outp, SKINS))
    print("%s %d accent PNGs (%d source images x2)" % (
        "wrote" if write else "would write", made, made // 2))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "test"
    if cmd == "test":
        do_test(sys.argv[2])
    elif cmd == "build":
        do_build(write=("--write" in sys.argv))
    else:
        print("usage: retint_pngs.py test <in.png> | build [--write]")
