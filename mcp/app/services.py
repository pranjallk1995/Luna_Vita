"""Luna Vita use cases, independent of the HTTP and MCP transports."""

from __future__ import annotations

from datetime import date

from .errors import NotFoundError
from .models import (
    BodyProfileUpdate,
    DailyLogUpsert,
    DailyRecommendationsUpsert,
    FoodEntryCreate,
    HealthMeasurementCreate,
)
from .reports import DailyReport, DailyReportRenderer
from .repositories import (
    MAX_PAGE_SIZE,
    DailyLogRepository,
    FoodRepository,
    MeasurementRepository,
    RecommendationRepository,
    Row,
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


class LunaVitaService:
    """Facade grouping every Luna Vita use case for the transport adapters."""

    def __init__(
        self,
        food: FoodService,
        measurements: MeasurementService,
        days: DayContextService,
        profile: ProfileService,
        reports: ReportService,
    ) -> None:
        self.food = food
        self.measurements = measurements
        self.days = days
        self.profile = profile
        self.reports = reports
