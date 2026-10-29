"""Luna Vita use cases, independent of the HTTP and MCP transports."""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from app.services.analysis import (
    DuplicateFinder,
    FoodAnalysis,
    FoodCatalog,
    FoodName,
    PeriodWindow,
)
from app.services.averages import RunningAverages
from app.services.body_composition import BodyComposition
from app.core.clock import LocalClock
from app.core.errors import NotFoundError
from app.core.models import (
    AnalysisRange,
    BodyProfileUpdate,
    DailyLogUpsert,
    DailyRecommendationsUpsert,
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
from app.services.reports import DailyReport, DailyReportRenderer
from app.data.repositories import (
    AnalysisRangeRepository,
    DailyLogRepository,
    ExerciseRepository,
    FoodAliasRepository,
    FoodRepository,
    MeasurementRepository,
    RecommendationRepository,
    Row,
    VerdictRepository,
    WorkoutRepository,
)
from app.integrations.visia import VisiaImageCatalog
from app.core.config import AppConfig


def food_catalog(food: FoodRepository, aliases: FoodAliasRepository) -> FoodCatalog:
    """Stored aliases plus every name already used, for resolving canonical names."""
    return FoodCatalog(aliases.mapping(), food.name_counts())


class FoodService:
    """Record, correct, and remove food and supplement entries.

    Entries added by the assistant always show a Luna Visia image: the one it
    found, or the Luna Vita food placeholder when it supplied none. Entries from the
    UI may carry an uploaded photo or none. New entries are saved under the
    food's canonical name, so spelling variants never become separate foods.
    """

    NOTE_MAX_LENGTH = 2_000

    def __init__(
        self, food: FoodRepository, images: VisiaImageCatalog, aliases: FoodAliasRepository
    ) -> None:
        self.food = food
        self.images = images
        self.aliases = aliases

    def with_canonical_name(self, entry: FoodEntryCreate) -> FoodEntryCreate:
        name = food_catalog(self.food, self.aliases).canonical(entry.food_name)
        return entry.model_copy(update={"food_name": name})

    def record(self, entry: FoodEntryCreate) -> Row:
        return self.food.add(self.with_canonical_name(entry))

    def with_visia_image(self, entry: FoodEntryCreate) -> FoodEntryCreate:
        """Store Visia's canonical URL for the image, or the placeholder if none was given."""
        supplied = (entry.image_url or "").strip()
        image_url = self.images.resolve(supplied) if supplied else self.images.placeholder_url()
        return entry.model_copy(update={"image_url": image_url})

    def record_with_visia_image(self, entry: FoodEntryCreate) -> Row:
        return self.record(self.with_visia_image(entry))

    def log_consumed(self, description: str, entry: FoodEntryCreate) -> Row:
        """Save an LLM-estimated entry, noting the chat message it came from."""
        note = f"AI-estimated from chat: {description.strip()}"[: self.NOTE_MAX_LENGTH]
        noted = FoodEntryCreate.model_validate({**entry.model_dump(), "notes": note})
        saved = self.record_with_visia_image(noted)
        renamed = (
            f" Saved as '{saved['food_name']}', the name already used for this food."
            if saved["food_name"] != entry.food_name
            else ""
        )
        return {
            "saved": True,
            "entry": saved,
            "message": (
                "Estimated nutrition was saved to LunaVita. "
                f"Values remain editable.{renamed}"
            ),
        }

    def list(
        self, start: date | None = None, end: date | None = None, limit: int = 100
    ) -> list[Row]:
        return self.food.list(start, end, limit)

    def update(self, entry_id: int, entry: FoodEntryCreate) -> Row | None:
        return self.food.update(entry_id, entry)

    def set_image(self, entry_id: int, image_url: str | None) -> Row | None:
        """Set an entry's image to Visia's canonical URL, or the placeholder if none was given."""
        supplied = (image_url or "").strip()
        resolved = self.images.resolve(supplied) if supplied else self.images.placeholder_url()
        return self.food.set_image(entry_id, resolved)

    def remove(self, entry_id: int, expected_day: date | None = None) -> bool:
        return self.food.delete(entry_id, expected_day)

    def totals(self, day: date) -> Row:
        return self.food.daily_totals(day)


class MeasurementService:
    """Record and maintain body measurements."""

    def __init__(self, measurements: MeasurementRepository) -> None:
        self.measurements = measurements

    def record(self, entry: HealthMeasurementCreate) -> Row:
        return self.record_many([entry])[0]

    def record_many(self, entries: list[HealthMeasurementCreate]) -> list[Row]:
        return self.measurements.add_many(entries)

    def list(self, metric: str | None = None, limit: int = 100) -> list[Row]:
        return self.measurements.list(metric, limit)

    def for_day(self, day: date) -> list[Row]:
        return self.measurements.list_for_day(day)

    def update(self, entry_id: int, entry: HealthMeasurementCreate) -> Row | None:
        return self.measurements.update(entry_id, entry)

    def remove(self, entry_id: int) -> bool:
        return self.measurements.delete(entry_id)


class BodyCompositionService:
    """Weight and body fat % over time, and the body fat % target."""

    DEFAULT_FAT_TARGET = 18.0

    def __init__(
        self, measurements: MeasurementRepository, recommendations: RecommendationRepository
    ) -> None:
        self.measurements = measurements
        self.recommendations = recommendations

    def fat_target(self) -> float:
        target = self.recommendations.body_fat_target()
        return self.DEFAULT_FAT_TARGET if target is None else target

    def set_fat_target(self, percent: float) -> Row:
        updated = self.recommendations.update_body_fat_target(percent)
        if updated is None:
            raise NotFoundError("Daily recommendations have not been created.")
        return updated

    def series(self, start: date, end: date) -> dict:
        """Weight and body fat % readings for local days ``start``..``end``, plus the target."""
        if end < start:
            raise ValueError("end must be on or after start")
        metrics = ["weight", "total_body_water", *sorted(BodyComposition.FAT_METRICS)]
        series = BodyComposition.series(self.measurements.list_between(start, end, metrics))
        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "body_fat_target_percent": self.fat_target(),
            **series,
        }


class DayContextService:
    """Read and save a day's goals, reported totals, and notes."""

    def __init__(self, daily_logs: DailyLogRepository) -> None:
        self.daily_logs = daily_logs

    def get(self, day: date) -> Row:
        return self.daily_logs.get(day)

    def save(self, day: date, entry: DailyLogUpsert) -> Row:
        return self.daily_logs.upsert(day, entry)


class WorkoutService:
    """Record whether each day's workout was done, what it trained, and list them for a calendar."""

    def __init__(self, workouts: WorkoutRepository, exercises: ExerciseRepository) -> None:
        self.workouts = workouts
        self.exercises = exercises

    def record(self, day: date, entry: WorkoutRecord) -> Row:
        return self.workouts.upsert(day, entry.done, entry.notes, entry.types)

    def record_many(self, batch: WorkoutBatch) -> list[Row]:
        return self.workouts.upsert_many(
            [
                (workout.day, workout.done, workout.notes, workout.types)
                for workout in batch.workouts
            ]
        )

    def list(self, start: date, end: date) -> list[Row]:
        if end < start:
            raise ValueError("end must be on or after start")
        return self.workouts.list_between(start, end)

    @staticmethod
    def streaks(done_by_day: dict[date, bool], start: date, end: date) -> tuple[int, int]:
        """The current and longest runs of consecutive done days.

        The current run counts back from ``end``; an unrecorded ``end`` (today,
        not logged yet) does not break it. Skipped or unrecorded days do.
        """
        days = [start + timedelta(days=offset) for offset in range((end - start).days + 1)]
        longest = run = 0
        for day in days:
            run = run + 1 if done_by_day.get(day) else 0
            longest = max(longest, run)
        current, day = 0, end if end in done_by_day else end - timedelta(days=1)
        while day >= start and done_by_day.get(day):
            current, day = current + 1, day - timedelta(days=1)
        return current, longest

    def summary(self, start: date, end: date) -> Row:
        """Counts, done rate, streaks, and days per workout type for the inclusive range."""
        records = self.list(start, end)
        done_by_day = {date.fromisoformat(row["workout_date"]): row["done"] for row in records}
        done = sum(done_by_day.values())
        current, longest = self.streaks(done_by_day, start, end)
        type_counts = Counter(
            kind for row in records if row["done"] for kind in row.get("types") or []
        )
        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "days": (end - start).days + 1,
            "done": done,
            "skipped": len(records) - done,
            "unrecorded": (end - start).days + 1 - len(records),
            "done_rate": round(done / len(records), 3) if records else None,
            "current_streak": current,
            "longest_streak": longest,
            "type_counts": dict(type_counts.most_common()),
            "records": records,
        }

    def remove(self, day: date) -> bool:
        return self.workouts.delete(day)

    def mark_done(self, day: date, types: list[str | None]) -> Row:
        """Mark a day done because exercises were logged, adding their types.

        The day's existing types and notes are kept; a skipped day becomes done.
        """
        current = self.workouts.get(day)
        kept = list(current.get("types") or []) if current and current["done"] else []
        merged = list(dict.fromkeys([*kept, *(kind for kind in types if kind)]))
        return self.workouts.upsert(day, True, current["notes"] if current else None, merged)

    def add_exercises(self, batch: ExerciseBatch) -> Row:
        """Log exercises and mark each of their days done with the types trained."""
        rows = self.exercises.add_many(batch.exercises)
        types_by_day: dict[date, list[str | None]] = {}
        for entry in batch.exercises:
            types_by_day.setdefault(entry.day, []).append(entry.type)
        days = [self.mark_done(day, types) for day, types in sorted(types_by_day.items())]
        return {"exercises": rows, "workouts": days}

    def list_exercises(self, start: date, end: date) -> list[Row]:
        if end < start:
            raise ValueError("end must be on or after start")
        return self.exercises.list_between(start, end)

    def update_exercise(self, entry_id: int, entry: ExerciseEntry) -> Row | None:
        row = self.exercises.update(entry_id, entry)
        if row is not None:
            self.mark_done(entry.day, [entry.type])
        return row

    def remove_exercise(self, entry_id: int) -> bool:
        return self.exercises.delete(entry_id)


class ProfileService:
    """Maintain the daily recommendations and the body profile they belong to."""

    def __init__(self, recommendations: RecommendationRepository) -> None:
        self.recommendations = recommendations

    def get(self) -> Row | None:
        return self.recommendations.get()

    def replace(self, entry: DailyRecommendationsUpsert) -> Row:
        return self.recommendations.upsert(entry)

    def update_body(self, entry: BodyProfileUpdate) -> Row:
        updated = self.recommendations.update_body_profile(**entry.model_dump())
        if updated is None:
            raise NotFoundError("Daily recommendations have not been created.")
        return updated


class ReportService:
    """Gather a day's records and render them as the daily PDF."""

    def __init__(
        self,
        food: FoodService,
        measurements: MeasurementService,
        days: DayContextService,
        renderer: DailyReportRenderer | None = None,
    ) -> None:
        self.food = food
        self.measurements = measurements
        self.days = days
        self.renderer = renderer or DailyReportRenderer()

    @staticmethod
    def filename(day: date) -> str:
        return f"lunavita-{day.isoformat()}.pdf"

    def collect(self, day: date) -> DailyReport:
        return DailyReport(
            day=day,
            food_entries=self.food.list(day, day, AppConfig.MAX_PAGE_SIZE),
            totals=self.food.totals(day),
            context=self.days.get(day),
            measurements=self.measurements.for_day(day),
        )

    def daily_pdf(self, day: date) -> bytes:
        return self.renderer.render(self.collect(day))


class AnalysisService:
    """Analyse food over a period and let callers correct names and verdicts.

    Counts, macro totals, and rule-based verdicts are derived from the stored
    food entries, so renaming entries updates all of them. Aliases merge other
    spellings into one canonical food; a rename over all dates records one.
    Verdict overrides are stored per canonical food key and survive across
    periods. A saved range, when present, replaces the calendar month on the
    Monthly tab.
    """

    def __init__(
        self,
        food: FoodRepository,
        verdicts: VerdictRepository,
        ranges: AnalysisRangeRepository,
        aliases: FoodAliasRepository,
    ) -> None:
        self.food = food
        self.verdicts = verdicts
        self.ranges = ranges
        self.aliases = aliases

    def catalog(self) -> FoodCatalog:
        return food_catalog(self.food, self.aliases)

    @staticmethod
    def window(start: date | None, end: date | None) -> PeriodWindow:
        """Both dates give that range; one or none gives its calendar month."""
        if start and end:
            if start > end:
                raise ValueError("start_date cannot be after end_date.")
            return PeriodWindow(start, end)
        return PeriodWindow.month_of(start or end or LocalClock.today())

    def overrides(self) -> dict[str, Row]:
        return {row["food_key"]: row for row in self.verdicts.list()}

    def analyze_window(self, window: PeriodWindow, source: str) -> Row:
        rows = self.food.list_between(window.start, window.end)
        analysis = FoodAnalysis(rows, window, self.overrides(), self.catalog())
        return {**analysis.to_dict(), "range_source": source}

    def analyze(self, start: date | None = None, end: date | None = None) -> Row:
        """Analyse an explicitly requested range or month."""
        return self.analyze_window(self.window(start, end), "requested")

    def displayed_window(self, day: date | None = None) -> tuple[PeriodWindow, str]:
        """The saved range if one is set, otherwise the month containing ``day``."""
        saved = self.ranges.get()
        if saved is not None:
            start, end = (date.fromisoformat(saved[key]) for key in ("start_date", "end_date"))
            return PeriodWindow(start, end), "saved"
        return PeriodWindow.month_of(day or LocalClock.today()), "month"

    def analyze_displayed(self, day: date | None = None) -> Row:
        """Exactly what the Monthly Tracking tab shows."""
        return self.analyze_window(*self.displayed_window(day))

    def range_status(self, day: date | None = None) -> Row:
        window, source = self.displayed_window(day)
        return {
            "source": source,
            "start_date": window.start.isoformat(),
            "end_date": window.end.isoformat(),
            "days": window.length,
            "label": window.label(),
        }

    def set_range(self, entry: AnalysisRange) -> Row:
        self.ranges.upsert(entry.start_date, entry.end_date)
        return self.range_status()

    def reset_range(self) -> Row:
        return {"reset": self.ranges.delete(), **self.range_status()}

    def matching_entries(self, name: str, start: date | None, end: date | None) -> list[Row]:
        """Entries of the food ``name`` resolves to, under any of its spellings."""
        catalog = self.catalog()
        key = catalog.key(name)
        return [
            row for row in self.food.list_between(start, end)
            if catalog.key(row["food_name"]) == key
        ]

    def food_summary(self, name: str, start: date | None, end: date | None) -> Row | None:
        """The merged food's counts, totals, and verdict over the renamed range."""
        rows = self.matching_entries(name, start, end)
        if not rows:
            return None
        days = sorted(date.fromisoformat(row["consumed_date"]) for row in rows)
        window = PeriodWindow(start or days[0], end or days[-1])
        analysis = FoodAnalysis(rows, window, self.overrides(), self.catalog())
        return analysis.food_dict(analysis.foods[0])

    def move_verdict(self, old_key: str, new_name: str) -> str | None:
        """Carry an override to the new name once no entry uses the old one."""
        old = self.verdicts.get(old_key)
        catalog = self.catalog()
        if old is not None and any(catalog.key(name) == old_key for name in self.food.names()):
            return (
                f"'{old['food_name']}' keeps its {old['verdict']} verdict because "
                "other entries still use that name."
            )
        return self.merge_verdict(old_key, new_name)

    def merge_verdict(self, old_key: str, new_name: str) -> str | None:
        """Move an override from ``old_key`` to ``new_name`` unless it already has one."""
        new_key = FoodName.key(new_name)
        old = self.verdicts.get(old_key)
        if old_key == new_key or old is None:
            return None
        if self.verdicts.get(new_key) is not None:
            self.verdicts.delete(old_key)
            return f"Dropped the old {old['verdict']} verdict; '{new_name}' already has one."
        self.verdicts.upsert(new_key, new_name, old["verdict"], old["reason"])
        self.verdicts.delete(old_key)
        return f"Moved the {old['verdict']} verdict to '{new_name}'."

    def rename(self, change: FoodRename) -> Row:
        """Rename matching entries; over all dates, also alias the old name to the new."""
        old_key = self.catalog().key(change.current_name)
        entries = self.matching_entries(change.current_name, change.start_date, change.end_date)
        if not entries:
            raise NotFoundError(f"No food entries match '{change.current_name}'.")
        previous_names = sorted({row["food_name"] for row in entries})
        renamed = self.food.rename([row["id"] for row in entries], change.new_name)
        verdict_note = self.move_verdict(old_key, change.new_name)
        everywhere = change.start_date is None and change.end_date is None
        if everywhere and old_key != FoodName.key(change.new_name):
            self.remember_alias(old_key, change.new_name)
        return {
            "renamed": renamed,
            "from": previous_names,
            "to": change.new_name,
            "alias_recorded": everywhere and old_key != FoodName.key(change.new_name),
            "verdict_note": verdict_note,
            "food": self.food_summary(change.new_name, change.start_date, change.end_date),
        }

    def remember_alias(self, alias_key: str, canonical_name: str) -> None:
        """Point ``alias_key`` and every alias that led to it at ``canonical_name``."""
        canonical_key = FoodName.key(canonical_name)
        for key, name in self.aliases.mapping().items():
            if key == canonical_key:
                self.aliases.delete(key)
            elif FoodName.key(name) == alias_key:
                self.aliases.upsert(key, canonical_name)
        self.aliases.upsert(alias_key, canonical_name)

    def list_food_names(self, query: str | None = None) -> list[Row]:
        """Canonical foods with entry counts and aliases, optionally filtered by text."""
        names = self.catalog().names()
        if not query or not FoodName.key(query):
            return names
        needle = FoodName.key(query)
        return [
            food for food in names
            if needle in FoodName.key(food["name"])
            or any(needle in FoodName.key(alias) for alias in food["aliases"])
        ]

    def resolve_food_name(self, name: str) -> Row:
        if not FoodName.key(name):
            raise ValueError("name must contain letters or digits.")
        return self.catalog().resolve(name)

    def suggest_duplicates(self, limit: int = 20) -> list[Row]:
        return DuplicateFinder.suggest(self.catalog().names(), min(max(limit, 1), 100))

    def set_alias(self, entry: FoodAliasUpsert) -> Row:
        """Merge ``alias`` into ``canonical_name`` for future logs and the analysis.

        Naming a food that is currently an alias of ``alias`` swaps the two.
        """
        alias_key = FoodName.key(entry.alias)
        canonical = self.catalog().canonical(entry.canonical_name)
        if FoodName.key(canonical) == alias_key:
            if FoodName.key(entry.canonical_name) == alias_key:
                raise ValueError("alias and canonical_name are already the same food.")
            canonical = entry.canonical_name
        self.remember_alias(alias_key, canonical)
        return {
            "alias": alias_key,
            "canonical_name": canonical,
            "verdict_note": self.merge_verdict(alias_key, canonical),
        }

    def remove_alias(self, alias: str) -> bool:
        if not self.aliases.delete(FoodName.key(alias)):
            raise NotFoundError(f"'{alias}' is not an alias of another food.")
        return True

    def list_verdicts(self) -> list[Row]:
        return self.verdicts.list()

    def set_verdict(self, entry: FoodVerdictUpsert) -> Row:
        name = self.catalog().canonical(entry.food_name)
        return self.verdicts.upsert(FoodName.key(name), name, entry.verdict, entry.reason)

    def clear_verdict(self, food_name: str) -> bool:
        if not self.verdicts.delete(self.catalog().key(food_name)):
            raise NotFoundError(f"'{food_name}' has no verdict override.")
        return True


class LunaVitaService:
    """Facade grouping every Luna Vita use case for the transport adapters."""

    def __init__(
        self,
        food: FoodService,
        measurements: MeasurementService,
        body: BodyCompositionService,
        days: DayContextService,
        profile: ProfileService,
        reports: ReportService,
        analysis: AnalysisService,
        workouts: WorkoutService,
        averages: RunningAverages,
    ) -> None:
        self.food = food
        self.measurements = measurements
        self.body = body
        self.days = days
        self.profile = profile
        self.reports = reports
        self.analysis = analysis
        self.workouts = workouts
        self.averages = averages
