"""Unit tests for Luna Vita application use cases."""

import json
import unittest
from datetime import date
from typing import Any

from pydantic import ValidationError

from app.errors import NotFoundError
from app.http_routes import LunaVitaHTTPRoutes
from app.models import (
    AnalysisRange,
    BodyProfileUpdate,
    FoodEntryCreate,
    FoodRename,
    FoodVerdictUpsert,
    HealthMeasurementCreate,
)
from app.services import (
    AnalysisService,
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


class FakeAnalysisFood:
    """Food entries kept in memory so renames are visible to later reads."""

    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    def list_between(self, start=None, end=None) -> list[dict]:
        return [
            row for row in self.rows
            if (start is None or row["consumed_date"] >= start.isoformat())
            and (end is None or row["consumed_date"] <= end.isoformat())
        ]

    def names(self) -> list[str]:
        return sorted({row["food_name"] for row in self.rows})

    def rename(self, entry_ids: list[int], food_name: str) -> int:
        changed = [row for row in self.rows if row["id"] in entry_ids]
        for row in changed:
            row["food_name"] = food_name
        return len(changed)


class FakeVerdicts:
    def __init__(self, rows: dict | None = None) -> None:
        self.rows = rows or {}

    def list(self) -> list[dict]:
        return list(self.rows.values())

    def get(self, food_key: str) -> dict | None:
        return self.rows.get(food_key)

    def upsert(self, food_key, food_name, verdict, reason) -> dict:
        self.rows[food_key] = {"food_key": food_key, "food_name": food_name,
                               "verdict": verdict, "reason": reason}
        return self.rows[food_key]

    def delete(self, food_key: str) -> bool:
        return self.rows.pop(food_key, None) is not None


class FakeRanges:
    def __init__(self) -> None:
        self.row = None

    def get(self) -> dict | None:
        return self.row

    def upsert(self, start: date, end: date) -> dict:
        self.row = {"start_date": start.isoformat(), "end_date": end.isoformat()}
        return self.row

    def delete(self) -> bool:
        existed, self.row = self.row is not None, None
        return existed


def food_row(entry_id, name, day="2026-10-15", calories=120, protein=25):
    return {"id": entry_id, "food_name": name, "consumed_date": day, "calories": calories,
            "protein_g": protein, "carbs_g": 3, "fat_g": 1.5,
            "natural_sugar_g": 0, "added_sugar_g": 0}


class AnalysisFixture(unittest.TestCase):
    """In-memory entries, verdicts, and saved range for analysis tests."""

    def setUp(self) -> None:
        self.food = FakeAnalysisFood([
            food_row(1, "Whey protein", "2026-10-14"),
            food_row(2, "ON Gold Standard Whey", "2026-10-15"),
            food_row(3, "ON gold standard whey", "2026-09-30"),
            food_row(4, "Paratha", calories=300, protein=6),
        ])
        self.verdicts = FakeVerdicts()
        self.ranges = FakeRanges()
        self.service = AnalysisService(self.food, self.verdicts, self.ranges)


class AnalysisServiceTests(AnalysisFixture):

    def test_window_defaults_to_month_of_the_given_date(self) -> None:
        window = AnalysisService.window(date(2026, 10, 17), None)

        self.assertEqual((window.start, window.end), (date(2026, 10, 1), date(2026, 10, 31)))
        with self.assertRaises(ValueError):
            AnalysisService.window(date(2026, 10, 17), date(2026, 10, 1))

    def test_rename_merges_counts_within_range(self) -> None:
        result = self.service.rename(FoodRename(
            current_name="on gold standard whey", new_name="Whey protein",
            start_date=date(2026, 10, 1), end_date=date(2026, 10, 31),
        ))

        self.assertEqual(result["renamed"], 1)
        self.assertEqual(result["from"], ["ON Gold Standard Whey"])
        self.assertEqual(result["food"]["count"], 2)
        self.assertEqual(result["food"]["totals"]["protein_g"], 50)
        self.assertEqual(self.food.rows[2]["food_name"], "ON gold standard whey")

    def test_analysis_reflects_rename(self) -> None:
        self.service.rename(FoodRename(current_name="ON Gold Standard Whey", new_name="Whey protein"))

        foods = self.service.analyze(date(2026, 10, 17))["foods"]
        self.assertEqual(foods[0]["name"], "Whey protein")
        self.assertEqual(foods[0]["count"], 2)

    def test_rename_of_unknown_food_is_not_found(self) -> None:
        with self.assertRaises(NotFoundError):
            self.service.rename(FoodRename(current_name="Pizza", new_name="Pie"))

    def test_override_moves_only_when_old_name_is_gone(self) -> None:
        self.service.set_verdict(FoodVerdictUpsert(
            food_name="ON Gold Standard Whey", verdict="prefer", reason="Clean protein"))

        partial = self.service.rename(FoodRename(
            current_name="ON Gold Standard Whey", new_name="Whey protein",
            start_date=date(2026, 10, 1), end_date=date(2026, 10, 31)))
        self.assertIn("keeps its prefer verdict", partial["verdict_note"])

        full = self.service.rename(FoodRename(
            current_name="ON Gold Standard Whey", new_name="Whey protein"))
        self.assertEqual(full["verdict_note"], "Moved the prefer verdict to 'Whey protein'.")
        self.assertEqual(list(self.verdicts.rows), ["whey protein"])

    def test_verdict_override_appears_in_analysis_and_can_be_cleared(self) -> None:
        self.service.set_verdict(FoodVerdictUpsert(
            food_name="parathas", verdict="prefer", reason="Homemade"))

        prefer = [f["name"] for f in self.service.analyze(date(2026, 10, 17))["prefer"]]
        self.assertIn("Paratha", prefer)

        self.assertTrue(self.service.clear_verdict("Paratha"))
        with self.assertRaises(NotFoundError):
            self.service.clear_verdict("Paratha")


class AnalysisRangeTests(AnalysisFixture):
    def test_displayed_analysis_defaults_to_month_of_day(self) -> None:
        result = self.service.analyze_displayed(date(2026, 10, 17))

        self.assertEqual(result["range_source"], "month")
        self.assertEqual(result["window"]["start"], "2026-10-01")
        self.assertEqual(result["entries"], 3)

    def test_saved_range_replaces_month_until_reset(self) -> None:
        status = self.service.set_range(
            AnalysisRange(start_date="2026-09-30", end_date="2026-10-14")
        )
        self.assertEqual((status["source"], status["days"]), ("saved", 15))

        result = self.service.analyze_displayed(date(2026, 10, 17))
        self.assertEqual(result["range_source"], "saved")
        self.assertEqual({f["name"] for f in result["foods"]},
                         {"Whey protein", "ON gold standard whey"})

        reset = self.service.reset_range()
        self.assertTrue(reset["reset"])
        self.assertEqual(reset["source"], "month")
        self.assertFalse(self.service.reset_range()["reset"])

    def test_explicit_request_ignores_saved_range(self) -> None:
        self.service.set_range(AnalysisRange(start_date="2026-09-01", end_date="2026-09-30"))

        result = self.service.analyze(date(2026, 10, 17))
        self.assertEqual(result["range_source"], "requested")
        self.assertEqual(result["window"]["start"], "2026-10-01")


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
