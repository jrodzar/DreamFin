DreamFin 0.1.2 — release notes
==============================

**DreamFin** is an Emby/Jellyfin client for Enigma2 forked from DreamPlex. It
reuses the DreamPlex user interface and replaces the Plex backend with an
Emby/Jellyfin one. See `README.md` for setup, lineage and attribution.

Fixed in 0.1.2
--------------

- TV shows and seasons now show their star rating (and cast). The rating only
  comes back in Emby's single-item detail response, and the per-item detail
  fetch that loads it was limited to playable rows — so series always showed
  empty rating stars, even when the show had a rating.

Fixed in 0.1.1
--------------

- The TV-show views no longer crash on items with no runtime. Series, seasons,
  artists and albums have no duration, and formatting that empty value used to
  raise an error that aborted the view refresh — which showed up as a green
  screen when browsing the series list and as series with no cover art and no
  metadata. Movies and episodes were unaffected.

What's in it
------------

- **Emby and Jellyfin**, auto-detected. Add a server by host name or IP and the
  plugin figures out which backend it is talking to; the UI recolours to match
  (green for Emby, lilac for Jellyfin, lilac by default).
- **Authentication** with username/password (token cached, single silent
  re-auth on 401) or a server **API key**. HTTPS on 443/8920 with TLS SNI kept
  for name-based reverse proxies.
- **Browsing** of movies, TV shows (seasons → episodes), music
  (artists → albums → tracks) and mixed folders, with a client-side synthesized
  filter menu (All / Unwatched / Recently Added / On Deck / By Genre / By Year /
  By Decade / Search), server-side artwork resizing and unwatched counts.
- **Playback**: direct streaming and HLS transcoding (h264 / HEVC), a version
  selector for multi-source items, audio/subtitle selection with burn-in for
  image subtitles when transcoding, and trailers where the server exposes them.
- **Watch state**: resume position round-trips with the server, progress is
  reported during playback, and watched / unwatched toggles sync both ways.
- Runs on **OpenATV 6.4 (Python 2.7)** and **6.5+/7.x (Python 3)**.

Known limitations
-----------------

- **Direct Local** playback needs an **admin API key**: Emby/Jellyfin hide
  `MediaSources[].Path` from non-admin users, so a non-admin login cannot
  resolve a local file path. Use *Streamed* or *Transcoded* otherwise.
- **HEVC direct decode** depends on the receiver: where the box cannot decode
  the source, use *Transcoded* (the server re-encodes to h264, or to HEVC where
  the box supports it).
- **Music** needs a music library on the server; on servers without one that
  section is empty.
- Playback controls follow the DreamPlex conventions: **STOP** ends playback
  (the EXIT-to-stop binding is off by default in the DreamFin settings).

Developed and verified against real **Emby 4.9** and **Jellyfin 10.11** servers
on an Octagon SF8008 running OpenATV 6.4 and 7.6, with an offline test suite
(mock Emby/Jellyfin backend) green on Python 2.7 and Python 3.

----

The DreamPlex release history is preserved upstream at
https://github.com/oe-alliance/DreamPlex.
