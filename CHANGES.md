DreamFin — Changelog
====================

DreamFin is a fork of DreamPlex (a Plex client for Enigma2) with the Plex
backend replaced by an Emby/Jellyfin one. See `RELEASENOTES.md` for the full
release notes and `README.md` for lineage and attribution.

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
