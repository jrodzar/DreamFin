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
from src.__common__ import (  # noqa: E402
    getEffectiveAccent, getAccentHighlightColor, ACCENT_HIGHLIGHT)


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


if __name__ == "__main__":
    unittest.main()
