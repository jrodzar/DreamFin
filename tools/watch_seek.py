#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Vigila la sesion de DreamFin en el servidor y registra la posicion.

Verifica el SEEK LEJANO sin tocar el deco: el usuario maneja el mando y aqui
se lee, desde el servidor, que posicion reporta DreamFin. Marca los saltos.

Run:  py -3 watch_seek.py [seg_entre_lecturas] [minutos_max] [emby|jellyfin]
"""
from __future__ import print_function

import io
import json
import os
import sys
import time

REPO = r"C:\Users\jrodzar\Desktop\claude_code\DreamFin\DreamFin"
sys.path.insert(0, REPO)

from tools.verify_real_servers import find_credentials  # noqa: E402
from tools.emby_session import make_lib  # noqa: E402

EVERY = int(sys.argv[1]) if len(sys.argv) > 1 else 5
MAX_MIN = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
WANT = (sys.argv[3].lower() if len(sys.argv) > 3 else "emby")


def mmss(seconds):
	seconds = int(seconds)
	return "%d:%02d:%02d" % (seconds // 3600, (seconds % 3600) // 60, seconds % 60)


def buildLib():
	cred = find_credentials()
	with io.open(cred, encoding="utf-8") as fd:
		servers = json.load(fd)
	server = None
	for s in servers:
		hay = (s.get("label", "") + " " + s.get("dns", "") + " "
		       + s.get("expectType", "")).lower()
		if WANT in hay:
			server = s
			break
	lib = make_lib(server or servers[0])
	if not lib.authenticate():
		raise RuntimeError("auth failed: %s" % lib.getLastErrorMessage())
	return lib


def dreamfinSessions(lib):
	raw = lib.getJson(lib.getContentUrl("/Sessions?api_key=%s" % lib.g_accessToken))
	sessions = raw if isinstance(raw, list) else (raw or {}).get("Items", [])
	out = []
	for s in sessions or []:
		if "dreamfin" not in (s.get("Client") or "").lower():
			continue
		item = s.get("NowPlayingItem")
		if not item:
			continue
		ps = s.get("PlayState") or {}
		out.append({
			"session": (s.get("Id") or "?")[:8],
			"item": item.get("Name"),
			"id": item.get("Id"),
			"runtime": (item.get("RunTimeTicks") or 0) / 10000000.0,
			"pos": (ps.get("PositionTicks") or 0) / 10000000.0,
			"method": ps.get("PlayMethod"),
			"paused": ps.get("IsPaused"),
			"transcode": bool(s.get("TranscodingInfo")),
		})
	return out


def main():
	lib = buildLib()
	print("vigilando DreamFin en '%s' cada %ss (hasta %s min). Ctrl+C para parar.\n"
	      % (WANT, EVERY, MAX_MIN))
	print("%-10s %-10s %-8s %s" % ("hora", "posicion", "avance", "estado"))
	print("-" * 60)
	seen = {}
	deadline = time.time() + MAX_MIN * 60
	while time.time() < deadline:
		try:
			sessions = dreamfinSessions(lib)
		except Exception as e:
			print("  (error: %s)" % e)
			time.sleep(EVERY)
			continue
		now = time.strftime("%H:%M:%S")
		if not sessions:
			if seen:
				print("%-10s --- sin reproduccion DreamFin ---" % now)
				seen = {}
			time.sleep(EVERY)
			continue
		if len(sessions) > 1:
			# OJO: el servidor arrastra sesiones DreamFin viejas y ademas sigue
			# avanciendo la posicion de un transcode aunque el cliente muera.
			# Por eso se imprimen TODAS y con su id: nunca asumir que hay una.
			print("%-10s  *** %d sesiones DreamFin reproduciendo ***" % (now, len(sessions)))
		for s in sessions:
			key = s["session"]
			if key not in seen:
				print("\n>>> [%s] %s   dura %s   metodo=%s   transcode=%s\n"
				      % (key, s["item"], mmss(s["runtime"]), s["method"],
				         "SI" if s["transcode"] else "no"))
				seen[key] = None
			prev = seen[key]
			delta = "" if prev is None else "%+.0fs" % (s["pos"] - prev)
			flag = ""
			if prev is not None and abs(s["pos"] - prev) > 45:
				flag = "   <<<< SALTO"
			if s["paused"]:
				flag += "   (pausa)"
			print("%-10s [%s] %-10s %-8s %s%s"
			      % (now, key, mmss(s["pos"]), delta, s["method"] or "?", flag))
			seen[key] = s["pos"]
		time.sleep(EVERY)
	print("\nfin de la vigilancia")


if __name__ == "__main__":
	main()
