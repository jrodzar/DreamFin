#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Report the Emby/Jellyfin server's active playback session(s).

Auths to the test server (credentials resolved like verify_real_servers.py)
and prints, for each NowPlaying session, the PlayMethod and — when
transcoding — the TranscodingInfo (video/audio codec, dimensions, whether
the video is direct). Used to confirm server-side that DreamFin's on-box
playback is really a transcode (and in which codec), e.g. to close the
HLS/HEVC transcode gate without needing to read pixels off the box.

Run:  py -3 tools/emby_session.py            (defaults to the emby entry)
      py -3 tools/emby_session.py jellyfin   (pick by label/dns substring)
"""
from __future__ import print_function

import io
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from tools.verify_real_servers import find_credentials  # noqa: E402
from tests import helpers  # noqa: E402
helpers.setup_environment()

import src  # noqa: E402
from src.DP_EmbyLibrary import EmbyLibrary  # noqa: E402


def make_lib(server):
    sc = src.initServerEntryConfig()
    sc.name.value = server["dns"]
    sc.connectionType.value = "1"
    sc.dns.value = server["dns"]
    sc.port.value = int(server.get("port", 443))
    sc.username.value = server.get("username", "")
    sc.password.value = server.get("password", "")
    sc.serverType.value = server.get("serverType", "auto")
    return EmbyLibrary(session=None, serverConfig=sc)


def main():
    want = sys.argv[1].lower() if len(sys.argv) > 1 else "emby"
    cred = find_credentials()
    if not os.path.isfile(cred):
        print("missing credentials: %s" % cred)
        return 2
    with io.open(cred, encoding="utf-8") as fd:
        servers = json.load(fd)

    server = None
    for s in servers:
        hay = (s.get("label", "") + " " + s.get("dns", "") + " " + s.get("expectType", "")).lower()
        if want in hay:
            server = s
            break
    if server is None:
        server = servers[0]

    lib = make_lib(server)
    if not lib.authenticate():
        print("auth failed: %s" % lib.getLastErrorMessage())
        return 1

    raw = lib.getJson(lib.getContentUrl("/Sessions?api_key=%s" % lib.g_accessToken))
    sessions = raw if isinstance(raw, list) else (raw or {}).get("Items", [])
    found = False
    for s in sessions or []:
        npi = s.get("NowPlayingItem")
        if not npi:
            continue
        found = True
        ps = s.get("PlayState", {}) or {}
        ti = s.get("TranscodingInfo", {}) or {}
        posTicks = ps.get("PositionTicks") or 0
        print("SESSION client=%s device=%s" % (s.get("Client"), s.get("DeviceName")))
        print("  item: %s (%s)" % (npi.get("Name"), npi.get("Id")))
        print("  PlayMethod: %s" % ps.get("PlayMethod"))
        print("  pos: %.1f min" % (posTicks / 10000000.0 / 60.0))
        if ti:
            print("  TranscodingInfo: Vcodec=%s Acodec=%s %sx%s bitrate=%s "
                  "isVideoDirect=%s container=%s" % (
                      ti.get("VideoCodec"), ti.get("AudioCodec"), ti.get("Width"),
                      ti.get("Height"), ti.get("Bitrate"), ti.get("IsVideoDirect"),
                      ti.get("Container")))
        else:
            print("  (no TranscodingInfo -> direct play / not transcoding)")
    if not found:
        print("no active NowPlaying session (start playback on the box first)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
