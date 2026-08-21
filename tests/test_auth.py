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
		# the key still short-circuits the login, but the user it acts as has
		# to be the configured one - see TestApiKeyUserResolution below
		self.mock.add_json("/Users", [{"Name": "admin", "Id": "adminuser0001"},
									{"Name": "prova", "Id": "provauser0001"}])
		lib = helpers.make_emby_instance(self.mock, username="prova", password="secret", apiKey="my-api-key")

		self.assertTrue(lib.authenticate())
		self.assertEqual(lib.g_accessToken, "my-api-key")
		self.assertEqual(lib.g_userId, "provauser0001")
		self.assertEqual(len(self.mock.requests_for(AUTH_PATH)), 0)


class TestApiKeyUserResolution(unittest.TestCase):
	"""An API key is not user-scoped, so DreamFin has to know WHICH user it
	acts as. Two ways that went wrong, both reported from the fleet:

	  * the provisioning side writes userIdCache along with the key; the
	    server config screen used to wipe it on every save, after which the
	    plugin fell back to asking /Users - admin-only on Emby (403
	    ManageServer for a normal client account) - and died with "Could not
	    resolve a user for the configured API key.".
	  * the fallback returned users[0]. With an admin key that silently opens
	    a stranger's library. Guessing is never acceptable here.
	"""

	def setUp(self):
		self.mock = MockEmby().start()

	def tearDown(self):
		self.mock.stop()

	def test_provisioned_user_id_is_used_without_asking_the_server(self):
		lib = helpers.make_emby_instance(self.mock, username="", password="",
										apiKey="my-api-key", userIdCache="provisioned01")

		self.assertTrue(lib.authenticate())
		self.assertEqual(lib.g_userId, "provisioned01")
		# the whole point: /Users is never reached, so a client key that
		# cannot list users still works
		self.assertEqual(len(self.mock.requests_for("/Users")), 0)

	def test_forced_reauth_keeps_the_provisioned_user_id(self):
		# a 401 retry must not throw away a working configuration: the key
		# comes from the config and re-resolving needs the admin-only endpoint
		lib = helpers.make_emby_instance(self.mock, username="", password="",
										apiKey="my-api-key", userIdCache="provisioned01")

		self.assertTrue(lib.authenticate(force=True))
		self.assertEqual(lib.g_userId, "provisioned01")
		self.assertEqual(len(self.mock.requests_for("/Users")), 0)

	def test_resolution_matches_the_configured_username(self):
		self.mock.add_json("/Users", [{"Name": "admin", "Id": "adminuser0001"},
									{"Name": "client", "Id": "clientuser001"},
									{"Name": "other", "Id": "otheruser0001"}])
		lib = helpers.make_emby_instance(self.mock, username="client", password="",
										apiKey="my-api-key")

		self.assertTrue(lib.authenticate())
		self.assertEqual(lib.g_userId, "clientuser001")

	def test_resolution_is_case_insensitive(self):
		self.mock.add_json("/Users", [{"Name": "Client", "Id": "clientuser001"}])
		lib = helpers.make_emby_instance(self.mock, username="client", password="",
										apiKey="my-api-key")

		self.assertTrue(lib.authenticate())
		self.assertEqual(lib.g_userId, "clientuser001")

	def test_never_falls_back_to_the_first_user(self):
		# the security bug: admin is listed first, but "client" is configured
		self.mock.add_json("/Users", [{"Name": "admin", "Id": "adminuser0001"},
									{"Name": "somebodyelse", "Id": "strangeruser1"}])
		lib = helpers.make_emby_instance(self.mock, username="client", password="",
										apiKey="my-api-key")

		self.assertFalse(lib.authenticate())
		self.assertNotEqual(lib.g_userId, "adminuser0001")
		self.assertFalse(lib.g_userId)
		self.assertIn("does not exist", lib.getLastErrorMessage())

	def test_forbidden_user_list_explains_what_to_do(self):
		# Emby answers 403 "does not have access to ManageServer feature"
		self.mock.add_error("/Users", 403, body="does not have access to ManageServer feature.")
		lib = helpers.make_emby_instance(self.mock, username="client", password="",
										apiKey="my-api-key")

		self.assertFalse(lib.authenticate())
		self.assertIn("user id", lib.getLastErrorMessage())

	def test_single_user_without_a_username_is_unambiguous(self):
		self.mock.add_json("/Users", [{"Name": "onlyone", "Id": "onlyuser00001"}])
		lib = helpers.make_emby_instance(self.mock, username="", password="",
										apiKey="my-api-key")

		self.assertTrue(lib.authenticate())
		self.assertEqual(lib.g_userId, "onlyuser00001")

	def test_several_users_without_a_username_is_an_error_not_a_guess(self):
		self.mock.add_json("/Users", [{"Name": "admin", "Id": "adminuser0001"},
									{"Name": "client", "Id": "clientuser001"}])
		lib = helpers.make_emby_instance(self.mock, username="", password="",
										apiKey="my-api-key")

		self.assertFalse(lib.authenticate())
		self.assertFalse(lib.g_userId)


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
