#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate the 'recently added' badge icon (new-fs8.png).

A four-point amber sparkle on a transparent background - deliberately amber
(not the per-server accent) so it never collides with the accent-coloured
rating stars, and a sparkle (not a dot) so it never reads as a second
seen/unseen circle. Rendered 4x and downscaled for clean anti-aliased edges.

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

SIZE = 64            # source size; the skin template scales it to 24..36 px
AMBER = (255, 176, 32, 255)
SS = 4               # supersampling factor for anti-aliasing


def sparkle(size):
    big = size * SS
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    c = big / 2.0
    outer = big * 0.47
    inner = big * 0.15          # small inner radius -> pinched, sparkly points
    points = []
    for i in range(8):
        ang = math.radians(i * 45.0)
        rad = outer if i % 2 == 0 else inner
        points.append((c + rad * math.sin(ang), c - rad * math.cos(ang)))
    draw.polygon(points, fill=AMBER)
    return img.resize((size, size), Image.LANCZOS)


def main():
    icon = sparkle(SIZE)
    for path in TARGETS:
        folder = os.path.dirname(path)
        if not os.path.isdir(folder):
            os.makedirs(folder)
        icon.save(path)
        print("wrote %s (%dx%d)" % (path, SIZE, SIZE))


if __name__ == "__main__":
    main()
