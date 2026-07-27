DreamFin — Changelog
====================

DreamFin is a fork of DreamPlex (a Plex client for Enigma2) with the Plex
backend replaced by an Emby/Jellyfin one. See `RELEASENOTES.md` for the full
release notes and `README.md` for lineage and attribution.

0.1.13 — fixes
--------------
* **Forced subtitles did not switch themselves on unless the plugin was in
  English.** The check that spots an external forced subtitle track compared a
  label against fixed English text — but that label is translated for the
  screen, so in Spanish and French it never matched and the track was left off.
  It worked in English, which is where testing tends to happen.
* **Two button labels fell back to English the moment you pressed them.** The
  blue playback-mode button and the green fast-scroll button are written twice:
  once when the screen is drawn and once when the button is pressed. Only the
  first was translated — so the label came up in your language and reverted on
  the first press. 0.1.12 fixed half of the blue one.
* Both were reported by the DreamPlex project, which shares this code.

0.1.12 — fix
------------
* **The blue button in the library was stuck in English.** Its label pasted the
  current playback mode into the middle of the text before looking the text up,
  so what it searched for changed with the mode and never matched a catalogue
  entry — the same fault fixed for the Wake on Lan dialog in 0.1.11. A finished
  Spanish translation of the label has shipped since the fork without ever
  appearing. The giveaway was on screen all along: it read `playback mode
  'Transcodificado'`, English wrapper around a translated value, because the
  mode names are listed separately.
* Swept the rest of the source for the same mistake. Eleven places pass
  something other than a fixed string for translation, but only that one was a
  fault; the others hand over a library name from the server, which does nothing
  either way. The page counter was asking for "9" and "1/9" to be translated
  and no longer does.

0.1.11 — fix
------------
* **The Wake on Lan dialog described something that never happened.** It said
  the spinner would run while the plugin waited for the server; it could not,
  because the spinner is driven by the same loop the wait used to block — and
  there is no spinner in that screen at all. It now says what really happens,
  including the part that only became true in 0.1.10: the receiver stays usable
  while it waits.
* **That message is translatable for the first time.** It was assembled by
  pasting the delay into the middle of the text before looking it up, so the
  lookup key changed with the number and never matched a catalogue entry — the
  Spanish translation shipped in every release since the fork has never once
  been displayed. It is one entry now, and the dialog appears in Spanish.

0.1.10 — fixes
--------------
* **The receiver stopped responding while a film was resuming.** Jumping to the
  saved point was driven by a wait loop running on the same single thread that
  draws the screen and reads the remote, so for as long as the resume took
  nothing answered — the presses were not lost, there was nobody reading them.
  And when the receiver could not report a playback position, which depends on
  the image rather than on the stream, that loop had no way out at all: the
  interface stayed frozen until the receiver's own watchdog killed it. The wait
  is now a timer, and the interface keeps running through it.
* **Waking a server with Wake on Lan froze the box for the whole delay.** The
  plugin slept on the thread that runs the interface while it waited for the
  server to come up — a minute by default, up to three. Same fix, same result:
  the wait no longer blocks anything. (The dialog still says a spinner will run
  during the wait; it does not, and never did.)
* Both faults were reported by the DreamPlex project, which shares this player
  code. Verified on hardware: with the fix in, a key pressed while a film was
  still resuming was accepted 1.4 seconds before the resume finished.

0.1.9 — fix
-----------
* **Resuming could die without a word.** When the player asked the service for
  the media length and got no answer, a later log line read a variable that had
  never been set; the error was swallowed by the catch around the whole routine
  and the film started from the beginning instead of where it was left. Same
  shape of silent failure as the two faults in 0.1.8, found by the DreamPlex
  side reporting back after fixing those there.
* The log line that reported a seek printed the name of a built-in function
  instead of the position being sought.

0.1.8 — fixes
-------------
* **Playback progress was never reported.** The ticker that tells the server
  where you are was built but never started: starting it was left to events
  that never arrive on a streamed or transcoded playback. Nothing reached the
  server for a whole film — no position on the dashboard, no resume point —
  and the playback clock added in 0.1.7 was idle the entire time. It now
  starts where it is built, and reports every five seconds.
* **Jumping to a minute did nothing while transcoding.** BLUE (or RED) opens
  the "Minutes" dialog, you type a minute, press OK — and playback carried on
  as if you had not. The jump asked the decoder where it was first and gave up
  when it could not say, which during a transcoded stream is always. It now
  seeks straight away, refuses to land past the end of the film, and copes
  with the dialog being cancelled.
* Verified on real hardware against both Emby and Jellyfin.

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
