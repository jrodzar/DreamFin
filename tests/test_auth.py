# -*- coding: utf-8 -*-
"""Authentication and server type detection against the Emby mock."""

import unittest

from tests import helpers
from tests.embymock import MockEmby

helpers.setup_environment()

AUTH_PATH = "/Users/AuthenticateByName"
EMBY_UID = "user0000000000000000000000000001"


def wire_auth(mock, fixtureName="auth_ok_emby.json", infoFixture="system_info_public_emby.json"):
	mock.add_json(AUTH_PATH, helpers.fixture_json(fixtureName), method="POST")
	mock.add_json("/System/Info/Public", helpers.fixture_json(infoFixture))


class TestLogin(unittest.TestCase):

	def setUp(self):
		self.mock = MockEmby().start()

	def tearDown(self):
		self.mock.stop()

	def test_login_posts_credentials_with_client_headers(self):
		wire_auth(self.mock)
		lib = helpers.make_emby_instance(self.mock, username="prova", password="topsecret")

		self.assertTrue(lib.authenticate())
		self.assertEqual(lib.g_accessToken, "mock-access-token-emby")
		self.assertEqual(lib.g_userId, EMBY_UID)

		requests = self.mock.requests_for(AUTH_PATH)
		self.assertEqual(len(requests), 1)
		request = requests[0]
		self.assertEqual(request["method"], "POST")
		self.assertEqual(request["body"], {"Username": "prova", "Pw": "topsecret"})
		self.assertIn("application/json", request["headers"].get("content-type", ""))

		authHeader = request["headers"].get("x-emby-authorization", "")
		self.assertIn('Client="DreamFin"', authHeader)
		self.assertIn('DeviceId="', authHeader)
		self.assertIn('Version="', authHeader)
		self.assertNotIn("Token=", authHeader)  # no token yet at login time
		# both header spellings go out (Jellyfin 10.8+ documents Authorization)
		self.assertEqual(request["headers"].get("authorization", ""), authHeader)

	def test_login_fills_the_token_cache(self):
		wire_auth(self.mock)
		lib = helpers.make_emby_instance(self.mock)

		self.assertTrue(lib.authenticate())
		self.assertEqual(lib.g_serverConfig.accessTokenCache.value, "mock-access-token-emby")
		self.assertEqual(lib.g_serverConfig.userIdCache.value, EMBY_UID)

	def test_cached_token_skips_the_login_roundtrip(self):
		lib = helpers.make_emby_instance(self.mock)
		lib.g_serverConfig.accessTokenCache.value = "cached-token"
		lib.g_serverConfig.userIdCache.value = EMBY_UID

		self.assertTrue(lib.authenticate())
		self.assertEqual(lib.g_accessToken, "cached-token")
		self.assertEqual(len(self.mock.requests_for(AUTH_PATH)), 0)

	def test_requests_carry_the_token_headers(self):
		wire_auth(self.mock)
		self.mock.add_json("/Ping", {"ok": True})
		lib = helpers.make_emby_instance(self.mock)

		self.assertEqual(lib.getJson(lib.getContentUrl("/Ping")), {"ok": True})

		request = self.mock.requests_for("/Ping")[0]
		self.assertEqual(request["headers"].get("x-emby-token"), "mock-access-token-emby")
		self.assertIn('Token="mock-access-token-emby"', request["headers"].get("x-emby-authorization", ""))

	def test_stale_token_reauthenticates_exactly_once(self):
		wire_auth(self.mock)
		self.mock.add_json("/Ping", {"ok": True})
		self.mock.add_error("/Ping", 401, times=1)

		lib = helpers.make_emby_instance(self.mock)
		lib.g_serverConfig.accessTokenCache.value = "stale-token"
		lib.g_serverConfig.userIdCache.value = EMBY_UID

		self.assertEqual(lib.getJson(lib.getContentUrl("/Ping")), {"ok": True})

		self.assertEqual(len(self.mock.requests_for(AUTH_PATH)), 1)
		pings = self.mock.requests_for("/Ping")
		self.assertEqual(len(pings), 2)
		self.assertEqual(pings[0]["headers"].get("x-emby-token"), "stale-token")
		self.assertEqual(pings[1]["headers"].get("x-emby-token"), "mock-access-token-emby")

	def test_persistent_401_gives_up_without_looping(self):
		wire_auth(self.mock)
		self.mock.add_error("/Ping", 401)  # permanent

		lib = helpers.make_emby_instance(self.mock)

		self.assertIsNone(lib.getJson(lib.getContentUrl("/Ping")))
		# initial auth + one re-auth, never more
		self.assertLessEqual(len(self.mock.requests_for(AUTH_PATH)), 2)

	def test_wrong_password_sets_a_clean_error(self):
		self.mock.add_error(AUTH_PATH, 401, method="POST")
		lib = helpers.make_emby_instance(self.mock, password="wrong")

		self.assertFalse(lib.authenticate())
		self.assertTrue(lib.getLastErrorMessage())
		self.assertIn("wrong username or password", lib.getLastErrorMessage())

	def test_no_credentials_fails_cleanly(self):
		lib = helpers.make_emby_instance(self.mock, username="", password="")

		self.assertFalse(lib.authenticate())
		self.assertTrue(lib.getLastErrorMessage())

	def test_dead_server_returns_falsy_without_raising(self):
		lib = helpers.make_emby_instance(host="127.0.0.1", port=1)

		self.assertFalse(lib.authenticate())
		self.assertTrue(lib.getLastErrorMessage())
		self.assertIsNone(lib.getJson("http://127.0.0.1:1/Ping"))


class TestApiKey(unittest.TestCase):

	def setUp(self):
		self.mock = MockEmby().start()

	def tearDown(self):
		self.mock.stop()

	def test_api_key_skips_login_and_resolves_a_user(self):
		self.mock.add_json("/Users", [{"Name": "admin", "Id": "adminuser0001"}])
		self.mock.add_json("/Ping", {"ok": True})

		lib = helpers.make_emby_instance(self.mock, username="", password="", apiKey="my-api-key")

		self.assertTrue(lib.authenticate())
		self.assertEqual(lib.g_accessToken, "my-api-key")
		self.assertEqual(lib.g_userId, "adminuser0001")
		self.assertEqual(len(self.mock.requests_for(AUTH_PATH)), 0)

		lib.getJson(lib.getContentUrl("/Ping"))
		request = self.mock.requests_for("/Ping")[0]
		self.assertEqual(request["headers"].get("x-emby-token"), "my-api-key")

	def test_api_key_wins_over_credentials(self):
		self.mock.add_json("/Users", [{"Name": "admin", "Id": "adminuser0001"}])
		lib = helpers.make_emby_instance(self.mock, username="prova", password="secret", apiKey="my-api-key")

		self.assertTrue(lib.authenticate())
		self.assertEqual(lib.g_accessToken, "my-api-key")
		self.assertEqual(len(self.mock.requests_for(AUTH_PATH)), 0)


class TestDetectServerType(unittest.TestCase):

	def setUp(self):
		self.mock = MockEmby().start()

	def tearDown(self):
		self.mock.stop()

	def test_detects_emby(self):
		self.mock.add_json("/System/Info/Public", helpers.fixture_json("system_info_public_emby.json"))
		lib = helpers.make_emby_instance(self.mock)

		self.assertEqual(lib.detectServerType(), "emby")
		config = helpers.get_config()
		self.assertEqual(config.plugins.dreamfin.lastAccent.value, "emby")

	def test_detects_jellyfin(self):
		self.mock.add_json("/System/Info/Public", helpers.fixture_json("system_info_public_jellyfin.json"))
		lib = helpers.make_emby_instance(self.mock)

		self.assertEqual(lib.detectServerType(), "jellyfin")
		config = helpers.get_config()
		self.assertEqual(config.plugins.dreamfin.lastAccent.value, "jellyfin")

	def test_manual_server_type_needs_no_request(self):
		lib = helpers.make_emby_instance(self.mock, serverType="emby")

		self.assertEqual(lib.detectServerType(), "emby")
		self.assertEqual(len(self.mock.requests), 0)


if __name__ == "__main__":
	unittest.main()
