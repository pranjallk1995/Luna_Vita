from datetime import date
from typing import Any

from .inference import NutritionEstimate, NutritionInferenceRequest, NutritionInferenceService
from .models import (
    DailyLogUpsert,
    DailyRecommendationsUpsert,
    FoodEntryCreate,
    HealthMeasurementCreate,
)
from .reports import DailyReportService
from .repository import LunaVitaRepository


class LunaVitaService:
    """Coordinate LunaVita use cases independently of HTTP and MCP."""

    def __init__(
        self,
        repository: LunaVitaRepository,
        inference: NutritionInferenceService,
        reports: DailyReportService,
    ) -> None:
        self.repository = repository
        self.inference = inference
        self.reports = reports

    def record_food(self, entry: FoodEntryCreate) -> dict[str, Any]:
        return self.repository.add_food_entry(entry)

    def ensure_schema(self) -> None:
        self.repository.ensure_schema()

    def log_consumed_food(
        self,
        *,
        description: str,
        food_name: str,
        quantity: str,
        calories: int,
        protein_g: float,
        carbs_g: float,
        fat_g: float,
        natural_sugar_g: float,
        added_sugar_g: float,
        image_url: str | None,
        consumed_at: str | None = None,
        consumed_date: str | None = None,
    ) -> dict[str, Any]:
        note = f"AI-estimated from chat: {description.strip()}"[:2000]
        entry = self.record_food(
            FoodEntryCreate(
                food_name=food_name,
                quantity=quantity,
                calories=calories,
                protein_g=protein_g,
                carbs_g=carbs_g,
                fat_g=fat_g,
                natural_sugar_g=natural_sugar_g,
                added_sugar_g=added_sugar_g,
                image_url=image_url,
                consumed_at=consumed_at,
                consumed_date=consumed_date,
                notes=note,
            )
        )
        return {
            "saved": True,
            "entry": entry,
            "message": (
                "Estimated nutrition was saved to LunaVita. "
                "Values remain editable."
            ),
        }

    def list_food(
        self,
        start: date | None = None,
        end: date | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self.repository.list_food_entries(start, end, limit)

    def update_food(
        self, entry_id: int, entry: FoodEntryCreate
    ) -> dict[str, Any] | None:
        return self.repository.update_food_entry(entry_id, entry)

    def set_food_image(
        self, entry_id: int, image_url: str | None
    ) -> dict[str, Any] | None:
        normalized = image_url.strip() if image_url and image_url.strip() else None
        return self.repository.set_food_image(entry_id, normalized)

    def remove_food(
        self, entry_id: int, expected_day: date | None = None
    ) -> bool:
        return self.repository.delete_food_entry(entry_id, expected_day)

    def record_measurement(
        self, entry: HealthMeasurementCreate
    ) -> dict[str, Any]:
        return self.repository.add_health_measurement(entry)

    def record_measurements(
        self, entries: list[HealthMeasurementCreate]
    ) -> list[dict[str, Any]]:
        return self.repository.add_health_measurements(entries)

    def list_measurements(
        self, metric: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        return self.repository.list_health_measurements(metric, limit)

    def update_measurement(
        self, entry_id: int, entry: HealthMeasurementCreate
    ) -> dict[str, Any] | None:
        return self.repository.update_health_measurement(entry_id, entry)

    def remove_measurement(self, entry_id: int) -> bool:
        return self.repository.delete_health_measurement(entry_id)

    def summary(self, day: date) -> dict[str, Any]:
        return self.repository.daily_summary(day)

    def day_context(self, day: date) -> dict[str, Any]:
        return self.repository.get_daily_log(day)

    def save_day_context(
        self, day: date, entry: DailyLogUpsert
    ) -> dict[str, Any]:
        return self.repository.upsert_daily_log(day, entry)

    def update_daily_recommendations(
        self, entry: DailyRecommendationsUpsert
    ) -> dict[str, Any]:
        return self.repository.upsert_daily_recommendations(entry)

    def daily_recommendations(self) -> dict[str, Any] | None:
        return self.repository.get_daily_recommendations()

    def update_body_profile(
        self,
        *,
        height_cm: float | None = None,
        birth_date: date | None = None,
        sex: str | None = None,
        weight_kg: float | None = None,
    ) -> dict[str, Any] | None:
        return self.repository.update_body_profile(
            height_cm=height_cm,
            birth_date=birth_date,
            sex=sex,
            weight_kg=weight_kg,
        )

    def infer_nutrition(
        self, request: NutritionInferenceRequest
    ) -> NutritionEstimate:
        return self.inference.infer(request)

    def daily_report(self, day: date) -> bytes:
        return self.reports.build(day)
