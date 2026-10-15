"""Tests for daily PDF report formatting."""

import unittest
from datetime import date

from reportlab.lib.styles import ParagraphStyle

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

    def test_long_food_text_wraps_into_pdf_table_cells(self) -> None:
        class Repository:
            def list_food_entries(self, *_args):
                return [
                    {
                        "consumed_at": "2026-10-15T07:30:00+00:00",
                        "time_label": None,
                        "food_name": "Vegetable sandwich with a deliberately long descriptive name",
                        "quantity": "Two large servings with extra vegetables and toasted bread",
                        "calories": 420,
                        "protein_g": 18,
                        "carbs_g": 54,
                        "fat_g": 14,
                        "natural_sugar_g": 7,
                        "added_sugar_g": 2,
                    }
                ]

            def daily_summary(self, *_args):
                return {
                    "calories": 420,
                    "protein_g": 18,
                    "carbs_g": 54,
                    "fat_g": 14,
                    "natural_sugar_g": 7,
                    "added_sugar_g": 2,
                }

            def get_daily_log(self, *_args):
                return {}

            def list_health_measurements_for_day(self, *_args):
                return []

        pdf = DailyReportService(Repository()).build(date(2026, 10, 15))
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 1_000)

    def test_wrapped_cell_uses_multiple_lines_for_long_text(self) -> None:
        style = ParagraphStyle("TestCell", fontSize=8, leading=10)
        cell = DailyReportService.wrapped_cell(
            "Two large servings with extra vegetables and toasted bread",
            style,
        )

        width, height = cell.wrap(110, 1_000)

        self.assertLessEqual(width, 110)
        self.assertGreater(height, style.leading)


if __name__ == "__main__":
    unittest.main()
