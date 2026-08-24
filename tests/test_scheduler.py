"""Regression tests for scheduler configuration validation."""

import unittest

from scheduler import get_refresh_times


class RefreshTimeTests(unittest.TestCase):
    def test_accepts_and_normalizes_valid_times(self):
        self.assertEqual(
            get_refresh_times({"refresh_times": ["7:05", "18:00", "07:05"]}),
            ["07:05", "18:00"],
        )

    def test_supports_legacy_single_refresh_time(self):
        self.assertEqual(get_refresh_times({"refresh_time": "9:00"}), ["09:00"])

    def test_rejects_invalid_time(self):
        with self.assertRaises(ValueError):
            get_refresh_times({"refresh_times": ["25:00"]})


if __name__ == "__main__":
    unittest.main()
