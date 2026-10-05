# -*- coding: utf-8 -*-
"""A title with an HDR and an SDR version: the version dialog names the HDR
kind, and a box that cannot show HDR gets the SDR version first.

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
