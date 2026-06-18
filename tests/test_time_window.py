from datetime import datetime, timezone
import unittest

from youtube_daily_update.time_window import brisbane_day_window, is_in_window


class TimeWindowTests(unittest.TestCase):
    def test_brisbane_window_boundaries(self):
        start, end = brisbane_day_window(datetime(2026, 6, 18, 2, 5, tzinfo=timezone.utc))

        self.assertEqual(datetime(2026, 6, 17, 14, 0, tzinfo=timezone.utc), start)
        self.assertEqual(datetime(2026, 6, 18, 14, 0, tzinfo=timezone.utc), end)
        self.assertTrue(is_in_window(datetime(2026, 6, 17, 14, 0, tzinfo=timezone.utc), start, end))
        self.assertTrue(is_in_window(datetime(2026, 6, 18, 13, 59, 59, tzinfo=timezone.utc), start, end))
        self.assertFalse(is_in_window(datetime(2026, 6, 18, 14, 0, tzinfo=timezone.utc), start, end))
