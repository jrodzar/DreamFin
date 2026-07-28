DreamFin 0.1.14 — release notes
===============================

**DreamFin** is an Emby/Jellyfin client for Enigma2 forked from DreamPlex. It
reuses the DreamPlex user interface and replaces the Plex backend with an
Emby/Jellyfin one. See `README.md` for setup, lineage and attribution.

New in 0.1.14
-------------

- **The fast-scroll button reads in Spanish now.** The previous release taught
  that label to be translatable, and it was — but nobody had ever written the
  Spanish for it. The catalogue held the entry with the English text copied into
  it, which looks identical to a missing translation once it reaches the screen.
  It now says "FastScroll 'Sí'" and "FastScroll 'No'", matching the wording the
  settings screen was already using.

- **DreamFin's own description in the plugin browser** is translatable too. Of
  the three places that declare it, only one was marked.

A short one, and a lesson in disguise: a translation that exists is not a
translation that happened. Checking one properly means asking the packaged
catalogue what it hands back, not searching the source file for the phrase.

DreamFin 0.1.13 — release notes
===============================

**DreamFin** is an Emby/Jellyfin client for Enigma2 forked from DreamPlex. It
reuses the DreamPlex user interface and replaces the Plex backend with an
Emby/Jellyfin one. See `README.md` for setup, lineage and attribution.

New in 0.1.13
-------------

- **The blue and green buttons no longer revert to English when pressed.**
  Those labels are written in two different places — once when the screen is
  drawn, once when you press the button — and only the first was translated.
  The label appeared in your language and switched back to English on the first
  press. 0.1.12 fixed the drawing half of the blue one; this fixes the rest.

- **A subtitle check no longer depends on the language.** The test that
  recognises an external forced-subtitle track compared a label against fixed
  English text — and that label is translated for the screen, so the test could
  only ever hold in English. It carries a flag now, which no translation can
  rewrite.

Both came from the DreamPlex project, DreamFin's upstream, which shares this
code.

### A correction to this entry

These notes first said the subtitle fault stopped forced subtitles from
switching themselves on in Spanish and French, and called it the more serious of
the two. **That was wrong, and no user was affected.**

Reaching that code also requires the player to have downloaded an external
forced-subtitle file, and this plugin's Emby/Jellyfin backend never does that —
it is Plex machinery that was not carried over. The flag it checks is set to
false in the single place it is assigned, and appears nowhere else in the
source, so the branch cannot run at all, in any language.

The fix is still worth having: it removes a dependency on the translation
catalogue that would have caused exactly the described fault the day that
download is implemented. What was wrong was the claim about its impact, which
was inferred from the language alone without checking the second condition the
code requires. Reported by the DreamPlex project, and confirmed here.

DreamFin 0.1.12 — release notes
===============================

**DreamFin** is an Emby/Jellyfin client for Enigma2 forked from DreamPlex. It
reuses the DreamPlex user interface and replaces the Plex backend with an
Emby/Jellyfin one. See `README.md` for setup, lineage and attribution.

New in 0.1.12
-------------

- **The blue button in the library speaks your language now.** Its label
  pasted the current playback mode into the sentence *before* looking the
  sentence up, so the text it searched for changed with the mode and matched
  nothing in the language files. A finished Spanish translation of that label
  has shipped in every release since the fork without ever being shown.

  The clue was on screen the whole time and easy to walk past: the button read
  `playback mode 'Transcodificado'` — an English label wrapped around a
  translated value, because the mode names are listed separately and were
  being found correctly.

- **The rest of the plugin was swept for the same mistake.** Eleven places ask
  for something other than a fixed phrase to be translated; only the one above
  was actually broken. The others pass a library name that came from your
  server, where translation does nothing in either direction. The page counter
  was politely asking for "9" and "1/9" to be translated, and has stopped.

Second release in a row fixing a translation that was written years ago and
never reached the screen. This one came out of a remark from the DreamPlex
project, DreamFin's upstream, that theirs had the same fault in two places —
so we went looking for our second, and there it was.

DreamFin 0.1.11 — release notes
===============================

**DreamFin** is an Emby/Jellyfin client for Enigma2 forked from DreamPlex. It
reuses the DreamPlex user interface and replaces the Plex backend with an
Emby/Jellyfin one. See `README.md` for setup, lineage and attribution.

New in 0.1.11
-------------

- **The Wake on Lan message says what actually happens.** It used to promise
  that a spinner would run while the plugin waited for your server to boot.
  There is no spinner on that screen, and even if there were, the wait blocked
  the very thing that would have animated it. The wording now describes the
  wait itself — and mentions what 0.1.10 made true, that the receiver stays
  usable throughout.

- **That message can be translated at last.** The delay in seconds was pasted
  into the middle of the sentence *before* the plugin looked the sentence up,
  so the text it searched for changed with your settings and never matched
  anything in the language files. A finished Spanish translation has shipped in
  every release since the fork without ever appearing on screen. It does now.
  Other languages fall back to English for this one message, as they already
  did in practice.

A small release, and an honest one: it fixes what the plugin *said*, not what
it did.

DreamFin 0.1.10 — release notes
===============================

**DreamFin** is an Emby/Jellyfin client for Enigma2 forked from DreamPlex. It
reuses the DreamPlex user interface and replaces the Plex backend with an
Emby/Jellyfin one. See `README.md` for setup, lineage and attribution.

New in 0.1.10
-------------

- **The remote works while a film is resuming.** Picking up where you left off
  used to lock the interface until it was done: the screen did not move and
  buttons did nothing. They were not being lost — there was simply nobody
  reading them, because the wait was running on the one thread the receiver
  uses for everything. On images where the receiver cannot report a playback
  position it was worse: nothing came back at all, and the interface stayed
  frozen until the receiver gave up on the plugin. The wait is a timer now.

- **Waking a server no longer freezes the box.** If your server is off and
  DreamFin offers to wake it, it waits for the machine to boot — a minute by
  default, up to three. That wait used to stop the whole interface for its full
  length. It no longer does. (The message still promises a spinner during the
  wait. There is no spinner, and there never was; the wording is left for
  another release.)

Both faults came from the DreamPlex project, DreamFin's upstream, which shares
this player code and found them while looking into a report sent the other way.
Checked on real hardware: with the fix in place, a button pressed while a film
was still resuming was accepted 1.4 seconds before the resume finished — which
the old code made impossible.

DreamFin 0.1.9 — release notes
==============================

**DreamFin** is an Emby/Jellyfin client for Enigma2 forked from DreamPlex. It
reuses the DreamPlex user interface and replaces the Plex backend with an
Emby/Jellyfin one. See `README.md` for setup, lineage and attribution.

New in 0.1.9
------------

- **Resuming no longer gives up quietly.** If the receiver could not tell the
  plugin how long the media was, the routine that jumps to your saved point
  raised on a value that had never been set. The error was caught by the guard
  around the whole routine, so nothing was shown and nothing was logged beyond
  a warning — the film simply started from the beginning. It survives that
  answer now.

- The log line for a jump printed the name of an internal function instead of
  the position being sought. Only visible with debug logging on.

Small release: one latent fault and one log line. It exists because the
DreamPlex project — DreamFin's upstream, which shares this player code — was
told about the two faults fixed in 0.1.8, confirmed them, fixed them on their
side, and reported four findings back. This is one of them, plus one more that
turned up while checking theirs.

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
