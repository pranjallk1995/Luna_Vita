"""Tests for daily PDF report formatting."""

import unittest

from app.reports import DailyReportService


class DailyReportServiceTests(unittest.TestCase):
    """Verify values rendered into the daily report."""

    def test_food_entry_time_prefers_consumed_at_over_label(self) -> None:
        entry = {
            "consumed_at": "2026-10-15T07:30:00+00:00",
            "time_label": "Breakfast",
        }

        self.assertEqual(DailyReportService.food_entry_time(entry), "1:00 PM")

    def test_food_entry_time_falls_back_to_time_label(self) -> None:
        entry = {"consumed_at": None, "time_label": "Late evening"}

        self.assertEqual(
            DailyReportService.food_entry_time(entry),
            "Late evening",
        )

    def test_food_entry_time_falls_back_when_timestamp_is_invalid(self) -> None:
        entry = {"consumed_at": "not-a-time", "time_label": "Morning"}

        self.assertEqual(DailyReportService.food_entry_time(entry), "Morning")


if __name__ == "__main__":
    unittest.main()
