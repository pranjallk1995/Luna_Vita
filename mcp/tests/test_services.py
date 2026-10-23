"""Unit tests for Luna Vita application use cases."""

import json
import unittest
from datetime import date
from typing import Any

from pydantic import ValidationError

from app.core.errors import NotFoundError
from app.transport.http_routes import LunaVitaHTTPRoutes
from app.core.models import (
    AnalysisRange,
    BodyProfileUpdate,
    ExerciseBatch,
    ExerciseEntry,
    FoodAliasUpsert,
    FoodEntryCreate,
    FoodRename,
    FoodVerdictUpsert,
    HealthMeasurementCreate,
    WorkoutBatch,
    WorkoutRecord,
)
from app.services.application import (
    AnalysisService,
    DayContextService,
    FoodService,
    MeasurementService,
    ProfileService,
    ReportService,
    WorkoutService,
)


class CallRecorder:
    """Capture repository calls without using PostgreSQL."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []


class FakeFoodRepository(CallRecorder):
    def __init__(self, name_counts: dict[str, int] | None = None) -> None:
        super().__init__()
        self.counts = name_counts or {}

    def name_counts(self) -> dict[str, int]:
        return self.counts

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


class FakeAliases:
    def __init__(self, rows: dict[str, str] | None = None) -> None:
        self.rows = rows or {}

    def mapping(self) -> dict[str, str]:
        return dict(self.rows)

    def upsert(self, alias_key: str, canonical_name: str) -> dict:
        self.rows[alias_key] = canonical_name
        return {"alias_key": alias_key, "canonical_name": canonical_name}

    def delete(self, alias_key: str) -> bool:
        return self.rows.pop(alias_key, None) is not None


class FakeImageCatalog:
    """Resolve any URL ending in a known ID to its canonical Visia URL."""

    CANONICAL = "https://visia.example/api/public/images/2d77a066-d097-4b1b-9682-c9eb41538b26"

    PLACEHOLDER = "https://visia.example/api/public/images/b7adf6ae-30b3-4750-8381-5dc6ab393de6"

    def resolve(self, image_url: str) -> str:
        if not image_url.endswith(self.CANONICAL.rsplit("/", 1)[1]):
            raise NotFoundError("No visible Luna Visia image has that ID.")
        return self.CANONICAL

    def placeholder_url(self) -> str:
        return self.PLACEHOLDER


class FoodServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = FakeFoodRepository()
        self.service = FoodService(self.repository, FakeImageCatalog(), FakeAliases())

    def test_record_delegates_validated_model(self) -> None:
        result = self.service.record(apple())

        self.assertEqual(result["id"], 7)
        self.assertEqual(self.repository.calls[0][0], "add")
        self.assertEqual(self.repository.calls[0][1].food_name, "Apple")

    def test_record_does_not_require_an_image(self) -> None:
        """The UI path may save an uploaded photo or no image at all."""
        self.service.record(apple())

        self.assertIsNone(self.repository.calls[-1][1].image_url)

    def test_assistant_entries_store_the_canonical_visia_url(self) -> None:
        entry = apple().model_copy(update={
            "image_url": "http://luna-visia-mcp:8000/api/public/images/"
                         "2d77a066-d097-4b1b-9682-c9eb41538b26"})

        self.service.record_with_visia_image(entry)

        self.assertEqual(self.repository.calls[-1][1].image_url, FakeImageCatalog.CANONICAL)

    def test_assistant_entries_without_an_image_get_the_placeholder(self) -> None:
        for image_url in (None, "", "   "):
            with self.subTest(image_url=image_url):
                self.service.record_with_visia_image(
                    apple().model_copy(update={"image_url": image_url}))
                self.assertEqual(
                    self.repository.calls[-1][1].image_url, FakeImageCatalog.PLACEHOLDER)

    def test_supplied_images_must_still_be_found_in_visia(self) -> None:
        with self.assertRaises(NotFoundError):
            self.service.record_with_visia_image(apple().model_copy(
                update={"image_url": "https://visia.example/api/public/images/x"}))
        self.assertEqual(self.repository.calls, [])

    def test_conversational_logging_preserves_estimate_and_note(self) -> None:
        entry = apple().model_copy(update={
            "consumed_date": date(2026, 10, 15), "image_url": FakeImageCatalog.CANONICAL})

        result = self.service.log_consumed("I ate an apple", entry)

        saved_entry = self.repository.calls[0][1]
        self.assertTrue(result["saved"])
        self.assertEqual(saved_entry.consumed_date, date(2026, 10, 15))
        self.assertEqual(saved_entry.notes, "AI-estimated from chat: I ate an apple")

    def test_conversational_logging_validates_the_generated_note(self) -> None:
        with self.assertRaises(ValidationError):
            self.service.log_consumed("I ate an apple 🍎", apple())

    def test_conversational_logging_without_image_uses_placeholder(self) -> None:
        result = self.service.log_consumed("I ate an apple", apple())

        self.assertTrue(result["saved"])
        self.assertEqual(self.repository.calls[-1][1].image_url, FakeImageCatalog.PLACEHOLDER)

    def test_set_image_strips_surrounding_whitespace(self) -> None:
        result = self.service.set_image(4, "  https://example.test/apple.jpg  ")

        self.assertEqual(result["image_url"], "https://example.test/apple.jpg")
        self.assertEqual(
            self.repository.calls[-1],
            ("set_image", (4, "https://example.test/apple.jpg")),
        )

    def test_set_image_converts_blank_value_to_none(self) -> None:
        self.assertIsNone(self.service.set_image(4, "   ")["image_url"])

    def test_new_entries_reuse_the_existing_name_or_alias(self) -> None:
        repository = FakeFoodRepository({"Paratha": 4, "Whey protein": 2})
        service = FoodService(
            repository, FakeImageCatalog(), FakeAliases({"on whey": "Whey protein"})
        )

        service.record(apple().model_copy(update={"food_name": "parathas"}))
        result = service.log_consumed(
            "Had a scoop of ON whey", apple().model_copy(update={"food_name": "ON whey"})
        )

        self.assertEqual(repository.calls[0][1].food_name, "Paratha")
        self.assertEqual(repository.calls[1][1].food_name, "Whey protein")
        self.assertIn("Saved as 'Whey protein'", result["message"])

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
            FoodService(food, FakeImageCatalog(), FakeAliases()),
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

    def name_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in self.rows:
            counts[row["food_name"]] = counts.get(row["food_name"], 0) + 1
        return counts

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
        self.aliases = FakeAliases()
        self.service = AnalysisService(self.food, self.verdicts, self.ranges, self.aliases)


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


class FoodAliasTests(AnalysisFixture):
    def test_full_rename_records_an_alias_but_a_ranged_one_does_not(self) -> None:
        ranged = self.service.rename(FoodRename(
            current_name="ON Gold Standard Whey", new_name="Whey protein",
            start_date=date(2026, 10, 1), end_date=date(2026, 10, 31)))
        self.assertFalse(ranged["alias_recorded"])
        self.assertEqual(self.aliases.rows, {})

        full = self.service.rename(FoodRename(
            current_name="ON Gold Standard Whey", new_name="Whey protein"))
        self.assertTrue(full["alias_recorded"])
        self.assertEqual(self.aliases.rows, {"on gold standard whey": "Whey protein"})

    def test_alias_merges_existing_entries_in_the_analysis(self) -> None:
        self.service.set_alias(FoodAliasUpsert(
            alias="ON Gold Standard Whey", canonical_name="whey protein"))

        foods = self.service.analyze(date(2026, 9, 1), date(2026, 10, 31))["foods"]
        whey = [food for food in foods if food["key"] == "whey protein"]
        self.assertEqual(len(foods), 2)
        self.assertEqual(whey[0]["name"], "Whey protein")
        self.assertEqual(whey[0]["count"], 3)

    def test_alias_chains_collapse_and_can_be_swapped(self) -> None:
        self.service.set_alias(FoodAliasUpsert(alias="Whey", canonical_name="Whey protein"))
        self.service.set_alias(FoodAliasUpsert(alias="Whey protein", canonical_name="ON Whey"))
        self.assertEqual(self.aliases.rows, {"whey": "ON Whey", "whey protein": "ON Whey"})

        self.service.set_alias(FoodAliasUpsert(alias="ON Whey", canonical_name="Whey protein"))
        self.assertEqual(
            self.aliases.rows, {"whey": "Whey protein", "on whey": "Whey protein"}
        )
        with self.assertRaises(ValueError):
            self.service.set_alias(FoodAliasUpsert(alias="Paratha", canonical_name="parathas"))

    def test_alias_carries_the_verdict_and_list_shows_merged_names(self) -> None:
        self.service.set_verdict(FoodVerdictUpsert(
            food_name="ON Gold Standard Whey", verdict="prefer", reason="Clean protein"))

        result = self.service.set_alias(FoodAliasUpsert(
            alias="ON Gold Standard Whey", canonical_name="Whey protein"))

        self.assertEqual(result["verdict_note"], "Moved the prefer verdict to 'Whey protein'.")
        names = self.service.list_food_names("gold standard")
        self.assertEqual([food["name"] for food in names], ["Whey protein"])
        self.assertEqual(names[0]["entries"], 3)

    def test_resolve_and_duplicate_suggestions_follow_registered_aliases(self) -> None:
        self.food.rows.append(food_row(5, "Whey"))
        self.assertEqual(self.service.resolve_food_name("on gold standard whey")["source"], "existing")
        self.assertEqual(
            [(p["keep"], p["merge"]) for p in self.service.suggest_duplicates()],
            [("Whey", "Whey protein"), ("ON Gold Standard Whey", "Whey")],
        )
        with self.assertRaises(ValueError):
            self.service.resolve_food_name("!!")

        self.service.rename(FoodRename(current_name="Whey", new_name="Whey protein"))

        resolved = self.service.resolve_food_name("whey")
        self.assertEqual((resolved["canonical_name"], resolved["source"]), ("Whey protein", "alias"))
        self.assertEqual(self.service.suggest_duplicates(), [])

    def test_removing_an_unknown_alias_is_not_found(self) -> None:
        with self.assertRaises(NotFoundError):
            self.service.remove_alias("Pizza")


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
                         {"Whey protein", "ON Gold Standard Whey"})

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


class FakeWorkoutRepository(CallRecorder):
    def __init__(self, rows: list[dict] | None = None) -> None:
        super().__init__()
        self.rows = rows or []

    def upsert_many(self, records: list[tuple]) -> list[dict]:
        self.calls.append(("upsert_many", records))
        return [{"workout_date": day.isoformat(), "done": done} for day, done, *_ in records]

    def upsert(self, day: date, done: bool, notes: str | None, types: list[str]) -> dict:
        self.calls.append(("upsert", (day, done, notes, types)))
        row = {"workout_date": day.isoformat(), "done": done, "notes": notes, "types": types}
        self.rows = [r for r in self.rows if r["workout_date"] != row["workout_date"]] + [row]
        return row

    def get(self, day: date) -> dict | None:
        return next((r for r in self.rows if r["workout_date"] == day.isoformat()), None)

    def list_between(self, start: date, end: date) -> list[dict]:
        self.calls.append(("list_between", (start, end)))
        return self.rows

    def delete(self, day: date) -> bool:
        self.calls.append(("delete", day))
        return False


class FakeExerciseRepository(CallRecorder):
    def __init__(self) -> None:
        super().__init__()
        self.rows: dict[int, dict] = {}

    def add_many(self, entries: list[ExerciseEntry]) -> list[dict]:
        self.calls.append(("add_many", entries))
        for entry in entries:
            entry_id = len(self.rows) + 1
            self.rows[entry_id] = {"id": entry_id, **entry.model_dump()}
        return list(self.rows.values())[-len(entries):]

    def list_between(self, start: date, end: date) -> list[dict]:
        return [row for row in self.rows.values() if start <= row["day"] <= end]

    def update(self, entry_id: int, entry: ExerciseEntry) -> dict | None:
        if entry_id not in self.rows:
            return None
        self.rows[entry_id] = {"id": entry_id, **entry.model_dump()}
        return self.rows[entry_id]

    def delete(self, entry_id: int) -> bool:
        return self.rows.pop(entry_id, None) is not None


class WorkoutServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = FakeWorkoutRepository()
        self.service = WorkoutService(self.repository, FakeExerciseRepository())

    def test_record_stores_the_day_and_status(self) -> None:
        saved = self.service.record(date(2026, 10, 21), WorkoutRecord(done=True, notes="  "))

        self.assertEqual(
            self.repository.calls, [("upsert", (date(2026, 10, 21), True, None, []))]
        )
        self.assertTrue(saved["done"])

    def test_record_stores_deduplicated_workout_types(self) -> None:
        entry = WorkoutRecord(done=True, types=["back", "biceps", "back"])

        self.service.record(date(2026, 10, 21), entry)

        self.assertEqual(
            self.repository.calls,
            [("upsert", (date(2026, 10, 21), True, None, ["back", "biceps"]))],
        )

    def test_workout_types_reject_unknown_values_and_skipped_days(self) -> None:
        with self.assertRaises(ValidationError):
            WorkoutRecord(done=True, types=["wings"])
        with self.assertRaises(ValidationError):
            WorkoutRecord(done=False, types=["legs"])

    def test_list_rejects_a_reversed_range(self) -> None:
        with self.assertRaises(ValueError):
            self.service.list(date(2026, 10, 21), date(2026, 10, 1))

    def test_remove_reports_a_missing_record(self) -> None:
        self.assertFalse(self.service.remove(date(2026, 10, 21)))

    def test_notes_reject_emojis(self) -> None:
        with self.assertRaises(ValidationError):
            WorkoutRecord(done=False, notes="Rest day 😴")

    def test_batch_saves_every_day_together(self) -> None:
        batch = WorkoutBatch(workouts=[
            {"day": "2026-10-15", "done": False},
            {"day": "2026-10-16", "done": True, "notes": "Heavy", "types": ["legs"]},
        ])

        self.service.record_many(batch)

        self.assertEqual(self.repository.calls, [("upsert_many", [
            (date(2026, 10, 15), False, None, []), (date(2026, 10, 16), True, "Heavy", ["legs"]),
        ])])

    def test_batch_rejects_a_repeated_day(self) -> None:
        with self.assertRaises(ValidationError):
            WorkoutBatch(workouts=[
                {"day": "2026-10-15", "done": False}, {"day": "2026-10-15", "done": True},
            ])

    def test_summary_counts_and_streaks(self) -> None:
        pattern = [False, True, False, True, True, True]  # 15-20 Oct; 21 Oct unrecorded
        rows = [
            {"workout_date": f"2026-10-{15 + offset}", "done": done}
            for offset, done in enumerate(pattern)
        ]
        service = WorkoutService(FakeWorkoutRepository(rows), FakeExerciseRepository())

        summary = service.summary(date(2026, 10, 15), date(2026, 10, 21))

        self.assertEqual((summary["done"], summary["skipped"], summary["unrecorded"]), (4, 2, 1))
        self.assertEqual(summary["done_rate"], 0.667)
        self.assertEqual((summary["current_streak"], summary["longest_streak"]), (3, 3))

    def test_summary_counts_done_days_per_type(self) -> None:
        rows = [
            {"workout_date": "2026-10-19", "done": True, "types": ["back", "biceps"]},
            {"workout_date": "2026-10-20", "done": True, "types": ["legs", "back"]},
            {"workout_date": "2026-10-21", "done": False, "types": []},
        ]
        summary = WorkoutService(FakeWorkoutRepository(rows), FakeExerciseRepository()).summary(
            date(2026, 10, 19), date(2026, 10, 21)
        )

        self.assertEqual(summary["type_counts"], {"back": 2, "biceps": 1, "legs": 1})

    def test_a_skipped_end_day_resets_the_current_streak(self) -> None:
        rows = [
            {"workout_date": "2026-10-20", "done": True},
            {"workout_date": "2026-10-21", "done": False},
        ]
        summary = WorkoutService(FakeWorkoutRepository(rows), FakeExerciseRepository()).summary(
            date(2026, 10, 20), date(2026, 10, 21)
        )

        self.assertEqual((summary["current_streak"], summary["longest_streak"]), (0, 1))


class ExerciseLogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workouts = FakeWorkoutRepository()
        self.exercises = FakeExerciseRepository()
        self.service = WorkoutService(self.workouts, self.exercises)

    def test_logging_exercises_marks_the_day_done_with_their_types(self) -> None:
        self.service.record(date(2026, 10, 21), WorkoutRecord(done=True, notes="Pull day", types=["back"]))

        result = self.service.add_exercises(ExerciseBatch(exercises=[
            {"day": "2026-10-21", "exercise": "Barbell row", "type": "back", "sets": 4, "reps": 8},
            {"day": "2026-10-21", "exercise": "Hammer curl", "type": "biceps", "weight_kg": 12.5},
            {"day": "2026-10-21", "exercise": "Stretching"},
        ]))

        self.assertEqual(len(result["exercises"]), 3)
        [day] = result["workouts"]
        self.assertEqual((day["done"], day["notes"], day["types"]), (True, "Pull day", ["back", "biceps"]))

    def test_logging_on_a_skipped_day_turns_it_done(self) -> None:
        self.service.record(date(2026, 10, 21), WorkoutRecord(done=False))

        self.service.add_exercises(ExerciseBatch(exercises=[
            {"day": "2026-10-21", "exercise": "Run", "type": "cardio", "duration_min": 30},
        ]))

        self.assertEqual(self.workouts.get(date(2026, 10, 21))["types"], ["cardio"])

    def test_update_and_remove_report_missing_entries(self) -> None:
        entry = ExerciseEntry(day=date(2026, 10, 21), exercise="Squat", type="legs")
        self.assertIsNone(self.service.update_exercise(99, entry))
        self.assertFalse(self.service.remove_exercise(99))
        self.assertEqual(self.workouts.calls, [])

    def test_update_adds_the_new_type_to_the_day(self) -> None:
        [row] = self.service.add_exercises(ExerciseBatch(exercises=[
            {"day": "2026-10-21", "exercise": "Squat"},
        ]))["exercises"]

        self.service.update_exercise(
            row["id"], ExerciseEntry(day=date(2026, 10, 21), exercise="Squat", type="legs")
        )

        self.assertEqual(self.workouts.get(date(2026, 10, 21))["types"], ["legs"])

    def test_exercise_entries_are_validated(self) -> None:
        for bad in ({"exercise": "  "}, {"exercise": "Squat", "sets": 0}, {"exercise": "Run", "type": "yoga"}):
            with self.assertRaises(ValidationError):
                ExerciseEntry(day=date(2026, 10, 21), **bad)
