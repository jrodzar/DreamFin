#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate the 'recently added' badge icon (new-fs8.png).

A four-point amber sparkle on a transparent background - deliberately amber
(not the per-server accent) so it never collides with the accent-coloured
rating stars, and a sparkle (not a dot) so it never reads as a second
seen/unseen circle. Rendered 4x and downscaled for clean anti-aliased edges.

The list template renders png = 5 with MultiContentEntryPixmapAlphaTest, the
same call as the seen/unseen circle. That renderer wants an 8-bit-*palette*
PNG whose transparency is a tRNS *table* (one alpha byte per palette index) -
exactly how pngquant writes seen-fs8.png / unseen-fs8.png (mode=P, a 72/111
byte tRNS table). A 32-bit RGBA icon renders as a white box there, and a
paletted icon with only a single transparent index (info['transparency'] = 0)
renders as nothing. So we quantise the anti-aliased alpha to a handful of
levels over an all-amber palette and emit those levels as a tRNS byte table.

Writes into the two base icon dirs; BlueMod / BlueMod_FHD reuse them via their
params (same as seen/started/unseen).

Run:  py -3 tools/make_new_badge.py
"""
from __future__ import print_function

import math
import os

from PIL import Image, ImageDraw

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGETS = (
    os.path.join(REPO, "src", "skins", "default", "icons", "new-fs8.png"),
    os.path.join(REPO, "src", "skins", "default_FHD", "icons", "new-fs8.png"),
)

SIZE = 24            # native template size (24x24); rendered 1:1 like the
                     # seen/unseen icons. enigma2 cannot scale a paletted+tRNS
                     # PNG (no palette-index interpolation) -> a bigger source
                     # scaled down by the template renders invisible.
AMBER = (255, 176, 32, 255)
SS = 4               # supersampling factor for anti-aliasing
LEVELS = 16          # alpha quantisation levels -> tRNS table length


def _star(draw, cx, cy, outer, inner, fill):
    """One pinched 4-point star centred at (cx, cy)."""
    pts = []
    for i in range(8):
        ang = math.radians(i * 45.0)
        rad = outer if i % 2 == 0 else inner
        pts.append((cx + rad * math.sin(ang), cy - rad * math.cos(ang)))
    draw.polygon(pts, fill=fill)


def sparkle(size):
    big = size * SS
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # a sparkle cluster: one dominant 4-point star plus two smaller accent
    # stars (upper-right and lower-left), like the ✨ glyph.
    _star(draw, big * 0.45, big * 0.48, big * 0.32, big * 0.11, AMBER)  # main
    _star(draw, big * 0.80, big * 0.20, big * 0.15, big * 0.05, AMBER)  # small, top-right
    _star(draw, big * 0.20, big * 0.78, big * 0.12, big * 0.04, AMBER)  # smaller, bottom-left
    return img.resize((size, size), Image.LANCZOS)


def to_palette(rgba):
    """Paletted PNG with a per-index alpha tRNS TABLE, like seen-fs8.png.

    All palette entries are the same amber; the transparency lives entirely in
    the tRNS table (index 0 fully transparent -> the background, top index
    fully opaque -> the sparkle body). AlphaTest thresholds the intermediate
    levels, but emitting them as a proper byte table is what makes enigma2
    load and draw the icon at all.
    """
    alpha = rgba.split()[3]
    idx = alpha.point(lambda a: int(round(a / 255.0 * (LEVELS - 1))))
    pal = Image.new("P", rgba.size)
    pal.putdata(list(idx.getdata()))
    palette = list(AMBER[:3]) * LEVELS + [0, 0, 0] * (256 - LEVELS)
    pal.putpalette(palette)
    # tRNS TABLE (bytes, one alpha per palette index) -- NOT a single index.
    pal.info["transparency"] = bytes(
        int(round(i / float(LEVELS - 1) * 255)) for i in range(LEVELS)
    )
    return pal


def main():
    icon = to_palette(sparkle(SIZE))
    for path in TARGETS:
        folder = os.path.dirname(path)
        if not os.path.isdir(folder):
            os.makedirs(folder)
        icon.save(path)
        # reload to confirm the tRNS survived as a byte table
        chk = Image.open(path)
        t = chk.info.get("transparency")
        kind = ("table:%dB" % len(t)) if isinstance(t, (bytes, bytearray)) else repr(t)
        print("wrote %s (%dx%d, mode=%s, tRNS=%s)" % (path, SIZE, SIZE, chk.mode, kind))


if __name__ == "__main__":
    main()
