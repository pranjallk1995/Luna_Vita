"""Tests for Luna Vita UI logic that runs without a Streamlit session."""

import unittest
from datetime import date

from domain.body_measurements import BodyMetrics
from domain.food_entries import FoodEntryPayload, FoodEntryTime
from domain.nutrition import MacroBreakdown, NutritionStatus
from domain.validation import FoodRowValidator


class FoodLogViewTests(unittest.TestCase):
    """Verify daily rows are ordered by their displayed IST time."""

    def test_rows_are_sorted_by_ist_time_with_label_only_rows_last(self) -> None:
        rows = [
            {"id": 3, "consumed_at": "2026-10-15T00:00:00+05:30", "time_label": "Evening"},
            {"id": 2, "consumed_at": "2026-10-15T07:30:00+00:00", "time_label": None},
            {"id": 1, "consumed_at": "2026-10-15T08:00:00+05:30", "time_label": None},
        ]

        ordered = FoodEntryTime.rows_by_time(rows)

        self.assertEqual([row["id"] for row in ordered], [1, 2, 3])

    def test_macro_percentages_never_make_last_value_negative(self) -> None:
        """Distribute rounding fairly when independently rounded values total 101%."""
        percentages = MacroBreakdown.macro_percentages([23, 55, 17, 6, 0])

        self.assertEqual(sum(percentages), 100)
        self.assertTrue(all(percentage >= 0 for percentage in percentages))
        self.assertEqual(percentages[-1], 0)

    def test_empty_macro_distribution_remains_zero(self) -> None:
        self.assertEqual(MacroBreakdown.macro_percentages([0, 0, 0]), [0, 0, 0])

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

        errors = FoodRowValidator.errors([row])

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

        self.assertEqual(FoodRowValidator.errors([row]), [])


class BodyMetricsTests(unittest.TestCase):
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

        normalized = BodyMetrics.measurement_frame(rows, date(2026, 10, 16))
        display = BodyMetrics.display_frame(normalized)

        self.assertEqual(list(display.columns), ["Measurement", "Morning", "Night"])
        self.assertEqual(display.iloc[0].to_dict(), {
            "Measurement": "Weight",
            "Morning": "79 kg",
            "Night": "80 kg",
        })

    def test_payloads_skip_blank_metrics_and_share_period(self) -> None:
        payloads = BodyMetrics.payloads(
            {"weight": 79, "bmr": None, "bmi": 24.1},
            measured_at="2026-10-16T07:00:00+05:30",
            period="Morning",
            notes="  ",
        )

        self.assertEqual([p["metric"] for p in payloads], ["weight", "bmi"])
        self.assertEqual(payloads[1]["unit"], "index")
        self.assertTrue(all(p["time_label"] == "Morning" for p in payloads))
        self.assertIsNone(payloads[0]["notes"])


class NutritionStatusTests(unittest.TestCase):
    def test_limits_warn_near_and_flag_above_target(self) -> None:
        self.assertEqual(NutritionStatus.limit(80, 100), "")
        self.assertEqual(NutritionStatus.limit(85, 100), "warning")
        self.assertEqual(NutritionStatus.limit(101, 100), "danger")
        self.assertEqual(NutritionStatus.protein(100, 100), "success")

    def test_breakdown_sums_rows(self) -> None:
        rows = [
            {"calories": 100, "protein_g": 10, "carbs_g": 10, "fat_g": 0,
             "natural_sugar_g": 0, "added_sugar_g": 0},
            {"calories": 50, "protein_g": 0, "carbs_g": 20, "fat_g": 0,
             "natural_sugar_g": 0, "added_sugar_g": 0},
        ]

        breakdown = MacroBreakdown(rows)

        self.assertEqual(breakdown.calories, 150)
        self.assertEqual(breakdown.percentages, [25, 75, 0, 0, 0])


class FoodEntryPayloadTests(unittest.TestCase):
    NUTRITION = {"calories": 95, "protein_g": 0.5, "carbs_g": 25, "fat_g": 0.3,
                 "natural_sugar_g": 19, "added_sugar_g": 0}

    def test_form_without_time_stores_midnight_and_label(self) -> None:
        payload = FoodEntryPayload.from_form(
            food_name=" Apple ",
            quantity="1",
            nutrition=self.NUTRITION,
            image_url=None,
            consumed_date=date(2026, 10, 16),
            consumed_time=None,
            time_label="",
            notes="",
        )

        self.assertEqual(payload["food_name"], "Apple")
        self.assertEqual(payload["consumed_at"], "2026-10-16T00:00:00+05:30")
        self.assertEqual(payload["time_label"], "Not recorded")
        self.assertIsNone(payload["notes"])

    def test_editor_row_keeps_original_day_and_parses_time(self) -> None:
        original = {"consumed_at": "2026-10-16T08:00:00+05:30",
                    "consumed_date": "2026-10-16", "meal_type": "other"}
        row = {**self.NUTRITION, "food_name": "Apple", "quantity": "1",
               "display_time": "1:15 PM", "image_url": None, "notes": None}

        payload = FoodEntryPayload.from_editor_row(row, original)

        self.assertEqual(payload["consumed_at"], "2026-10-16T13:15:00+05:30")
        self.assertIsNone(payload["time_label"])
        self.assertEqual(payload["consumed_date"], "2026-10-16")


if __name__ == "__main__":
    unittest.main()
