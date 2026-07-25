DreamFin 0.1.8 — release notes
==============================

**DreamFin** is an Emby/Jellyfin client for Enigma2 forked from DreamPlex. It
reuses the DreamPlex user interface and replaces the Plex backend with an
Emby/Jellyfin one. See `README.md` for setup, lineage and attribution.

New in 0.1.8
------------

- **Your server knows where you are again.** DreamFin was not reporting
  playback progress at all: the ticker that sends it was created but never
  started, because starting it had been left to events that never happen on a
  streamed or transcoded playback. A whole film could play without the server
  learning anything — nothing on the dashboard, and no resume point when you
  came back. It now reports every five seconds, from the moment playback
  begins.

- **Jumping to a minute works.** Press BLUE (or RED) during playback, type a
  minute, press OK — and until now, while transcoding, absolutely nothing
  happened. No error, no message: the jump asked the decoder where it was
  before moving, and a transcoded stream never tells it. The jump now happens
  straight away, will not land past the end of the film, and leaving the
  dialog without typing anything is no longer a problem.

Both were checked on a real box against Emby and Jellyfin.

Skin
----

- The **server menu of the `default` skin** is now a vertical list, like the
  BlueMod skin, instead of a five-slot horizontal carousel: every library is
  on screen at once. The logo below the mini-TV was resized and centred, and
  the FHD variant received the same treatment plus its bottom bar.

DreamFin 0.1.7 — release notes
==============================

**DreamFin** is an Emby/Jellyfin client for Enigma2 forked from DreamPlex. It
reuses the DreamPlex user interface and replaces the Plex backend with an
Emby/Jellyfin one. See `README.md` for setup, lineage and attribution.

New in 0.1.7
------------

- **Nothing gets marked as watched behind your back.** While a media was still
  opening, the player read a play position that does not mean anything yet; a
  negative value made it think it had reached the end, and the item was
  scrobbled as seen without anybody having watched it.
- **The server now sees your progress while transcoding.** For a transcoded
  HLS stream the box has no position to report — it is asked on every tick and
  answers "don't know" every time — so the plugin keeps its own clock,
  correcting it against the decoder whenever that one does know. Playback shows
  up in the server's dashboard and the resume point is stored, both of which
  used to fail silently while transcoding.
- **Resuming starts the report where playback starts**, so a resumed film is no
  longer shown as restarted from the beginning until a later report catches up.
- **Each playback is its own session.** The id that ties the stream to its
  progress reports was the receiver's device id, which never changes, so every
  playback of a session looked like the same one.
- **A broken plugin can no longer stop the receiver from booting.** If anything
  fails while the box starts, DreamFin now disables itself for that boot and
  says so, instead of taking the whole interface down and leaving the receiver
  in a restart loop.
- **HEVC transcoding gets its own quality ladder.** Reusing the H.264 one spent
  the codec's efficiency on picture quality and left the frame where it was —
  3 Mbps still asked for 720p when HEVC comfortably holds more. The HEVC steps
  keep the same bitrates and buy a bigger picture instead, and two of them go
  past the 1080p ceiling that only H.264 needs (1440p and 2160p). The setting
  lists only the ladder of the codec you picked, and the steps say *up to*: the
  resolution you set is a ceiling, and what the server delivers within it
  depends on the source.

New in 0.1.6
------------

- **"Recently Added" in a TV library now groups by series.** It used to mix
  loose episodes from different shows; it now lists the shows themselves,
  most-recently-added first (a show moves up when it gains an episode), and
  selecting one opens its seasons — like the rest of the show list.
- **New content is flagged with an amber sparkle** to the right of the title,
  for every kind of item. A show or season carries the mark too, so you can
  follow the trail down to the newly added episode. "New" means recently
  *added* (not release date); the window is configurable in the settings
  (Off / 3 / 7 / 14 / 30 / 60 / 90 days, default 7 days).
- The **BlueMod** skin draws a poster placeholder behind the player poster, so
  the frame is not empty while the cover art loads.

Fixed in 0.1.5
--------------

- **Artwork no longer blanks out while scrolling.** Without the picture cache
  (the default) every row wrote its poster and backdrop to the same shared
  file, so scrolling — which fetches one image per row — made the concurrent
  downloads clobber each other and leave random blank or wrong artwork that
  only a re-visit fixed. Each item now caches to its own file (de-duplicated,
  reused on revisit, truncated downloads rejected), so posters and backdrops
  load reliably.
- The spinner's **"Loading…" caption** followed a hard-coded amber; it now uses
  the server accent (green for Emby, lilac for Jellyfin), like the counter next
  to it.

Fixed in 0.1.4
--------------

- **Search works again.** The search box padded the term with trailing spaces,
  which produced a request the server rejected — so a search always came back
  empty ("No data").
- **"Recently added" no longer hangs the plugin.** A query that already asks for
  a fixed number of items (recently added, on deck) was still paged through the
  whole library; on a library with tens of thousands of episodes it walked the
  lot and locked up on "Loading…". These are now fetched in a single request.
- **The subtitle menu (the TEXT button) no longer green-screens.** Opening it
  crashed on a method-name mismatch, a missing lookup and a subtitle row missing
  a field; all three are fixed and the forced-subtitle path with it.
- **"Recently added" and "Recently released" show the newest first again.** For
  movies, shows and music these lists were coming back in alphabetical order —
  the request carried two conflicting sort keys and the server kept the wrong
  one. They now sort by date as intended.
- **No crash on an item with no media.** Showing the technical badges of a
  metadata-only entry (a "coming soon" movie or episode with no file) no longer
  green-screens.

Fixed in 0.1.3
--------------

- No more green-screen crash when browsing the episodes of a series.
- "Recently added" loads again (the server's Latest endpoint 500'd when the
  pager appended a StartIndex).
- No crash when leaving the "Recently added" / mixed view, which can contain
  series as well as movies.
- General robustness pass on the show, mixed, movie and music views.

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
- Runs on **OpenATV 6.4 (Python 2.7)** and **6.5+ / 7.x / 8.0 (Python 3)**.

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
on an Octagon SF8008. Browsing, playback, transcoding and watch-state were
exercised in depth on **OpenATV 6.4** (Python 2.7) and **7.6** (Python 3); the
plugin is also installed and smoke-tested on **7.0** and **8.0-beta**. The
offline test suite (mock Emby/Jellyfin backend) is green on Python 2.7 and
Python 3.

----

The DreamPlex release history is preserved upstream at
https://github.com/oe-alliance/DreamPlex.
