from contextlib import asynccontextmanager
from datetime import date
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Response
from mcp.server.fastmcp import FastMCP

from .database import Database
from .inference import (
    NutritionInferenceRequest,
    NutritionInferenceService,
    NutritionInferenceUnavailable,
)
from .models import (
    DailyLogUpsert,
    FoodEntryCreate,
    HealthMeasurementBatchCreate,
    HealthMeasurementCreate,
)
from .reports import DailyReportService
from .repository import LunaVitaRepository
from .services import LunaVitaService


class LunaVitaMCPAdapter:
    """Expose application services as conversational MCP tools."""

    def __init__(self, server: FastMCP, service: LunaVitaService) -> None:
        self.server = server
        self.service = service
        self.register_tools()

    def register_tools(self) -> None:
        for tool in (
            self.record_food,
            self.log_consumed_food,
            self.get_food_log,
            self.update_food,
            self.remove_food,
            self.record_health_measurement,
            self.get_health_measurements,
            self.get_daily_nutrition_summary,
            self.get_day_context,
            self.save_day_context,
        ):
            self.server.tool()(tool)

    def record_food(
        self,
        food_name: str,
        calories: int,
        quantity: str | None = None,
        meal_type: str = "other",
        protein_g: float = 0,
        carbs_g: float = 0,
        fat_g: float = 0,
        natural_sugar_g: float = 0,
        added_sugar_g: float = 0,
        consumed_at: str | None = None,
        consumed_date: str | None = None,
        time_label: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Record food and its calories in kcal plus macronutrients."""
        return self.service.record_food(
            FoodEntryCreate(
                food_name=food_name,
                quantity=quantity,
                calories=calories,
                meal_type=meal_type,
                protein_g=protein_g,
                carbs_g=carbs_g,
                fat_g=fat_g,
                natural_sugar_g=natural_sugar_g,
                added_sugar_g=added_sugar_g,
                consumed_at=consumed_at,
                consumed_date=consumed_date,
                time_label=time_label,
                notes=notes,
            )
        )

    def log_consumed_food(
        self,
        description: str,
        food_name: str,
        quantity: str,
        calories: int,
        protein_g: float,
        carbs_g: float,
        fat_g: float,
        natural_sugar_g: float = 0,
        added_sugar_g: float = 0,
        consumed_at: str | None = None,
        consumed_date: str | None = None,
    ) -> dict[str, Any]:
        """Log food reported conversationally by the user.

        Use this tool when the user says they ate or drank something and wants
        LunaVita to track it, including natural statements such as "I had 4
        parathas of 40 g each right now". Infer a reasonable nutrition estimate
        for the complete stated quantity before calling the tool. Use the current
        date/time when the user says "now"; otherwise preserve the stated time.
        """
        return self.service.log_consumed_food(
            description=description,
            food_name=food_name,
            quantity=quantity,
            calories=calories,
            protein_g=protein_g,
            carbs_g=carbs_g,
            fat_g=fat_g,
            natural_sugar_g=natural_sugar_g,
            added_sugar_g=added_sugar_g,
            consumed_at=consumed_at,
            consumed_date=consumed_date,
        )

    def get_food_log(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List food entries within an optional inclusive YYYY-MM-DD range."""
        start = date.fromisoformat(start_date) if start_date else None
        end = date.fromisoformat(end_date) if end_date else None
        return self.service.list_food(start, end, limit)

    def update_food(
        self,
        entry_id: int,
        food_name: str,
        calories: int,
        quantity: str | None = None,
        meal_type: str = "other",
        protein_g: float = 0,
        carbs_g: float = 0,
        fat_g: float = 0,
        natural_sugar_g: float = 0,
        added_sugar_g: float = 0,
        consumed_at: str | None = None,
        consumed_date: str | None = None,
        time_label: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing food entry by its id."""
        entry = FoodEntryCreate(
            food_name=food_name,
            quantity=quantity,
            calories=calories,
            meal_type=meal_type,
            protein_g=protein_g,
            carbs_g=carbs_g,
            fat_g=fat_g,
            natural_sugar_g=natural_sugar_g,
            added_sugar_g=added_sugar_g,
            consumed_at=consumed_at,
            consumed_date=consumed_date,
            time_label=time_label,
            notes=notes,
        )
        updated = self.service.update_food(entry_id, entry)
        return {"updated": updated is not None, "entry": updated}

    def remove_food(
        self, entry_id: int, expected_date: str | None = None
    ) -> dict[str, Any]:
        """Remove food by id, optionally requiring an expected YYYY-MM-DD date."""
        day = date.fromisoformat(expected_date) if expected_date else None
        return {
            "deleted": self.service.remove_food(entry_id, day),
            "entry_id": entry_id,
        }

    def record_health_measurement(
        self,
        metric: str,
        value: float,
        unit: str,
        measured_at: str | None = None,
        time_label: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Record a health measurement such as weight, BMI, BMR, or water ratio."""
        return self.service.record_measurement(
            HealthMeasurementCreate(
                metric=metric,
                value=value,
                unit=unit,
                measured_at=measured_at,
                time_label=time_label,
                notes=notes,
            )
        )

    def get_health_measurements(
        self, metric: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """List recent health measurements, optionally filtered by metric."""
        return self.service.list_measurements(metric, limit)

    def get_daily_nutrition_summary(self, day: str) -> dict[str, Any]:
        """Return kcal and macronutrient totals for a YYYY-MM-DD date."""
        return self.service.summary(date.fromisoformat(day))

    def get_day_context(self, day: str) -> dict[str, Any]:
        """Get goals, reported totals, activity, supplements, and daily notes."""
        return self.service.day_context(date.fromisoformat(day))

    def save_day_context(self, day: str, context: dict) -> dict[str, Any]:
        """Save goals, reported totals, activity, supplements, and daily notes."""
        return self.service.save_day_context(
            date.fromisoformat(day),
            DailyLogUpsert.model_validate(context),
        )


class LunaVitaAPIAdapter:
    """Configure FastAPI routes around the application service."""

    def __init__(
        self,
        database: Database,
        service: LunaVitaService,
        mcp_server: FastMCP,
    ) -> None:
        self.database = database
        self.service = service
        self.mcp_server = mcp_server
        self.app = FastAPI(
            title="LunaVita API",
            version="0.1.0",
            lifespan=self.lifespan,
        )
        self.register_routes()
        self.app.mount("/", self.mcp_server.streamable_http_app())

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        self.database.open()
        async with self.mcp_server.session_manager.run():
            yield
        self.database.close()

    def register_routes(self) -> None:
        self.app.add_api_route("/health", self.health, methods=["GET"])
        self.app.add_api_route(
            "/api/nutrition/infer",
            self.infer_food_nutrition,
            methods=["POST"],
        )
        self.app.add_api_route("/api/food", self.create_food, methods=["POST"])
        self.app.add_api_route(
            "/api/food/{entry_id}",
            self.replace_food,
            methods=["PUT"],
        )
        self.app.add_api_route(
            "/api/food/{entry_id}",
            self.remove_food,
            methods=["DELETE"],
            status_code=204,
        )
        self.app.add_api_route("/api/food", self.read_food, methods=["GET"])
        self.app.add_api_route(
            "/api/measurements",
            self.create_measurement,
            methods=["POST"],
        )
        self.app.add_api_route(
            "/api/measurements/batch",
            self.create_measurement_batch,
            methods=["POST"],
        )
        self.app.add_api_route(
            "/api/measurements",
            self.read_measurements,
            methods=["GET"],
        )
        self.app.add_api_route(
            "/api/summary/{day}",
            self.read_summary,
            methods=["GET"],
        )
        self.app.add_api_route("/api/days/{day}", self.read_day, methods=["GET"])
        self.app.add_api_route("/api/days/{day}", self.save_day, methods=["PUT"])
        self.app.add_api_route(
            "/api/reports/daily/{day}",
            self.daily_pdf,
            methods=["GET"],
        )

    def health(self) -> dict[str, str]:
        return {"status": "ok"}

    def infer_food_nutrition(
        self, request: NutritionInferenceRequest
    ) -> dict[str, Any]:
        try:
            return self.service.infer_nutrition(request).model_dump()
        except NutritionInferenceUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    def create_food(self, entry: FoodEntryCreate) -> dict[str, Any]:
        return self.service.record_food(entry)

    def replace_food(
        self, entry_id: int, entry: FoodEntryCreate
    ) -> dict[str, Any]:
        updated = self.service.update_food(entry_id, entry)
        if updated is None:
            raise HTTPException(status_code=404, detail="Food entry not found")
        return updated

    def remove_food(self, entry_id: int) -> Response:
        if not self.service.remove_food(entry_id):
            raise HTTPException(status_code=404, detail="Food entry not found")
        return Response(status_code=204)

    def read_food(
        self,
        start: date | None = None,
        end: date | None = None,
        limit: int = Query(100, ge=1, le=500),
    ) -> list[dict[str, Any]]:
        return self.service.list_food(start, end, limit)

    def create_measurement(
        self, entry: HealthMeasurementCreate
    ) -> dict[str, Any]:
        return self.service.record_measurement(entry)

    def create_measurement_batch(
        self, batch: HealthMeasurementBatchCreate
    ) -> list[dict[str, Any]]:
        return self.service.record_measurements(batch.measurements)

    def read_measurements(
        self,
        metric: str | None = None,
        limit: int = Query(100, ge=1, le=500),
    ) -> list[dict[str, Any]]:
        return self.service.list_measurements(metric, limit)

    def read_summary(self, day: date) -> dict[str, Any]:
        return self.service.summary(day)

    def read_day(self, day: date) -> dict[str, Any]:
        return self.service.day_context(day)

    def save_day(
        self, day: date, entry: DailyLogUpsert
    ) -> dict[str, Any]:
        return self.service.save_day_context(day, entry)

    def daily_pdf(self, day: date) -> Response:
        return Response(
            content=self.service.daily_report(day),
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="lunavita-{day.isoformat()}.pdf"'
                )
            },
        )


database = Database.from_env()
repository = LunaVitaRepository(database)
inference = NutritionInferenceService()
reports = DailyReportService(repository)
service = LunaVitaService(repository, inference, reports)

mcp = FastMCP("LunaVita", stateless_http=True, json_response=True)
mcp_adapter = LunaVitaMCPAdapter(mcp, service)
api_adapter = LunaVitaAPIAdapter(database, service, mcp)
app = api_adapter.app
