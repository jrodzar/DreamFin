#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Cuanto hay traducido de verdad, y si el arreglo se vera en el idioma de prueba.

Dos preguntas distintas, y hacen falta las dos:

1. **Los catalogos**: cuantas entradas tiene cada `.po` y cuantas siguen sin
   traducir (`msgstr` vacio **o identico al `msgid`**). Sirve para saber, ANTES
   de probar, si un arreglo de i18n se va a poder ver en el idioma en que se va
   a probar. Un `msgstr` igual al `msgid` hace que roto y arreglado se vean
   EXACTAMENTE igual.

2. **El paquete** (`--ipk`): abrir el `.ipk` recien construido, sacar el `.mo` y
   preguntarle a gettext. Eso cubre **las tres patas de una vez** — que el `.mo`
   se regenerase al empaquetar, que la entrada exista, y que este traducida.
   Mirarlo en el `.po` solo cubre dos.

Idea del intercambio con DreamPlex (2026-07-25), medidor y verificacion suyos.

DOS TRAMPAS, las dos de la misma familia (mirar el testigo equivocado):
  * El IPK se elige por **fecha de modificacion**, NO ordenando por nombre:
    "0.1.9" ordena DESPUES de "0.1.13" como texto, y se acaba midiendo un
    paquete de hace una semana. Le paso a DreamPlex.
  * Por eso esto **imprime siempre de donde sale el dato** (que fichero abrio),
    no solo el resultado. Si la salida fuese solo "sin traducir", uno se la cree.

Run:  py -3 tools/i18n_status.py
      py -3 tools/i18n_status.py --ipk
      py -3 tools/i18n_status.py --ipk --check "fastScroll 'On'" --lang es
"""
from __future__ import print_function

import gettext
import glob
import io
import os
import re
import sys
import tarfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PO_DIR = os.path.join(REPO, "po")
DIST = os.path.join(REPO, "dist")

# lo que arreglamos esta semana: si alguna sale igual que su msgid, el arreglo
# es invisible en ese idioma y una prueba en pantalla no probaria nada
DEFAULT_CHECKS = (
	"playback mode '%s'",
	"fastScroll 'On'",
	"fastScroll 'Off'",
	"<unknown>",
)

ENTRY = re.compile(
	r'^msgid\s+((?:"(?:[^"\\]|\\.)*"\s*)+)msgstr\s+((?:"(?:[^"\\]|\\.)*"\s*)+)',
	re.M)
PIECE = re.compile(r'"((?:[^"\\]|\\.)*)"')


def joined(blob):
	return "".join(PIECE.findall(blob))


def readCatalogue(path):
	"""(total, sin traducir) de un .po, saltando la cabecera (msgid vacio)."""
	text = io.open(path, encoding="utf-8", errors="replace").read()
	total = untranslated = 0
	for m in ENTRY.finditer(text):
		msgid, msgstr = joined(m.group(1)), joined(m.group(2))
		if not msgid:
			continue                      # la cabecera del catalogo
		total += 1
		if not msgstr or msgstr == msgid:
			untranslated += 1
	return total, untranslated


def newestIpk():
	"""Por FECHA, nunca por nombre: '0.1.9' > '0.1.13' alfabeticamente."""
	found = glob.glob(os.path.join(DIST, "*.ipk"))
	return max(found, key=os.path.getmtime) if found else None


def catalogueFromIpk(path, lang):
	"""El .mo que va DENTRO del paquete, que es el que acabara en el deco."""
	outer = tarfile.open(path)
	data = [m for m in outer.getmembers() if "data.tar" in m.name][0]
	inner = tarfile.open(fileobj=outer.extractfile(data))
	wanted = [n for n in inner.getnames()
	          if n.endswith(".mo") and "/%s/" % lang in n]
	if not wanted:
		return None, None
	member = [m for m in inner.getmembers() if m.name == wanted[0]][0]
	blob = inner.extractfile(member).read()
	return gettext.GNUTranslations(io.BytesIO(blob)), wanted[0]


def main():
	args = sys.argv[1:]
	lang = "es"
	if "--lang" in args:
		lang = args[args.index("--lang") + 1]
	checks = []
	while "--check" in args:
		i = args.index("--check")
		checks.append(args[i + 1])
		del args[i:i + 2]
	checks = checks or list(DEFAULT_CHECKS)

	print("catalogos en %s" % PO_DIR)
	print("%-10s %8s %14s %8s" % ("idioma", "entradas", "sin traducir", ""))
	for path in sorted(glob.glob(os.path.join(PO_DIR, "*.po"))):
		total, untranslated = readCatalogue(path)
		pct = (100.0 * untranslated / total) if total else 0.0
		note = "  <- catalogo ingles, correcto" if os.path.basename(path) == "en.po" else ""
		print("%-10s %8d %14d %7.0f%%%s"
		      % (os.path.basename(path), total, untranslated, pct, note))

	if "--ipk" not in args:
		print("\n(--ipk para comprobar el .mo DENTRO del paquete: las tres patas)")
		return 0

	ipk = newestIpk()
	if not ipk:
		print("\nno hay ningun .ipk en dist/ - construye uno antes")
		return 2

	print("\npaquete: %s" % os.path.basename(ipk))       # de donde sale el dato
	translations, name = catalogueFromIpk(ipk, lang)
	if translations is None:
		print("  el paquete NO trae catalogo para '%s'" % lang)
		return 1
	print("  catalogo dentro: %s\n" % name)

	bad = 0
	for text in checks:
		got = translations.gettext(text)
		ok = got != text
		bad += 0 if ok else 1
		print("  %-24s -> %-28s %s"
		      % (repr(text[:22]), repr(got[:26]), "traducido" if ok else "SIN TRADUCIR"))

	if bad:
		print("\n%d de %d saldrian en ingles en '%s'. Un arreglo sobre esas NO se "
		      "puede verificar en pantalla en ese idioma." % (bad, len(checks), lang))
	return 0


if __name__ == "__main__":
	sys.exit(main())
