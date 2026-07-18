DreamFin — Emby/Jellyfin client for Enigma2
===========================================

DreamFin is a media client for Enigma2 receivers (OpenATV and friends) that
browses and plays your **Emby** and **Jellyfin** libraries on the TV. It is a
fork of [DreamPlex](https://github.com/oe-alliance/DreamPlex) — the Plex
client for Enigma2 — with the Plex backend replaced by an Emby/Jellyfin one,
reusing the mature DreamPlex user interface almost unchanged.

Runs on **both** OpenATV 6.4 (Python 2.7) and OpenATV 6.5+/7.x (Python 3).

The plugin installs alongside DreamPlex — it is a separate package
(`enigma2-plugin-extensions-dreamfin`) with its own settings, skins and menu
entry, so you can keep both.

What it does
------------

* **Emby and Jellyfin, auto-detected.** Add a server by host name or IP; the
  plugin queries `/System/Info/Public` and figures out whether it is talking
  to Emby or Jellyfin. Each server type gets its own accent colour (see
  *Automatic theme* below).
* **Authentication that fits a set-top box.** Username/password login with the
  access token cached in the settings (a single silent re-auth on a 401), or
  paste a **server API key** that wins over everything else. Connections go
  over HTTPS on port 443/8920 with the host name kept for TLS SNI, so
  name-based reverse proxies work.
* **Full library browsing.** Movies, TV shows (seasons → episodes), music
  (artists → albums → tracks) and mixed folders. When a section has no
  server-provided sub-menu the plugin **synthesizes the filter menu on the
  client**:
  * Movies: All, Unwatched, Recently Added, Recently Released, On Deck,
    By Genre, By Year, By Decade, Search
  * Shows: All, Unwatched, Recently Added, On Deck, By Genre, By Year, Search
  * Music: All Artists, Recently Added, By Genre, Search

  Posters and backdrops are fetched at the size the skin needs (server-side
  resize), unwatched counts are shown, and genre/year/decade drill-downs and
  search hit the matching Emby/Jellyfin endpoints.
* **Direct play and transcoding.** Stream the original file, or let the server
  transcode to an HLS stream (h264 or, where the box decodes it, HEVC) when
  the source is too heavy. A version selector appears when an item has more
  than one media source, audio and subtitle tracks can be picked (with
  burn-in for image subtitles when transcoding), and trailers play where the
  server exposes them.
* **Watch state that round-trips.** Playback position is reported back to the
  server and the *resume* point comes back the next time you open the item;
  watched / unwatched toggles sync both ways; a library refresh is available
  from the context menu.
* **Automatic theme.** The whole UI recolours to match the server you last
  entered — **green for Emby, lilac for Jellyfin** (lilac is the fresh-install
  default). A one-line hint tells you the colours will follow on the next
  open. The brand mark is a fusion of the two ecosystems: the Jellyfin rounded
  triangle with the Emby play glyph, in a green→lilac gradient.

Installation
------------

Build the package (any OS — only Python is needed, no cross-toolchain):

    py -3 tools/build_ipk.py        # Windows
    python3 tools/build_ipk.py      # Linux/macOS

Copy the resulting IPK to the receiver and install it there:

    scp dist/enigma2-plugin-extensions-dreamfin_*.ipk root@<box-ip>:/tmp/
    ssh root@<box-ip>
    opkg install /tmp/enigma2-plugin-extensions-dreamfin_*.ipk

Then restart the Enigma2 GUI. Works on OpenATV 6.4 (Python 2.7) and
OpenATV 6.5/7.x (Python 3). The plugin needs the `six` module, which both
image generations ship by default; if it is ever missing:
`opkg install python-six` (6.4) or `opkg install python3-six` (6.5+).

Setting up a server
-------------------

Open **DreamFin** from the main menu → *System* → add a server entry:

* **Server type** — leave on *auto* to detect Emby vs Jellyfin, or force one.
* **Address / port** — the host name or IP of your server, and its port
  (usually `443` for a reverse-proxied HTTPS server, `8096`/`8920` otherwise).
* **Username / password** — a normal server user; the token is cached after
  the first login.
* **API key (optional)** — a server API key, used instead of username/password
  when present.

Note on *Direct Local* playback: Emby/Jellyfin hide `MediaSources[].Path` from
non-admin users, so a non-admin login cannot resolve a local file path. Use an
**admin API key** if you rely on Direct Local; otherwise use *Streamed* or
*Transcoded*.

Troubleshooting logs: enable `debugMode` + `writeDebugFile` in the plugin
settings to write `dreamplex.log` under the plugin log folder (default
`/tmp/` if `/hdd` is not mounted); GUI crashlogs live in `/home/root/logs/`.

Development
-----------

An offline test suite is included — no receiver and no server needed, a mock
Emby/Jellyfin backend answers the requests:

    py -3 -m unittest discover -s tests          # Python 3
    <py27>/python -m unittest discover -s tests  # Python 2.7 portable
    py -3 tools/run_checks.py                     # byte-compile + py2 gate + skin-path lint
    py -3 tools/build_ipk.py                      # build the IPK into dist/

Both suites are expected green on Python 3 and Python 2.7 before every commit.

Skins
-----

The bundled skins descend from the DreamPlex skinning work — big thanks to the
skinners:

* Blockbuster — http://www.vuplus-support.org/wbb3/index.php?page=Thread&threadID=69568
* YouPlex-Blue/Green/Purple/Red, Plex_Experience — https://github.com/OpenViX/DreamPlexSkins

License and attribution
-----------------------

GPL-2.0-or-later (see `src/LICENSE.txt`), like the original. This is a
derivative work; the files keep their original `DP_*` names and copyright
headers on purpose, both to stay diffable against the upstream DreamPlex tree
and to honour the GPL's authorship requirements.

Lineage:

* **DreamPlex** was written by **DonDavici** (2012), ported to Python 3 and
  maintained by **jbleyel** and the **oe-alliance** / **OpenViX** teams, with
  parts based on **hippojay**'s plexbmc.
* **DreamFin** replaces the Plex backend with an Emby/Jellyfin one and adds the
  automatic per-server theme, keeping the DreamPlex UI. The Emby/Jellyfin
  backend, the offline test harness, the automatic theme and logos, and the
  on-receiver verification were implemented by **Claude** (Anthropic),
  directed by **jrodzar**. Every commit carries the corresponding
  `Co-Authored-By` trailer.

Statement of changes (relative to DreamPlex)
--------------------------------------------

* Removed the Plex backend (`DP_PlexLibrary.py`), the plex.tv account plumbing,
  the Companion/remote-agent and home-users code, and the autotools/GDM build
  scaffolding.
* Added `DP_EmbyLibrary.py`: a JSON transport (redirects, bounded timeouts,
  TLS with SNI in DNS mode), Emby/Jellyfin authentication and server-type
  detection, section and item parsers, a client-side synthesized filter menu,
  transcoding with a quality table and stream selection, and playback
  reporting / resume / watched state.
* Renamed the package, config namespace, gettext domain, on-disk paths and
  skin variant files from `dreamplex` to `dreamfin`.
* Added the automatic per-server accent theme (green Emby / lilac Jellyfin) and
  the fusion brand mark, plus the tooling that generates them.
* Refreshed the translation catalogs so the strings are server-neutral, and
  neutralised the Plex-specific wording that remained.
