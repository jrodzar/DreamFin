DreamFin — Changelog
====================

DreamFin is a fork of DreamPlex (a Plex client for Enigma2) with the Plex
backend replaced by an Emby/Jellyfin one. See `RELEASENOTES.md` for the full
release notes and `README.md` for lineage and attribution.

0.1.24 — improvement and fixes
------------------------------
* **The SDR version also comes first when the HDR one would be transcoded.**
  An HDR version that the server transcodes does not arrive as HDR: Emby turns
  HLG into 8-bit video that keeps its HLG signalling, which some receivers show
  with a green line along the top and others show black. When every HDR
  version of a title would be transcoded with the current quality setting, the
  "Select media to play" list now opens on the SDR version. With a quality that
  lets the HDR version through unchanged, or with direct playback, the order
  stays as before.
* **An audio or subtitle choice no longer carries over to other titles.** The
  track picked with the AUDIO or TEXT buttons was kept for the rest of the
  session and applied by number to every title played after it, so the next
  film could start in another language, with subtitles nobody asked for burned
  in. A choice now belongs to the title it was made for, and finds the same
  track in whichever version of it plays.
* **The AUDIO and TEXT lists show the selected title's tracks, each once.**
  After playing a film they could list that film's tracks instead, and a title
  with several versions listed every track once per version.

0.1.23 — improvement
--------------------
* **The SDR version also comes first when the receiver could show HDR but
  will not.** 0.1.22 put the SDR versions of a title first on receivers that
  cannot show HDR. Now they also come first when HDR is switched off in the
  receiver's video settings, or when the TV does not take HDR - DreamFin reads
  what the TV announces to the receiver. When both can show HDR, the list
  keeps its usual order.

0.1.22 — improvement
--------------------
* **The version list names HDR versions, and receivers without HDR get the SDR
  one first.** When a title comes in more than one version, the "Select media
  to play" list now says which ones are HDR, and of which kind: "[4K / hevc /
  HLG / 4.39 GB]". On a receiver that cannot show HDR, the SDR versions come
  first, so the list opens on one. This matters with Emby: it never converts
  HLG titles to SDR when it transcodes, and a receiver without HDR shows them
  black.

0.1.21 — fixes
--------------
* **The audio button crashed DreamFin during playback on OpenATV 7.6 and
  later** - and so did the option and yellow buttons, which open the same
  screen. Pressing any of them while something played brought up the crash
  window instead of the audio track selection. DreamFin relied on a piece of
  the receiver's own software that OpenATV removed in 2025, so every receiver
  on OpenATV 7.6 or 8.0 was affected; 7.5 and older were not. The audio track
  selection now opens on all of them.
* **The yellow button offered to mark as unseen a film you had only just
  started.** After stopping a film a few seconds in, the yellow button read
  "set 'Unseen'" although the film was still unwatched - and pressing it
  marked it unwatched again, so it took two presses to mark it seen. Emby
  counts every stop as a play, however short; the yellow button now goes by
  whether the film was actually watched, as its marker does.

0.1.20 — fix
------------
* **The letter filter opened its list on an arbitrary title.** The receiver's
  list keeps the cursor's position number when its contents change, so after
  filtering the cursor landed wherever that number fell - usually on the last
  title, once the red button had left it deep in the whole list. A list the
  filter puts on screen now starts at the top, in the library views and in the
  section menu.

0.1.19 — fix
------------
* **After watching something, the yellow button offered the wrong action.**
  When you stop a title and come back to the list, DreamFin asks the server
  for its new state and updates the title's seen marker. The marker changed,
  but the yellow button kept offering what made sense before you pressed
  play: "set 'Seen'" on a title that had just become seen. Moving the cursor
  away and back put it right; now it is right straight away.

0.1.18 — fixes
--------------
* **Marking a title as seen or unseen while the letter filter was on did not
  stick.** Clearing the filter brought the whole list back with the title's old
  marker, although the server had the new state and the yellow button offered
  the opposite action. The marker a title gets when you come back from playing
  it went the same way, and could even land on another title if the list
  changed in the few seconds that refresh takes.
* **Turning the letter filter off now gives the whole list back.** The red
  "turn filter mode off" button only stopped the letter input and left the
  list filtered, and the only way back was typing a space - on OpenATV 7.0, the
  second press of key 1. Key 0, the one most people would try, matched nothing
  and left an empty list reading "no data retrieved". The red button now
  restores the whole list with the cursor on the same title, and a key that
  matches nothing leaves the list as it was, in the library views and in the
  section menu.

0.1.17 — fix
------------
* **Pressing OK after backing out of a list could play the wrong title, or take
  the receiver down.** Going back a level put the right list on screen but left
  DreamFin working with the list you had just left. The cursor position was then
  looked up in the wrong list: if it fitted, a different title started playing
  without a word; if it did not, the receiver's interface crashed. It shows up in
  views that mix films and series, after opening a series and coming back out.
  Marking a title as seen or unseen, and the letter filter, were caught by the
  same mismatch.

0.1.16 — fixes
--------------
* **Saving the server settings could leave the plugin unable to open your
  library.** Every save threw away the cached session, even a save that only
  changed a playback preference. That is harmless when DreamFin can log in
  again on its own, but not when it is set up with an API key: those are not
  tied to a user, so the user id has to be stored alongside them, and once it
  was gone the plugin had no way to work out whose library to open. Only a
  change to the connection or account details drops the cached session now.
* **An API key could open the wrong user's library.** When DreamFin had to work
  out which user an API key belonged to, it took whichever user the server
  listed first. With an administrator key that is somebody else's library, and
  nothing on screen would have said so. It now matches the configured username,
  and says plainly when it cannot rather than picking someone.
* A forced re-login no longer discards a user id that came from the
  configuration, and the errors around all of this now say what to do about it.

0.1.15 — fixes
--------------
* **DreamFin's own entry in the plugin browser was always in English**, however
  well translated it was. Enigma2 reads the plugin list before the plugin has
  had a chance to tell the translation machinery where its catalogue lives, so
  every lookup made at that moment came back untranslated. The plugin now points
  at its own catalogue the first time it translates anything.
* **Three buttons in the library never reached the catalogue at all** — the
  yellow "refresh Library" and, one level down, the red and green settings
  buttons. They went unnoticed for years because their neighbours on the same
  row were translated, so the bar read half in one language and half in the
  other, which looks like a translation nobody has got round to.
* Both reported by the DreamPlex project, which shares this code; the first was
  proved on hardware with DreamFin's own entry visible next to theirs.

0.1.14 — fix
------------
* **The fast-scroll button now actually reads in Spanish.** 0.1.13 marked those
  two labels for translation, but the catalogue entries had never been filled
  in — the entry existed and repeated the English text, so the fix was real and
  invisible at the same time. They read "FastScroll 'Sí'" and "FastScroll 'No'"
  now, matching the wording the settings screen already used.
* The plugin browser shows DreamFin's description untranslated; two of the three
  places that declare it were missing the mark. Fixed.

0.1.13 — fixes
--------------
* **A subtitle check only worked in English.** The test that recognises an
  external forced subtitle track compared a label against fixed English text,
  and that label is translated for the screen — so it could only ever hold in
  English. It carries a flag now instead, which no catalogue can rewrite.
  *(Corrected after release: this entry first claimed the fault stopped forced
  subtitles from switching themselves on in Spanish and French. It did not. That
  branch also needs the player to have downloaded an external forced subtitle
  file, and this plugin's Emby/Jellyfin backend never does — the flag it reads
  is set to false in the one place it is assigned and nowhere else. So no user
  was affected; the fix removes a language dependency that would have bitten the
  day that download is implemented. The impact was asserted from the language
  alone, without checking the second condition.)*
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
