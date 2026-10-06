# -*- coding: utf-8 -*-
"""Phase 4: transcode URL building, quality table, stopEncoding, the
audio/subtitle stream indices and trailers, against the Emby mock."""

import unittest

try:
	from urllib.parse import urlparse, parse_qs
except ImportError:  # py2
	from urlparse import urlparse, parse_qs

from tests import helpers
from tests.embymock import MockEmby

helpers.setup_environment()

from src.DP_EmbyLibrary import UNI_QUALITY_TABLE, UNI_QUALITY_HEVC_TABLE  # noqa: E402

AUTH_PATH = "/Users/AuthenticateByName"
EMBY_UID = "user0000000000000000000000000001"
MOVIE_ID = "104906"
ITEM_B = "222847"


def _track(kind, index, language, title, default=False, forced=False):
	return {"Type": kind, "Index": index, "Language": language, "DisplayTitle": title,
		"IsDefault": default, "IsForced": forced}


# title A: two versions whose tracks carry DIFFERENT indices, and a forced
# subtitle only the first one has
DETAIL_A = {"Id": MOVIE_ID, "Name": "A", "Type": "Movie", "UserData": {"PlayCount": 0}, "MediaSources": [
	{"Id": "src-0", "Container": "mkv", "MediaStreams": [
		{"Type": "Video", "Codec": "hevc", "Width": 1920, "Height": 800, "Index": 0},
		_track("Audio", 1, "spa", "Spanish AAC 5.1", default=True),
		_track("Audio", 2, "chi", "Chinese AAC 5.1"),
		_track("Subtitle", 3, "spa", "Spanish (Forced SUBRIP)", forced=True),
		_track("Subtitle", 4, "spa", "Spanish (SUBRIP)")]},
	{"Id": "src-1", "Container": "mkv", "MediaStreams": [
		{"Type": "Video", "Codec": "hevc", "Width": 3840, "Height": 1600, "Index": 0},
		_track("Audio", 1, "chi", "Chinese AAC 5.1"),
		_track("Audio", 2, "spa", "Spanish AAC 5.1", default=True),
		_track("Subtitle", 3, "spa", "Spanish (SUBRIP)"),
		_track("Subtitle", 4, "eng", "English (SUBRIP)")]}]}  # only this version
# title B: the same numbering as A's first version, other languages
DETAIL_B = {"Id": ITEM_B, "Name": "B", "Type": "Movie", "UserData": {"PlayCount": 0}, "MediaSources": [
	{"Id": "src-b", "Container": "mkv", "MediaStreams": [
		{"Type": "Video", "Codec": "h264", "Width": 1920, "Height": 808, "Index": 0},
		_track("Audio", 1, "spa", "Spanish AAC 5.1", default=True),
		_track("Audio", 2, "fre", "French AAC 5.1"),
		_track("Subtitle", 3, "spa", "Spanish (SUBRIP)"),
		_track("Subtitle", 4, "eng", "English (SUBRIP)")]}]}


def wire_auth(mock):
	mock.add_json(AUTH_PATH, helpers.fixture_json("auth_ok_emby.json"), method="POST")
	mock.add_json("/System/Info/Public", helpers.fixture_json("system_info_public_emby.json"))


def query_of(url):
	return parse_qs(urlparse(url).query)


class TranscodeTestCase(unittest.TestCase):

	def setUp(self):
		self.mock = MockEmby().start()
		wire_auth(self.mock)
		self.lib = helpers.make_emby_instance(self.mock)
		self.assertTrue(self.lib.authenticate())
		self.lib.g_currentMediaSourceId = "src-0"

	def tearDown(self):
		self.mock.stop()


class TestQualityTable(TranscodeTestCase):

	def test_selected_quality_maps_to_dimensions(self):
		self.lib.g_serverConfig.uniQuality.value = "7"
		self.assertEqual(self.lib.getUniversalTranscoderSettings(), (1920, 1080, 10000000))

	def test_unknown_quality_falls_back_to_default(self):
		self.lib.g_serverConfig.uniQuality.value = "999"
		self.assertEqual(self.lib.getUniversalTranscoderSettings(), (1024, 768, 2000000))

	def test_table_is_complete(self):
		for key in "0123456789":
			self.assertIn(key, UNI_QUALITY_TABLE)


class _Val(object):
	"""Minimal stand-in for a ConfigSelection (just the .value)."""

	def __init__(self, value):
		self.value = value


class TestHevcQualityLadder(TranscodeTestCase):
	"""hevc gets its own ladder: the same bitrates as h264 but a bigger frame
	at every step, and top steps past the 1080p ceiling only h264 needs."""

	def test_h264_ladder_is_untouched(self):
		self.lib.g_serverConfig.transcodeVideoCodec.value = "h264"
		self.lib.g_serverConfig.uniQuality.value = "4"
		self.assertEqual(self.lib.getUniversalTranscoderSettings(), (1280, 720, 3000000))

	def test_hevc_uses_its_own_ladder(self):
		self.lib.g_serverConfig.transcodeVideoCodec.value = "hevc"
		self.lib.g_serverConfig.uniQualityHevc.value = "4"
		# same 3 mbps as h264 step 4, but a 1080p frame instead of 720p
		self.assertEqual(self.lib.getUniversalTranscoderSettings(), (1920, 1080, 3000000))

	def test_hevc_goes_beyond_the_h264_ceiling(self):
		self.lib.g_serverConfig.transcodeVideoCodec.value = "hevc"
		self.lib.g_serverConfig.uniQualityHevc.value = "7"
		self.assertEqual(self.lib.getUniversalTranscoderSettings(), (3840, 2160, 10000000))

	def test_unknown_hevc_quality_falls_back_to_the_hevc_default(self):
		self.lib.g_serverConfig.transcodeVideoCodec.value = "hevc"
		self.lib.g_serverConfig.uniQualityHevc.value = "999"
		self.assertEqual(self.lib.getUniversalTranscoderSettings(), (1280, 720, 2000000))

	def test_server_entry_written_before_this_setting_still_works(self):
		# an entry saved by an older version carries no uniQualityHevc at all;
		# it must fall back to the hevc default step, not to the h264 ladder
		old = _Val(None)
		old.transcodeVideoCodec = _Val("hevc")
		old.uniQuality = _Val("7")  # would be 1920x1080@10mbps on the h264 ladder
		self.lib.g_serverConfig = old
		self.assertEqual(self.lib.getUniversalTranscoderSettings(), (1280, 720, 2000000))

	def test_hevc_table_is_complete(self):
		# stops at 7: measured on real servers, 12 and 20 Mbps deliver exactly
		# what 10 does, so those steps were three ways to ask for one picture
		for key in "01234567":
			self.assertIn(key, UNI_QUALITY_HEVC_TABLE)
		self.assertNotIn("8", UNI_QUALITY_HEVC_TABLE)
		self.assertNotIn("9", UNI_QUALITY_HEVC_TABLE)

	def test_same_bitrate_and_never_a_smaller_picture(self):
		"""The design rule: hevc spends its efficiency on resolution, so each
		step keeps the h264 bitrate and never asks for a smaller frame."""
		shared = set(UNI_QUALITY_TABLE) & set(UNI_QUALITY_HEVC_TABLE)
		self.assertTrue(shared)
		for key in shared:
			h264W, h264H, h264Rate = UNI_QUALITY_TABLE[key]
			hevcW, hevcH, hevcRate = UNI_QUALITY_HEVC_TABLE[key]
			self.assertEqual(hevcRate, h264Rate, "step %s changed the bitrate" % key)
			self.assertGreaterEqual(hevcW * hevcH, h264W * h264H, "step %s shrank the frame" % key)

	def test_a_step_from_a_longer_ladder_keeps_the_top_quality(self):
		# the ladder used to reach 9; a setting saved back then must not be
		# read as "no idea" and silently dropped to the default, which would
		# quietly downgrade somebody who had picked the very best step
		self.lib.g_serverConfig.transcodeVideoCodec.value = "hevc"
		self.lib.g_serverConfig.uniQualityHevc.value = "9"
		self.assertEqual(self.lib.getUniversalTranscoderSettings(),
			UNI_QUALITY_HEVC_TABLE["7"])

	def test_hevc_ladder_reaches_the_transcode_url(self):
		self.lib.g_serverConfig.transcodeVideoCodec.value = "hevc"
		self.lib.g_serverConfig.uniQualityHevc.value = "6"
		self.mock.add_raw("/Videos/%s/master.m3u8" % MOVIE_ID, "application/x-mpegURL",
			"#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=8000000\nmain.m3u8\n")
		self.lib.transcode(MOVIE_ID, "http://ignored")

		q = self.mock.requests_for("/Videos/%s/master.m3u8" % MOVIE_ID)[0]["query"]
		self.assertEqual(q.get("VideoCodec"), ["hevc"])
		self.assertEqual(q.get("MaxWidth"), ["2560"])
		self.assertEqual(q.get("MaxHeight"), ["1440"])
		self.assertEqual(q.get("VideoBitrate"), ["8000000"])


class TestPlaySessionId(TranscodeTestCase):
	"""PlaySessionId identifies ONE playback; DeviceId identifies the box.

	They used to be the same value, so the server saw every playback of the
	whole run under a single session.
	"""

	def test_play_session_id_is_not_the_device_id(self):
		self.assertTrue(self.lib.g_playSessionId)
		self.assertNotEqual(self.lib.g_playSessionId, self.lib.g_sessionID)

	def test_every_playback_mints_a_new_one(self):
		first = self.lib.g_playSessionId
		self.lib.playLibraryMedia(MOVIE_ID, "http://ignored")
		second = self.lib.g_playSessionId
		self.lib.streams = None  # a fresh media
		self.lib.playLibraryMedia(MOVIE_ID, "http://ignored")
		third = self.lib.g_playSessionId

		self.assertNotEqual(first, second)
		self.assertNotEqual(second, third)

	def test_the_device_id_survives_a_playback(self):
		device = self.lib.g_sessionID
		self.lib.playLibraryMedia(MOVIE_ID, "http://ignored")
		self.assertEqual(self.lib.g_sessionID, device, "DeviceId must identify the box, not the playback")

	def test_transcode_and_reports_travel_under_the_same_session(self):
		# a stream opened under one identity and progress reported under
		# another leaves the server unable to tie them together
		self.mock.add_raw("/Videos/%s/master.m3u8" % MOVIE_ID, "application/x-mpegURL",
			"#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=3000000\nmain.m3u8\n")
		self.lib.transcode(MOVIE_ID, "http://ignored")
		fromUrl = self.mock.requests_for("/Videos/%s/master.m3u8" % MOVIE_ID)[0]["query"].get("PlaySessionId")

		self.lib.reportProgress(MOVIE_ID, 1000)
		fromReport = self.mock.requests_for("/Sessions/Playing/Progress")[-1]["body"]["PlaySessionId"]

		self.assertEqual(fromUrl, [fromReport])


class TestTranscodeUrl(TranscodeTestCase):

	def _master(self, body=None):
		# by default the prefetch returns a relative media playlist line
		if body is None:
			body = "#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=3000000\nmain.m3u8\n"
		self.mock.add_raw("/Videos/%s/master.m3u8" % MOVIE_ID, "application/x-mpegURL", body)

	def test_master_url_carries_the_emby_params(self):
		self.lib.g_serverConfig.uniQuality.value = "4"  # 1280x720, 3mbps
		# capture the master.m3u8 request the prefetch makes
		self._master()
		self.lib.transcode(MOVIE_ID, "http://ignored")

		req = self.mock.requests_for("/Videos/%s/master.m3u8" % MOVIE_ID)[0]
		q = req["query"]
		self.assertEqual(q.get("VideoCodec"), ["h264"])
		self.assertEqual(q.get("AudioCodec"), ["aac,mp3,ac3"])
		self.assertEqual(q.get("MaxWidth"), ["1280"])
		self.assertEqual(q.get("MaxHeight"), ["720"])
		self.assertEqual(q.get("VideoBitrate"), ["3000000"])
		self.assertEqual(q.get("SegmentContainer"), ["ts"])
		self.assertEqual(q.get("SubtitleMethod"), ["Encode"])
		self.assertEqual(q.get("MediaSourceId"), ["src-0"])
		# the stream travels under the PLAYBACK session, while the box itself
		# is identified by DeviceId - they used to be the same value
		self.assertEqual(q.get("PlaySessionId"), [self.lib.g_playSessionId])
		self.assertEqual(q.get("DeviceId"), [self.lib.g_sessionID])
		self.assertIn("api_key", q)

	def test_video_codec_can_be_hevc(self):
		# boxes that decode HEVC (e.g. the SF8008) can ask the server to
		# transcode to HEVC for better quality at a lower bitrate
		self.lib.g_serverConfig.transcodeVideoCodec.value = "hevc"
		self._master()
		self.lib.transcode(MOVIE_ID, "http://ignored")

		q = self.mock.requests_for("/Videos/%s/master.m3u8" % MOVIE_ID)[0]["query"]
		self.assertEqual(q.get("VideoCodec"), ["hevc"])

	def test_prefetch_returns_absolutized_media_playlist(self):
		self._master("#EXTM3U\nmain.m3u8\n")
		resolved = self.lib.transcode(MOVIE_ID, "http://ignored")
		self.assertIn("/Videos/%s/main.m3u8" % MOVIE_ID, resolved)
		self.assertIn("api_key=", resolved)

	def test_prefetch_keeps_absolute_playlist_line(self):
		self._master("#EXTM3U\nhttps://cdn.example/live/x.m3u8\n")
		resolved = self.lib.transcode(MOVIE_ID, "http://ignored")
		self.assertTrue(resolved.startswith("https://cdn.example/live/x.m3u8"))

	def test_prefetch_failure_falls_back_to_master_url(self):
		# no route registered -> 404 -> falsy -> master URL is handed over
		resolved = self.lib.transcode(MOVIE_ID, "http://ignored")
		self.assertIn("/Videos/%s/master.m3u8" % MOVIE_ID, resolved)
		self.assertIn("api_key=", resolved)

	def test_audio_and_subtitle_indices_go_into_the_url(self):
		self._master()
		self.mock.add_json("/Users/%s/Items/%s" % (EMBY_UID, MOVIE_ID), DETAIL_A)
		# what the dialogs do: list the tracks, then hand back the picked row
		audio = [r for r in self.lib.getAudioById("srv", MOVIE_ID) if r["language"] == "Chinese AAC 5.1"][0]
		subtitle = [r for r in self.lib.getSubtitleById("srv", MOVIE_ID) if r["language"] == "Spanish (SUBRIP)"][0]
		self.lib.setAudioById("srv", audio["id"], audio["partid"])
		self.lib.setSubtitleById("srv", subtitle["id"], subtitle["partid"])
		self.lib.getMediaOptionsToPlay(MOVIE_ID, self.lib.g_address, False, myType="Video")
		self.lib.transcode(MOVIE_ID, "http://ignored")

		q = self.mock.requests_for("/Videos/%s/master.m3u8" % MOVIE_ID)[0]["query"]
		self.assertEqual(q.get("AudioStreamIndex"), ["2"])
		self.assertEqual(q.get("SubtitleStreamIndex"), ["4"])

	def test_without_a_pick_no_index_is_sent(self):
		self._master()
		self.mock.add_json("/Users/%s/Items/%s" % (EMBY_UID, MOVIE_ID), DETAIL_A)
		self.lib.getMediaOptionsToPlay(MOVIE_ID, self.lib.g_address, False, myType="Video")
		self.lib.transcode(MOVIE_ID, "http://ignored")

		q = self.mock.requests_for("/Videos/%s/master.m3u8" % MOVIE_ID)[0]["query"]
		self.assertNotIn("AudioStreamIndex", q)
		self.assertNotIn("SubtitleStreamIndex", q)

	def test_progressive_fallback_uses_stream_ts(self):
		self.lib.g_serverConfig.progressiveTranscode.value = True
		self.mock.add_raw("/Videos/%s/stream.ts" % MOVIE_ID, "video/mp2t", "x")
		resolved = self.lib.transcode(MOVIE_ID, "http://ignored")
		self.assertIn("/Videos/%s/stream.ts" % MOVIE_ID, resolved)
		q = query_of(resolved)
		self.assertEqual(q.get("VideoCodec"), ["h264"])
		self.assertIn("api_key", q)


class TestStopEncoding(TranscodeTestCase):

	def test_stop_encoding_deletes_active_encodings(self):
		self.mock.add_json("/Videos/ActiveEncodings", {}, method="DELETE")
		self.assertTrue(self.lib.stopEncoding())
		req = self.mock.requests_for("/Videos/ActiveEncodings")[0]
		self.assertEqual(req["method"], "DELETE")
		self.assertEqual(req["query"].get("DeviceId"), [self.lib.g_sessionID])
		# tear down THIS playback's encoding, not everything the box ever started
		self.assertEqual(req["query"].get("PlaySessionId"), [self.lib.g_playSessionId])

	def test_stop_encoding_never_raises_on_a_dead_server(self):
		self.mock.stop()  # server gone
		self.assertTrue(self.lib.stopEncoding())


class TestAudioSubtitleStreams(TranscodeTestCase):

	def _wire_detail(self):
		detail = {
			"Id": MOVIE_ID, "Name": "Movie", "Type": "Movie",
			"UserData": {"PlayCount": 0},
			"MediaSources": [{
				"Id": "src-0", "Container": "mkv",
				"MediaStreams": [
					{"Type": "Video", "Codec": "h264", "Width": 1920, "Height": 1080, "Index": 0},
					{"Type": "Audio", "Codec": "ac3", "Language": "spa", "DisplayTitle": "Espanol AC3", "Index": 1, "IsDefault": True},
					{"Type": "Audio", "Codec": "aac", "Language": "eng", "DisplayTitle": "English AAC", "Index": 2},
					{"Type": "Subtitle", "Language": "spa", "DisplayTitle": "Espanol", "Index": 3},
				],
			}],
		}
		self.mock.add_json("/Users/%s/Items/%s" % (EMBY_UID, MOVIE_ID), detail)

	def test_audio_streams_listed_with_index_as_id(self):
		self._wire_detail()
		audio = self.lib.getAudioById("srv", MOVIE_ID)
		self.assertEqual(len(audio), 2)
		self.assertEqual(audio[0]["id"], "1")
		self.assertEqual(audio[0]["selected"], "1")  # IsDefault
		self.assertEqual(audio[1]["id"], "2")
		self.assertEqual(audio[1]["selected"], "")

	def test_subtitle_streams_listed(self):
		self._wire_detail()
		subs = self.lib.getSubtitleById("srv", MOVIE_ID)
		self.assertEqual(len(subs), 1)
		self.assertEqual(subs[0]["id"], "3")
		# the subtitle menu reads each of these keys directly (item['forced']
		# etc.); a missing one is a KeyError crash on the box, which is exactly
		# what 'forced' did during the QA sweep.
		for key in ("language", "languageCode", "id", "partid", "selected", "forced"):
			self.assertIn(key, subs[0])

	def test_a_pick_is_kept_with_its_title_and_a_bad_row_clears_it(self):
		self._wire_detail()
		row = self.lib.getAudioById("srv", MOVIE_ID)[1]
		self.lib.setAudioById("srv", row["id"], row["partid"])
		self.assertEqual(self.lib.g_audioChoice[0], MOVIE_ID)
		self.lib.setAudioById("srv", "n/a", "src-0")
		self.assertIsNone(self.lib.g_audioChoice)


class TestTrackChoice(TranscodeTestCase):
	"""A track picked in the audio/subtitle dialogs belongs to the title it was
	picked for. It used to be a bare MediaStream Index kept for the whole
	server session: picking Chinese audio and full subtitles in one film made
	the next one play in French with English subtitles burned in, because
	Emby took index 2 and 4 of THAT film (seen on the box, 2026-10-06)."""

	def setUp(self):
		super(TestTrackChoice, self).setUp()
		self.mock.add_json("/Users/%s/Items/%s" % (EMBY_UID, MOVIE_ID), DETAIL_A)
		self.mock.add_json("/Users/%s/Items/%s" % (EMBY_UID, ITEM_B), DETAIL_B)

	def pick(self, itemId, kind, title):
		"""What a dialog callback does with the row the user chose."""
		rows = self.lib.getAudioById("srv", itemId) if kind == "Audio" else self.lib.getSubtitleById("srv", itemId)
		row = [r for r in rows if r["language"] == title][0]
		setter = self.lib.setAudioById if kind == "Audio" else self.lib.setSubtitleById
		setter("srv", row["id"], row["partid"])

	def play(self, itemId, sourceId=None):
		"""The stream params a transcode of this title would carry."""
		self.lib.getMediaOptionsToPlay(itemId, self.lib.g_address, False, myType="Video")
		if sourceId:
			self.lib.g_currentMediaSourceId = sourceId  # the version dialog's pick
		return dict(self.lib._transcodeStreamParams())

	def test_a_pick_goes_with_its_own_title(self):
		self.pick(MOVIE_ID, "Audio", "Chinese AAC 5.1")
		self.pick(MOVIE_ID, "Subtitle", "Spanish (SUBRIP)")

		params = self.play(MOVIE_ID, "src-0")
		self.assertEqual(params.get("AudioStreamIndex"), "2")
		self.assertEqual(params.get("SubtitleStreamIndex"), "4")

	def test_a_pick_does_not_follow_into_another_title(self):
		self.pick(MOVIE_ID, "Audio", "Chinese AAC 5.1")
		self.pick(MOVIE_ID, "Subtitle", "Spanish (SUBRIP)")

		params = self.play(ITEM_B)
		self.assertNotIn("AudioStreamIndex", params)
		self.assertNotIn("SubtitleStreamIndex", params)

	def test_a_pick_finds_its_track_in_the_other_version(self):
		self.pick(MOVIE_ID, "Audio", "Chinese AAC 5.1")  # index 2 in src-0

		self.assertEqual(self.play(MOVIE_ID, "src-1").get("AudioStreamIndex"), "1")

	def test_a_track_the_version_lacks_is_not_sent(self):
		self.pick(MOVIE_ID, "Subtitle", "Spanish (Forced SUBRIP)")  # only in src-0

		self.assertNotIn("SubtitleStreamIndex", self.play(MOVIE_ID, "src-1"))

	def test_the_dialog_lists_each_track_once(self):
		audio = self.lib.getAudioById("srv", MOVIE_ID)
		subtitles = self.lib.getSubtitleById("srv", MOVIE_ID)

		self.assertEqual(sorted(r["language"] for r in audio), ["Chinese AAC 5.1", "Spanish AAC 5.1"])
		self.assertEqual(sorted(r["language"] for r in subtitles),
			["English (SUBRIP)", "Spanish (Forced SUBRIP)", "Spanish (SUBRIP)"])

	def test_a_track_only_the_second_version_has_is_resolved_in_that_version(self):
		self.pick(MOVIE_ID, "Subtitle", "English (SUBRIP)")  # index 4 of src-1; src-0's 4 is Spanish

		self.assertEqual(self.play(MOVIE_ID, "src-1").get("SubtitleStreamIndex"), "4")
		self.assertNotIn("SubtitleStreamIndex", self.play(MOVIE_ID, "src-0"))

	def test_the_dialog_shows_this_titles_tracks_not_the_last_played(self):
		self.play(MOVIE_ID)  # leaves title A's detail cached for the player

		audio = self.lib.getAudioById("srv", ITEM_B)
		self.assertEqual(sorted(r["language"] for r in audio), ["French AAC 5.1", "Spanish AAC 5.1"])

	def test_a_row_that_is_not_there_clears_the_pick(self):
		self.pick(MOVIE_ID, "Audio", "Chinese AAC 5.1")
		self.lib.setAudioById("srv", "n/a", "src-0")

		self.assertNotIn("AudioStreamIndex", self.play(MOVIE_ID, "src-0"))


class TestTrailers(TranscodeTestCase):

	def test_local_trailers_become_selectable_parts_with_id_at_index_5(self):
		trailers = [{"Id": "trl-1", "Name": "Trailer 1", "Container": "mp4"},
					{"Id": "trl-2", "Name": "Trailer 2", "Container": "mp4"}]
		self.mock.add_json("/Users/%s/Items/%s/LocalTrailers" % (EMBY_UID, MOVIE_ID), trailers)

		count, parts, server = self.lib.getMediaOptionsToPlay(MOVIE_ID, None, loadExtraData=True)
		self.assertEqual(count, 2)
		self.assertEqual(parts[0][5], "trl-1")  # DP_View.selectMedia reads items[5]
		self.assertEqual(parts[0][1], "Trailer 1")
		self.assertIn("/Videos/trl-1/stream", parts[0][0])

	def test_no_trailers_returns_empty(self):
		self.mock.add_json("/Users/%s/Items/%s/LocalTrailers" % (EMBY_UID, MOVIE_ID), [])
		count, parts, server = self.lib.getMediaOptionsToPlay(MOVIE_ID, None, loadExtraData=True)
		self.assertEqual(count, 0)
		self.assertEqual(parts, [])


class TestMediaDataArr(TranscodeTestCase):
	"""buildMediaDataArr is the source of self.details['mediaDataArr']. It
	returns [] for an item the server sends with no MediaSources (a metadata-
	only 'coming soon' Movie/Episode). The media-pixmap handlers in DP_View
	index [0], so the empty case has to stay representable here - that is what
	_firstMediaData() guards against instead of an IndexError green screen."""

	def test_no_media_sources_yields_empty_arr(self):
		self.assertEqual(self.lib.buildMediaDataArr({"Id": "x", "Type": "Movie"}), [])
		self.assertEqual(self.lib.buildMediaDataArr({"Id": "y", "MediaSources": []}), [])

	def test_media_source_yields_one_entry_with_stream_data(self):
		arr = self.lib.buildMediaDataArr({"Id": "z", "MediaSources": [{
			"Id": "s0", "Container": "mkv", "Bitrate": 8000000,
			"MediaStreams": [
				{"Type": "Video", "Codec": "h264", "Width": 1920, "Height": 1080},
				{"Type": "Audio", "Codec": "ac3", "Channels": 6},
			],
		}]})
		self.assertEqual(len(arr), 1)
		self.assertEqual(arr[0]["videoCodec"], "h264")
		self.assertEqual(arr[0]["audioCodec"], "ac3")


class TestTranscodedPlayerData(TranscodeTestCase):

	def test_playbacktype_1_playurl_is_a_transcode_url(self):
		# one MediaSource for the detail fetch playLibraryMedia does
		detail = {"Id": MOVIE_ID, "Name": "Movie", "Type": "Movie",
				"UserData": {"PlayCount": 0},
				"MediaSources": [{"Id": "src-0", "Container": "mkv",
								"MediaStreams": [{"Type": "Video", "Codec": "h264", "Width": 1920, "Height": 1080}]}]}
		self.mock.add_json("/Users/%s/Items/%s" % (EMBY_UID, MOVIE_ID), detail)
		self.mock.add_raw("/Videos/%s/master.m3u8" % MOVIE_ID, "application/x-mpegURL", "#EXTM3U\nmain.m3u8\n")

		self.lib.setPlaybackType("1")  # transcoded
		directUrl = "http://%s/Videos/%s/stream?static=true" % (self.lib.g_address, MOVIE_ID)
		playerData = self.lib.playLibraryMedia(MOVIE_ID, directUrl)
		# playUrl is the resolved transcode playlist, not the direct stream
		self.assertIn("main.m3u8", playerData["playUrl"])
		self.assertNotIn("stream?static=true", playerData["playUrl"])


if __name__ == "__main__":
	unittest.main()
