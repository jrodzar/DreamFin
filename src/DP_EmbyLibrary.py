# -*- coding: utf-8 -*-
"""
DreamFin - Emby/Jellyfin backend

Derived from DreamPlex (DP_PlexLibrary.py) by DonDavici, 2012 and
jbleyel 2021 - https://github.com/oe-alliance/DreamPlex

This module replaces the Plex backend with an Emby/Jellyfin one while
producing exactly the same data shapes the inherited UI consumes:
menu 4-tuples, list 5-tuples and string-typed entryData dictionaries.

DreamFin is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 2 of the License, or
(at your option) any later version.

DreamFin is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
"""
#===============================================================================
# IMPORT
#===============================================================================
import json
import socket
import ssl
import sys
import time
import traceback

from six import PY2

if PY2:
	from httplib import HTTPConnection, HTTPSConnection
	from urlparse import urljoin, urlparse
	_textType = unicode  # noqa: F821
else:
	from http.client import HTTPConnection, HTTPSConnection
	from urllib.parse import urljoin, urlparse
	_textType = str

from Components.config import config

from .__common__ import printl2 as printl, getUUID, getVersion, IMAGE_SIZE_PLACEHOLDER, isRecentlyAdded, newPlaybackId
from .__plugin__ import Plugin, getPlugin
from .__init__ import _  # _ is translation

#===============================================================================
# CONSTANTS
#===============================================================================

# fields requested with every item LISTING. Deliberately without People:
# Jellyfin 10.11 spends ~60ms per item resolving cast/crew, which turns a
# 200-item page into a 13s answer (measured against the real server);
# without People the same page takes 0.36s. Lists therefore show no
# director/cast; the per-item detail fetch below carries them instead.
DEFAULT_ITEM_FIELDS = ("Overview,Genres,Studios,MediaSources,"
					"DateCreated,DateLastMediaAdded,PremiereDate,ProductionYear,"
					"RecursiveItemCount,ChildCount,Taglines")

# fields for single-item detail requests (selection refresh, pre-playback)
DETAIL_ITEM_FIELDS = DEFAULT_ITEM_FIELDS + ",People"

# ports that imply TLS when no scheme information exists in the config
HTTPS_PORTS = (443, 8920)

# Emby item Type -> the type literals the inherited UI switches on
ITEM_TYPE_MAP = {
	"Movie": "movie",
	"Series": "show",
	"Season": "season",
	"Episode": "episode",
	"MusicArtist": "artist",
	"MusicAlbum": "album",
	"Audio": "track",
	"Video": "clip",
	"MusicVideo": "clip",
	"BoxSet": "Folder",
	"Folder": "Folder",
	"CollectionFolder": "Folder",
}

REQUEST_TIMEOUT = 8
# item pages are heavy (MediaSources for up to 200 items) and a cold
# server can need well over 8s for the very first page; the fetch runs
# in a worker thread, so a larger cap does not freeze the GUI
PAGED_REQUEST_TIMEOUT = 20
CONNECT_ATTEMPTS = 2
MAX_REDIRECTS = 3

# config.uniQuality choice -> (MaxWidth, MaxHeight, VideoBitrate bps) for the
# transcoder. Labels in __init__ match these (e.g. "1920x1080, 10mbps").
UNI_QUALITY_TABLE = {
	"0": (420, 240, 320000),
	"1": (576, 320, 720000),
	"2": (720, 480, 1500000),
	"3": (1024, 768, 2000000),
	"4": (1280, 720, 3000000),
	"5": (1280, 720, 4000000),
	"6": (1920, 1080, 8000000),
	"7": (1920, 1080, 10000000),
	"8": (1920, 1080, 12000000),
	"9": (1920, 1080, 20000000),
}
DEFAULT_UNI_QUALITY = (1024, 768, 2000000)  # matches uniQuality default "3"

# The same ladder for hevc output would waste it. hevc carries the same
# picture in clearly less bitrate, so reusing the h264 steps spends the whole
# gain on picture quality and leaves the frame where it was - 3 Mbps would
# still ask for 720p when it comfortably holds 1080p. This ladder keeps the
# h264 bitrates and buys a bigger frame at every step instead, and the top
# steps go past the 1080p ceiling that only h264 needs.
UNI_QUALITY_HEVC_TABLE = {
	"0": (576, 320, 320000),
	"1": (720, 480, 720000),
	"2": (1280, 720, 1500000),
	"3": (1280, 720, 2000000),
	"4": (1920, 1080, 3000000),
	"5": (1920, 1080, 4000000),
	"6": (2560, 1440, 8000000),
	"7": (3840, 2160, 10000000),
}
# it stops at 7 on purpose: measured against real Emby and Jellyfin servers,
# 12 and 20 Mbps deliver exactly what 10 does (the frame is already the source's
# own), so the extra steps were three ways to ask for the same picture.
DEFAULT_UNI_QUALITY_HEVC = (1280, 720, 2000000)  # matches uniQualityHevc default "3"
# the ladder briefly reached 9 before 8 and 9 were dropped; a server entry saved
# back then is rescued to the top step instead of falling back to the default
FORMER_UNI_QUALITY_HEVC_TOP = 9

# ticks are 100 ns units: 10**4 ticks per millisecond
TICKS_PER_MS = 10000


def ticksToMs(ticks):
	"""RunTimeTicks/PositionTicks (100 ns units) -> integer milliseconds."""
	return int(ticks) // TICKS_PER_MS


def msToTicks(ms):
	"""Integer milliseconds -> ticks (100 ns units)."""
	return int(ms) * TICKS_PER_MS


def jsonToStr(value, default=""):
	"""JSON scalar -> native str, utf-8 encoded on Python 2.

	The inherited UI concatenates and int()s entryData values, so every
	value crossing the JSON boundary must become a plain str exactly
	here (py2 str() would ascii-encode unicode and blow up on the first
	accented title).
	"""
	if value is None:
		return default
	if PY2 and isinstance(value, _textType):
		return value.encode("utf-8")
	return str(value)


#===============================================================================
#
#===============================================================================


class EmbyLibrary(object):
	"""Backend for Emby and Jellyfin servers.

	Plain object (not a Screen) with the same construction signature and
	method surface as the PlexLibrary it replaces. All network I/O is
	blocking and therefore must be driven through runInThread/fireAndForget
	by the UI - exactly how the UI already drives the Plex backend.
	"""

	def __init__(self, session, serverConfig=None):
		printl("", self, "S")

		self.g_session = session
		self.g_serverConfig = serverConfig
		self.g_error = False
		self.lastError = None
		self.lastStatus = None

		printl("running on " + str(sys.version_info), self, "I")

		self.g_sessionID = getUUID()  # DeviceId: the BOX, stable for the whole run
		# PlaySessionId identifies ONE playback, so the server can tell them
		# apart in its dashboard; minted again for every media opened below
		self.g_playSessionId = newPlaybackId()
		self.g_useFilterSections = config.plugins.dreamfin.showFilter.value

		# server settings
		self.serverConfig_Name = str(self.g_serverConfig.name.value)
		self.serverConfig_connectionType = str(self.g_serverConfig.connectionType.value)
		self.serverConfig_port = str(self.g_serverConfig.port.value)
		self.serverConfig_playbackType = str(self.g_serverConfig.playbackType.value)
		self.serverConfig_universalTranscoder = bool(getattr(self.g_serverConfig, "universalTranscoder", _emptyConfig(True)).value)

		self.serverConfig_username = str(getattr(self.g_serverConfig, "username", _emptyConfig()).value)
		self.serverConfig_password = str(getattr(self.g_serverConfig, "password", _emptyConfig()).value)
		# manually entered API key, wins over username/password
		self.serverConfig_accessToken = str(getattr(self.g_serverConfig, "accessToken", _emptyConfig()).value).strip()

		# resolved at runtime by authenticate()/detectServerType()
		self.g_accessToken = ""
		self.g_userId = ""
		self.g_serverType = str(getattr(self.g_serverConfig, "serverType", _emptyConfig("auto")).value) or "auto"
		# set true once detectServerType() flips the accent to a server type
		# different from the one the skin was loaded with (Phase 5 hint)
		self.g_accentJustChanged = False

		# host: keep the hostname for DNS entries (TLS SNI needs it -
		# resolving to an IP here would break name-based virtual hosts)
		if self.serverConfig_connectionType == "0":  # IP
			self.g_host = "%d.%d.%d.%d" % tuple(self.g_serverConfig.ip.value)
		else:  # DNS
			self.g_host = str(self.g_serverConfig.dns.value)

		if int(self.g_serverConfig.port.value) in HTTPS_PORTS:
			self.http = "https"
		else:
			self.http = "http"

		self.g_address = "%s:%s" % (self.g_host, self.serverConfig_port)

		printl("using server: %s://%s (type %s)" % (self.http, self.g_address, self.g_serverType), self, "I")

		# playback state (phase 3): the Plex backend kept the picked media,
		# server and version between the getMediaOptions -> mediaType ->
		# playLibraryMedia round trips; the singleton lives across them here too
		self.lastResponse = None
		self.streams = None
		self.server = self.g_address
		self.g_selectedMediaIndex = None
		self.g_stream = "1"
		self.g_transcode = "false"
		self.g_currentMediaSourceId = None
		# stream indices the audio/subtitle dialogs pick; consumed by
		# transcode() (Emby has no server-side "set active stream" call)
		self.g_audioStreamIndex = None
		self.g_subtitleStreamIndex = None
		self.fallback = False
		self.locations = ""
		self.currentFile = ""

		printl("", self, "C")

	#===============================================================================
	# TRANSPORT
	#===============================================================================

	def buildAuthHeaders(self, withToken=True):
		"""X-Emby-Authorization (+ Authorization twin) and X-Emby-Token.

		The MediaBrowser header is understood by Emby 4.x and every
		Jellyfin; newer Jellyfin (10.8+) documents plain Authorization,
		so both spellings are always sent.
		"""
		boxName = str(config.plugins.dreamfin.boxName.value).replace('"', "")
		token = self.g_accessToken if withToken else ""

		mediaBrowser = 'MediaBrowser Client="DreamFin", Device="%s", DeviceId="%s", Version="%s"' % (
			boxName, self.g_sessionID, getVersion())
		if token:
			mediaBrowser += ', Token="%s"' % token

		headers = {
			"X-Emby-Authorization": mediaBrowser,
			"Authorization": mediaBrowser,
			"Accept": "application/json",
		}
		if token:
			headers["X-Emby-Token"] = token
		return headers

	#===============================================================================
	#
	#===============================================================================
	def doRequest(self, url, myType="GET", extraHeaders=None, body=None, timeout=None):
		"""Fetch url and return the payload bytes, or False on any error.

		Follows up to MAX_REDIRECTS redirects, retries the connection
		once on socket-level errors, never verifies TLS (local boxes
		have no CA store for private servers) and stores the last HTTP
		status in self.lastStatus for the 401 re-auth path.
		"""
		printl("", self, "S")
		printl("url: " + str(url), self, "D")

		requestTimeout = timeout or REQUEST_TIMEOUT
		currentUrl = url
		redirectsLeft = MAX_REDIRECTS
		self.lastStatus = None

		if body is not None and not isinstance(body, bytes):
			body = body.encode("utf-8")

		try:
			while True:
				parsed = urlparse(currentUrl)
				server = parsed.netloc
				urlPath = parsed.path
				if parsed.query:
					urlPath += "?" + parsed.query

				conn = None
				data = None
				for attempt in range(1, CONNECT_ATTEMPTS + 1):
					if currentUrl.startswith("https"):
						conn = HTTPSConnection(server, timeout=requestTimeout, context=ssl._create_unverified_context())
					else:
						conn = HTTPConnection(server, timeout=requestTimeout)

					headers = self.buildAuthHeaders()
					if body is not None:
						headers["Content-Type"] = "application/json"
					if extraHeaders:
						headers.update(extraHeaders)

					try:
						conn.request(myType, urlPath, body=body, headers=headers)
						data = conn.getresponse()
						break
					except (socket.timeout, socket.error) as msg:
						printl("attempt %d/%d failed: %s" % (attempt, CONNECT_ATTEMPTS, str(msg)), self, "W")
						try:
							conn.close()
						except Exception:
							pass
						if attempt >= CONNECT_ATTEMPTS:
							raise

				status = int(data.status)
				self.lastStatus = status

				if status in (301, 302, 303, 307, 308):
					location = data.getheader("Location")
					printl("status %d, following Location: %s" % (status, str(location)), self, "I")
					conn.close()

					if not location or redirectsLeft <= 0:
						error = "HTTP redirect error: " + str(status) + " at " + str(currentUrl)
						printl(error, self, "D")
						self.lastError = error

						printl("", self, "C")
						return False

					redirectsLeft -= 1
					currentUrl = urljoin(currentUrl, location)

					if status == 303:
						myType = "GET"

					continue

				elif status >= 400:
					error = "HTTP response error: " + str(data.status) + " " + str(data.reason)
					printl(error, self, "D")
					self.lastError = error
					conn.close()

					printl("", self, "C")
					return False

				else:
					link = data.read()
					conn.close()

					printl("", self, "C")
					return link

		except socket.gaierror:
			error = "Unable to lookup host: " + str(self.g_host) + "\nCheck host name is correct"
			printl(error, self, "D")
			self.lastError = error

		except socket.timeout:
			error = "Connection to " + str(self.g_host) + " timed out"
			printl(error, self, "D")
			self.lastError = error

		except socket.error as msg:
			error = "Unable to connect to " + str(self.g_host) + "\nReason: " + str(msg)
			self.lastError = error
			printl(error, self, "D")

		except Exception as ex:
			traceback.print_exc()
			error = "Request error: " + str(ex)
			printl(error, self, "D")
			self.lastError = error

		printl("", self, "C")
		return False

	#===============================================================================
	#
	#===============================================================================
	def getJson(self, url, myType="GET", body=None, allowAuthRetry=True, timeout=None):
		"""JSON request against the server; returns dict/list or None.

		Ensures authentication first and re-authenticates exactly once
		when a cached/expired token answers 401.
		"""
		if not self.ensureAuthenticated():
			return None

		payload = self.doRequest(url, myType=myType, body=body, timeout=timeout)

		if payload is False and self.lastStatus == 401 and allowAuthRetry:
			printl("401 from server, re-authenticating once", self, "I")
			if self.authenticate(force=True):
				payload = self.doRequest(url, myType=myType, body=body, timeout=timeout)

		if payload is False:
			return None

		if not payload:
			# some POST/DELETE endpoints answer 204 with an empty body
			return {}

		try:
			return json.loads(payload.decode("utf-8"))
		except (ValueError, UnicodeDecodeError) as ex:
			error = "No parseable JSON payload from " + str(url)
			printl(error + " (" + str(ex) + ")", self, "W")
			self.lastError = error
			return None

	#===============================================================================
	#
	#===============================================================================
	def getJsonPaged(self, url, pageSize=200):
		"""Fetch an Items envelope page by page (StartIndex/Limit query
		parameters) and merge all Items into one envelope. Endpoints that
		ignore paging (no TotalRecordCount) are handled with one request."""
		printl("url: " + str(url), self, "D")

		# A URL that already carries its own Limit wants exactly that many rows and
		# must NOT be walked page by page:
		#  - /Items/Latest returns a bare array and 500s when StartIndex is added;
		#  - the "recently added / on deck" episode queries ask for Limit=100 but
		#    live under a library with tens of thousands of episodes, so paging by
		#    TotalRecordCount walked the WHOLE library and hung the plugin.
		# Fetch these in one request, honouring the caller's Limit.
		if "Limit=" in url:
			return self.getJson(url, timeout=PAGED_REQUEST_TIMEOUT)

		merged = None
		start = 0
		separator = "&" if "?" in url else "?"

		while True:
			pagedUrl = "%s%sStartIndex=%d&Limit=%d" % (url, separator, start, pageSize)
			envelope = self.getJson(pagedUrl, timeout=PAGED_REQUEST_TIMEOUT)

			if envelope is None:
				break

			if not isinstance(envelope, dict) or "Items" not in envelope:
				# bare array or unexpected shape: nothing to page
				if merged is None:
					merged = envelope
				break

			if merged is None:
				merged = envelope
			else:
				merged["Items"].extend(envelope["Items"])

			totalSize = envelope.get("TotalRecordCount")
			if totalSize is None:
				break

			start += pageSize
			if not envelope["Items"] or start >= int(totalSize):
				break

		if isinstance(merged, dict) and "Items" in merged:
			printl("merged %d items" % len(merged["Items"]), self, "D")
		return merged

	#===============================================================================
	# AUTH + SERVER TYPE
	#===============================================================================

	def ensureAuthenticated(self):
		if self.g_accessToken and self.g_userId:
			return True
		return self.authenticate()

	#===============================================================================
	#
	#===============================================================================
	def authenticate(self, force=False):
		"""Resolve an access token + user id for this server.

		Priority: manual API key from the config, then cached token from
		an earlier login, then POST /Users/AuthenticateByName. Fills the
		accessTokenCache/userIdCache config so later plugin starts skip
		the login roundtrip.
		"""
		printl("", self, "S")

		# 1) manual API key wins over everything
		if self.serverConfig_accessToken:
			self.g_accessToken = self.serverConfig_accessToken
			if not self.g_userId:
				# A configured user id always wins, even on a forced re-auth:
				# the key comes from the config and never changes, so asking
				# the server again could only turn a working setup into a
				# broken one (resolving needs admin-only /Users).
				cachedUserId = str(getattr(self.g_serverConfig, "userIdCache", _emptyConfig()).value)
				if cachedUserId:
					self.g_userId = cachedUserId
				else:
					self.lastError = None
					self.g_userId = self._userIdForApiKey()
					if self.g_userId:
						self._saveTokenCache(userId=self.g_userId)
			ok = bool(self.g_accessToken and self.g_userId)
			if not ok:
				if not self.lastError:
					self.lastError = _("Could not resolve a user for the configured API key.")
				self.g_accessToken = ""
			printl("", self, "C")
			return ok

		# 2) cached token from an earlier username/password login
		if not force:
			cachedToken = str(getattr(self.g_serverConfig, "accessTokenCache", _emptyConfig()).value)
			cachedUserId = str(getattr(self.g_serverConfig, "userIdCache", _emptyConfig()).value)
			if cachedToken and cachedUserId:
				self.g_accessToken = cachedToken
				self.g_userId = cachedUserId
				printl("using cached access token", self, "D")
				printl("", self, "C")
				return True

		# 3) fresh login
		if not self.serverConfig_username:
			self.lastError = _("No username or API key configured for this server.")
			printl("", self, "C")
			return False

		self.g_accessToken = ""
		self.g_userId = ""

		url = self.getContentUrl("/Users/AuthenticateByName")
		body = json.dumps({"Username": self.serverConfig_username, "Pw": self.serverConfig_password})
		payload = self.doRequest(url, myType="POST", body=body)

		if payload is False:
			if self.lastStatus == 401:
				self.lastError = _("Login failed: wrong username or password.")
			elif not self.lastError:
				self.lastError = _("Login failed.")
			printl("", self, "C")
			return False

		try:
			answer = json.loads(payload.decode("utf-8"))
			self.g_accessToken = str(answer["AccessToken"])
			self.g_userId = str(answer["User"]["Id"])
		except (ValueError, KeyError, TypeError, UnicodeDecodeError) as ex:
			self.lastError = _("Login failed: unexpected answer from server.")
			printl("auth parse error: " + str(ex), self, "W")
			printl("", self, "C")
			return False

		self._saveTokenCache(token=self.g_accessToken, userId=self.g_userId)

		printl("authenticated as userId " + self.g_userId, self, "I")
		printl("", self, "C")
		return True

	#===============================================================================
	#
	#===============================================================================
	def _userIdForApiKey(self):
		"""Resolve WHICH user an API key should act as - never by guessing.

		API keys are not user-scoped, so the id has to come from somewhere.
		This used to return users[0], which on an admin key silently opens a
		stranger's library; the configured username is matched instead, and
		anything ambiguous is an explicit error.

		This is only a fallback: /Users is admin-only on Emby (it answers 403
		"does not have access to ManageServer" for a normal client account),
		which is why a provisioned userIdCache is the supported way to pair a
		key with its user. Emby has no /Users/Me to fall back on either - it
		answers 500 "Unrecognized Guid format", unlike Jellyfin.
		"""
		payload = self.doRequest(self.getContentUrl("/Users"))
		if payload is False:
			if self.lastStatus in (401, 403):
				self.lastError = _("This API key is not allowed to list the users of this server. Configure the user id for this server instead.")
			else:
				self.lastError = _("Could not ask the server which users exist.")
			return ""

		try:
			users = json.loads(payload.decode("utf-8"))
			if isinstance(users, dict):  # defensive: some proxies wrap it
				users = users.get("Items", [])
		except (ValueError, TypeError, UnicodeDecodeError) as ex:
			printl("could not parse /Users: " + str(ex), self, "W")
			self.lastError = _("Could not read the user list of this server.")
			return ""

		users = users or []
		wanted = self.serverConfig_username.strip().lower()

		if wanted:
			for user in users:
				try:
					if str(user.get("Name", "")).strip().lower() == wanted:
						return str(user["Id"])
				except (AttributeError, KeyError, TypeError):
					continue
			self.lastError = _("The configured user does not exist on this server.")
			return ""

		# Without a username there is nothing to match. One single user is
		# still unambiguous; more than one would be a coin flip.
		if len(users) == 1:
			try:
				return str(users[0]["Id"])
			except (KeyError, TypeError):
				pass
			self.lastError = _("Could not read the user list of this server.")
			return ""

		self.lastError = _("Configure a username so the API key knows which library to open.")
		return ""

	#===============================================================================
	#
	#===============================================================================
	def _saveTokenCache(self, token=None, userId=None):
		try:
			if token is not None and hasattr(self.g_serverConfig, "accessTokenCache"):
				self.g_serverConfig.accessTokenCache.value = token
				self.g_serverConfig.accessTokenCache.save()
			if userId is not None and hasattr(self.g_serverConfig, "userIdCache"):
				self.g_serverConfig.userIdCache.value = userId
				self.g_serverConfig.userIdCache.save()
		except Exception as ex:
			# a failed cache write must never break the session itself
			printl("could not persist token cache: " + str(ex), self, "W")

	#===============================================================================
	#
	#===============================================================================
	def detectServerType(self):
		"""Ask /System/Info/Public (no auth needed) whether this is Emby
		or Jellyfin. Only runs when the config says 'auto'; updates the
		global lastAccent so the next plugin start loads matching colors."""
		printl("", self, "S")

		if self.g_serverType in ("emby", "jellyfin"):
			self._updateAccent(self.g_serverType)
			printl("", self, "C")
			return self.g_serverType

		payload = self.doRequest(self.getContentUrl("/System/Info/Public"))
		detected = "emby"
		if payload is not False:
			try:
				info = json.loads(payload.decode("utf-8"))
				productName = str(info.get("ProductName", ""))
				if "jellyfin" in productName.lower():
					detected = "jellyfin"
			except (ValueError, UnicodeDecodeError) as ex:
				printl("could not parse /System/Info/Public: " + str(ex), self, "W")

		self.g_serverType = detected
		self._updateAccent(detected)

		printl("detected server type: " + detected, self, "I")
		printl("", self, "C")
		return detected

	#===============================================================================
	#
	#===============================================================================
	def _updateAccent(self, serverType):
		try:
			accentConfig = getattr(config.plugins.dreamfin, "lastAccent", None)
			if accentConfig is not None and accentConfig.value != serverType:
				accentConfig.value = serverType
				accentConfig.save()
				# the skin this open loaded used the old accent -> hint that
				# the colours will match on the next plugin open
				self.g_accentJustChanged = True
		except Exception as ex:
			printl("could not persist accent: " + str(ex), self, "W")

	def accentJustChanged(self):
		"""True once after entering a server whose type differs from the accent
		the skin was loaded with this plugin open (read-and-clear)."""
		changed = self.g_accentJustChanged
		self.g_accentJustChanged = False
		return changed

	#===============================================================================
	#
	#===============================================================================
	def getServerType(self):
		return self.g_serverType

	#===============================================================================
	# URL HELPERS
	#===============================================================================

	def getContentUrl(self, path):
		return "%s://%s%s" % (self.http, self.g_address, path)

	#===============================================================================
	#
	#===============================================================================
	def buildItemsUrl(self, sectionId, includeItemTypes, extra=""):
		"""The canonical 'all items of this section' listing URL.

		Default sort is SortName ascending, but a caller can override it by
		putting its own SortBy in ``extra`` (Recently Added/Released). Emby and
		Jellyfin both honour the FIRST SortBy when the query has duplicates, so
		the default one must NOT be emitted in that case or the caller's sort is
		silently dropped and the list comes back alphabetical."""
		sort = "" if "SortBy=" in extra else "&SortBy=SortName&SortOrder=Ascending"
		url = self.getContentUrl(
			"/Users/%s/Items?ParentId=%s&Recursive=true&IncludeItemTypes=%s"
			"%s&Fields=%s"
			% (self.g_userId, sectionId, includeItemTypes, sort, DEFAULT_ITEM_FIELDS))
		if extra:
			url += extra
		return url

	#===============================================================================
	# LIBRARY ACCESS
	#===============================================================================

	def getSectionTypes(self):
		printl("", self, "S")

		# Phase 5: resolve the server accent on entry here too. This summarized
		# path (config default summerizeSections=True) is the one most users
		# hit, so without this the colours never learn the server type - the
		# detectServerType() call in getAllSections() only covers the full path.
		self.detectServerType()

		fullList = []
		entryData = {}
		fullList.append((_("Movies"), Plugin.MENU_MOVIES, "movieEntry", entryData))
		fullList.append((_("Tv Shows"), Plugin.MENU_TVSHOWS, "showEntry", entryData))
		fullList.append((_("Music"), Plugin.MENU_MUSIC, "musicEntry", entryData))

		printl("mainMenuList: " + str(fullList), self, "D")
		printl("", self, "C")
		return fullList

	#===============================================================================
	#
	#===============================================================================
	def getAllSections(self, myFilter=None, serverFilterActive=False):
		"""User views -> section menu 4-tuples.

		CollectionType movies/tvshows/music map onto the movie/show/artist
		flows; views without a CollectionType (mixed folders) enter the
		mixed browser directly. Everything else (boxsets, livetv,
		playlists, photos) has no v1 flow and is skipped.
		"""
		printl("getAllSections", self, "S")
		printl("myFilter: " + str(myFilter), self, "D")

		if not self.ensureAuthenticated():
			return []
		self.detectServerType()

		envelope = self.getJson(self.getContentUrl("/Users/%s/Views" % self.g_userId))
		if envelope is None:
			if not self.lastError:
				self.lastError = _("No data in this section!")
			printl("", self, "C")
			return []

		items = envelope.get("Items", []) if isinstance(envelope, dict) else []
		fullList = []

		for item in items:
			collectionType = item.get("CollectionType")
			sectionId = jsonToStr(item.get("Id"))
			title = jsonToStr(item.get("Name"), "no Title")

			entryData = {
				"title": title,
				"key": sectionId,
				"section": sectionId,
				"address": self.g_address,
				"server": self.g_address,
				"isSectionRoot": True,
			}

			if collectionType == "movies":
				entryData["type"] = "movie"
				entryData["contentUrl"] = self.buildItemsUrl(sectionId, "Movie")
				if myFilter is not None and myFilter != "movies":
					continue
				if self.g_useFilterSections:
					fullList.append((_(title), Plugin.MENU_FILTER, "movieEntry", entryData))
				else:
					fullList.append((_(title), getPlugin("movies", Plugin.MENU_MOVIES), "movieEntry", entryData))

			elif collectionType == "tvshows":
				entryData["type"] = "show"
				entryData["contentUrl"] = self.buildItemsUrl(sectionId, "Series")
				if myFilter is not None and myFilter != "tvshow":
					continue
				if self.g_useFilterSections:
					fullList.append((_(title), Plugin.MENU_FILTER, "showEntry", entryData))
				else:
					fullList.append((_(title), getPlugin("tvshows", Plugin.MENU_TVSHOWS), "showEntry", entryData))

			elif collectionType == "music":
				entryData["type"] = "artist"
				entryData["contentUrl"] = self.getContentUrl(
					"/Artists/AlbumArtists?ParentId=%s&UserId=%s&SortBy=SortName&SortOrder=Ascending"
					% (sectionId, self.g_userId))
				if myFilter is not None and myFilter != "music":
					continue
				# music always uses the filter menu, exactly like the Plex flow
				fullList.append((_(title), Plugin.MENU_FILTER, "musicEntry", entryData))

			elif collectionType in (None, "", "homevideos"):
				# mixed content folder: no filter menu, straight into the browser
				if myFilter is not None:
					continue
				entryData["type"] = "movie"
				entryData["currentViewMode"] = "movie"
				entryData["nextViewMode"] = "mixed"
				entryData["contentUrl"] = self.buildItemsUrl(sectionId, "Movie,Series,Video")
				fullList.append((_(title), getPlugin("mixed", Plugin.MENU_MIXED), "mixedEntry", entryData))

			else:
				printl("skipping view '%s' with unsupported CollectionType %s" % (title, str(collectionType)), self, "D")
				continue

		# synthesized global entries on top, like Plex' On Deck/New
		if myFilter is None and items:
			continueWatching = {
				"title": "Continue watching",
				"type": "movie",
				"currentViewMode": "movie",
				"nextViewMode": "mixed",
				"address": self.g_address,
				"server": self.g_address,
				"key": "onDeck",
				"contentUrl": self.getContentUrl(
					"/Users/%s/Items/Resume?Recursive=true&MediaTypes=Video&Fields=%s"
					% (self.g_userId, DEFAULT_ITEM_FIELDS)),
			}
			fullList.insert(0, (_("Continue watching"), getPlugin("mixed", Plugin.MENU_MIXED), "mixedEntry", continueWatching))

			recentlyAdded = {
				"title": "Recently added",
				"type": "movie",
				"currentViewMode": "movie",
				"nextViewMode": "mixed",
				"address": self.g_address,
				"server": self.g_address,
				"key": "recentlyAdded",
				"contentUrl": self.getContentUrl(
					"/Users/%s/Items/Latest?Limit=60&Fields=%s"
					% (self.g_userId, DEFAULT_ITEM_FIELDS)),
			}
			fullList.insert(1, (_("Recently added"), getPlugin("mixed", Plugin.MENU_MIXED), "mixedEntry", recentlyAdded))

		if not fullList:
			self.lastError = _("No data in this section!")

		printl("", self, "C")
		return fullList

	#===============================================================================
	#
	#===============================================================================
	def getSectionFilter(self, incomingEntryData):
		"""Emby/Jellyfin have no legacy secondary navigation: the filter
		menu of a section root is always synthesized locally, and the
		genre/year/decade secondaries are resolved through /Genres and
		/Years. Tuple shapes match the Plex synthesizer exactly."""
		printl("", self, "S")
		printl("incomingEntryData: " + str(incomingEntryData), self, "D")

		key = incomingEntryData.get("key", "")

		if key == "genre":
			result = self._getGenreFilter(incomingEntryData)
		elif key == "year":
			result = self._getYearFilter(incomingEntryData, decades=False)
		elif key == "decade":
			result = self._getYearFilter(incomingEntryData, decades=True)
		elif incomingEntryData.get("isSectionRoot", False):
			result = self.getSynthesizedSectionFilter(incomingEntryData)
		else:
			printl("nothing to build a filter from: " + str(key), self, "W")
			result = []

		if not result and not self.lastError:
			self.lastError = _("No data in this section!")

		printl("", self, "C")
		return result

	#===============================================================================
	#
	#===============================================================================
	def getSynthesizedSectionFilter(self, incomingEntryData):
		"""Same menu, titles and key literals as the Plex synthesizer -
		DP_LibShows routes by these exact key values - with the
		contentUrl pointing at the equivalent Emby/Jellyfin request."""
		printl("", self, "S")

		sectionType = incomingEntryData.get("type")
		sectionId = incomingEntryData.get("section") or incomingEntryData.get("key")

		if sectionType == "movie":
			plugin = getPlugin("movies", Plugin.MENU_MOVIES)
			entryType = "movieEntry"
			allUrl = self.buildItemsUrl(sectionId, "Movie")
			menu = [
				(_("All Movies"), "all", None, None,
					allUrl),
				(_("Unwatched"), "all?unwatched=1", None, None,
					self.buildItemsUrl(sectionId, "Movie", "&Filters=IsUnplayed")),
				(_("Recently Added"), "recentlyAdded", None, None,
					self.buildItemsUrl(sectionId, "Movie", "&SortBy=DateCreated&SortOrder=Descending&Limit=100")),
				(_("Recently Released"), "newest", None, None,
					self.buildItemsUrl(sectionId, "Movie", "&SortBy=PremiereDate&SortOrder=Descending&Limit=100")),
				(_("On Deck"), "onDeck", None, None,
					self.getContentUrl("/Users/%s/Items/Resume?ParentId=%s&Recursive=true&MediaTypes=Video&Fields=%s"
						% (self.g_userId, sectionId, DEFAULT_ITEM_FIELDS))),
				(_("By Genre"), "genre", "secondary", None, None),
				(_("By Year"), "year", "secondary", None, None),
				(_("By Decade"), "decade", "secondary", None, None),
				(_("Search..."), "search?type=1", "prompt", None,
					self.buildItemsUrl(sectionId, "Movie")),
			]

		elif sectionType == "show" or sectionType == "episode":
			plugin = getPlugin("tvshows", Plugin.MENU_TVSHOWS)
			entryType = "showEntry"
			menu = [
				(_("All Shows"), "all", None, None,
					self.buildItemsUrl(sectionId, "Series")),
				(_("Unwatched"), "all?unwatched=1", None, None,
					self.buildItemsUrl(sectionId, "Series", "&Filters=IsUnplayed")),
				# Grouped by series: return the shows (not loose episodes) sorted
				# by DateLastContentAdded so a series bubbles up when it gets a new
				# episode. Renders like "All Shows" (see DP_LibShows.loadLibrary).
				(_("Recently Added"), "recentlyAdded", None, None,
					self.buildItemsUrl(sectionId, "Series", "&SortBy=DateLastContentAdded&SortOrder=Descending&Limit=100")),
				(_("On Deck"), "onDeck", None, None,
					self.getContentUrl("/Shows/NextUp?ParentId=%s&UserId=%s&Fields=%s"
						% (sectionId, self.g_userId, DEFAULT_ITEM_FIELDS))),
				(_("By Genre"), "genre", "secondary", None, None),
				(_("By Year"), "year", "secondary", None, None),
				(_("Search..."), "search?type=2", "prompt", None,
					self.buildItemsUrl(sectionId, "Series")),
			]

		elif sectionType == "artist":
			plugin = getPlugin("music", Plugin.MENU_MUSIC)
			entryType = "musicEntry"
			menu = [
				(_("All Artists"), "all", None, None,
					self.getContentUrl("/Artists/AlbumArtists?ParentId=%s&UserId=%s&SortBy=SortName&SortOrder=Ascending"
						% (sectionId, self.g_userId))),
				(_("Recently Added"), "recentlyAdded", None,
					{"nextViewMode": "ShowAlbums", "currentViewMode": "ShowAlbums"},
					self.buildItemsUrl(sectionId, "MusicAlbum", "&SortBy=DateCreated&SortOrder=Descending&Limit=100")),
				(_("By Genre"), "genre", "secondary", None, None),
				(_("Search..."), "search?type=8", "prompt", None,
					self.getContentUrl("/Artists/AlbumArtists?ParentId=%s&UserId=%s" % (sectionId, self.g_userId))),
			]

		else:
			printl("unsupported section type: " + str(sectionType), self, "W")
			printl("", self, "C")
			return []

		fullList = []
		for title, key, kind, extraData, contentUrl in menu:
			entryData = {
				"title": title,
				"key": key,
				"type": sectionType,
				"section": sectionId,
				"address": self.g_address,
				"server": self.g_address,
				"hasSecondaryTag": kind == "secondary",
				"hasPromptTag": kind == "prompt",
				"synthesized": True,
			}
			if contentUrl:
				entryData["contentUrl"] = contentUrl

			if extraData:
				entryData.update(extraData)

			if kind == "secondary":
				fullList.append((title, Plugin.MENU_FILTER, "showFilter", entryData))
			else:
				fullList.append((title, plugin, entryType, entryData))

			printl("synthesized entryData: " + str(entryData), self, "D")

		printl("", self, "C")
		return fullList

	#===============================================================================
	#
	#===============================================================================
	def _sectionContentTarget(self, incomingEntryData):
		"""(plugin, entryType, includeItemTypes) for a section type."""
		sectionType = incomingEntryData.get("type")
		if sectionType == "show" or sectionType == "episode":
			return getPlugin("tvshows", Plugin.MENU_TVSHOWS), "showEntry", "Series"
		if sectionType == "artist":
			return getPlugin("music", Plugin.MENU_MUSIC), "musicEntry", "MusicAlbum"
		return getPlugin("movies", Plugin.MENU_MOVIES), "movieEntry", "Movie"

	#===============================================================================
	#
	#===============================================================================
	def _getGenreFilter(self, incomingEntryData):
		printl("", self, "S")

		sectionId = incomingEntryData.get("section")
		sectionType = incomingEntryData.get("type")
		plugin, entryType, includeItemTypes = self._sectionContentTarget(incomingEntryData)

		if sectionType == "artist":
			genresPath = "/MusicGenres"
		else:
			genresPath = "/Genres"

		url = self.getContentUrl("%s?ParentId=%s&UserId=%s&SortBy=SortName&SortOrder=Ascending"
								% (genresPath, sectionId, self.g_userId))
		envelope = self.getJsonPaged(url)
		if envelope is None:
			printl("", self, "C")
			return []

		fullList = []
		for item in envelope.get("Items", []):
			name = jsonToStr(item.get("Name"))
			genreId = jsonToStr(item.get("Id"))
			if not name or not genreId:
				continue

			entryData = dict(incomingEntryData)
			entryData["title"] = name
			entryData["key"] = "genre/" + genreId
			entryData["hasSecondaryTag"] = False
			entryData["hasPromptTag"] = False
			if sectionType == "artist":
				entryData["contentUrl"] = self.getContentUrl(
					"/Artists/AlbumArtists?ParentId=%s&UserId=%s&GenreIds=%s&SortBy=SortName&SortOrder=Ascending"
					% (sectionId, self.g_userId, genreId))
			else:
				entryData["contentUrl"] = self.buildItemsUrl(sectionId, includeItemTypes, "&GenreIds=" + genreId)

			fullList.append((name, plugin, entryType, entryData))

		printl("", self, "C")
		return fullList

	#===============================================================================
	#
	#===============================================================================
	def _getYearFilter(self, incomingEntryData, decades=False):
		printl("", self, "S")

		sectionId = incomingEntryData.get("section")
		plugin, entryType, includeItemTypes = self._sectionContentTarget(incomingEntryData)

		url = self.getContentUrl("/Years?ParentId=%s&UserId=%s&SortBy=SortName&SortOrder=Descending"
								% (sectionId, self.g_userId))
		envelope = self.getJsonPaged(url)
		if envelope is None:
			printl("", self, "C")
			return []

		years = []
		for item in envelope.get("Items", []):
			try:
				years.append(int(item.get("Name")))
			except (TypeError, ValueError):
				continue

		fullList = []
		if decades:
			decadeMap = {}
			for year in years:
				decadeMap.setdefault((year // 10) * 10, []).append(year)

			for decade in sorted(decadeMap.keys(), reverse=True):
				title = "%ds" % decade
				entryData = dict(incomingEntryData)
				entryData["title"] = title
				entryData["key"] = "decade/%d" % decade
				entryData["hasSecondaryTag"] = False
				entryData["hasPromptTag"] = False
				yearsParam = ",".join(str(y) for y in sorted(decadeMap[decade]))
				entryData["contentUrl"] = self.buildItemsUrl(sectionId, includeItemTypes, "&Years=" + yearsParam)
				fullList.append((title, plugin, entryType, entryData))
		else:
			for year in sorted(years, reverse=True):
				title = str(year)
				entryData = dict(incomingEntryData)
				entryData["title"] = title
				entryData["key"] = "year/%d" % year
				entryData["hasSecondaryTag"] = False
				entryData["hasPromptTag"] = False
				entryData["contentUrl"] = self.buildItemsUrl(sectionId, includeItemTypes, "&Years=%d" % year)
				fullList.append((title, plugin, entryType, entryData))

		printl("", self, "C")
		return fullList

	#===============================================================================
	# ITEM PARSING - the golden rule lives here: every entryData value the
	# UI can see leaves this section as a native str (utf-8 bytes on py2)
	#===============================================================================

	def _nowEpoch(self):
		"""Current UTC epoch, wrapped so tests can pin 'now'."""
		return time.time()

	def _newContentDays(self):
		"""The 'mark recently added' window in days (0 = feature off)."""
		try:
			return int(config.plugins.dreamfin.newContentDays.value)
		except (AttributeError, ValueError, TypeError):
			return 7

	#===============================================================================
	#
	#===============================================================================
	def itemToEntryData(self, item):
		"""Map one Emby/Jellyfin item onto the entryData dictionary shape
		the inherited UI reads. Caller adds server/viewModes/tagType."""
		userData = item.get("UserData") or {}

		entryData = {
			"type": ITEM_TYPE_MAP.get(item.get("Type"), jsonToStr(item.get("Type"), "Folder")),
			"key": jsonToStr(item.get("Id")),
			"ratingKey": jsonToStr(item.get("Id")),
			"title": jsonToStr(item.get("Name"), "no Title"),
			"summary": jsonToStr(item.get("Overview")),
			"year": jsonToStr(item.get("ProductionYear")),
			"studio": self._firstStudio(item),
			"contentRating": jsonToStr(item.get("OfficialRating")),
			"rating": self._communityRating(item),
			"duration": jsonToStr(ticksToMs(item["RunTimeTicks"])) if item.get("RunTimeTicks") else "",
			"viewCount": self._viewCount(userData),
			# "seen" is UserData.Played (a real boolean), NOT PlayCount: Emby
			# bumps PlayCount on every stop, even one a few seconds in (and then
			# zeroes the resume position), so PlayCount>0 does NOT mean watched.
			"played": "1" if userData.get("Played") else "0",
			"viewOffset": jsonToStr(ticksToMs(userData["PlaybackPositionTicks"])) if userData.get("PlaybackPositionTicks") else "0",
			"genre": self._joinNames(item.get("Genres")),
			"director": self._joinPeople(item, "Director"),
			"cast": self._joinPeople(item, "Actor"),
			"writer": self._joinPeople(item, "Writer"),
			"country": self._joinNames(item.get("ProductionLocations")),
		}

		# "new" = recently ADDED to the library (DateCreated for leaves;
		# DateLastMediaAdded lets a series/season bubble up on new content where
		# the server exposes it - Jellyfin does, Emby does not). Never the
		# premiere/air date. Window comes from settings; "0" days turns it off.
		entryData["isNew"] = "1" if isRecentlyAdded(
			(item.get("DateLastMediaAdded"), item.get("DateCreated")),
			self._nowEpoch(), self._newContentDays()) else "0"

		taglines = item.get("Taglines")
		if taglines:
			entryData["tagline"] = jsonToStr(taglines[0])

		if item.get("IndexNumber") is not None:
			entryData["index"] = jsonToStr(item.get("IndexNumber"))
		if item.get("ParentIndexNumber") is not None:
			entryData["parentIndex"] = jsonToStr(item.get("ParentIndexNumber"))

		# show/season episode counters; the show view does int() arithmetic on
		# them, so they must always be present and numeric - a missing key made
		# int('') raise and crashed the whole refresh for items without a count.
		entryData["leafCount"] = "0"
		entryData["viewedLeafCount"] = "0"
		if item.get("RecursiveItemCount") is not None:
			leafCount = int(item["RecursiveItemCount"])
			entryData["leafCount"] = jsonToStr(leafCount)
			unplayed = userData.get("UnplayedItemCount")
			if unplayed is not None:
				entryData["viewedLeafCount"] = jsonToStr(max(0, leafCount - int(unplayed)))
			elif userData.get("Played"):
				entryData["viewedLeafCount"] = entryData["leafCount"]

		# episodes/seasons: the show view builds the poster/backdrop cache keys
		# from the parent/grandparent ids and title (Plex supplied these
		# natively). Without them _refresh did self.details['parentRatingKey']
		# -> KeyError and crashed while navigating episodes.
		if item.get("SeasonId"):
			entryData["parentRatingKey"] = jsonToStr(item.get("SeasonId"))
		if item.get("SeriesId"):
			entryData["grandparentRatingKey"] = jsonToStr(item.get("SeriesId"))
		if item.get("SeriesName"):
			entryData["grandparentTitle"] = jsonToStr(item.get("SeriesName"))

		# marker the show detail view checks ('theme' in self.details) to
		# decide whether to fetch a series theme song; the real URL is
		# resolved lazily by getThemeUrl(). Only series carry a theme.
		if item.get("Type") == "Series":
			entryData["theme"] = jsonToStr(item.get("Id"))

		return entryData

	#===============================================================================
	#
	#===============================================================================
	def buildMediaDataArr(self, item):
		"""MediaSources[] -> the mediaDataArr shape the UI and the version
		selector consume. All values are strings; sizes/bitrates numeric-ish
		strings; durations in milliseconds."""
		mediaDataArr = []

		for source in item.get("MediaSources") or []:
			videoStream = None
			audioStream = None
			for stream in source.get("MediaStreams") or []:
				streamType = stream.get("Type")
				if streamType == "Video" and videoStream is None:
					videoStream = stream
				elif streamType == "Audio" and audioStream is None:
					audioStream = stream

			defaultAudioIndex = source.get("DefaultAudioStreamIndex")
			if defaultAudioIndex is not None:
				for stream in source.get("MediaStreams") or []:
					if stream.get("Type") == "Audio" and stream.get("Index") == defaultAudioIndex:
						audioStream = stream
						break

			videoStream = videoStream or {}
			audioStream = audioStream or {}

			mediaData = {
				"id": jsonToStr(source.get("Id")),
				"videoCodec": jsonToStr(videoStream.get("Codec")),
				"audioCodec": jsonToStr(audioStream.get("Codec")),
				"audioChannels": jsonToStr(audioStream.get("Channels")),
				"videoResolution": self._mapResolution(videoStream.get("Width"), videoStream.get("Height")),
				"aspectRatio": self._mapAspect(videoStream.get("AspectRatio")),
				"bitrate": jsonToStr(source.get("Bitrate")),
				"videoFrameRate": jsonToStr(videoStream.get("RealFrameRate") or videoStream.get("AverageFrameRate")),
				"container": jsonToStr(source.get("Container")),
			}

			part = {
				"id": jsonToStr(source.get("Id")),
				"key": jsonToStr(source.get("Id")),
				"file": jsonToStr(source.get("Path")),
				"container": jsonToStr(source.get("Container")),
				"size": jsonToStr(source.get("Size")),
				"duration": jsonToStr(ticksToMs(source["RunTimeTicks"])) if source.get("RunTimeTicks") else "",
			}
			mediaData["Parts"] = [part]

			mediaDataArr.append(mediaData)

		return mediaDataArr

	#===============================================================================
	#
	#===============================================================================
	@staticmethod
	def _mapResolution(width, height):
		"""Width/Height -> the four buckets the skin has icons for."""
		try:
			width = int(width or 0)
			height = int(height or 0)
		except (TypeError, ValueError):
			return "SD"
		if height >= 2000 or width >= 3600:
			return "4K"
		if height >= 1000 or width >= 1900:
			return "1080"
		if height >= 700 or width >= 1260:
			return "720"
		return "SD"

	#===============================================================================
	#
	#===============================================================================
	@staticmethod
	def _mapAspect(value):
		"""AspectRatio ('2.40:1', '16:9', '1.78', 2.35, None) -> nearest of
		the three literals the skin has icons for."""
		if value in (None, ""):
			return ""
		try:
			if isinstance(value, (int, float)):
				ratio = float(value)
			else:
				text = jsonToStr(value)
				if ":" in text:
					left, right = text.split(":", 1)
					ratio = float(left) / float(right)
				else:
					ratio = float(text)
		except (TypeError, ValueError, ZeroDivisionError):
			return ""

		best = min((1.33, 1.78, 2.35), key=lambda candidate: abs(candidate - ratio))
		return "%.2f" % best

	#===============================================================================
	#
	#===============================================================================
	def _joinNames(self, values):
		if not values:
			return ""
		return " / ".join(jsonToStr(value) for value in values if value)

	def _joinPeople(self, item, personType):
		names = []
		for person in item.get("People") or []:
			if person.get("Type") == personType and person.get("Name"):
				names.append(jsonToStr(person.get("Name")))
		return " / ".join(names)

	def _firstStudio(self, item):
		for studio in item.get("Studios") or []:
			if studio.get("Name"):
				return jsonToStr(studio.get("Name"))
		return ""

	def _communityRating(self, item):
		rating = item.get("CommunityRating")
		if rating is None:
			return ""
		try:
			return "%.1f" % float(rating)
		except (TypeError, ValueError):
			return jsonToStr(rating)

	def _viewCount(self, userData):
		playCount = userData.get("PlayCount")
		if playCount is None:
			playCount = 1 if userData.get("Played") else 0
		return jsonToStr(playCount)

	#===============================================================================
	# IMAGES
	#===============================================================================

	def getImageUrl(self, itemId, imageType="Primary", tag=None):
		"""Server-side resized image URL.

		The size params are appended LAST, keeping IMAGE_SIZE_PLACEHOLDER
		intact as a trailing '&maxWidth=...&maxHeight=...' substring: the
		UI does download_url.replace(IMAGE_SIZE_PLACEHOLDER, real dims),
		so the placeholder must appear verbatim (with its leading '&').
		"""
		url = self.getContentUrl("/Items/%s/Images/%s" % (jsonToStr(itemId), imageType))
		params = []
		if tag:
			params.append("tag=" + jsonToStr(tag))
		if self.g_accessToken:
			params.append("api_key=" + self.g_accessToken)
		url += "?" + "&".join(params) if params else "?"
		url += IMAGE_SIZE_PLACEHOLDER
		return url

	#===============================================================================
	#
	#===============================================================================
	def _attachImages(self, entryData, item, switchMedias=False):
		"""thumb/art like the Plex backend: '' when the artwork does not
		exist (the UI routes '' into its no-picture path)."""
		imageTags = item.get("ImageTags") or {}

		primary = ""
		if imageTags.get("Primary"):
			primary = self.getImageUrl(item.get("Id"), "Primary", imageTags.get("Primary"))
		elif item.get("SeriesPrimaryImageTag") and item.get("SeriesId"):
			primary = self.getImageUrl(item.get("SeriesId"), "Primary", item.get("SeriesPrimaryImageTag"))

		backdrop = ""
		backdropTags = item.get("BackdropImageTags") or []
		if backdropTags:
			backdrop = self.getImageUrl(item.get("Id"), "Backdrop/0", backdropTags[0])
		elif item.get("ParentBackdropItemId"):
			parentTags = item.get("ParentBackdropImageTags") or []
			backdrop = self.getImageUrl(item.get("ParentBackdropItemId"), "Backdrop/0",
									parentTags[0] if parentTags else None)

		if switchMedias:
			# episodes: the list artwork is the series backdrop, the detail
			# artwork is the episode still
			entryData["thumb"] = backdrop
			entryData["art"] = primary
		else:
			entryData["thumb"] = primary
			entryData["art"] = backdrop

		return entryData

	#===============================================================================
	# LIST ENTRIES
	#===============================================================================

	def getFullListEntry(self, entryData, nextUrl, viewState=None):
		"""The 5-tuple every list row is made of."""
		if "ratingKey" in entryData:
			contextMenu = self.buildContextMenu(entryData["ratingKey"])
		else:
			contextMenu = None

		title = entryData.get("title", "no Title")
		return title, entryData, contextMenu, viewState, nextUrl

	#===============================================================================
	#
	#===============================================================================
	def buildContextMenu(self, itemId):
		"""Same keys as the Plex backend produced. The URLs already point
		at the Emby endpoints; phase 3 turns the GET call sites in
		DP_View into backend method calls with the right HTTP verbs."""
		return {
			"itemId": jsonToStr(itemId),
			"libraryRefreshURL": self.getContentUrl("/Items/%s/Refresh" % itemId),
			"unwatchURL": self.getContentUrl("/Users/%s/PlayedItems/%s" % (self.g_userId, itemId)),
			"watchedURL": self.getContentUrl("/Users/%s/PlayedItems/%s" % (self.g_userId, itemId)),
			"deleteURL": self.getContentUrl("/Items/%s" % itemId),
		}

	#===============================================================================
	#
	#===============================================================================
	def getViewStateForShowEntry(self, entryData):
		if "viewedLeafCount" not in entryData or "leafCount" not in entryData:
			return "unseen"
		try:
			viewed = int(entryData["viewedLeafCount"])
			total = int(entryData["leafCount"])
		except (TypeError, ValueError):
			return "unseen"
		if total > 0 and viewed >= total:
			return "seen"
		if viewed > 0:
			return "started"
		return "unseen"

	def getViewStatefromViewCount(self, entryData):
		# watched is the Played boolean, not PlayCount (see itemToEntryData):
		# a movie stopped after a few seconds comes back with PlayCount=1 but
		# Played=False and a zeroed position, i.e. it is NOT watched.
		if str(entryData.get("played")) == "1":
			return "seen"
		viewOffset = int(entryData.get("viewOffset") or 0)
		if viewOffset > 0:
			return "started"
		return "unseen"

	#===============================================================================
	# NAVIGATION - every method returns (fullList, mediaContainer) like the
	# Plex backend did; mediaContainer carries nothing the UI still reads
	#===============================================================================

	def _seasonsUrl(self, seriesId):
		return self.getContentUrl("/Shows/%s/Seasons?UserId=%s&Fields=%s" % (jsonToStr(seriesId), self.g_userId, DEFAULT_ITEM_FIELDS))

	def _episodesUrl(self, seriesId, seasonId):
		return self.getContentUrl("/Shows/%s/Episodes?SeasonId=%s&UserId=%s&Fields=%s" % (jsonToStr(seriesId), jsonToStr(seasonId), self.g_userId, DEFAULT_ITEM_FIELDS))

	def _albumsOfArtistUrl(self, artistId):
		return self.getContentUrl("/Users/%s/Items?IncludeItemTypes=MusicAlbum&Recursive=true&AlbumArtistIds=%s&SortBy=SortName&SortOrder=Ascending&Fields=%s" % (self.g_userId, jsonToStr(artistId), DEFAULT_ITEM_FIELDS))

	def _tracksOfAlbumUrl(self, albumId):
		return self.getContentUrl("/Users/%s/Items?ParentId=%s&IncludeItemTypes=Audio&SortBy=IndexNumber&Fields=%s" % (self.g_userId, jsonToStr(albumId), DEFAULT_ITEM_FIELDS))

	def _childrenUrl(self, itemId):
		return self.getContentUrl("/Users/%s/Items?ParentId=%s&Fields=%s" % (self.g_userId, jsonToStr(itemId), DEFAULT_ITEM_FIELDS))

	def _detailUrl(self, itemId):
		return self.getContentUrl("/Users/%s/Items/%s?Fields=%s" % (self.g_userId, jsonToStr(itemId), DETAIL_ITEM_FIELDS))

	#===============================================================================
	#
	#===============================================================================
	def _itemsFromAnswer(self, answer):
		"""Envelope dual parser: {Items: [...]}, the bare array some
		endpoints (/Users/{id}/Items/Latest) return, or a single item
		object (/Users/{uid}/Items/{id}) wrapped into a one-element list
		so the post-playback view refresh sees exactly one entry."""
		if answer is None:
			return None
		if isinstance(answer, list):
			return answer
		if isinstance(answer, dict):
			if "Items" in answer:
				return answer.get("Items", [])
			if "Id" in answer:
				return [answer]
			return []
		return []

	#===============================================================================
	#
	#===============================================================================
	def _browse(self, url, currentViewMode, defaultNextViewMode, defaultTagType, switchMedias=False):
		"""Shared list builder. Playable items follow the requested view
		modes; container items (series/seasons/albums/folders) get their
		drill-in target derived from their own type, which is exactly how
		mixed containers behaved on the Plex side."""
		printl("url: " + str(url), self, "D")

		if not self.ensureAuthenticated():
			return [], {}

		answer = self.getJsonPaged(url)
		items = self._itemsFromAnswer(answer)
		if items is None:
			if not self.lastError:
				self.lastError = _("No data in this section!")
			return [], {}

		fullList = []
		for item in items:
			itemType = item.get("Type")
			entryData = self.itemToEntryData(item)
			entryData["server"] = self.g_address
			entryData["currentViewMode"] = currentViewMode

			if itemType in ("Movie", "Episode", "Video", "MusicVideo"):
				entryData["nextViewMode"] = "play"
				entryData["tagType"] = defaultTagType if defaultTagType in ("Video", "Track") else "Video"
				if itemType == "Episode" and entryData.get("index"):
					entryData["title"] = entryData["index"] + ". " + entryData["title"]
				entryData["mediaDataArr"] = self.buildMediaDataArr(item)
				entryData["contentUrl"] = self._detailUrl(item.get("Id"))
				self._attachImages(entryData, item, switchMedias=switchMedias or itemType == "Episode")
				viewState = self.getViewStatefromViewCount(entryData)
				nextUrl = self._detailUrl(item.get("Id"))

			elif itemType == "Audio":
				entryData["nextViewMode"] = "play"
				entryData["tagType"] = "Track"
				entryData["mediaDataArr"] = self.buildMediaDataArr(item)
				entryData["contentUrl"] = self._detailUrl(item.get("Id"))
				self._attachImages(entryData, item)
				viewState = self.getViewStatefromViewCount(entryData)
				nextUrl = self._detailUrl(item.get("Id"))

			elif itemType == "Series":
				entryData["nextViewMode"] = "ShowSeasons"
				entryData["tagType"] = "Show"
				entryData["type"] = "show"
				self._attachImages(entryData, item)
				viewState = self.getViewStateForShowEntry(entryData)
				nextUrl = self._seasonsUrl(item.get("Id"))
				entryData["contentUrl"] = nextUrl

			elif itemType == "Season":
				entryData["nextViewMode"] = "ShowEpisodes"
				entryData["tagType"] = "Episodes"
				self._attachImages(entryData, item)
				viewState = self.getViewStateForShowEntry(entryData)
				nextUrl = self._episodesUrl(item.get("SeriesId"), item.get("Id"))
				entryData["contentUrl"] = nextUrl

			elif itemType == "MusicArtist":
				entryData["nextViewMode"] = "ShowAlbums"
				entryData["tagType"] = "Directory"
				self._attachImages(entryData, item)
				viewState = None
				nextUrl = self._albumsOfArtistUrl(item.get("Id"))
				entryData["contentUrl"] = nextUrl

			elif itemType == "MusicAlbum":
				entryData["nextViewMode"] = "ShowTracks"
				entryData["tagType"] = "Directory"
				self._attachImages(entryData, item)
				viewState = None
				nextUrl = self._tracksOfAlbumUrl(item.get("Id"))
				entryData["contentUrl"] = nextUrl

			elif itemType in ("Folder", "BoxSet", "CollectionFolder"):
				entryData["nextViewMode"] = "mixed"
				entryData["tagType"] = "Directory"
				entryData["type"] = "Folder"
				self._attachImages(entryData, item)
				viewState = None
				nextUrl = self._childrenUrl(item.get("Id"))
				entryData["contentUrl"] = nextUrl

			else:
				printl("skipping unsupported item type: " + str(itemType), self, "D")
				continue

			fullList.append(self.getFullListEntry(entryData, nextUrl, viewState))

		if not fullList and not self.lastError:
			self.lastError = _("No data in this section!")

		mediaContainer = {"size": jsonToStr(len(fullList))}
		return fullList, mediaContainer

	#===============================================================================
	#
	#===============================================================================
	def getMoviesFromSection(self, url):
		return self._browse(url, currentViewMode="ShowMovies", defaultNextViewMode="play", defaultTagType="Video")

	def getMixedContentFromSection(self, url, fromRemotePlayer=False):
		return self._browse(url, currentViewMode="ShowMovies", defaultNextViewMode="play", defaultTagType="Video")

	def getShowsFromSection(self, url):
		return self._browse(url, currentViewMode="ShowShows", defaultNextViewMode="ShowSeasons", defaultTagType="Show")

	def getSeasonsOfShow(self, url):
		return self._browse(url, currentViewMode="ShowSeasons", defaultNextViewMode="ShowEpisodes", defaultTagType="Episodes")

	def getEpisodesOfSeason(self, url, directMode=False):
		currentViewMode = "ShowEpisodesDirect" if directMode else "ShowEpisodes"
		return self._browse(url, currentViewMode=currentViewMode, defaultNextViewMode="play", defaultTagType="Video", switchMedias=True)

	def getMusicByArtist(self, url):
		return self._browse(url, currentViewMode="ShowArtists", defaultNextViewMode="ShowAlbums", defaultTagType="Directory")

	def getMusicByAlbum(self, url):
		return self._browse(url, currentViewMode="ShowAlbums", defaultNextViewMode="ShowTracks", defaultTagType="Directory")

	def getMusicTracks(self, url):
		return self._browse(url, currentViewMode="ShowTracks", defaultNextViewMode="play", defaultTagType="Track")

	#===============================================================================
	# PLAYBACK SURFACE (phase 3: direct play + progress + watched + resume)
	# transcode(), local-file resolution and audio/subtitle preselection are
	# phase 4; here every path plays the direct stream URL.
	#===============================================================================

	def appendTokenToUrl(self, url):
		"""Media players cannot send auth headers, so the token travels as
		api_key inside the playback/theme URLs themselves."""
		if not url or not self.g_accessToken or "api_key=" in url:
			return url
		separator = "&" if "?" in url else "?"
		return url + separator + "api_key=" + self.g_accessToken

	#===============================================================================
	#
	#===============================================================================
	def getAudioSubtitlesMedia(self, server, myId, myType="Video", loadExtraData=False):
		"""Fetch the item detail and build the 'streams' dict the player
		reads: one 8-tuple part per MediaSource (= one version), plus the
		videoData/mediaData the detail panel shows. Never raises."""
		printl("myId: " + str(myId), self, "S")

		empty = {
			"partsCount": 0, "parts": [], "sourceIds": [],
			"videoData": {"title": "", "tagline": "", "summary": "", "year": "",
						"studio": "", "viewOffset": "0", "duration": "", "contentRating": ""},
			"mediaData": {}, "contents": "", "audio": {}, "audioCount": 0,
			"subtitle": {}, "subCount": 0, "external": {}, "subOffset": -1, "audioOffset": -1,
		}

		# tráilers/extras: one selectable part per LocalTrailer. The UI reads
		# the trailer id at index 5 (DP_View.selectMedia) to play it.
		if loadExtraData:
			trailers = self._itemsFromAnswer(
				self.getJson(self.getContentUrl("/Users/%s/Items/%s/LocalTrailers" % (self.g_userId, jsonToStr(myId))))) or []
			parts = []
			for index, trailer in enumerate(trailers):
				trailerId = jsonToStr(trailer.get("Id"))
				key = "/Videos/%s/stream?static=true" % trailerId
				parts.append((
					key,                                   # 0 stream url
					jsonToStr(trailer.get("Name")),        # 1 label
					jsonToStr(trailer.get("Container")),   # 2 container
					"",                                    # 3 size
					"",                                    # 4 duration
					trailerId,                             # 5 id (DP_View.selectMedia reads items[5])
					"",                                    # 6 codec
					index,                                 # 7 mediaIndex
				))
			streams = dict(empty)
			streams["partsCount"] = len(parts)
			streams["parts"] = parts
			printl("trailers: " + str(len(parts)), self, "C")
			return streams

		item = self.getJson(self._detailUrl(myId))
		self.lastResponse = item
		if not item or not isinstance(item, dict):
			if not self.lastError:
				self.lastError = _("No data in this section!")
			printl("", self, "C")
			return empty

		entryData = self.itemToEntryData(item)
		videoData = {
			"title": entryData.get("title", ""),
			"tagline": entryData.get("tagline", ""),
			"summary": entryData.get("summary", ""),
			"year": entryData.get("year", ""),
			"studio": entryData.get("studio", ""),
			"viewOffset": entryData.get("viewOffset", "0"),
			"duration": entryData.get("duration", ""),
			"contentRating": entryData.get("contentRating", ""),
		}
		mediaDataArr = self.buildMediaDataArr(item)
		mediaData = mediaDataArr[0] if mediaDataArr else {}

		parts = []
		sourceIds = []
		for index, source in enumerate(item.get("MediaSources") or []):
			sourceId = jsonToStr(source.get("Id"))
			videoResolution = ""
			videoCodec = ""
			for stream in source.get("MediaStreams") or []:
				if stream.get("Type") == "Video":
					videoResolution = self._mapResolution(stream.get("Width"), stream.get("Height"))
					videoCodec = jsonToStr(stream.get("Codec"))
					break
			key = "/Videos/%s/stream?static=true&MediaSourceId=%s" % (jsonToStr(myId), sourceId)
			part = (
				key,
				jsonToStr(source.get("Path")),
				jsonToStr(source.get("Container")),
				jsonToStr(source.get("Size")),
				jsonToStr(ticksToMs(source["RunTimeTicks"])) if source.get("RunTimeTicks") else "",
				videoResolution,
				videoCodec,
				index,  # mediaIndex -> setSelectedVersion -> MediaSources[index]
			)
			parts.append(part)
			sourceIds.append(sourceId)

		streams = dict(empty)
		streams["partsCount"] = len(parts)
		streams["parts"] = parts
		streams["sourceIds"] = sourceIds
		streams["videoData"] = videoData
		streams["mediaData"] = mediaData
		streams["_item"] = item  # reused by the audio/subtitle stream dialogs
		self.g_currentMediaSourceId = sourceIds[0] if sourceIds else jsonToStr(myId)

		printl("parts: " + str(len(parts)), self, "C")
		return streams

	#===============================================================================
	#
	#===============================================================================
	def _sourceIdForIndex(self, index):
		if index is None or not self.streams:
			return None
		sourceIds = self.streams.get("sourceIds") or []
		try:
			return sourceIds[int(index)]
		except (IndexError, TypeError, ValueError):
			return None

	def getMediaOptionsToPlay(self, myId, vids, override=False, myType="Video", loadExtraData=False):
		"""(partsCount, parts, server) - one part per version. count>1 makes
		the player raise the 'Select media to play' version dialog."""
		self.g_selectedMediaIndex = None
		self.server = self.g_address
		self.streams = self.getAudioSubtitlesMedia(self.server, myId, myType, loadExtraData)
		return self.streams["partsCount"], self.streams["parts"], self.server

	def setSelectedVersion(self, mediaIndex):
		"""Remember which MediaSource the version dialog picked."""
		self.g_selectedMediaIndex = mediaIndex

	def setPlaybackType(self, myType):
		"""Streamed/Transcoded/Direct-Local flags. Phase 3 plays direct for
		all three; transcode() and local resolution arrive in phase 4."""
		myType = str(myType)
		if myType == "1":  # Transcoded
			self.g_transcode = "true"
			self.g_stream = "1"
		elif myType == "2":  # Direct Local
			self.g_transcode = "false"
			self.g_stream = "0"
		else:  # "0" Streamed
			self.g_transcode = "false"
			self.g_stream = "1"

	def mediaType(self, partData, server):
		"""Turn the picked part into the absolute direct-stream URL. Direct
		Local/SMB resolution is phase 4; here everything streams direct."""
		self.fallback = False
		self.locations = ""
		self.currentFile = partData.get("file", "")
		return "%s://%s%s" % (self.http, server, partData["key"])

	#===============================================================================
	#
	#===============================================================================
	def playLibraryMedia(self, myId, url, isExtraData=False):
		"""Build the playerData dict setPlayerData()/playSelectedMedia() read.
		No network here (phase 3 direct play); the URL is already resolved."""
		printl("myId: " + str(myId), self, "S")

		# one PlaySessionId per playback, minted BEFORE the URL is built so the
		# transcode request and the progress reports travel under the same
		# session. Reusing the device id for both made the server see every
		# playback of the run as the same session.
		self.g_playSessionId = newPlaybackId()
		printl("playSessionId: " + str(self.g_playSessionId), self, "D")

		if self.streams is None:
			self.streams = self.getAudioSubtitlesMedia(self.server, myId, "Video", False)

		videoData = self.streams.get("videoData", {})
		try:
			resume = int(videoData.get("viewOffset") or 0)  # milliseconds
		except (TypeError, ValueError):
			resume = 0

		sourceId = self._sourceIdForIndex(self.g_selectedMediaIndex)
		if not sourceId:
			sourceIds = self.streams.get("sourceIds") or []
			sourceId = sourceIds[0] if sourceIds else jsonToStr(myId)
		self.g_currentMediaSourceId = sourceId

		# transcoded playback (playbackType 1) swaps the direct URL for the
		# HLS/progressive transcode URL; direct/local keep the resolved url
		if self.g_transcode == "true" and not isExtraData:
			playUrl = self.transcode(myId, url)
		else:
			playUrl = self.appendTokenToUrl(url)

		playerData = {
			"playUrl": playUrl,
			"resumeStamp": resume,
			"server": self.server,
			"id": jsonToStr(myId),
			"mediaSourceId": sourceId,
			"multiUserServer": True,  # Emby/Jellyfin always expose /Sessions
			"playbackType": self.serverConfig_playbackType,
			"connectionType": self.serverConfig_connectionType,
			"localAuth": False,
			"transcodingSession": self.g_playSessionId,
			"universalTranscoder": self.serverConfig_universalTranscoder,
			"videoData": videoData,
			"mediaData": self.streams.get("mediaData", {}),
			"fallback": self.fallback,
			"locations": self.locations,
			"currentFile": self.currentFile,
			"subtitleFileTemp": None,
			"usingExtForcedSubs": False,
		}
		printl("", self, "C")
		return playerData

	#===============================================================================
	# PROGRESS / WATCHED REPORTING (POST bodies carry ticks = ms * 10000)
	#===============================================================================

	def _postJson(self, path, body):
		"""POST a JSON body; True on any non-error answer (incl. 204)."""
		answer = self.getJson(self.getContentUrl(path), myType="POST", body=json.dumps(body))
		return answer is not None

	def reportPlaybackStart(self, itemId, positionMs=0, isPaused=False, mediaSourceId=None):
		body = {
			"ItemId": jsonToStr(itemId),
			"MediaSourceId": mediaSourceId or self.g_currentMediaSourceId or jsonToStr(itemId),
			"PlaySessionId": self.g_playSessionId,
			"PositionTicks": msToTicks(positionMs),
			"IsPaused": bool(isPaused),
			"CanSeek": True,
			"PlayMethod": "Transcode" if self.g_transcode == "true" else "DirectStream",
		}
		return self._postJson("/Sessions/Playing", body)

	def reportProgress(self, itemId, positionMs, isPaused=False, mediaSourceId=None):
		body = {
			"ItemId": jsonToStr(itemId),
			"MediaSourceId": mediaSourceId or self.g_currentMediaSourceId or jsonToStr(itemId),
			"PlaySessionId": self.g_playSessionId,
			"PositionTicks": msToTicks(positionMs),
			"IsPaused": bool(isPaused),
			"CanSeek": True,
		}
		return self._postJson("/Sessions/Playing/Progress", body)

	def reportStopped(self, itemId, positionMs, mediaSourceId=None):
		body = {
			"ItemId": jsonToStr(itemId),
			"MediaSourceId": mediaSourceId or self.g_currentMediaSourceId or jsonToStr(itemId),
			"PlaySessionId": self.g_playSessionId,
			"PositionTicks": msToTicks(positionMs),
		}
		return self._postJson("/Sessions/Playing/Stopped", body)

	#===============================================================================
	# CONTEXT-MENU ACTIONS (the right HTTP verb is the whole point)
	#===============================================================================

	def markWatched(self, itemId):
		url = self.getContentUrl("/Users/%s/PlayedItems/%s" % (self.g_userId, jsonToStr(itemId)))
		return self.getJson(url, myType="POST") is not None

	def markUnwatched(self, itemId):
		url = self.getContentUrl("/Users/%s/PlayedItems/%s" % (self.g_userId, jsonToStr(itemId)))
		return self.getJson(url, myType="DELETE") is not None

	def refreshItem(self, itemId):
		url = self.getContentUrl("/Items/%s/Refresh" % jsonToStr(itemId))
		return self.getJson(url, myType="POST") is not None

	def deleteItem(self, itemId):
		url = self.getContentUrl("/Items/%s" % jsonToStr(itemId))
		return self.getJson(url, myType="DELETE") is not None

	#===============================================================================
	#
	#===============================================================================
	def getItemUrl(self, itemId):
		"""Single-item detail URL, for the post-playback view-state refresh."""
		return self._detailUrl(itemId)

	def getThemeUrl(self, itemId):
		"""Series theme song stream URL (with api_key), or '' if none."""
		answer = self.getJson(self.getContentUrl("/Items/%s/ThemeSongs" % jsonToStr(itemId)))
		items = self._itemsFromAnswer(answer) or []
		if not items:
			return ""
		themeId = jsonToStr(items[0].get("Id"))
		if not themeId:
			return ""
		return self.appendTokenToUrl(self.getContentUrl("/Audio/%s/stream?static=true" % themeId))

	#===============================================================================
	# TRANSCODING (phase 4). The gstreamer HLS gate on OpenATV 6.4 is verified
	# on the box; a config/auto progressive .ts fallback is offered for hlsdemux
	# builds that choke on the m3u8.
	#===============================================================================

	def getTranscodeVideoCodec(self):
		"""Output codec picked for this server, h264 when unset."""
		return jsonToStr(getattr(self.g_serverConfig, "transcodeVideoCodec", _emptyConfig("h264")).value) or "h264"

	def getUniversalTranscoderSettings(self):
		"""(MaxWidth, MaxHeight, VideoBitrate) for the picked quality.

		Each codec has its own ladder - see UNI_QUALITY_HEVC_TABLE for why hevc
		does not reuse the h264 one. A server entry written before that ladder
		existed carries no uniQualityHevc and falls back to its default step.
		"""
		if self.getTranscodeVideoCodec() == "hevc":
			quality = jsonToStr(getattr(self.g_serverConfig, "uniQualityHevc", _emptyConfig("3")).value)
			if quality in UNI_QUALITY_HEVC_TABLE:
				return UNI_QUALITY_HEVC_TABLE[quality]
			# a value left behind by a build whose ladder had more steps (it used
			# to reach 9): honour the intent - the best quality - instead of
			# silently falling back to the default, which would be a downgrade.
			# Only for steps that really existed: anything else is garbage and
			# must NOT be read as "give me the heaviest transcode you have".
			top = max(UNI_QUALITY_HEVC_TABLE, key=int)
			try:
				if int(top) < int(quality) <= FORMER_UNI_QUALITY_HEVC_TOP:
					return UNI_QUALITY_HEVC_TABLE[top]
			except (TypeError, ValueError):
				pass
			return DEFAULT_UNI_QUALITY_HEVC

		quality = jsonToStr(getattr(self.g_serverConfig, "uniQuality", _emptyConfig("3")).value)
		return UNI_QUALITY_TABLE.get(quality, DEFAULT_UNI_QUALITY)

	def _transcodeStreamParams(self):
		"""Common query params for the transcode request (quality + the audio/
		subtitle stream indices the dialogs picked)."""
		maxWidth, maxHeight, videoBitrate = self.getUniversalTranscoderSettings()
		sourceId = self.g_currentMediaSourceId or ""
		# h264 for max compatibility (older gstreamer / 6.4); hevc for better
		# quality at a lower bitrate on boxes that decode HEVC (per server)
		videoCodec = self.getTranscodeVideoCodec()
		params = [
			("DeviceId", self.g_sessionID),
			("MediaSourceId", sourceId),
			("PlaySessionId", self.g_playSessionId),
			("VideoCodec", videoCodec),
			("AudioCodec", "aac,mp3,ac3"),
			("MaxWidth", jsonToStr(maxWidth)),
			("MaxHeight", jsonToStr(maxHeight)),
			("VideoBitrate", jsonToStr(videoBitrate)),
			("AudioBitrate", "192000"),
		]
		if self.g_audioStreamIndex is not None:
			params.append(("AudioStreamIndex", jsonToStr(self.g_audioStreamIndex)))
		if self.g_subtitleStreamIndex is not None:
			params.append(("SubtitleStreamIndex", jsonToStr(self.g_subtitleStreamIndex)))
		return params

	def _progressive(self):
		return bool(getattr(self.g_serverConfig, "progressiveTranscode", _emptyConfig(False)).value)

	def transcode(self, myId, url):
		"""Resolve the URL the player feeds to gstreamer for a transcode.

		Default: HLS master.m3u8 (SegmentContainer=ts, SubtitleMethod=Encode);
		the master playlist is prefetched so the server spins up the session,
		its last non-comment line absolutized and given an api_key, with the
		master URL itself as the fallback (hlsdemux resolves it). When the
		server entry asks for a progressive stream, hand over /stream.ts.

		The playlist covers the WHOLE media (VOD, with ENDLIST) - measured on
		Emby 4.9 and Jellyfin 10.11 - so a seek is served by moving inside it,
		not by asking the server for a new stream: both ignore StartTimeTicks
		here (identical playlist with and without it, 2026-07-25).
		"""
		printl("myId: " + str(myId), self, "S")

		params = self._transcodeStreamParams()

		if self._progressive():
			# progressive fallback: a single .ts the old hlsdemux can play
			progressive = [(k, v) for (k, v) in params if k not in ("PlaySessionId", "AudioCodec")]
			path = "/Videos/%s/stream.ts?%s" % (jsonToStr(myId), self._encodeParams(progressive))
			resolved = self.appendTokenToUrl(self.getContentUrl(path))
			printl("progressive transcode URL: " + resolved, self, "C")
			return resolved

		hlsParams = list(params) + [("SegmentContainer", "ts"), ("SubtitleMethod", "Encode")]
		masterPath = "/Videos/%s/master.m3u8?%s" % (jsonToStr(myId), self._encodeParams(hlsParams))
		masterUrl = self.appendTokenToUrl(self.getContentUrl(masterPath))

		resolved = self._prefetchMasterPlaylist(masterUrl)
		printl("transcode URL: " + str(resolved), self, "C")
		return resolved

	@staticmethod
	def _encodeParams(pairs):
		return "&".join("%s=%s" % (k, v) for k, v in pairs)

	def _prefetchMasterPlaylist(self, masterUrl):
		"""GET the master playlist so the server starts the encode, then hand
		the player the media playlist it points at (absolutized, with api_key).
		Falls back to the master URL itself on any hiccup."""
		payload = self.doRequest(masterUrl, timeout=PAGED_REQUEST_TIMEOUT)
		if not payload:
			return masterUrl

		base = masterUrl.split("?", 1)[0].rsplit("/", 1)[0]
		lastUrl = None
		try:
			for raw in payload.decode("utf-8", "replace").splitlines():
				line = raw.strip()
				if not line or line.startswith("#"):
					continue
				if line.startswith("http"):
					lastUrl = line
				else:
					lastUrl = "%s/%s" % (base, line)
		except Exception as ex:
			printl("master playlist parse failed: " + str(ex), self, "W")

		if not lastUrl:
			return masterUrl
		return self.appendTokenToUrl(lastUrl)

	def stopEncoding(self):
		"""Tear down the active transcode session (best effort)."""
		path = "/Videos/ActiveEncodings?DeviceId=%s&PlaySessionId=%s" % (self.g_sessionID, self.g_playSessionId)
		self.getJson(self.getContentUrl(path), myType="DELETE")
		return True

	#===============================================================================
	# AUDIO / SUBTITLE STREAMS. Emby has no server-side "set active stream"; the
	# dialogs store the picked MediaStream Index, consumed by transcode().
	#===============================================================================

	def _streamsOfType(self, itemId, streamType):
		item = self.streams.get("_item") if self.streams else None
		if not item:
			item = self.getJson(self._detailUrl(itemId))
		rows = []
		for source in (item or {}).get("MediaSources") or []:
			sourceId = jsonToStr(source.get("Id"))
			for stream in source.get("MediaStreams") or []:
				if stream.get("Type") != streamType:
					continue
				rows.append({
					"language": jsonToStr(stream.get("DisplayTitle") or stream.get("Language") or streamType),
					"languageCode": jsonToStr(stream.get("Language")),
					"id": jsonToStr(stream.get("Index")),
					"partid": sourceId,
					"selected": "1" if stream.get("IsDefault") else "",
					# the subtitle menu labels forced tracks; without this key it
					# used to KeyError('forced') and crash the TEXT menu
					"forced": "1" if stream.get("IsForced") else "",
				})
		return rows

	def getAudioById(self, server=None, itemId=None):
		return self._streamsOfType(itemId, "Audio")

	def getSubtitleById(self, server=None, itemId=None):
		return self._streamsOfType(itemId, "Subtitle")

	def setAudioById(self, server=None, stream_id=None, part_id=None):
		"""Remember the audio MediaStream Index for the next transcode."""
		try:
			self.g_audioStreamIndex = int(stream_id)
		except (TypeError, ValueError):
			self.g_audioStreamIndex = None

	def setSubtitleById(self, server=None, stream_id=None, part_id=None):
		try:
			self.g_subtitleStreamIndex = int(stream_id)
		except (TypeError, ValueError):
			self.g_subtitleStreamIndex = None

	def getSelectedEmbeddedSubtitleData(self):
		return None

	def getSelectedSubtitleDataById(self, server=None, itemId=None, forcedOnly=False):
		"""Forced-subtitle auto-preselection for the transcode path. Not
		implemented for the Emby/Jellyfin backend (subtitles are chosen
		explicitly via the TEXT menu -> setSubtitleById); return None so the
		player skips it instead of crashing with AttributeError when the
		'useForcedSubtitles' + transcode config path calls this."""
		return None

	def getLastResponse(self):
		return self.lastResponse or self.lastError

	#===============================================================================
	#
	#===============================================================================
	def get_hTokenForServer(self, server=None):
		"""Image/download auth travels as api_key inside the URLs the
		backend hands out, so no extra header is needed."""
		return {}

	#===============================================================================
	# MISC SURFACE THE UI RELIES ON
	#===============================================================================

	def getLastErrorMessage(self):
		return self.lastError

	def getServerConfig(self):
		return self.g_serverConfig

	def sessionID(self):
		return self.g_sessionID

	def getServerName(self):
		return self.serverConfig_Name


def _emptyConfig(default=""):
	"""Stand-in for config attributes older entries do not have yet."""
	class _Empty(object):
		def __init__(self, value):
			self.value = value
	return _Empty(default)
