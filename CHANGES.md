DreamFin — Changelog
====================

DreamFin is a fork of DreamPlex (a Plex client for Enigma2) with the Plex
backend replaced by an Emby/Jellyfin one. See `RELEASENOTES.md` for the full
release notes and `README.md` for lineage and attribution.

0.1.7 — features and fixes
--------------------------
* **Media is no longer marked as watched without being watched.** While the
  service was still starting the player read a play position that means
  nothing yet; a negative value failed the "did we get anywhere" test and fell
  through to the end-of-file path, which scrobbles the item as seen.
* **Playback progress is reported while transcoding.** For a transcoded HLS
  stream the decoder has no position to give — it answers "don't know" on
  every tick — so the plugin now keeps its own clock, synced to the decoder
  whenever that one does know. The server shows the stream and stores the
  resume point instead of nothing.
* **Resuming reports where playback actually starts**, not zero, so the server
  no longer shows a resumed film as restarted from the beginning.
* **Every playback is its own session on the server.** The session id sent
  with the stream and the progress reports was the box's device id, which
  never changes, so all playbacks looked like one long session.
* **A failure inside the plugin can no longer stop the receiver from
  booting.** Both boot entry points are guarded: a broken plugin now disables
  itself and prints why, instead of taking the whole GUI down with it.
* **HEVC transcoding has its own quality ladder.** Reusing the H.264 one spent
  the codec's efficiency on picture quality and left the frame where it was;
  the HEVC steps keep the same bitrates and ask for a bigger picture instead,
  with two steps beyond 1080p (1440p and 2160p) that only make sense here. The
  quality entry lists only the ladder of the codec in use, and its labels say
  "up to", because what the server actually delivers depends on the source.

0.1.6 — features
----------------
* "Recently added" in a TV-show library now groups by series instead of listing
  loose episodes from different shows — the query returns series (most recently
  added first, a show rising when it gains an episode) and opening one goes to
  its seasons, like the rest of the show list.
* Recently-added content is flagged with an amber sparkle to the right of the
  title, for every item type; a show/season carries the mark too so it can be
  followed down to the new episode. "New" means recently *added* (not release
  date). The window is configurable in the settings (Off / 3 / 7 / 14 / 30 / 60
  / 90 days, default 7).
* BlueMod skin: a poster placeholder is drawn behind the player poster so the
  frame is not empty while the artwork loads.

0.1.5 — bugfix
--------------
* Artwork stopped blanking out at random while scrolling. Without the picture
  cache (the default) every row wrote its poster/backdrop to the same shared
  file, so the per-row downloads a scroll fires clobbered each other and left
  blank/wrong images that only a re-visit fixed. Each item now caches to its
  own file (de-duplicated, reused on revisit, truncated fetches rejected), so
  posters and backdrops load reliably.
* The spinner's "Loading…" caption now follows the server accent (green for
  Emby, lilac for Jellyfin) instead of a hard-coded amber.

0.1.4 — bugfix
--------------
* Search no longer always returns "No data": the term is stripped and
  URL-encoded (a trailing space produced an invalid request URL).
* "Recently added" and other limited queries are fetched in a single request
  instead of being paged through the whole (tens-of-thousands-strong) library,
  which hung the plugin.
* The subtitle menu (TEXT) no longer crashes: a method-name typo, a missing
  by-id lookup, and a subtitle row missing its ``forced`` key each green-screened.
* "Recently added" and "Recently released" (movies, shows, music) were sorted
  alphabetically instead of by date — the listing URL carried a second SortBy
  the server ignored in favour of the default SortName. The date sort is now
  the only one, so these lists show the newest first.
* Hardened the media-pixmap handlers against a Movie/Episode with no media
  source (a metadata-only entry): reading its media info no longer indexes an
  empty list into a green screen.

0.1.3 — bugfix
--------------
* Fixed a green-screen crash when navigating episodes of a series (episode
  entries were missing the parent/grandparent ids the show view reads).
* "Recently added" no longer shows "No data": the ``/Items/Latest`` endpoint
  is a bare-array, non-pageable endpoint that 500s when a StartIndex is added.
* Fixed a crash when leaving the mixed / "Recently added" view, which can list
  series — the view raised on any non movie/episode/season type.
* Hardened the show/mixed/movie/music views against items with no media source
  and unexpected view modes.

0.1.2 — bugfix
--------------
* TV shows and seasons now load their community rating (and cast). Emby only
  returns the rating in the single-item detail response, and the per-item
  enrichment that fetches it was limited to playable rows, so show-list rating
  stars were always empty.

0.1.1 — bugfix
--------------
* Fixed a crash (and missing artwork/metadata) in the TV-show views: items
  with no runtime — series, seasons, artists, albums — carry an empty
  duration, which used to raise `int('')` while formatting it and abort the
  whole view refresh. Movies/episodes were unaffected.

0.1.0 — first release
---------------------
* Emby and Jellyfin backend (`DP_EmbyLibrary.py`) with automatic server-type
  detection via `/System/Info/Public`.
* Authentication: username/password with the access token cached in settings
  (single silent re-auth on 401), or a server API key that overrides it;
  HTTPS with TLS SNI in DNS mode.
* Library browsing: movies, TV shows (seasons/episodes), music
  (artists/albums/tracks) and mixed folders, with a client-side synthesized
  filter menu (All / Unwatched / Recently Added / On Deck / By Genre / By Year
  / By Decade / Search) and server-side artwork resizing.
* Playback: direct streaming and HLS transcoding (h264 / HEVC) with a version
  selector and audio/subtitle track selection (subtitle burn-in when
  transcoding).
* Watch state: resume round-trip, progress reporting, watched / unwatched sync,
  trailers, library refresh from the context menu.
* Automatic per-server theme — green for Emby, lilac for Jellyfin (lilac is the
  fresh-install default) — with a fusion Emby+Jellyfin brand mark.
* Runs on OpenATV 6.4 (Python 2.7) and OpenATV 6.5+/7.x (Python 3).
* Offline test suite with a mock Emby/Jellyfin backend, green on Python 2.7
  and Python 3.

Lineage
-------
DreamFin descends from DreamPlex by DonDavici (2012), ported to Python 3 by
jbleyel and the oe-alliance/OpenViX teams, with parts based on hippojay's
plexbmc. The DreamPlex changelog is preserved upstream at
https://github.com/oe-alliance/DreamPlex.
