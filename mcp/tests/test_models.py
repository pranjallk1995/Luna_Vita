"""Validation tests for Luna Vita request models."""

import unittest

from pydantic import ValidationError

from app.models import (
    DailyRecommendationsUpsert,
    FoodEntryCreate,
    HealthMeasurementBatchCreate,
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


if __name__ == "__main__":
    unittest.main()
