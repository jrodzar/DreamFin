#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate the DreamFin logos (Phase 5 Bloque 5): a stylised fin with a
green->lilac gradient (Emby + Jellyfin), on a dark rounded badge/tile.

  - pluginLogo.png (100x40) / pluginLogoHD.png (150x60): the plugin-browser
    icon (shown before a server is known -> neutral dual accent + "DreamFin").
  - picon dreamfin.png (256/350): the main-menu tile; `emby`/`jellyfin`/`dual`.

Run:  py -3 tools/make_logo.py <outdir>
"""
from __future__ import print_function

import colorsys
import math
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = os.path.join(REPO, "src", "fonts", "OpenSans.ttf")


def _vivid(rgb, s=1.6, v=1.14):
    h, ss, vv = colorsys.rgb_to_hsv(*[c / 255.0 for c in rgb])
    r, g, b = colorsys.hsv_to_rgb(h, min(1.0, ss * s), min(1.0, vv * v))
    return (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))


GREEN = _vivid((0x52, 0xb5, 0x4b))   # Emby green, punched up (logo only)
LILAC = _vivid((0xaa, 0x5c, 0xc3))   # Jellyfin violet, punched up (logo only)
AMBER = (0xf0, 0xa3, 0x0a)           # base accent, retinted per server by retint_pngs.py
SS = 4  # supersample for smooth edges


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def hgradient(w, h, c1, c2):
    grad = Image.new("RGB", (w, h))
    px = grad.load()
    for x in range(w):
        col = _lerp(c1, c2, x / float(max(1, w - 1)))
        for y in range(h):
            px[x, y] = col
    return grad


def vgradient(w, h, c1, c2):
    grad = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(grad)
    for y in range(h):
        d.line([(0, y), (w, y)], fill=_lerp(c1, c2, y / float(max(1, h - 1))))
    return grad


def _quad(p0, p1, p2, n=26):
    pts = []
    for i in range(n + 1):
        t = i / float(n)
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]
        pts.append((x, y))
    return pts


def fin_rgba(box_w, box_h, c1, c2):
    """A dorsal fin (leaning right) filled with a c1->c2 horizontal gradient."""
    w, h = box_w * SS, box_h * SS
    # normalised fin outline (y down): base + curved leading edge + swept back
    A = (0.16 * w, 0.86 * h)   # base front (bottom-left)
    B = (0.74 * w, 0.86 * h)   # base back  (bottom-right)
    C = (0.62 * w, 0.12 * h)   # peak (top, leaning right)
    leading = _quad(A, (0.16 * w, 0.34 * h), C)     # front edge bulges up-left
    trailing = _quad(C, (0.78 * w, 0.42 * h), B)    # back edge swept
    poly = leading + trailing

    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).polygon(poly, fill=255)
    grad = hgradient(w, h, c1, c2)
    fin = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    fin.paste(grad, (0, 0), mask)
    return fin.resize((box_w, box_h), Image.LANCZOS)


def jellyfish_rgba(size, c1, c2):
    """A Jellyfin-style jellyfish (bell + wavy tentacles) filled top->bottom
    with c1->c2. c1 green (Emby) + c2 lilac (Jellyfin) = the two-brand fusion."""
    w = h = size * SS
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    bw = int(w * 0.60)
    bx = (w - bw) // 2
    top = int(h * 0.16)
    bell_h = int(h * 0.40)
    rim = top + bell_h
    d.pieslice([bx, top, bx + bw, top + 2 * bell_h], 180, 360, fill=255)  # dome
    d.rectangle([bx, rim - int(bell_h * 0.12), bx + bw, rim], fill=255)
    frills = 4
    r = bw * 0.085
    for i in range(frills + 1):                                           # frilly rim
        cx = bx + i * bw / float(frills)
        d.ellipse([cx - r, rim - r * 0.7, cx + r, rim + r * 0.7], fill=255)
    tents = 4
    for i in range(tents):                                                # tentacles
        cx = bx + bw * (0.18 + 0.64 * i / float(tents - 1))
        pts = []
        for k in range(0, 25):
            t = k / 24.0
            yy = rim + t * (h * 0.33)
            xx = cx + math.sin(t * math.pi * 2.2 + i * 1.3) * bw * 0.055 * (0.4 + t)
            pts.append((xx, yy))
        d.line(pts, fill=255, width=max(2, int(bw * 0.055)), joint="curve")
    grad = vgradient(w, h, c1, c2)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(grad, (0, 0), mask)
    return out.resize((size, size), Image.LANCZOS)


def monogram_rgba(size, text, c1, c2):
    w = h = size * SS
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    font = ImageFont.truetype(FONT, int(h * 0.72))
    bb = d.textbbox((0, 0), text, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    d.text(((w - tw) / 2 - bb[0], (h - th) / 2 - bb[1]), text, font=font, fill=255)
    grad = hgradient(w, h, c1, c2)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(grad, (0, 0), mask)
    return out.resize((size, size), Image.LANCZOS)


def dgradient(w, h, c1, c2):
    grad = Image.new("RGB", (w, h))
    px = grad.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = _lerp(c1, c2, (x + y) / float(max(1, w + h - 2)))
    return grad


def _rtri(w, h, cx, cy, R, up=True, blur=6.0):
    """A rounded equilateral triangle mask: sharp triangle -> blur -> threshold
    rounds every corner cleanly (no apex artefacts)."""
    m = Image.new("L", (w, h), 0)
    verts = []
    for k in range(3):
        ang = -math.pi / 2 + k * 2 * math.pi / 3 + (0 if up else math.pi)
        verts.append((cx + R * math.cos(ang), cy + R * math.sin(ang)))
    ImageDraw.Draw(m).polygon(verts, fill=255)
    m = m.filter(ImageFilter.GaussianBlur(blur))
    return m.point(lambda p: 255 if p >= 128 else 0)


def fusion_rgba(size, c1, c2, play_white=True):
    """Jellyfin's rounded-triangle ring + Emby's play triangle inside, in a
    c1->c2 diagonal gradient: the two official marks fused into one. The play
    is white (Emby style) by default, or the gradient itself."""
    w = h = size * SS
    cx, cy = w / 2.0, h * 0.52
    ring = ImageChops.subtract(
        _rtri(w, h, cx, cy, w * 0.46, True, w * 0.055),
        _rtri(w, h, cx, cy, w * 0.29, True, w * 0.038))
    play = Image.new("L", (w, h), 0)
    pr = w * 0.11
    ImageDraw.Draw(play).polygon(
        [(cx - pr * 0.66, cy - pr), (cx - pr * 0.66, cy + pr), (cx + pr, cy)], fill=255)
    play = play.filter(ImageFilter.GaussianBlur(w * 0.008)).point(lambda p: 255 if p >= 128 else 0)
    grad = dgradient(w, h, c1, c2)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if play_white:
        out.paste(grad, (0, 0), ring)
        out.paste(Image.new("RGBA", (w, h), (255, 255, 255, 255)), (0, 0), play)
    else:
        out.paste(grad, (0, 0), ImageChops.lighter(ring, play))
    return out.resize((size, size), Image.LANCZOS)


def accent_pair(kind):
    return {"emby": (GREEN, GREEN), "jellyfin": (LILAC, LILAC),
            "base": (AMBER, AMBER)}.get(kind, (GREEN, LILAC))


def dark_tile(size, radius):
    w = h = size * SS
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # near-black vertical gradient body
    for y in range(h):
        v = 30 - int(18 * y / float(h))
        d.line([(0, y), (w, y)], fill=(max(0, v), max(0, v), max(0, v + 2), 255))
    # rounded-corner mask + thin border
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius * SS, fill=255)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    ImageDraw.Draw(out).rounded_rectangle(
        [SS, SS, w - 1 - SS, h - 1 - SS], radius * SS, outline=(60, 60, 66, 255), width=SS)
    return out.resize((size, size), Image.LANCZOS)


def make_picon(size, motif="fin", kind="dual"):
    tile = dark_tile(size, radius=int(size * 0.10))
    c1, c2 = accent_pair(kind)
    aw = int(size * 0.62)
    if motif == "fusion":
        art = fusion_rgba(aw, c1, c2)
    elif motif == "jellyfish":
        art = jellyfish_rgba(aw, c1, c2)
    elif motif == "monogram":
        art = monogram_rgba(aw, "Df", c1, c2)
    else:
        art = fin_rgba(aw, aw, c1, c2)
    tile.alpha_composite(art, (int((size - aw) / 2), int((size - aw) / 2)))
    return tile


def make_badge(w, h, kind="dual"):
    S = SS
    W, H = w * S, h * S
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rad = int(H * 0.22)
    # dark body
    body = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(body)
    for y in range(H):
        v = 34 - int(20 * y / float(H))
        bd.line([(0, y), (W, y)], fill=(max(0, v), max(0, v), max(0, v + 2), 255))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, H - 1], rad, fill=255)
    img.paste(body, (0, 0), mask)
    # accent border (green->lilac), matching the old amber frame idea
    border = hgradient(W, H, GREEN, LILAC).convert("RGBA")
    bmask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(bmask).rounded_rectangle([S, S, W - 1 - S, H - 1 - S], rad, outline=255, width=2 * S)
    img.paste(border, (0, 0), bmask)
    # fusion mark on the left
    fs = int(H * 0.80)
    fx = int(W * 0.03)
    img.alpha_composite(fusion_rgba(fs, GREEN, LILAC), (fx, int((H - fs) / 2)))
    # "DreamFin" text, auto-fit to the remaining width
    tx = fx + fs - int(H * 0.04)
    avail = W - tx - int(H * 0.10)
    fsize = int(H * 0.46)
    font = ImageFont.truetype(FONT, fsize)
    while fsize > 8 and d.textlength("DreamFin", font=font) > avail:
        fsize -= 2
        font = ImageFont.truetype(FONT, fsize)
    d.text((tx, H * 0.52), "DreamFin", font=font, fill=(238, 238, 238, 255), anchor="lm")
    return img.resize((w, h), Image.LANCZOS)


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else "."
    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    # plugin-browser badge (vivid, dual, with "DreamFin")
    make_badge(100, 40).save(os.path.join(outdir, "pluginLogo.png"))
    make_badge(150, 60).save(os.path.join(outdir, "pluginLogoHD.png"))
    # DreamFin brand picon: the dual green->lilac fusion (same for BOTH servers -
    # it stands for Emby AND Jellyfin), NOT retinted per accent. Placed into the
    # base and both accent dirs so build_skins can point each variant at it.
    make_picon(256, "fusion", "dual").save(os.path.join(outdir, "dreamfin_256.png"))
    make_picon(350, "fusion", "dual").save(os.path.join(outdir, "dreamfin_350.png"))
    print("wrote logos to %s" % outdir)


if __name__ == "__main__":
    main()
