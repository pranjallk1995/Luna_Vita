"""Luna Vita use cases, independent of the HTTP and MCP transports."""

from __future__ import annotations

from datetime import date

from .analysis import FoodAnalysis, FoodName, PeriodWindow
from .clock import LocalClock
from .errors import NotFoundError
from .models import (
    AnalysisRange,
    BodyProfileUpdate,
    DailyLogUpsert,
    DailyRecommendationsUpsert,
    FoodEntryCreate,
    FoodRename,
    FoodVerdictUpsert,
    HealthMeasurementCreate,
)
from .reports import DailyReport, DailyReportRenderer
from .repositories import (
    MAX_PAGE_SIZE,
    AnalysisRangeRepository,
    DailyLogRepository,
    FoodRepository,
    MeasurementRepository,
    RecommendationRepository,
    Row,
    VerdictRepository,
)


class FoodService:
    """Record, correct, and remove food and supplement entries."""

    NOTE_MAX_LENGTH = 2_000

    def __init__(self, food: FoodRepository) -> None:
        self.food = food

    def record(self, entry: FoodEntryCreate) -> Row:
        return self.food.add(entry)

    def log_consumed(self, description: str, entry: FoodEntryCreate) -> Row:
        """Save an LLM-estimated entry, noting the chat message it came from."""
        note = f"AI-estimated from chat: {description.strip()}"[: self.NOTE_MAX_LENGTH]
        noted = FoodEntryCreate.model_validate({**entry.model_dump(), "notes": note})
        saved = self.record(noted)
        return {
            "saved": True,
            "entry": saved,
            "message": (
                "Estimated nutrition was saved to LunaVita. "
                "Values remain editable."
            ),
        }

    def list(
        self, start: date | None = None, end: date | None = None, limit: int = 100
    ) -> list[Row]:
        return self.food.list(start, end, limit)

    def update(self, entry_id: int, entry: FoodEntryCreate) -> Row | None:
        return self.food.update(entry_id, entry)

    def set_image(self, entry_id: int, image_url: str | None) -> Row | None:
        normalized = image_url.strip() if image_url and image_url.strip() else None
        return self.food.set_image(entry_id, normalized)

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


class DayContextService:
    """Read and save a day's goals, reported totals, and notes."""

    def __init__(self, daily_logs: DailyLogRepository) -> None:
        self.daily_logs = daily_logs

    def get(self, day: date) -> Row:
        return self.daily_logs.get(day)

    def save(self, day: date, entry: DailyLogUpsert) -> Row:
        return self.daily_logs.upsert(day, entry)


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
            food_entries=self.food.list(day, day, MAX_PAGE_SIZE),
            totals=self.food.totals(day),
            context=self.days.get(day),
            measurements=self.measurements.for_day(day),
        )

    def daily_pdf(self, day: date) -> bytes:
        return self.renderer.render(self.collect(day))


class AnalysisService:
    """Analyse food over a period and let callers correct names and verdicts.

    Counts, macro totals, and rule-based verdicts are derived from the stored
    food entries, so renaming entries updates all of them. Verdict overrides
    are stored per normalized food name and survive across periods. A saved
    range, when present, replaces the calendar month on the Monthly tab.
    """

    def __init__(
        self,
        food: FoodRepository,
        verdicts: VerdictRepository,
        ranges: AnalysisRangeRepository,
    ) -> None:
        self.food = food
        self.verdicts = verdicts
        self.ranges = ranges

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
        return {**FoodAnalysis(rows, window, self.overrides()).to_dict(), "range_source": source}

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
        key = FoodName.key(name)
        return [
            row for row in self.food.list_between(start, end)
            if FoodName.key(row["food_name"]) == key
        ]

    def food_summary(self, name: str, start: date | None, end: date | None) -> Row | None:
        """The merged food's counts, totals, and verdict over the renamed range."""
        rows = self.matching_entries(name, start, end)
        if not rows:
            return None
        days = sorted(date.fromisoformat(row["consumed_date"]) for row in rows)
        window = PeriodWindow(start or days[0], end or days[-1])
        analysis = FoodAnalysis(rows, window, self.overrides())
        return analysis.food_dict(analysis.foods[0])

    def move_verdict(self, old_key: str, new_name: str) -> str | None:
        """Carry an override to the new name once no entry uses the old one."""
        new_key = FoodName.key(new_name)
        old = self.verdicts.get(old_key)
        if old_key == new_key or old is None:
            return None
        if any(FoodName.key(name) == old_key for name in self.food.names()):
            return (
                f"'{old['food_name']}' keeps its {old['verdict']} verdict because "
                "other entries still use that name."
            )
        if self.verdicts.get(new_key) is not None:
            self.verdicts.delete(old_key)
            return f"Dropped the old {old['verdict']} verdict; '{new_name}' already has one."
        self.verdicts.upsert(new_key, new_name, old["verdict"], old["reason"])
        self.verdicts.delete(old_key)
        return f"Moved the {old['verdict']} verdict to '{new_name}'."

    def rename(self, change: FoodRename) -> Row:
        entries = self.matching_entries(change.current_name, change.start_date, change.end_date)
        if not entries:
            raise NotFoundError(f"No food entries match '{change.current_name}'.")
        previous_names = sorted({row["food_name"] for row in entries})
        renamed = self.food.rename([row["id"] for row in entries], change.new_name)
        return {
            "renamed": renamed,
            "from": previous_names,
            "to": change.new_name,
            "verdict_note": self.move_verdict(FoodName.key(change.current_name), change.new_name),
            "food": self.food_summary(change.new_name, change.start_date, change.end_date),
        }

    def list_verdicts(self) -> list[Row]:
        return self.verdicts.list()

    def set_verdict(self, entry: FoodVerdictUpsert) -> Row:
        return self.verdicts.upsert(
            FoodName.key(entry.food_name), entry.food_name, entry.verdict, entry.reason
        )

    def clear_verdict(self, food_name: str) -> bool:
        if not self.verdicts.delete(FoodName.key(food_name)):
            raise NotFoundError(f"'{food_name}' has no verdict override.")
        return True


class LunaVitaService:
    """Facade grouping every Luna Vita use case for the transport adapters."""

    def __init__(
        self,
        food: FoodService,
        measurements: MeasurementService,
        days: DayContextService,
        profile: ProfileService,
        reports: ReportService,
        analysis: AnalysisService,
    ) -> None:
        self.food = food
        self.measurements = measurements
        self.days = days
        self.profile = profile
        self.reports = reports
        self.analysis = analysis
