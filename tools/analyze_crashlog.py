#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Leer un crashlog de enigma2 y decir DONDE peto, no solo que peto.

El backtrace que trae el crashlog NO sirve: son dos marcos, el manejador de la
senal y el restorer de libc, y ahi se acaba. Lo que si sirve es el `PC:`, pero
**solo en relativo**: ASLR mueve el bloque de mmap entero y conserva las
distancias entre bibliotecas, asi que la direccion absoluta cambia en cada
arranque y la RESTA contra libc no.

De ahi salen las dos cosas que contesta esta herramienta:

  1. **żEs la misma instruccion en varios crashes?** Si el delta
     `PC - <direccion del restorer>` coincide, el fallo es UNO y determinista.
     Corrupcion difusa daria deltas distintos.
  2. **żEs el crash que ya conocemos?** El del 2026-07-25 dio `0x623614` en los
     cinco, y resulto ser `Py_INCREF` con puntero nulo dentro de libpython
     (ver doc/JOURNAL.md). Si vuelve a salir ese numero, es el mismo y sigue
     vivo; si sale otro, es otra cosa.

De regalo, el `dmesg` del crashlog trae cientos de lineas `video pts <ms> <90k>`
que pone el driver de video: una traza REAL del decodificador. Se ven los saltos
(un seek o una reanudacion), la cadencia entre fotogramas y hasta donde llego.
Cuando el log de enigma2 va ahogado por `eServicePeer` -lo normal- es lo unico
que queda del momento del fallo.

Resolver la biblioteca y el simbolo necesita la caja, y es opcional:
    py -3 tools/analyze_crashlog.py <logs> --maps maps.txt --so libpython.so
donde `maps.txt` es `cat /proc/$(pidof enigma2)/maps` de un enigma2 VIVO y `--so`
la biblioteca a la que haya caido. Sin esas dos, el analisis es 100% offline.

Run:  py -3 tools/analyze_crashlog.py /ruta/a/*.log
"""
from __future__ import print_function

import glob
import io
import os
import re
import struct
import sys

# Delta conocido: PC - direccion del simbolo __default_rt_sa_restorer.
# 2026-07-25, los 5 crashes de aquel dia. Resulto ser Py_INCREF(NULL).
KNOWN = {
	0x623614: "Py_INCREF con puntero nulo en libpython (crash del 2026-07-25)",
}

# Offset de __default_rt_sa_restorer dentro de libc.so.6, OpenATV 7.6 armhf.
# Se saca en la caja con:
#   python3 -c "import ctypes;l=ctypes.CDLL('libc.so.6');print(hex(...))"
# menos la base de libc en /proc/self/maps. Solo se usa para la comprobacion de
# alineacion de pagina, que es lo que valida el resto del calculo.
OFF_RESTORER = 0x322A0

RE_PC = re.compile(r"PC:\s*([0-9a-fA-F]+)")
RE_FAULT = re.compile(r"Fault Address:\s*([0-9a-fA-F]+)")
RE_ERRCODE = re.compile(r"Error Code::\s*(\d+)")
RE_RESTORER = re.compile(r"__default_rt_sa_restorer\)\s*\[0x([0-9a-fA-F]+)\]")
RE_PTS = re.compile(r"video pts (\d+) (\d+)")
RE_HEADER = re.compile(r"^(crashdate|imageversion|model|component|imagebuild)=(.*)$", re.M)
RE_MAPS = re.compile(r"^([0-9a-f]+)-([0-9a-f]+) (\S+) \S+ \S+ \S+\s+(.+)$")


def mins(ms):
	return ms / 60000.0


def readHeader(text):
	return dict((m.group(1), m.group(2).strip()) for m in RE_HEADER.finditer(text))


def readPts(text):
	"""La traza del decodificador que queda en el dmesg."""
	dmesg = text.split("\ndmesg", 1)[-1]
	return [int(m.group(1)) for m in RE_PTS.finditer(dmesg)]


def describePts(values):
	if not values:
		return ["  sin traza de video en el dmesg"]

	out = ["  traza del decodificador: %d muestras, de %.2f a %.2f min"
	       % (len(values), mins(values[0]), mins(values[-1]))]

	jumps = [(i, values[i - 1], values[i])
	         for i in range(1, len(values)) if abs(values[i] - values[i - 1]) > 2000]
	if jumps:
		for _, a, b in jumps[:5]:
			out.append("    SALTO %.2f -> %.2f min (%+.1f s)%s"
			           % (mins(a), mins(b), (b - a) / 1000.0,
			              "  <- minuto exacto" if b % 60000 == 0 else ""))
		out.append("    (un salto a minuto EXACTO es un seek manual o una "
		           "reanudacion a una posicion que guardo uno)")
	else:
		out.append("    sin saltos: reproduccion lineal en toda la ventana")

	tail = values[-6:]
	steps = [tail[i] - tail[i - 1] for i in range(1, len(tail))]
	out.append("    ultimos fotogramas cada %s ms -> el video %s al morir"
	           % (steps, "iba FINO" if steps and max(steps) < 500 else "iba A TIRONES"))
	return out


def resolveLibrary(mapsPath, offsetFromLibc):
	"""Que biblioteca ocupa `base_de_libc + offset` en un enigma2 vivo."""
	rows = []
	for line in io.open(mapsPath, encoding="utf-8", errors="replace"):
		m = RE_MAPS.match(line.strip())
		if m:
			rows.append((int(m.group(1), 16), int(m.group(2), 16), m.group(3), m.group(4).strip()))

	libc = [r for r in rows if "libc.so.6" in r[3]]
	if not libc:
		return None, "no encuentro libc en el mapa"

	base = min(r[0] for r in libc)
	target = base + offsetFromLibc
	for lo, hi, perm, path in rows:
		if lo <= target < hi:
			return (path, target - lo), None
	return None, "0x%X no cae en ningun mapeo" % target


def resolveSymbol(soPath, addr):
	"""Nombre de funcion para una direccion dentro de un ELF32 (ARM)."""
	data = io.open(soPath, "rb").read()
	if data[:4] != b"\x7fELF" or struct.unpack_from("<B", data, 4)[0] != 1:
		return None, "no es un ELF32"

	shoff, = struct.unpack_from("<I", data, 0x20)
	shentsize, shnum = struct.unpack_from("<HH", data, 0x2E)

	sections = []
	for i in range(shnum):
		sections.append(struct.unpack_from("<10I", data, shoff + i * shentsize))

	syms = []
	for s in sections:
		if s[1] not in (2, 11) or not s[9]:          # SYMTAB / DYNSYM
			continue
		strtab = sections[s[6]]
		for i in range(s[5] // s[9]):
			nameOff, value, size, info, other, shndx = struct.unpack_from(
				"<IIIBBH", data, s[4] + i * s[9])
			if not value or not shndx:
				continue
			end = data.index(b"\0", strtab[4] + nameOff)
			name = data[strtab[4] + nameOff:end].decode("ascii", "replace")
			if name:
				syms.append((value & ~1, size, name))   # bit 0 = marca Thumb
	syms.sort()

	inside = [s for s in syms if s[1] and s[0] <= addr < s[0] + s[1]]
	if inside:
		return ("%s (+%d)" % (inside[0][2], addr - inside[0][0])), None

	before = [s for s in syms if s[0] <= addr]
	after = [s for s in syms if s[0] > addr]
	hint = "sin simbolo (funcion estatica). Entre %s y %s" % (
		before[-1][2] if before else "?", after[0][2] if after else "?")
	return None, hint


def readLog(path):
	"""La fecha del crashlog sale en el idioma de la caja, y la codificacion
	depende de su locale: los de este deco son UTF-8 validos, pero otro con
	locale latin-1 reventaria un decode estricto. De ahi el fallback.

	(Si la tilde sale rota en pantalla NO es esto: es la consola de Windows en
	cp1252. El analisis no depende de esa linea.)"""
	raw = io.open(path, "rb").read()
	for encoding in ("utf-8", "latin-1"):
		try:
			return raw.decode(encoding)
		except UnicodeDecodeError:
			continue
	return raw.decode("utf-8", "replace")


def analyse(path, maps=None, so=None):
	text = readLog(path)
	head = readHeader(text)
	print("===== %s =====" % os.path.basename(path))
	print("  %s | %s %s | %s" % (head.get("crashdate", "?"), head.get("model", "?"),
	                             head.get("imageversion", "?"), head.get("component", "?")))

	pc = RE_PC.search(text)
	restorer = RE_RESTORER.search(text)

	if not pc:
		traceback = "Traceback (most recent call last)" in text
		print("  NO es un fallo nativo: %s"
		      % ("lleva traza de Python, mirala directamente" if traceback else "sin PC en el log"))
		for line in describePts(readPts(text)):
			print(line)
		print()
		return None

	pcVal = int(pc.group(1), 16)
	fault = RE_FAULT.search(text)
	err = RE_ERRCODE.search(text)
	print("  PC=0x%X  fault=0x%s  errcode=%s"
	      % (pcVal, fault.group(1) if fault else "?", err.group(1) if err else "?"))

	if not restorer:
		print("  sin la direccion del restorer: no puedo sacar el delta")
		print()
		return None

	restVal = int(restorer.group(1), 16)
	delta = pcVal - restVal
	libcBase = restVal - OFF_RESTORER

	print("  delta PC-restorer = 0x%X" % delta)
	# Si el offset del simbolo es el bueno, la base de libc DEBE quedar alineada
	# a pagina. Es la comprobacion de que todo el calculo se sostiene.
	print("  base de libc = 0x%X  [%s]"
	      % (libcBase, "alineada a pagina, calculo OK" if libcBase % 0x1000 == 0
	         else "NO alineada: el offset del restorer no es el de esta imagen"))

	if delta in KNOWN:
		print("  >>> CONOCIDO: %s" % KNOWN[delta])
	else:
		print("  >>> delta NUEVO: no coincide con ningun crash catalogado")

	if maps:
		hit, why = resolveLibrary(maps, OFF_RESTORER + delta)
		if hit:
			print("  cae en %s  (+0x%X del mapeo)" % (hit[0], hit[1]))
			if so and os.path.basename(so) in hit[0]:
				name, hint = resolveSymbol(so, hit[1])
				print("  simbolo: %s" % (name or hint))
		else:
			print("  no resuelto: %s" % why)

	for line in describePts(readPts(text)):
		print(line)
	print()
	return delta


def main():
	args = [a for a in sys.argv[1:] if not a.startswith("--")]
	maps = so = None
	for i, a in enumerate(sys.argv):
		if a == "--maps" and i + 1 < len(sys.argv):
			maps = sys.argv[i + 1]
		if a == "--so" and i + 1 < len(sys.argv):
			so = sys.argv[i + 1]
	args = [a for a in args if a not in (maps, so)]

	paths = []
	for a in args:
		paths.extend(sorted(glob.glob(a)) if any(c in a for c in "*?") else
		             (sorted(glob.glob(os.path.join(a, "*.log"))) if os.path.isdir(a) else [a]))

	if not paths:
		print(__doc__)
		print("Nada que analizar. Los crashlogs del deco estan en /home/root/logs/")
		return 2

	deltas = [d for d in (analyse(p, maps, so) for p in paths) if d is not None]

	if len(deltas) > 1:
		unique = sorted(set(deltas))
		print("===== VEREDICTO (%d fallos nativos) =====" % len(deltas))
		if len(unique) == 1:
			print("  Delta IDENTICO en todos: 0x%X" % unique[0])
			print("  -> UNA sola instruccion, fallo determinista.")
			print("     %s" % KNOWN.get(unique[0], "sin catalogar: resolverlo con --maps/--so"))
		else:
			print("  %d deltas distintos: %s" % (len(unique), ["0x%X" % u for u in unique]))
			print("  -> NO es un unico punto de fallo. Agruparlos por delta.")
	return 0


if __name__ == "__main__":
	sys.exit(main())
