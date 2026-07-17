#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate the real HLS transcode URL the plugin would feed gstreamer.

Auths to the Emby test server, picks an HD movie, sets playbackType=1 and
calls the very same EmbyLibrary.transcode() the on-box player uses, then
prints the resolved media-playlist URL (and the /stream.ts progressive
fallback URL). Used to probe the OpenATV 6.4 gstreamer HLS gate directly
via a 4097 service ref, without blind plugin navigation.

Run:  py -3 tools/gen_transcode_url.py [uniQuality]   (default quality 3)
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

out = sys.stdout


def say(t):
    out.write(t + "\n")
    out.flush()


def to_text(v):
    return v.decode("utf-8") if isinstance(v, bytes) else v


def make_lib(server, uniQuality="3", codec="h264"):
    sc = src.initServerEntryConfig()
    sc.name.value = server["dns"]
    sc.connectionType.value = "1"
    sc.dns.value = server["dns"]
    sc.port.value = int(server.get("port", 8096))
    sc.username.value = server.get("username", "")
    sc.password.value = server.get("password", "")
    sc.serverType.value = server.get("serverType", "auto")
    sc.playbackType.value = "1"          # Transcoded
    sc.uniQuality.value = uniQuality
    sc.transcodeVideoCodec.value = codec
    return EmbyLibrary(session=None, serverConfig=sc)


def pick_movie(lib):
    """Return (id, title, resolution) of an HD movie from the Emby lib."""
    sections = lib.getAllSections()
    movieRoot = None
    for e in sections:
        if e[2] == "movieEntry" and e[3].get("isSectionRoot"):
            movieRoot = e[3]
            break
    if not movieRoot:
        return None
    menu = lib.getSectionFilter(movieRoot)
    allUrl = None
    for e in menu:
        if e[3]["key"] == "all":
            allUrl = e[3]["contentUrl"]
            break
    movies, _mc = lib.getMoviesFromSection(allUrl)
    say("  movies in section: %d" % len(movies))
    if not movies:
        return None
    m = movies[0]
    data = m[1]
    arr = data.get("mediaDataArr") or []
    if arr:
        say("  mediaDataArr[0] keys: %s" % repr(sorted(arr[0].keys()) if isinstance(arr[0], dict) else type(arr[0])))
    mid = data.get("id") or data.get("ratingKey") or m[4]
    res = ""
    if arr and isinstance(arr[0], dict):
        res = str(arr[0].get("videoResolution") or arr[0].get("Height") or "")
    return (mid, to_text(m[0]), res)


def main():
    cred = find_credentials()
    if not os.path.isfile(cred):
        say("missing credentials: %s" % cred)
        return 2
    with io.open(cred, encoding="utf-8") as fd:
        servers = json.load(fd)
    emby = None
    for s in servers:
        if s.get("expectType") == "emby" or "emby" in s.get("dns", ""):
            emby = s
            break
    if not emby:
        say("no emby server in credentials")
        return 2

    uniQuality = sys.argv[1] if len(sys.argv) > 1 else "3"
    knownId = sys.argv[2] if len(sys.argv) > 2 else None
    codec = sys.argv[3] if len(sys.argv) > 3 else "h264"
    lib = make_lib(emby, uniQuality=uniQuality, codec=codec)
    say("=== %s (uniQuality=%s, codec=%s) ===" % (emby["dns"], uniQuality, codec))
    if not lib.authenticate():
        say("auth failed: %s" % lib.getLastErrorMessage())
        return 1
    say("  auth OK, userId %s..., sessionID %s" % (lib.g_userId[:8], getattr(lib, "g_sessionID", "?")))

    if knownId:
        mid, title, res = knownId, "(known id)", "?"
        say("  using known id: %s" % mid)
    else:
        picked = pick_movie(lib)
        if not picked:
            say("no movie found")
            return 1
        mid, title, res = picked
        say("  picked: '%s' (id=%s, res=%s)" % (title, mid, res))

    lib.setPlaybackType("1")
    say("  g_transcode = %s" % lib.g_transcode)

    hlsUrl = lib.transcode(mid, "")
    say("")
    say("HLS_URL=%s" % hlsUrl)

    # progressive fallback URL for the same item
    lib.g_serverConfig.progressiveTranscode.value = True
    tsUrl = lib.transcode(mid, "")
    say("TS_URL=%s" % tsUrl)
    return 0


if __name__ == "__main__":
    sys.exit(main())
