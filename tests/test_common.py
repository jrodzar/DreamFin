# -*- coding: utf-8 -*-
"""Pure helpers in __common__ that the UI relies on."""

import unittest

from tests import helpers

helpers.setup_environment()

from src.__common__ import getRatingValue  # noqa: E402


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
