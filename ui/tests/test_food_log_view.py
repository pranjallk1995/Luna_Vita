"""Tests for Luna Vita food-log presentation ordering."""

import unittest
from datetime import date

from app import FoodLogView, WeightView


class FoodLogViewTests(unittest.TestCase):
    """Verify daily rows are ordered by their displayed IST time."""

    def test_rows_are_sorted_by_ist_time_with_label_only_rows_last(self) -> None:
        rows = [
            {"id": 3, "consumed_at": "2026-10-15T00:00:00+05:30", "time_label": "Evening"},
            {"id": 2, "consumed_at": "2026-10-15T07:30:00+00:00", "time_label": None},
            {"id": 1, "consumed_at": "2026-10-15T08:00:00+05:30", "time_label": None},
        ]

        ordered = FoodLogView.rows_by_time(rows)

        self.assertEqual([row["id"] for row in ordered], [1, 2, 3])

    def test_macro_percentages_never_make_last_value_negative(self) -> None:
        """Distribute rounding fairly when independently rounded values total 101%."""
        percentages = FoodLogView.macro_percentages([23, 55, 17, 6, 0])

        self.assertEqual(sum(percentages), 100)
        self.assertTrue(all(percentage >= 0 for percentage in percentages))
        self.assertEqual(percentages[-1], 0)

    def test_empty_macro_distribution_remains_zero(self) -> None:
        self.assertEqual(FoodLogView.macro_percentages([0, 0, 0]), [0, 0, 0])

    def test_editor_rejects_negative_numbers_and_emojis(self) -> None:
        row = {
            "food_name": "Apple 🍎",
            "quantity": "1",
            "display_time": "8:00 AM",
            "notes": None,
            "calories": -10,
            "protein_g": 0,
            "carbs_g": 20,
            "fat_g": 0,
            "natural_sugar_g": 15,
            "added_sugar_g": 0,
            "remove": False,
        }

        errors = FoodLogView.editor_validation_errors([row])

        self.assertTrue(any("cannot contain emojis" in error for error in errors))
        self.assertTrue(any("cannot be negative" in error for error in errors))

    def test_editor_accepts_normal_food_values(self) -> None:
        row = {
            "food_name": "Apple",
            "quantity": "1 medium (180 g)",
            "display_time": "8:00 AM",
            "notes": "With breakfast",
            "calories": 95,
            "protein_g": 0.5,
            "carbs_g": 25,
            "fat_g": 0.3,
            "natural_sugar_g": 19,
            "added_sugar_g": 0,
            "remove": False,
        }

        self.assertEqual(FoodLogView.editor_validation_errors([row]), [])


class WeightViewTests(unittest.TestCase):
    def test_display_columns_always_put_morning_before_night(self) -> None:
        rows = [
            {
                "metric": "weight",
                "value": 80,
                "unit": "kg",
                "measured_at": "2026-10-16T21:00:00+05:30",
                "time_label": "Night",
            },
            {
                "metric": "weight",
                "value": 79,
                "unit": "kg",
                "measured_at": "2026-10-16T07:00:00+05:30",
                "time_label": "Morning",
            },
        ]

        normalized = WeightView.measurement_frame(rows, date(2026, 10, 16))
        display = WeightView.display_frame(normalized)

        self.assertEqual(list(display.columns), ["Measurement", "Morning", "Night"])
        self.assertEqual(display.iloc[0].to_dict(), {
            "Measurement": "Weight",
            "Morning": "79 kg",
            "Night": "80 kg",
        })


if __name__ == "__main__":
    unittest.main()
