DreamFin — Changelog
====================

DreamFin is a fork of DreamPlex (a Plex client for Enigma2) with the Plex
backend replaced by an Emby/Jellyfin one. See `RELEASENOTES.md` for the full
release notes and `README.md` for lineage and attribution.

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
