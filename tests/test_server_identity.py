# -*- coding: utf-8 -*-
"""Saving the server config must not throw away a working session.

The config screen used to clear accessTokenCache/userIdCache on EVERY save,
including a save that only touched a playback preference. That mattered because
the userId is not always recoverable: an Emby API key is not user-scoped, and
looking one up needs /Users, which is admin-only. A fleet deployment that
provisions key + user id from outside was left with an unusable plugin as soon
as a client opened the server settings and pressed save.

DP_Server cannot be imported here (it pulls enigma2's Components.ConfigList),
so the pure part is unit-tested and the wiring is checked in the source.
"""
from __future__ import absolute_import

import io
import os
import re
import unittest

from tests import helpers

helpers.setup_environment()

from src.__common__ import serverIdentityFingerprint, SERVER_IDENTITY_FIELDS  # noqa: E402

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")


class TestServerIdentityFingerprint(unittest.TestCase):

	def _entry(self, **values):
		return helpers.make_server_config(**values)

	def test_same_config_compares_equal(self):
		entry = self._entry()
		self.assertEqual(serverIdentityFingerprint(entry), serverIdentityFingerprint(entry))

	def test_playback_preferences_do_not_change_it(self):
		entry = self._entry()
		before = serverIdentityFingerprint(entry)

		entry.playbackType.value = "1"
		entry.universalTranscoder.value = False
		entry.transcodeVideoCodec.value = "hevc"
		entry.subtitlesLanguage.value = "es"

		self.assertEqual(serverIdentityFingerprint(entry), before)

	def test_account_and_connection_changes_do_change_it(self):
		for field, value in (("username", "someoneelse"), ("password", "another"),
							("accessToken", "a-different-key"), ("dns", "other.example.invalid"),
							("port", 9999), ("serverType", "jellyfin"), ("connectionType", "1")):
			entry = self._entry()
			before = serverIdentityFingerprint(entry)
			getattr(entry, field).value = value
			self.assertNotEqual(serverIdentityFingerprint(entry), before,
							"changing %s must invalidate the cached session" % field)

	def test_the_caches_themselves_are_not_part_of_it(self):
		# otherwise writing the cache would look like an identity change
		self.assertNotIn("accessTokenCache", SERVER_IDENTITY_FIELDS)
		self.assertNotIn("userIdCache", SERVER_IDENTITY_FIELDS)

	def test_missing_attribute_does_not_raise(self):
		class Partial(object):
			pass
		self.assertEqual(len(serverIdentityFingerprint(Partial())), len(SERVER_IDENTITY_FIELDS))


class TestKeySaveWiring(unittest.TestCase):
	"""Source-level guard: keySave must not clear the caches unconditionally."""

	def _key_save_body(self):
		with io.open(os.path.join(SRC, "DP_Server.py"), encoding="utf-8") as fd:
			source = fd.read()
		match = re.search(r"\n\tdef keySave\(self\):\n(.*?)\n\tdef ", source, re.S)
		self.assertIsNotNone(match, "keySave not found in DP_Server.py")
		return match.group(1)

	def test_cache_reset_is_guarded(self):
		body = self._key_save_body()
		self.assertIn("userIdCache", body, "keySave no longer touches the cache at all")

		for line in body.splitlines():
			stripped = line.strip()
			if stripped.startswith("#") or "Cache.value" not in stripped:
				continue
			# every reset has to sit deeper than the def's own body level
			indent = len(line) - len(line.lstrip("\t"))
			self.assertGreater(indent, 2,
							"cache reset is unconditional in keySave: %r" % stripped)

	def test_it_compares_the_identity_fingerprint(self):
		body = self._key_save_body()
		self.assertIn("serverIdentityFingerprint", body)


if __name__ == "__main__":
	unittest.main()
