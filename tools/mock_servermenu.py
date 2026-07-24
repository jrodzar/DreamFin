# -*- coding: utf-8 -*-
"""Ajuste fino de la posicion del logo en DPS_ServerMenu, SOBRE UN GRAB REAL.

Por que sobre un grab y no reconstruyendo la pantalla: reconstruirla a mano
enganya. Dos ejemplos reales (2026-07-23):
  - `main_menu-fs8.png` (la barra inferior) lleva ~58 filas TRANSPARENTES
    arriba, asi que su `position="0,610"` en el skin NO es su borde visible;
    ese esta ~58 px mas abajo. Medir sobre el skin daba 610; sobre el grab, 668.
  - el "borde" por encima del logo NO es el primer cambio de brillo: ese es el
    panel gris INTERIOR del mini-TV (~y390). El borde real es el MARCO negro
    (~y424), que sobre fondo oscuro no dispara un umbral de brillo.
Conclusion: las medidas salen del pixel del grab, nunca del `position=` del skin.

Uso:
    py -3 tools/mock_servermenu.py <grab.png> [Y1 Y2 ...]

  <grab.png>  captura real del DPS_ServerMenu a 1280x720
              (OpenWebif: http://<caja>/grab?format=png&mode=osd)
  Y1 Y2 ...   Ys candidatas del logo (por defecto: actual, centrada y +-10)

Escribe `<grab>_logo_candidatos.png` al lado del grab: una tira con cada
candidata etiquetada y sus huecos arriba/abajo MEDIDOS.
"""
from __future__ import print_function

import os
import sys

from PIL import Image, ImageDraw, ImageFont

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO = os.path.join(REPO, "src", "skins", "default", "picons", "dreamfin.png")
FONT = os.path.join(REPO, "src", "fonts", "OpenSans.ttf")

LOGO_X = 190              # x del picon en el skin (widget size 224)
LOGO_SIZE = 224
# Se MIDE en una columna que ESQUIVA el logo (x 190..414): si se midiera en el
# centro del logo, su triangulo blanco (~y525) se confundiria con la barra.
# x=500 cruza el marco del mini-TV (25..580) y la barra (ancho completo), pero
# no el logo ni el texto de usuario (izquierda). Verificado 2026-07-23.
MEAS_COL = 500


def font(sz):
	try:
		return ImageFont.truetype(FONT, sz)
	except Exception:
		return ImageFont.load_default()


def measureFrame(px):
	"""Borde inferior del MARCO NEGRO del mini-TV (ultima fila casi-negra en la
	franja donde vive el marco, no mas abajo para no pillar sombras de la barra)."""
	last_black = None
	for y in range(300, 480):
		if sum(px[MEAS_COL, y]) <= 8:
			last_black = y
	return last_black


def measureBar(px, h):
	"""Borde VISIBLE de la barra inferior: primer salto de brillo sostenido por
	debajo de la banda del logo."""
	prev = None
	for y in range(500, h - 1):
		v = sum(px[MEAS_COL, y])
		if prev is not None and v - prev > 40:
			return y
		prev = v
	return h - 1


def main():
	if len(sys.argv) < 2:
		print(__doc__)
		return 2
	grabPath = sys.argv[1]
	grab = Image.open(grabPath).convert("RGB")
	W, H = grab.size
	if (W, H) != (1280, 720):
		print("aviso: el grab es %sx%s, se esperaba 1280x720" % (W, H))
	px = grab.load()

	frame = measureFrame(px)
	bar = measureBar(px, H)
	gap = bar - frame
	centred = frame + (gap - LOGO_SIZE) // 2
	print("MEDIDO sobre %s:" % os.path.basename(grabPath))
	print("  borde inferior del marco (mini-TV) : y=%s" % frame)
	print("  borde visible de la barra          : y=%s" % bar)
	print("  hueco util = %s px | logo %s px -> centrado en y=%s"
	      % (gap, LOGO_SIZE, centred))

	ys = [int(a) for a in sys.argv[2:]] or [430, centred, centred - 10,
	                                         centred + 10]

	# fondo sin el logo: copiar una columna de fondo limpio en la banda del logo
	base = grab.copy()
	bpx = base.load()
	for y in range(frame + 1, bar):
		ref = bpx[MEAS_COL, y]
		for x in range(LOGO_X - 40, LOGO_X + LOGO_SIZE + 40):
			bpx[x, y] = ref

	logo = Image.open(LOGO).convert("RGBA")
	crops = []
	for y in ys:
		im = base.copy()
		im.paste(logo, (LOGO_X, y), logo)
		crop = im.crop((0, max(0, frame - 20), 640, min(H, bar + 20)))
		d = ImageDraw.Draw(crop)
		d.rectangle([0, 0, 640, 30], fill=(0, 0, 0))
		up, dn = y - frame, bar - (y + LOGO_SIZE)
		d.text((10, 15), "y=%d  (arriba %d / abajo %d)" % (y, up, dn),
		       font=font(20), fill=(255, 210, 60), anchor="lm")
		crops.append(crop)
		print("  candidata y=%-4s arriba %-3s abajo %-3s" % (y, up, dn))

	cw, ch = crops[0].size
	out = Image.new("RGB", (cw, ch * len(crops)))
	for i, c in enumerate(crops):
		out.paste(c, (0, i * ch))
	outPath = os.path.splitext(grabPath)[0] + "_logo_candidatos.png"
	out.save(outPath)
	print("escrito: %s" % outPath)
	return 0


if __name__ == "__main__":
	sys.exit(main())
