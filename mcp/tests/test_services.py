"""Unit tests for Luna Vita application use cases."""

import json
import unittest
from datetime import date
from typing import Any

from pydantic import ValidationError

from app.errors import NotFoundError
from app.http_routes import LunaVitaHTTPRoutes
from app.models import BodyProfileUpdate, FoodEntryCreate, HealthMeasurementCreate
from app.services import (
    DayContextService,
    FoodService,
    MeasurementService,
    ProfileService,
    ReportService,
)


class CallRecorder:
    """Capture repository calls without using PostgreSQL."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []


class FakeFoodRepository(CallRecorder):
    def add(self, entry: FoodEntryCreate) -> dict[str, Any]:
        self.calls.append(("add", entry))
        return {"id": 7, **entry.model_dump()}

    def set_image(self, entry_id: int, image_url: str | None) -> dict:
        self.calls.append(("set_image", (entry_id, image_url)))
        return {"id": entry_id, "image_url": image_url}

    def delete(self, entry_id: int, expected_day: date | None) -> bool:
        self.calls.append(("delete", (entry_id, expected_day)))
        return True

    def list(self, start, end, limit) -> list[dict]:
        self.calls.append(("list", (start, end, limit)))
        return [{"id": 1}]

    def daily_totals(self, day: date) -> dict:
        return {"calories": 95, "date": day.isoformat()}


class FakeMeasurementRepository(CallRecorder):
    def add_many(self, entries: list[HealthMeasurementCreate]) -> list[dict]:
        self.calls.append(("add_many", entries))
        return [{"id": index + 1} for index, _ in enumerate(entries)]

    def update(self, entry_id: int, entry: HealthMeasurementCreate) -> dict:
        self.calls.append(("update", (entry_id, entry)))
        return {"id": entry_id, **entry.model_dump()}

    def delete(self, entry_id: int) -> bool:
        self.calls.append(("delete", entry_id))
        return True

    def list_for_day(self, day: date) -> list[dict]:
        return [{"metric": "weight"}]


class FakeDailyLogRepository:
    def get(self, day: date) -> dict:
        return {"log_date": day.isoformat()}


class FakeRecommendationRepository(CallRecorder):
    def __init__(self, exists: bool = True) -> None:
        super().__init__()
        self.exists = exists

    def update_body_profile(self, **values: Any) -> dict | None:
        self.calls.append(("update_body_profile", values))
        return values if self.exists else None


class FakeRenderer:
    def __init__(self) -> None:
        self.report = None

    def render(self, report) -> bytes:
        self.report = report
        return b"%PDF-test"


def apple() -> FoodEntryCreate:
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


class FoodServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = FakeFoodRepository()
        self.service = FoodService(self.repository)

    def test_record_delegates_validated_model(self) -> None:
        result = self.service.record(apple())

        self.assertEqual(result["id"], 7)
        self.assertEqual(self.repository.calls[0][0], "add")
        self.assertEqual(self.repository.calls[0][1].food_name, "Apple")

    def test_conversational_logging_preserves_estimate_and_note(self) -> None:
        entry = apple().model_copy(update={"consumed_date": date(2026, 10, 15)})

        result = self.service.log_consumed("I ate an apple", entry)

        saved_entry = self.repository.calls[0][1]
        self.assertTrue(result["saved"])
        self.assertEqual(saved_entry.consumed_date, date(2026, 10, 15))
        self.assertEqual(saved_entry.notes, "AI-estimated from chat: I ate an apple")

    def test_conversational_logging_validates_the_generated_note(self) -> None:
        with self.assertRaises(ValidationError):
            self.service.log_consumed("I ate an apple 🍎", apple())

    def test_set_image_strips_surrounding_whitespace(self) -> None:
        result = self.service.set_image(4, "  https://example.test/apple.jpg  ")

        self.assertEqual(result["image_url"], "https://example.test/apple.jpg")
        self.assertEqual(
            self.repository.calls[-1],
            ("set_image", (4, "https://example.test/apple.jpg")),
        )

    def test_set_image_converts_blank_value_to_none(self) -> None:
        self.assertIsNone(self.service.set_image(4, "   ")["image_url"])

    def test_remove_passes_expected_date_guard(self) -> None:
        expected_day = date(2026, 10, 15)

        self.assertTrue(self.service.remove(9, expected_day))
        self.assertEqual(self.repository.calls[-1], ("delete", (9, expected_day)))


class MeasurementServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = FakeMeasurementRepository()
        self.service = MeasurementService(self.repository)

    def test_batch_is_persisted_together(self) -> None:
        entries = [
            HealthMeasurementCreate(metric="weight", value=70, unit="kg"),
            HealthMeasurementCreate(metric="bmi", value=22, unit="index"),
        ]

        self.assertEqual(self.service.record_many(entries), [{"id": 1}, {"id": 2}])
        self.assertEqual(self.repository.calls[-1], ("add_many", entries))

    def test_single_record_uses_the_batch_path(self) -> None:
        entry = HealthMeasurementCreate(metric="weight", value=70, unit="kg")

        self.assertEqual(self.service.record(entry), {"id": 1})
        self.assertEqual(self.repository.calls[-1], ("add_many", [entry]))

    def test_update_replaces_complete_entry(self) -> None:
        entry = HealthMeasurementCreate(
            metric="weight",
            value=69.5,
            unit="kg",
            measured_at="2026-10-16T08:00:00+05:30",
            time_label="Morning",
            notes="After waking",
        )

        self.assertEqual(self.service.update(12, entry)["id"], 12)
        self.assertEqual(self.repository.calls[-1], ("update", (12, entry)))

    def test_remove_deletes_complete_entry(self) -> None:
        self.assertTrue(self.service.remove(12))
        self.assertEqual(self.repository.calls[-1], ("delete", 12))


class ProfileServiceTests(unittest.TestCase):
    def test_body_profile_update_passes_named_fields(self) -> None:
        repository = FakeRecommendationRepository()
        entry = BodyProfileUpdate(
            height_cm=175, birth_date=date(1990, 1, 2), sex="male", weight_kg=70
        )

        result = ProfileService(repository).update_body(entry)

        self.assertEqual(result["height_cm"], 175)
        self.assertEqual(result["birth_date"], date(1990, 1, 2))

    def test_body_profile_update_requires_existing_recommendations(self) -> None:
        service = ProfileService(FakeRecommendationRepository(exists=False))

        with self.assertRaises(NotFoundError):
            service.update_body(BodyProfileUpdate(height_cm=175))


class ReportServiceTests(unittest.TestCase):
    def test_daily_pdf_collects_every_section_for_the_day(self) -> None:
        food = FakeFoodRepository()
        renderer = FakeRenderer()
        service = ReportService(
            FoodService(food),
            MeasurementService(FakeMeasurementRepository()),
            DayContextService(FakeDailyLogRepository()),
            renderer,
        )
        day = date(2026, 10, 15)

        self.assertEqual(service.daily_pdf(day), b"%PDF-test")
        self.assertEqual(food.calls[-1], ("list", (day, day, 500)))
        self.assertEqual(renderer.report.day, day)
        self.assertEqual(renderer.report.food_entries, [{"id": 1}])
        self.assertEqual(renderer.report.totals["calories"], 95)
        self.assertEqual(renderer.report.context, {"log_date": "2026-10-15"})
        self.assertEqual(renderer.report.measurements, [{"metric": "weight"}])

    def test_filename_is_dated(self) -> None:
        self.assertEqual(ReportService.filename(date(2026, 10, 15)), "lunavita-2026-10-15.pdf")


class HTTPErrorMappingTests(unittest.TestCase):
    """Verify domain errors become the status codes the UI relies on."""

    @staticmethod
    def body(response) -> dict:
        return json.loads(response.body)

    def test_not_found_maps_to_404(self) -> None:
        response = LunaVitaHTTPRoutes.error(NotFoundError("Food entry not found"))

        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.body(response), {"error": "Food entry not found"})

    def test_validation_error_maps_to_422(self) -> None:
        try:
            BodyProfileUpdate()
        except ValidationError as error:
            response = LunaVitaHTTPRoutes.error(error)

        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.body(response)["error"], "Invalid request")

    def test_value_error_maps_to_400(self) -> None:
        self.assertEqual(LunaVitaHTTPRoutes.error(ValueError("bad")).status_code, 400)

    def test_found_rejects_missing_rows(self) -> None:
        for missing in (None, False):
            with self.subTest(missing=missing):
                with self.assertRaises(NotFoundError):
                    LunaVitaHTTPRoutes.found(missing, "Measurement not found")
        self.assertEqual(LunaVitaHTTPRoutes.found({"id": 1}, "x"), {"id": 1})


if __name__ == "__main__":
    unittest.main()
