"""Validation tests for Luna Vita request models."""

import unittest
from datetime import timedelta

from pydantic import ValidationError

from app.clock import LocalClock
from app.models import (
    BodyProfileUpdate,
    DailyRecommendationsUpsert,
    FoodEntryCreate,
    HealthMeasurementBatchCreate,
    HealthMeasurementCreate,
)


class RequestModelTests(unittest.TestCase):
    """Verify invalid health data is rejected before persistence."""

    def test_food_requires_nonempty_name_and_quantity(self) -> None:
        with self.assertRaises(ValidationError):
            FoodEntryCreate(
                food_name="",
                quantity="",
                calories=0,
                protein_g=0,
                carbs_g=0,
                fat_g=0,
                natural_sugar_g=0,
                added_sugar_g=0,
            )

    def test_food_rejects_negative_nutrition(self) -> None:
        with self.assertRaises(ValidationError):
            FoodEntryCreate(
                food_name="Apple",
                quantity="1",
                calories=-1,
                protein_g=0,
                carbs_g=0,
                fat_g=0,
                natural_sugar_g=0,
                added_sugar_g=0,
            )

    def test_food_rejects_emojis_and_whitespace_only_required_text(self) -> None:
        for food_name, quantity in (("Apple 🍎", "1"), ("Apple", "   ")):
            with self.subTest(food_name=food_name, quantity=quantity):
                with self.assertRaises(ValidationError):
                    FoodEntryCreate(
                        food_name=food_name,
                        quantity=quantity,
                        calories=95,
                        protein_g=0.5,
                        carbs_g=25,
                        fat_g=0.3,
                        natural_sugar_g=19,
                        added_sugar_g=0,
                    )

    def test_measurement_batch_requires_at_least_one_entry(self) -> None:
        with self.assertRaises(ValidationError):
            HealthMeasurementBatchCreate(measurements=[])

    def test_recommendations_reject_unknown_sex_value(self) -> None:
        with self.assertRaises(ValidationError):
            DailyRecommendationsUpsert(
                calories_kcal=2000,
                protein_g=100,
                carbs_g=220,
                fat_g=70,
                sugars_g=30,
                height_cm=175,
                sex="unknown",
            )

    def test_naive_food_timestamp_is_interpreted_as_ist(self) -> None:
        entry = FoodEntryCreate(
            food_name="Apple",
            quantity="1",
            calories=95,
            protein_g=0.5,
            carbs_g=25,
            fat_g=0.3,
            natural_sugar_g=19,
            added_sugar_g=0,
            consumed_at="2026-10-15T14:30:00",
        )

        self.assertEqual(entry.consumed_at.utcoffset(), timedelta(hours=5, minutes=30))

    def test_food_entry_date_defaults_from_consumed_timestamp(self) -> None:
        entry = FoodEntryCreate(
            food_name="Apple",
            quantity="1",
            calories=95,
            protein_g=0.5,
            carbs_g=25,
            fat_g=0.3,
            natural_sugar_g=19,
            added_sugar_g=0,
            consumed_at="2026-10-14T23:30:00+00:00",
        )

        self.assertEqual(entry.effective_consumed_date.isoformat(), "2026-10-15")

    def test_measurement_metric_and_unit_are_normalized(self) -> None:
        entry = HealthMeasurementCreate(metric=" Weight ", value=70, unit=" kg ")

        self.assertEqual((entry.metric, entry.unit), ("weight", "kg"))

    def test_body_profile_requires_at_least_one_field(self) -> None:
        with self.assertRaises(ValidationError):
            BodyProfileUpdate()

    def test_body_profile_rejects_out_of_range_and_future_values(self) -> None:
        tomorrow = LocalClock.today() + timedelta(days=1)
        for values in (
            {"height_cm": 0},
            {"height_cm": 301},
            {"weight_kg": 1_001},
            {"sex": "unknown"},
            {"birth_date": tomorrow},
        ):
            with self.subTest(values=values):
                with self.assertRaises(ValidationError):
                    BodyProfileUpdate(**values)

    def test_body_profile_accepts_partial_update(self) -> None:
        entry = BodyProfileUpdate(birth_date="1990-01-02")

        self.assertEqual(entry.birth_date.isoformat(), "1990-01-02")
        self.assertIsNone(entry.height_cm)


if __name__ == "__main__":
    unittest.main()
