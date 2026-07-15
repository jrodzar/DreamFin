# -*- coding: utf-8 -*-
"""Bootstrap helpers for the offline DreamFin test harness.

``setup_environment()`` puts the enigma2 stubs and the repository root on
``sys.path`` so the real plugin package (``src``) can be imported in a
plain CPython interpreter. ``make_plex_instance()`` builds a fully wired
``PlexLibrary`` pointing at a :class:`tests.plexmock.MockPMS`.
"""

import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TESTS_DIR)
STUBS_DIR = os.path.join(TESTS_DIR, "stubs")
FIXTURES_DIR = os.path.join(TESTS_DIR, "fixtures")

_initialized = [False]


def setup_environment():
	if _initialized[0]:
		return
	_initialized[0] = True

	# six is a hard dependency of the plugin; provide a micro-fallback so the
	# harness also runs on interpreters without six installed.
	try:
		import six  # noqa: F401
	except ImportError:
		import types
		six = types.ModuleType("six")
		six.PY2 = sys.version_info[0] == 2
		six.PY3 = not six.PY2
		sys.modules["six"] = six

	for path in (STUBS_DIR, REPO_ROOT):
		if path not in sys.path:
			sys.path.insert(0, path)


def fixture(name):
	"""Return the content of a fixture file as text."""
	path = os.path.join(FIXTURES_DIR, name)
	fd = open(path, "rb")
	try:
		return fd.read().decode("utf-8")
	finally:
		fd.close()


def get_config():
	setup_environment()
	from Components.config import config
	import src  # noqa: F401  (creates config.plugins.dreamfin)
	return config


def make_server_config(host="127.0.0.1", port=32400, name="TestServer",
					playbackType="0", localAuth=False, myplexToken="",
					myplexLocalToken="", universalTranscoder=True, **extraValues):
	"""Create a server entry through the real initServerEntryConfig()."""
	setup_environment()
	import src

	serverConfig = src.initServerEntryConfig()
	serverConfig.name.value = name
	serverConfig.connectionType.value = "0"  # IP
	serverConfig.ip.value = [int(x) for x in host.split(".")]
	serverConfig.port.value = port
	serverConfig.playbackType.value = playbackType
	serverConfig.localAuth.value = localAuth
	serverConfig.myplexToken.value = myplexToken
	serverConfig.myplexLocalToken.value = myplexLocalToken
	serverConfig.universalTranscoder.value = universalTranscoder

	for key, value in extraValues.items():
		getattr(serverConfig, key).value = value

	return serverConfig


def make_plex_instance(mock=None, showFilter=True, useCache=False, **serverKwargs):
	"""Instantiate PlexLibrary against a MockPMS (or bare, if mock is None)."""
	setup_environment()
	config = get_config()
	config.plugins.dreamfin.showFilter.value = showFilter
	config.plugins.dreamfin.useCache.value = useCache
	config.plugins.dreamfin.summerizeSections.value = False
	config.plugins.dreamfin.debugMode.value = False

	if mock is not None:
		serverKwargs.setdefault("host", mock.host)
		serverKwargs.setdefault("port", mock.port)

	serverConfig = make_server_config(**serverKwargs)

	from src.DP_PlexLibrary import PlexLibrary
	return PlexLibrary(session=None, serverConfig=serverConfig)


def make_emby_instance(mock=None, showFilter=True, serverType="auto",
					username="prova", password="secret", apiKey="",
					**serverKwargs):
	"""Instantiate EmbyLibrary against a MockEmby (or bare, if mock is None)."""
	setup_environment()
	config = get_config()
	config.plugins.dreamfin.showFilter.value = showFilter
	config.plugins.dreamfin.debugMode.value = False

	if mock is not None:
		serverKwargs.setdefault("host", mock.host)
		serverKwargs.setdefault("port", mock.port)

	serverConfig = make_server_config(**serverKwargs)
	serverConfig.serverType.value = serverType
	serverConfig.username.value = username
	serverConfig.password.value = password
	serverConfig.accessToken.value = apiKey

	from src.DP_EmbyLibrary import EmbyLibrary
	return EmbyLibrary(session=None, serverConfig=serverConfig)


def fixture_json(name):
	"""Return a fixture file parsed as JSON."""
	import json
	return json.loads(fixture(name))


def nat(text):
	"""Native-str form of a unicode literal: utf-8 bytes on py2, str on py3.

	The backend hands the UI native strings (the golden rule), so tests
	comparing against non-ASCII titles must expect exactly that form.
	"""
	if sys.version_info[0] == 2:
		return text.encode("utf-8")
	return text
