"""Unit tests for Luna Vita application use cases."""

import unittest
from datetime import date
from typing import Any

from app.models import FoodEntryCreate, HealthMeasurementCreate
from app.services import LunaVitaService


class FakeRepository:
    """Capture service calls without using PostgreSQL."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def add_food_entry(self, entry: FoodEntryCreate) -> dict[str, Any]:
        self.calls.append(("add_food_entry", entry))
        return {"id": 7, **entry.model_dump()}

    def set_food_image(self, entry_id: int, image_url: str | None) -> dict:
        self.calls.append(("set_food_image", (entry_id, image_url)))
        return {"id": entry_id, "image_url": image_url}

    def delete_food_entry(self, entry_id: int, expected_day: date | None) -> bool:
        self.calls.append(("delete_food_entry", (entry_id, expected_day)))
        return True

    def add_health_measurement(self, entry: HealthMeasurementCreate) -> dict:
        self.calls.append(("add_health_measurement", entry))
        return {"id": 11, **entry.model_dump()}

    def add_health_measurements(
        self, entries: list[HealthMeasurementCreate]
    ) -> list[dict]:
        self.calls.append(("add_health_measurements", entries))
        return [{"id": index + 1} for index, _ in enumerate(entries)]

    def update_body_profile(self, **values: Any) -> dict:
        self.calls.append(("update_body_profile", values))
        return values


class FakeReportService:
    """Return deterministic PDF bytes for report delegation tests."""

    def __init__(self) -> None:
        self.requested_day: date | None = None

    def build(self, day: date) -> bytes:
        self.requested_day = day
        return b"%PDF-test"


class LunaVitaServiceTests(unittest.TestCase):
    """Verify use-case behavior independently of transport and storage."""

    def setUp(self) -> None:
        self.repository = FakeRepository()
        self.reports = FakeReportService()
        self.service = LunaVitaService(self.repository, self.reports)

    @staticmethod
    def food() -> FoodEntryCreate:
        return FoodEntryCreate(
            food_name="Apple",
            quantity="1 medium",
            calories=95,
            protein_g=0.5,
            carbs_g=25,
            fat_g=0.3,
            natural_sugar_g=19,
            added_sugar_g=0,
        )

    def test_record_food_delegates_validated_model(self) -> None:
        result = self.service.record_food(self.food())

        self.assertEqual(result["id"], 7)
        self.assertEqual(self.repository.calls[0][0], "add_food_entry")
        self.assertEqual(self.repository.calls[0][1].food_name, "Apple")

    def test_conversational_food_logging_preserves_estimate_and_note(self) -> None:
        result = self.service.log_consumed_food(
            description="I ate an apple",
            food_name="Apple",
            quantity="1 medium",
            calories=95,
            protein_g=0.5,
            carbs_g=25,
            fat_g=0.3,
            natural_sugar_g=19,
            added_sugar_g=0,
            image_url=None,
            consumed_date="2026-10-15",
        )

        saved_entry = self.repository.calls[0][1]
        self.assertTrue(result["saved"])
        self.assertEqual(saved_entry.consumed_date, date(2026, 10, 15))
        self.assertEqual(saved_entry.notes, "AI-estimated from chat: I ate an apple")

    def test_set_food_image_strips_surrounding_whitespace(self) -> None:
        result = self.service.set_food_image(4, "  https://example.test/apple.jpg  ")

        self.assertEqual(result["image_url"], "https://example.test/apple.jpg")
        self.assertEqual(
            self.repository.calls[-1],
            ("set_food_image", (4, "https://example.test/apple.jpg")),
        )

    def test_set_food_image_converts_blank_value_to_none(self) -> None:
        result = self.service.set_food_image(4, "   ")

        self.assertIsNone(result["image_url"])

    def test_remove_food_passes_expected_date_guard(self) -> None:
        expected_day = date(2026, 10, 15)

        self.assertTrue(self.service.remove_food(9, expected_day))
        self.assertEqual(
            self.repository.calls[-1],
            ("delete_food_entry", (9, expected_day)),
        )

    def test_measurement_batch_is_persisted_together(self) -> None:
        entries = [
            HealthMeasurementCreate(metric="weight", value=70, unit="kg"),
            HealthMeasurementCreate(metric="bmi", value=22, unit="index"),
        ]

        result = self.service.record_measurements(entries)

        self.assertEqual(result, [{"id": 1}, {"id": 2}])
        self.assertEqual(self.repository.calls[-1][1], entries)

    def test_body_profile_update_preserves_named_fields(self) -> None:
        result = self.service.update_body_profile(
            height_cm=175,
            birth_date=date(1990, 1, 2),
            sex="male",
            weight_kg=70,
        )

        self.assertEqual(result["height_cm"], 175)
        self.assertEqual(result["birth_date"], date(1990, 1, 2))

    def test_daily_report_delegates_to_report_service(self) -> None:
        requested_day = date(2026, 10, 15)

        self.assertEqual(self.service.daily_report(requested_day), b"%PDF-test")
        self.assertEqual(self.reports.requested_day, requested_day)


if __name__ == "__main__":
    unittest.main()
