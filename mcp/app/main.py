from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .database import Database
from .models import (
    DailyLogUpsert,
    DailyRecommendationsUpsert,
    FoodEntryCreate,
    HealthMeasurementBatchCreate,
    HealthMeasurementCreate,
)
from .report_tools import CurrentLogPdfTool
from .reports import DailyReportService
from .repository import LunaVitaRepository
from .services import LunaVitaService


class LunaVitaMCPAdapter:
    """Expose application services as conversational MCP tools."""

    LOCAL_TIMEZONE = ZoneInfo("Asia/Kolkata")

    def __init__(self, server: FastMCP, service: LunaVitaService) -> None:
        self.server = server
        self.service = service
        self.current_log_pdf = CurrentLogPdfTool(service)
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
            self.get_current_log_pdf,
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

    def get_current_log_pdf(self):
        """Generate and return today's complete Luna Vita log as a PDF.

        The current day is determined in the Asia/Kolkata timezone. The PDF is
        generated from the latest saved food, context, and measurement data and
        returned as an embedded application/pdf resource.
        """
        return self.current_log_pdf.generate()

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
        if birth_date is not None and birth_date > datetime.now(
            self.LOCAL_TIMEZONE
        ).date():
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


class LunaVitaHTTPAdapter:
    """Expose UI-facing HTTP routes through the existing FastMCP server."""

    def __init__(self, server: FastMCP, service: LunaVitaService) -> None:
        self.server = server
        self.service = service
        self.register_routes()

    @classmethod
    def json_value(cls, value: Any) -> Any:
        """Convert repository values into JSON-compatible primitives."""
        if isinstance(value, BaseModel):
            return cls.json_value(value.model_dump())
        if isinstance(value, dict):
            return {key: cls.json_value(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls.json_value(item) for item in value]
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        return value

    @classmethod
    def json_response(cls, value: Any, status_code: int = 200) -> JSONResponse:
        return JSONResponse(cls.json_value(value), status_code=status_code)

    @staticmethod
    async def payload(request: Request, model: type[BaseModel]) -> BaseModel:
        return model.model_validate(await request.json())

    @staticmethod
    def bounded_limit(request: Request) -> int:
        limit = int(request.query_params.get("limit", "100"))
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        return limit

    @classmethod
    def error_response(cls, error: Exception) -> JSONResponse:
        if isinstance(error, ValidationError):
            return cls.json_response({"error": "Invalid request", "details": error.errors()}, 422)
        if isinstance(error, (ValueError, TypeError)):
            return cls.json_response({"error": str(error)}, 400)
        return cls.json_response({"error": str(error)}, 500)

    def register_routes(self) -> None:
        service = self.service

        @self.server.custom_route("/health", methods=["GET"])
        async def health_route(request: Request) -> JSONResponse:
            del request
            return self.json_response({"status": "ok"})

        @self.server.custom_route("/api/food", methods=["POST"])
        async def create_food_route(request: Request) -> JSONResponse:
            try:
                entry = await self.payload(request, FoodEntryCreate)
                return self.json_response(service.record_food(entry), 201)
            except Exception as error:
                return self.error_response(error)

        @self.server.custom_route("/api/food", methods=["GET"])
        async def read_food_route(request: Request) -> JSONResponse:
            try:
                start = request.query_params.get("start")
                end = request.query_params.get("end")
                result = service.list_food(
                    date.fromisoformat(start) if start else None,
                    date.fromisoformat(end) if end else None,
                    self.bounded_limit(request),
                )
                return self.json_response(result)
            except Exception as error:
                return self.error_response(error)

        @self.server.custom_route("/api/food/{entry_id}", methods=["PUT"])
        async def replace_food_route(request: Request) -> JSONResponse:
            try:
                entry = await self.payload(request, FoodEntryCreate)
                result = service.update_food(int(request.path_params["entry_id"]), entry)
                if result is None:
                    return self.json_response({"error": "Food entry not found"}, 404)
                return self.json_response(result)
            except Exception as error:
                return self.error_response(error)

        @self.server.custom_route("/api/food/{entry_id}", methods=["DELETE"])
        async def delete_food_route(request: Request) -> Response:
            try:
                if not service.remove_food(int(request.path_params["entry_id"])):
                    return self.json_response({"error": "Food entry not found"}, 404)
                return Response(status_code=204)
            except Exception as error:
                return self.error_response(error)

        @self.server.custom_route("/api/measurements", methods=["POST"])
        async def create_measurement_route(request: Request) -> JSONResponse:
            try:
                entry = await self.payload(request, HealthMeasurementCreate)
                return self.json_response(service.record_measurement(entry), 201)
            except Exception as error:
                return self.error_response(error)

        @self.server.custom_route("/api/measurements/batch", methods=["POST"])
        async def create_measurement_batch_route(request: Request) -> JSONResponse:
            try:
                batch = await self.payload(request, HealthMeasurementBatchCreate)
                return self.json_response(service.record_measurements(batch.measurements), 201)
            except Exception as error:
                return self.error_response(error)

        @self.server.custom_route("/api/measurements", methods=["GET"])
        async def read_measurements_route(request: Request) -> JSONResponse:
            try:
                result = service.list_measurements(
                    request.query_params.get("metric"), self.bounded_limit(request)
                )
                return self.json_response(result)
            except Exception as error:
                return self.error_response(error)

        @self.server.custom_route("/api/measurements/{entry_id}", methods=["PUT"])
        async def replace_measurement_route(request: Request) -> JSONResponse:
            try:
                entry = await self.payload(request, HealthMeasurementCreate)
                result = service.update_measurement(
                    int(request.path_params["entry_id"]), entry
                )
                if result is None:
                    return self.json_response({"error": "Measurement not found"}, 404)
                return self.json_response(result)
            except Exception as error:
                return self.error_response(error)

        @self.server.custom_route("/api/measurements/{entry_id}", methods=["DELETE"])
        async def delete_measurement_route(request: Request) -> Response:
            try:
                if not service.remove_measurement(int(request.path_params["entry_id"])):
                    return self.json_response({"error": "Measurement not found"}, 404)
                return Response(status_code=204)
            except Exception as error:
                return self.error_response(error)

        @self.server.custom_route("/api/recommendations", methods=["GET"])
        async def recommendations_route(request: Request) -> JSONResponse:
            del request
            return self.json_response(service.daily_recommendations())

        @self.server.custom_route("/api/summary/{day}", methods=["GET"])
        async def summary_route(request: Request) -> JSONResponse:
            try:
                return self.json_response(
                    service.summary(date.fromisoformat(request.path_params["day"]))
                )
            except Exception as error:
                return self.error_response(error)

        @self.server.custom_route("/api/days/{day}", methods=["GET"])
        async def day_route(request: Request) -> JSONResponse:
            try:
                return self.json_response(
                    service.day_context(date.fromisoformat(request.path_params["day"]))
                )
            except Exception as error:
                return self.error_response(error)

        @self.server.custom_route("/api/days/{day}", methods=["PUT"])
        async def save_day_route(request: Request) -> JSONResponse:
            try:
                entry = await self.payload(request, DailyLogUpsert)
                result = service.save_day_context(
                    date.fromisoformat(request.path_params["day"]), entry
                )
                return self.json_response(result)
            except Exception as error:
                return self.error_response(error)

        @self.server.custom_route("/api/reports/daily/{day}", methods=["GET"])
        async def daily_report_route(request: Request) -> Response:
            try:
                day = date.fromisoformat(request.path_params["day"])
                return Response(
                    service.daily_report(day),
                    media_type="application/pdf",
                    headers={
                        "Content-Disposition": (
                            f'attachment; filename="lunavita-{day.isoformat()}.pdf"'
                        )
                    },
                )
            except Exception as error:
                return self.error_response(error)


class LunaVitaApplication:
    """Compose and own Luna Vita's database, services, MCP, and HTTP adapters."""

    def __init__(self) -> None:
        self.database = Database.from_env()
        self.repository = LunaVitaRepository(self.database)
        self.reports = DailyReportService(self.repository)
        self.service = LunaVitaService(self.repository, self.reports)
        self.database.open()
        self.service.ensure_schema()
        self.mcp = FastMCP(
            "LunaVita",
            host="0.0.0.0",
            port=8000,
            stateless_http=True,
            json_response=True,
        )
        self.mcp_adapter = LunaVitaMCPAdapter(self.mcp, self.service)
        self.http_adapter = LunaVitaHTTPAdapter(self.mcp, self.service)

    def run(self) -> None:
        try:
            self.mcp.run(transport="streamable-http")
        finally:
            self.database.close()


application = LunaVitaApplication()
mcp = application.mcp
app = mcp.streamable_http_app()

if __name__ == "__main__":
    application.run()
