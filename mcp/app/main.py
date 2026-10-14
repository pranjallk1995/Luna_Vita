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
    DailyRecommendationsUpsert,
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
            self.set_food_image,
            self.remove_food,
            self.record_health_measurement,
            self.get_health_measurements,
            self.get_daily_nutrition_summary,
            self.get_day_context,
            self.save_day_context,
            self.update_daily_recommendations,
            self.get_daily_recommendations,
            self.update_body_profile,
        ):
            self.server.tool()(tool)

    def record_food(
        self,
        food_name: str,
        quantity: str,
        calories: int,
        protein_g: float,
        carbs_g: float,
        fat_g: float,
        natural_sugar_g: float,
        added_sugar_g: float,
        image_url: str | None,
        meal_type: str = "other",
        consumed_at: str | None = None,
        consumed_date: str | None = None,
        time_label: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Record a food item after completing its nutrition estimate.

        Food name and quantity are mandatory. When the user omits kcal, protein,
        carbs, fat, natural sugar, added sugar, or an image, infer those values
        from the stated food and complete quantity before calling this tool.
        Supply a representative verified image URL/data URI when available;
        otherwise pass null rather than inventing a URL.
        """
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
                image_url=image_url,
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
        natural_sugar_g: float,
        added_sugar_g: float,
        image_url: str | None,
        consumed_at: str | None = None,
        consumed_date: str | None = None,
    ) -> dict[str, Any]:
        """Log food reported conversationally by the user.

        Use this tool when the user says they ate or drank something and wants
        LunaVita to track it, including natural statements such as "I had 4
        parathas of 40 g each right now". Food name and quantity are mandatory.
        Infer kcal, protein, carbs, fat, natural sugar, and added sugar for the
        complete stated quantity before calling the tool. Also supply a
        representative verified image URL/data URI when available; pass null
        rather than inventing a URL. Use the current date/time when the user says
        "now"; otherwise preserve the stated time.
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
            image_url=image_url,
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
        quantity: str,
        calories: int,
        protein_g: float,
        carbs_g: float,
        fat_g: float,
        natural_sugar_g: float,
        added_sugar_g: float,
        image_url: str | None,
        meal_type: str = "other",
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
            image_url=image_url,
            consumed_at=consumed_at,
            consumed_date=consumed_date,
            time_label=time_label,
            notes=notes,
        )
        updated = self.service.update_food(entry_id, entry)
        return {"updated": updated is not None, "entry": updated}

    def set_food_image(
        self, entry_id: int, image_url: str | None = None
    ) -> dict[str, Any]:
        """Set, replace, or clear the optional image URL for a food entry."""
        updated = self.service.set_food_image(entry_id, image_url)
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


    def update_daily_recommendations(
        self,
        calories_kcal: int,
        protein_g: float,
        carbs_g: float,
        fat_g: float,
        sugars_g: float,
        height_cm: float,
        sex: str,
        birth_date: str | None = None,
        weight_kg: float | None = None,
        goal: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Replace the current daily nutrition recommendations and body profile.

        Calories are in kcal. Protein, carbohydrates, fat, and sugars are in
        grams. Treat sugars_g as the daily free/added-sugar ceiling rather than
        a limit on intrinsic sugars in whole fruit or unsweetened dairy.
        """
        entry = DailyRecommendationsUpsert(
            calories_kcal=calories_kcal,
            protein_g=protein_g,
            carbs_g=carbs_g,
            fat_g=fat_g,
            sugars_g=sugars_g,
            height_cm=height_cm,
            sex=sex,
            birth_date=birth_date,
            weight_kg=weight_kg,
            goal=goal,
            notes=notes,
        )
        return self.service.update_daily_recommendations(entry)

    def get_daily_recommendations(self) -> dict[str, Any] | None:
        """Return the current daily nutrition recommendations and body profile."""
        return self.service.daily_recommendations()


    def update_body_profile(
        self,
        height_cm: float | None = None,
        date_of_birth: str | None = None,
        sex: str | None = None,
        weight_kg: float | None = None,
    ) -> dict[str, Any]:
        """Update any supplied body-profile fields while preserving the rest.

        Store date_of_birth as YYYY-MM-DD. Age is calculated dynamically from
        that date, so it automatically changes on the person's birthday.
        """
        if all(
            value is None
            for value in (height_cm, date_of_birth, sex, weight_kg)
        ):
            raise ValueError("Provide at least one body-profile field.")
        if height_cm is not None and not 0 < height_cm <= 300:
            raise ValueError("height_cm must be between 0 and 300.")
        if weight_kg is not None and not 0 < weight_kg <= 1000:
            raise ValueError("weight_kg must be between 0 and 1000.")
        if sex is not None and sex not in {"male", "female", "other"}:
            raise ValueError("sex must be male, female, or other.")
        birth_date = date.fromisoformat(date_of_birth) if date_of_birth else None
        if birth_date is not None and birth_date > date.today():
            raise ValueError("date_of_birth cannot be in the future.")
        updated = self.service.update_body_profile(
            height_cm=height_cm,
            birth_date=birth_date,
            sex=sex,
            weight_kg=weight_kg,
        )
        if updated is None:
            raise ValueError("Daily recommendations have not been created.")
        return updated


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
        self.service.ensure_schema()
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
            "/api/measurements/{entry_id}",
            self.replace_measurement,
            methods=["PUT"],
        )
        self.app.add_api_route(
            "/api/measurements/{entry_id}",
            self.remove_measurement,
            methods=["DELETE"],
            status_code=204,
        )
        self.app.add_api_route(
            "/api/recommendations",
            self.read_recommendations,
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

    def replace_measurement(
        self, entry_id: int, entry: HealthMeasurementCreate
    ) -> dict[str, Any]:
        updated = self.service.update_measurement(entry_id, entry)
        if updated is None:
            raise HTTPException(status_code=404, detail="Measurement not found")
        return updated

    def remove_measurement(self, entry_id: int) -> Response:
        if not self.service.remove_measurement(entry_id):
            raise HTTPException(status_code=404, detail="Measurement not found")
        return Response(status_code=204)

    def read_measurements(
        self,
        metric: str | None = None,
        limit: int = Query(100, ge=1, le=500),
    ) -> list[dict[str, Any]]:
        return self.service.list_measurements(metric, limit)

    def read_recommendations(self) -> dict[str, Any] | None:
        return self.service.daily_recommendations()

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
