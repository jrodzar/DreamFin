# -*- coding: utf-8 -*-
"""Pure helpers in __common__ that the UI relies on."""

import calendar
import os
import shutil
import tempfile
import time
import unittest

from tests import helpers

helpers.setup_environment()

from src.__common__ import getRatingValue, buildMediaChoiceName, isCompleteImage, durationToTime, rememberEphemeralArt  # noqa: E402
from src.__common__ import _ephemeralArt  # noqa: E402
from src.__common__ import parseServerDate, isRecentlyAdded  # noqa: E402


class TestDurationToTime(unittest.TestCase):
	"""Regression: series/seasons/artists carry no runtime, so their entryData
	duration is '' . durationToTime('') used to do int('') -> ValueError, which
	crashed the whole show-view refresh (green screen) and, because setDuration
	runs first, also left the year/genre/studio/artwork unset."""

	def test_numeric_ms_formats_as_hms(self):
		self.assertEqual(durationToTime("5400000"), "1:30:00")
		self.assertEqual(durationToTime("0"), "0:00:00")

	def test_empty_duration_is_placeholder_not_crash(self):
		self.assertEqual(durationToTime(""), " - ")

	def test_non_numeric_duration_is_placeholder(self):
		self.assertEqual(durationToTime(" - "), " - ")
		self.assertEqual(durationToTime("abc"), " - ")

	def test_none_duration_does_not_raise(self):
		self.assertEqual(durationToTime(None), " - ")


NOW = calendar.timegm((2026, 7, 20, 12, 0, 0, 0, 0, 0))


def _ago(days):
	"""An Emby/Jellyfin-shaped UTC timestamp `days` before the fixed NOW."""
	return time.strftime("%Y-%m-%dT%H:%M:%S.0000000Z", time.gmtime(NOW - int(days * 86400)))


class TestParseServerDate(unittest.TestCase):
	def test_valid_utc_timestamp_to_epoch(self):
		self.assertEqual(parseServerDate("2026-07-20T12:00:00.0000000Z"), NOW)

	def test_missing_or_garbage_is_none(self):
		for value in ("", None, "not-a-date", 12345, "2026-13-40T99:99:99Z"):
			self.assertIsNone(parseServerDate(value))

	def test_year_one_sentinel_is_none(self):
		# Jellyfin emits this for an empty DateLastMediaAdded (e.g. some seasons)
		self.assertIsNone(parseServerDate("0001-01-01T00:00:00.0000000Z"))


class TestIsRecentlyAdded(unittest.TestCase):
	"""'new' = recently ADDED to the library, within the configured window."""

	def test_recent_leaf_is_new(self):
		self.assertTrue(isRecentlyAdded((None, _ago(2)), NOW, 7))

	def test_old_leaf_is_not_new(self):
		self.assertFalse(isRecentlyAdded((None, _ago(30)), NOW, 7))

	def test_window_boundary_is_inclusive(self):
		self.assertTrue(isRecentlyAdded((None, _ago(7)), NOW, 7))
		self.assertFalse(isRecentlyAdded((None, _ago(8)), NOW, 7))

	def test_media_added_bubbles_an_old_container_up(self):
		# series added long ago but with a fresh episode: DateLastMediaAdded wins
		self.assertTrue(isRecentlyAdded((_ago(2), _ago(400)), NOW, 7))

	def test_null_media_added_falls_back_to_date_created(self):
		sentinel = "0001-01-01T00:00:00.0000000Z"
		self.assertTrue(isRecentlyAdded((sentinel, _ago(2)), NOW, 7))
		self.assertFalse(isRecentlyAdded((sentinel, _ago(30)), NOW, 7))

	def test_zero_days_disables_the_badge(self):
		self.assertFalse(isRecentlyAdded((None, _ago(0)), NOW, 0))

	def test_non_numeric_or_negative_window_is_off(self):
		self.assertFalse(isRecentlyAdded((None, _ago(1)), NOW, -5))
		self.assertFalse(isRecentlyAdded((None, _ago(1)), NOW, "abc"))

	def test_no_valid_dates_is_not_new(self):
		self.assertFalse(isRecentlyAdded((None, "", "0001-01-01T00:00:00.0000000Z"), NOW, 7))


class TestMediaChoiceName(unittest.TestCase):
	"""The "Select media to play" labels must be native str: on py2 the
	enigma2 listbox renders a unicode label as "<not a string>", which is
	exactly what non-ascii file names produced (py2 hands non-ascii JSON
	strings over as unicode). Propagated from DreamPlex 826bb27."""

	def test_non_ascii_file_name_yields_native_str(self):
		items = (u"mediasource-1",
				u"/data/Pel·lis/La película (2024)/La película 4K.mkv",
				u"mkv", u"2600000000", u"7200", u"4K", u"hevc", 0)

		name = buildMediaChoiceName(items)

		self.assertIsInstance(name, str)  # native str on BOTH pythons
		expected = u"[4K / hevc / 2.42 GB]  La película 4K.mkv"
		if str is bytes:  # py2: utf-8 encoded bytes
			self.assertEqual(name, expected.encode("utf-8"))
		else:
			self.assertEqual(name, expected)

	def test_version_prefix_and_basename(self):
		items = ("mediasource-2", "/data/movies/Movie.1080p.mkv",
				"mkv", "1073741824", "5400", "1080", "h264", 1)

		self.assertEqual(buildMediaChoiceName(items),
				"[1080 / h264 / 1.0 GB]  Movie.1080p.mkv")

	def test_no_file_name_falls_back_to_key_and_stays_str(self):
		items = (u"película", None, u"mkv", u"1048576", u"61")

		name = buildMediaChoiceName(items)

		self.assertIsInstance(name, str)
		expected = u"película (mkv / 1.0 MB / 00:01:01)"
		if str is bytes:
			self.assertEqual(name, expected.encode("utf-8"))
		else:
			self.assertEqual(name, expected)


class TestGetRatingValue(unittest.TestCase):
	"""Feeds the 0-10 popularity score to the star widget."""

	def test_reads_the_rating_key(self):
		self.assertEqual(getRatingValue({"rating": "7.5"}), 7.5)

	def test_falls_back_to_user_rating(self):
		self.assertEqual(getRatingValue({"rating": "", "userRating": "8"}), 8.0)

	def test_empty_when_no_score(self):
		self.assertEqual(getRatingValue({}), 0.0)
		self.assertEqual(getRatingValue({"rating": ""}), 0.0)
		self.assertEqual(getRatingValue({"rating": "0"}), 0.0)

	def test_garbage_does_not_raise(self):
		self.assertEqual(getRatingValue({"rating": "n/a"}), 0.0)
		self.assertEqual(getRatingValue({"rating": None}), 0.0)

	def test_decimal_is_not_truncated_by_the_caller(self):
		# handlePopularityPixmaps does int(popularity * 10), not
		# int(popularity) * 10 - so 5.5 -> 55 (2.75 stars), not 50
		popularity = getRatingValue({"rating": "5.5"})
		self.assertEqual(int(popularity * 10), 55)
		self.assertNotEqual(int(popularity) * 10, 55)


class TestIsCompleteImage(unittest.TestCase):
	"""A poster fetched during a transcode can arrive truncated (half JPEG ->
	grey bottom). isCompleteImage rejects a partial download."""

	JPEG_HEAD = b"\xff\xd8\xff\xe0" + b"\x00" * 200

	def test_complete_jpeg_is_accepted(self):
		self.assertTrue(isCompleteImage(self.JPEG_HEAD + b"\xff\xd9"))

	def test_truncated_jpeg_is_rejected(self):
		# same JPEG without the EOI marker -> a partial download
		self.assertFalse(isCompleteImage(self.JPEG_HEAD))

	def test_complete_png_is_accepted(self):
		png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200 + b"IEND\xae\x42\x60\x82"
		self.assertTrue(isCompleteImage(png))

	def test_truncated_png_is_rejected(self):
		self.assertFalse(isCompleteImage(b"\x89PNG\r\n\x1a\n" + b"\x00" * 200))

	def test_empty_or_tiny_is_rejected(self):
		self.assertFalse(isCompleteImage(b""))
		self.assertFalse(isCompleteImage(None))
		self.assertFalse(isCompleteImage(b"\xff\xd8\xff\xff\xd9"))  # under 128 bytes

	def test_unknown_format_is_accepted(self):
		self.assertTrue(isCompleteImage(b"GIF89a" + b"\x00" * 200))


class TestEphemeralArtLRU(unittest.TestCase):
	"""No-cache artwork is keyed per item now (a shared "temp" file made
	concurrent downloads clobber each other while scrolling -> blank art). The
	LRU keeps the tmpfs log dir from filling on a long scroll by deleting the
	oldest files once past the cap."""

	def setUp(self):
		_ephemeralArt.clear()
		self.tmp = tempfile.mkdtemp()

	def tearDown(self):
		_ephemeralArt.clear()
		shutil.rmtree(self.tmp, ignore_errors=True)

	def _mk(self, name):
		p = os.path.join(self.tmp, name)
		with open(p, "wb") as fd:
			fd.write(b"x")
		return p

	def test_prunes_oldest_past_cap(self):
		paths = [self._mk("art%d.jpg" % i) for i in range(5)]
		for p in paths:
			rememberEphemeralArt(p, cap=3)

		# only the newest 3 survive on disk; the 2 oldest were deleted
		self.assertFalse(os.path.exists(paths[0]))
		self.assertFalse(os.path.exists(paths[1]))
		for p in paths[2:]:
			self.assertTrue(os.path.exists(p))
		self.assertEqual(list(_ephemeralArt), paths[2:])

	def test_same_path_is_not_tracked_twice(self):
		p = self._mk("a.jpg")
		rememberEphemeralArt(p, cap=3)
		rememberEphemeralArt(p, cap=3)
		self.assertEqual(list(_ephemeralArt), [p])

	def test_eviction_of_a_vanished_file_does_not_raise(self):
		gone = self._mk("gone.jpg")
		rememberEphemeralArt(gone, cap=2)
		os.remove(gone)  # disappears before it is evicted
		rememberEphemeralArt(self._mk("b.jpg"), cap=2)
		rememberEphemeralArt(self._mk("c.jpg"), cap=2)  # evicts the vanished one
		self.assertNotIn(gone, list(_ephemeralArt))


if __name__ == "__main__":
	unittest.main()
