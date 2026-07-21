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
		for key in "0123456789":
			self.assertIn(key, UNI_QUALITY_HEVC_TABLE)

	def test_same_bitrate_and_never_a_smaller_picture(self):
		"""The design rule: hevc spends its efficiency on resolution, so each
		step keeps the h264 bitrate and never asks for a smaller frame."""
		for key in UNI_QUALITY_TABLE:
			h264W, h264H, h264Rate = UNI_QUALITY_TABLE[key]
			hevcW, hevcH, hevcRate = UNI_QUALITY_HEVC_TABLE[key]
			self.assertEqual(hevcRate, h264Rate, "step %s changed the bitrate" % key)
			self.assertGreaterEqual(hevcW * hevcH, h264W * h264H, "step %s shrank the frame" % key)

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
		self.assertEqual(q.get("PlaySessionId"), [self.lib.g_sessionID])
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
		self.lib.setAudioById("srv", "3", "src-0")
		self.lib.setSubtitleById("srv", "5", "src-0")
		self.lib.transcode(MOVIE_ID, "http://ignored")

		q = self.mock.requests_for("/Videos/%s/master.m3u8" % MOVIE_ID)[0]["query"]
		self.assertEqual(q.get("AudioStreamIndex"), ["3"])
		self.assertEqual(q.get("SubtitleStreamIndex"), ["5"])

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
		self.assertEqual(req["query"].get("PlaySessionId"), [self.lib.g_sessionID])

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

	def test_set_index_stores_int_and_bad_value_clears(self):
		self.lib.setAudioById("srv", "2", "src-0")
		self.assertEqual(self.lib.g_audioStreamIndex, 2)
		self.lib.setAudioById("srv", "n/a", "src-0")
		self.assertIsNone(self.lib.g_audioStreamIndex)


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
