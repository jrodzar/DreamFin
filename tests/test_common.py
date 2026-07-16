# -*- coding: utf-8 -*-
"""Pure helpers in __common__ that the UI relies on."""

import unittest

from tests import helpers

helpers.setup_environment()

from src.__common__ import getRatingValue, buildMediaChoiceName  # noqa: E402


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


if __name__ == "__main__":
	unittest.main()
