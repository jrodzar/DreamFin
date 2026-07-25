#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Auditar los Listbox: selectionPixmap mas bajo que la fila -> franja sin cubrir.

Si la imagen de seleccion es mas baja que `itemHeight`, enigma2 rellena lo que
falta con su highlight AZUL por defecto... salvo que el Listbox tenga un
`backgroundPixmap`, que tapa el hueco. Ese fue justo el caso de DreamFin: 17 px
sin cubrir en el FHD y aun asi 0 pixeles azules en pantalla, porque
`sel_bg.png` (480x1) se estira por todo el Listbox.

Lo que hay que mirar son las lineas HUECO **sin** backgroundPixmap.

Es un analisis ESTATICO: dice DONDE mirar y descarta de golpe lo que no puede
fallar, pero no sustituye a ver la pantalla. Un Listbox construido desde codigo
en vez de desde el XML no aparece aqui.

Idea original de la sesion de DreamPlex (2026-07-25).

Run:  py -3 tools/audit_listbox_selection.py
"""
from __future__ import print_function

import glob
import io
import os
import re
import sys

from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKINS = os.path.join(REPO, "src", "skins")

WIDGET = re.compile(r'<widget\b[^>]*render="Listbox"[^>]*>.*?</widget>', re.S)
SELPIX = re.compile(r'selectionPixmap="([^"]+)"')
ITEMH = re.compile(r'"itemHeight"\s*:\s*(\d+)')
SCREEN = re.compile(r'<screen\s+name="([^"]+)"')


def resolve(skinDir, pixmapPath):
	"""Las rutas del skin son absolutas del deco; quedarse con lo que hay tras
	`skins/<nombre>/` para poder encontrarlas en el repo (respeta accent_*/)."""
	marker = "/skins/"
	if marker in pixmapPath:
		tail = pixmapPath.split(marker, 1)[1]
		parts = tail.split("/", 1)
		if len(parts) == 2:
			return os.path.join(skinDir, parts[1].replace("/", os.sep))
	return os.path.join(skinDir, "images", os.path.basename(pixmapPath))


def screenAt(source, pos):
	found = "?"
	for m in SCREEN.finditer(source):
		if m.start() > pos:
			break
		found = m.group(1)
	return found


def main():
	problems, checked = [], 0
	for skinXml in sorted(glob.glob(os.path.join(SKINS, "*", "skin.xml"))):
		skinDir = os.path.dirname(skinXml)
		skin = os.path.basename(skinDir)
		with io.open(skinXml, encoding="utf-8") as fh:
			source = fh.read()

		for m in WIDGET.finditer(source):
			block = m.group(0)
			sel, item = SELPIX.search(block), ITEMH.search(block)
			if not sel or not item:
				continue
			checked += 1
			itemH = int(item.group(1))
			png = resolve(skinDir, sel.group(1))
			if not os.path.exists(png):
				print("  FALTA PNG: %s" % png)
				continue
			height = Image.open(png).height
			hasBg = "backgroundPixmap" in block
			screen = screenAt(source, m.start())
			gap = itemH - height

			if gap <= 0:
				state = "ok"
			elif hasBg:
				state = "hueco %2d px, tapado por backgroundPixmap" % gap
			else:
				state = "*** HUECO %d px SIN backgroundPixmap -> puede verse el azul ***" % gap
				problems.append((skin, screen, gap))
			print("%-14s %-22s %-26s item=%-3s png=%-3s %s"
			      % (skin, screen[:22], os.path.basename(png), itemH, height, state))

	print("\n%d Listbox con selectionPixmap revisados" % checked)
	if problems:
		print("REVISAR EN PANTALLA (%d):" % len(problems))
		for skin, screen, gap in problems:
			print("  %s :: %s  (%d px)" % (skin, screen, gap))
		return 1
	print("ninguno queda al descubierto")
	return 0


if __name__ == "__main__":
	sys.exit(main())
