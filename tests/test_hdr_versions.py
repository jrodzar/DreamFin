# -*- coding: utf-8 -*-
"""A title with an HDR and an SDR version: the version dialog names the HDR
kind, and a box that cannot show HDR gets the SDR version first - as does one
that can, when the HDR version would reach it re-encoded (2026-10-06).

Why (2026-10-05): Emby never tone-maps HLG when it transcodes and keeps its
BT.2020/HLG signalling, which a box without HDR (a Zgemma H8.2H) shows black
with either of its players - while the very same transcode from an SDR
source plays. The dialog opens on its first entry, so the order decides what
a plain OK plays.
"""

import unittest

from tests import helpers
from tests.embymock import MockEmby

helpers.setup_environment()

import src.DP_EmbyLibrary as library  # noqa: E402

EMBY_UID = "user0000000000000000000000000001"
MOVIE_ID = "104906"
HLG_SOURCE = "mediasource_104906"  # version 0 on the server: 4K HEVC HLG
SDR_SOURCE = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"  # version 1: 1080p HEVC SDR
DETAIL_PATH = "/Users/%s/Items/%s" % (EMBY_UID, MOVIE_ID)


def wire_auth(mock):
	mock.add_json("/Users/AuthenticateByName", helpers.fixture_json("auth_ok_emby.json"), method="POST")
	mock.add_json("/System/Info/Public", helpers.fixture_json("system_info_public_emby.json"))


def source_of(option):
	return option[0].split("MediaSourceId=")[1].split("&")[0]


class _VersionsTest(object):
	BOX_HAS_HDR = None

	def setUp(self):
		self.mock = MockEmby().start()
		self.addCleanup(self.mock.stop)
		wire_auth(self.mock)
		self.mock.add_json(DETAIL_PATH, helpers.fixture_json("item_detail_hdr_versions_emby.json"))
		self.addCleanup(setattr, library, "boxSupportsHdr", library.boxSupportsHdr)
		library.boxSupportsHdr = lambda: self.BOX_HAS_HDR

	def options(self):
		lib = helpers.make_emby_instance(self.mock)
		self.assertTrue(lib.authenticate())
		count, options, server = lib.getMediaOptionsToPlay(MOVIE_ID, lib.g_address, False, myType="Video")
		self.assertEqual(count, 2)
		return lib, options, server

	def played(self, lib, option, server):
		"""The MediaSourceId a pick of this entry of the dialog plays."""
		lib.setSelectedVersion(option[7])  # what DP_Player does on a choice
		url = lib.mediaType({"key": option[0], "file": option[1]}, server)
		return lib.playLibraryMedia(MOVIE_ID, url)["mediaSourceId"]

	def test_the_dialog_names_the_hdr_kind(self):
		lib, options, server = self.options()

		self.assertEqual(dict((source_of(o), o[8]) for o in options), {HLG_SOURCE: "HLG", SDR_SOURCE: ""})


class TestOnABoxWithoutHdr(_VersionsTest, unittest.TestCase):
	BOX_HAS_HDR = False

	def test_the_sdr_version_comes_first(self):
		lib, options, server = self.options()

		self.assertEqual([source_of(o) for o in options], [SDR_SOURCE, HLG_SOURCE])

	def test_a_plain_ok_plays_the_sdr_version(self):
		lib, options, server = self.options()

		self.assertEqual(self.played(lib, options[0], server), SDR_SOURCE)

	def test_the_hdr_version_can_still_be_picked(self):
		lib, options, server = self.options()

		self.assertEqual(self.played(lib, options[1], server), HLG_SOURCE)


class TestOnABoxWithHdr(_VersionsTest, unittest.TestCase):
	BOX_HAS_HDR = True

	def test_the_server_order_is_kept(self):
		lib, options, server = self.options()

		self.assertEqual([source_of(o) for o in options], [HLG_SOURCE, SDR_SOURCE])

	def test_a_plain_ok_plays_the_first_version(self):
		lib, options, server = self.options()

		self.assertEqual(self.played(lib, options[0], server), HLG_SOURCE)


class TestOnABoxWithHdrWhenTheServerReencodes(_VersionsTest, unittest.TestCase):
	"""A box that CAN show HDR still gets the SDR version first when every HDR
	version would reach it re-encoded. Emby re-encodes HLG to 8 bits and keeps
	the HLG signalling; the SF8008 draws that with a green line on top, while
	the very same HLG copied in 10 bits plays clean (2026-10-06). The fixture:
	HLG 3840x1592 and SDR 1920x796, both HEVC at 4.2 Mbps."""
	BOX_HAS_HDR = True

	def options_with(self, mode, quality, codec="hevc"):
		step = {"uniQualityHevc": quality} if codec == "hevc" else {"uniQuality": quality}
		lib = helpers.make_emby_instance(self.mock, playbackType=mode, transcodeVideoCodec=codec, **step)
		self.assertTrue(lib.authenticate())
		lib.setPlaybackType(mode)  # what DP_Player does before asking for the versions
		count, options, server = lib.getMediaOptionsToPlay(MOVIE_ID, lib.g_address, False, myType="Video")
		self.assertEqual(count, 2)
		return lib, options, server

	def test_a_re_encoded_hdr_version_goes_after_the_sdr_one(self):
		lib, options, server = self.options_with("1", "4")  # 1920x1080, 3 Mbps

		self.assertEqual([source_of(o) for o in options], [SDR_SOURCE, HLG_SOURCE])

	def test_a_plain_ok_then_plays_the_sdr_version(self):
		lib, options, server = self.options_with("1", "4")

		self.assertEqual(self.played(lib, options[0], server), SDR_SOURCE)

	def test_an_hdr_version_the_step_lets_through_stays_first(self):
		lib, options, server = self.options_with("1", "7")  # 3840x2160, 10 Mbps: copied

		self.assertEqual([source_of(o) for o in options], [HLG_SOURCE, SDR_SOURCE])

	def serve_hlg_video(self, **fields):
		"""The fixture with the HLG version's video stream changed, so that a
		single limit is passed (the real one is over width, height AND
		bitrate at most steps, which hides a broken check)."""
		detail = helpers.fixture_json("item_detail_hdr_versions_emby.json")
		for source in detail["MediaSources"]:
			if source["Id"] == HLG_SOURCE:
				for stream in source["MediaStreams"]:
					if stream.get("Type") == "Video":
						stream.update(fields)
		self.mock.add_json(DETAIL_PATH, detail)

	def test_only_too_wide_is_a_re_encode(self):
		self.serve_hlg_video(Height=796)  # 3840x796 at 4.2 Mbps
		lib, options, server = self.options_with("1", "6")  # 2560x1440, 8 Mbps

		self.assertEqual([source_of(o) for o in options], [SDR_SOURCE, HLG_SOURCE])

	def test_only_too_tall_is_a_re_encode(self):
		self.serve_hlg_video(Width=1920)  # 1920x1592 at 4.2 Mbps
		lib, options, server = self.options_with("1", "6")  # 2560x1440, 8 Mbps

		self.assertEqual([source_of(o) for o in options], [SDR_SOURCE, HLG_SOURCE])

	def test_only_too_much_bitrate_is_a_re_encode(self):
		self.serve_hlg_video(Width=1920, Height=796)  # 1920x796 at 4.2 Mbps
		lib, options, server = self.options_with("1", "4")  # 1920x1080, 3 Mbps

		self.assertEqual([source_of(o) for o in options], [SDR_SOURCE, HLG_SOURCE])

	def test_only_another_codec_is_a_re_encode(self):
		self.serve_hlg_video(Width=1920, Height=796)  # fits the top h264 step but is hevc
		lib, options, server = self.options_with("1", "9", codec="h264")  # 1920x1080, 20 Mbps

		self.assertEqual([source_of(o) for o in options], [SDR_SOURCE, HLG_SOURCE])

	def test_a_version_within_every_limit_stays_first(self):
		self.serve_hlg_video(Width=1920, Height=796)  # 1920x796 at 4.2 Mbps, hevc
		lib, options, server = self.options_with("1", "6")  # 2560x1440, 8 Mbps: all within

		self.assertEqual([source_of(o) for o in options], [HLG_SOURCE, SDR_SOURCE])

	def test_without_a_transcode_the_hdr_version_stays_first(self):
		lib, options, server = self.options_with("0", "4")

		self.assertEqual([source_of(o) for o in options], [HLG_SOURCE, SDR_SOURCE])


class TestThePlayerGivesTheModeBeforeTheVersions(unittest.TestCase):
	"""The order above depends on the playback mode, so DP_Player must hand it
	to the backend BEFORE asking for the versions. It used to set it only after
	the version dialog, so the order would follow the previous playback's mode.
	DP_Player cannot be imported offline: read its source."""

	def test_set_playback_type_comes_first(self):
		import ast
		import os
		path = os.path.join(helpers.REPO_ROOT, "src", "DP_Player.py")
		with open(path, "rb") as handle:
			tree = ast.parse(handle.read(), filename=path)

		def calls(node, name):
			return [child.lineno for child in ast.walk(node) if isinstance(child, ast.Call)
				and isinstance(child.func, ast.Attribute) and child.func.attr == name]

		asking = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
			and calls(node, "getMediaOptionsToPlay") and not any(
				isinstance(inner, ast.FunctionDef) and inner is not node and calls(inner, "getMediaOptionsToPlay")
				for inner in ast.walk(node))]
		# the innermost function that asks; seeing none means the walk broke
		self.assertEqual(len(asking), 1, "expected one function asking for the media options")
		modes = calls(asking[0], "setPlaybackType")
		self.assertTrue(modes, "the function asking for the versions does not set the playback mode")
		self.assertLess(min(modes), min(calls(asking[0], "getMediaOptionsToPlay")))


class TestVideoRangeLabel(unittest.TestCase):
	"""The values both test servers really return (2026-10-05): Emby says it
	in VideoRange only, Jellyfin in VideoRangeType."""

	def label(self, **stream):
		return library.EmbyLibrary._videoRangeLabel(stream)

	def test_emby(self):
		self.assertEqual(self.label(VideoRange="SDR"), "")
		self.assertEqual(self.label(VideoRange="HLG"), "HLG")
		self.assertEqual(self.label(VideoRange="HDR 10"), "HDR10")

	def test_jellyfin(self):
		self.assertEqual(self.label(VideoRange="SDR", VideoRangeType="SDR"), "")
		self.assertEqual(self.label(VideoRange="HDR", VideoRangeType="HLG"), "HLG")
		self.assertEqual(self.label(VideoRange="HDR", VideoRangeType="HDR10"), "HDR10")
		self.assertEqual(self.label(VideoRange="HDR", VideoRangeType="HDR10Plus"), "HDR10+")
		self.assertEqual(self.label(VideoRange="HDR", VideoRangeType="DOVIWithHDR10"), "DV")

	def test_nothing_known(self):
		self.assertEqual(self.label(), "")
		self.assertEqual(self.label(VideoRangeType="Unknown"), "")


if __name__ == "__main__":
	unittest.main()
