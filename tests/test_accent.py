# -*- coding: utf-8 -*-
"""Phase 5: the effective server accent and its highlight colour.

getEffectiveAccent() decides which skin_<accent>.xml loadPlexSkin() loads and
which highlight colour loadSkinParams() applies - green for Emby, lilac for
Jellyfin, lilac as the fresh-install default."""

import re
import unittest

from tests import helpers

helpers.setup_environment()

from Components.config import config  # noqa: E402
import src  # noqa: E402
from src.__common__ import (  # noqa: E402
    getEffectiveAccent, getAccentHighlightColor, ACCENT_HIGHLIGHT)
from src.DP_EmbyLibrary import EmbyLibrary  # noqa: E402


def _lib(serverType):
    sc = src.initServerEntryConfig()
    sc.serverType.value = serverType
    return EmbyLibrary(session=None, serverConfig=sc)


class TestAccent(unittest.TestCase):

    def test_jellyfin_is_lilac(self):
        config.plugins.dreamfin.lastAccent.value = "jellyfin"
        self.assertEqual(getEffectiveAccent(), "jellyfin")
        self.assertEqual(getAccentHighlightColor(), "#aa5cc3")

    def test_emby_is_green(self):
        config.plugins.dreamfin.lastAccent.value = "emby"
        self.assertEqual(getEffectiveAccent(), "emby")
        self.assertEqual(getAccentHighlightColor(), "#52b54b")

    def test_table_covers_both_servers(self):
        self.assertEqual(set(ACCENT_HIGHLIGHT), {"emby", "jellyfin"})
        # enigma2 6-hex colours (no alpha), matching the amber #e69405 format
        for value in ACCENT_HIGHLIGHT.values():
            self.assertTrue(re.match(r"^#[0-9a-fA-F]{6}$", value), value)


class TestAccentHint(unittest.TestCase):
    """detectServerType flags a one-time hint when it flips the accent to a
    server type different from what the skin was loaded with this open."""

    def test_flag_fires_once_on_change_then_stays_clear(self):
        config.plugins.dreamfin.lastAccent.value = "jellyfin"
        lib = _lib("emby")  # g_serverType=emby -> detectServerType short-circuits
        self.assertFalse(lib.accentJustChanged())   # nothing happened yet
        lib.detectServerType()                       # jellyfin -> emby: changes
        self.assertTrue(lib.accentJustChanged())     # hint fires once
        self.assertFalse(lib.accentJustChanged())    # read-and-clear
        lib.detectServerType()                       # emby == emby: no change
        self.assertFalse(lib.accentJustChanged())


if __name__ == "__main__":
    unittest.main()
