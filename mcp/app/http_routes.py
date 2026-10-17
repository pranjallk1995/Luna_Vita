"""REST routes used by the Luna Vita Streamlit dashboard."""

from collections.abc import Awaitable, Callable
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .errors import NotFoundError
from .models import (
    DailyLogUpsert,
    FoodEntryCreate,
    HealthMeasurementBatchCreate,
    HealthMeasurementCreate,
)
from .services import LunaVitaService

Handler = Callable[[Request], Awaitable[Any]]
NO_CONTENT = 204


class LunaVitaHTTPRoutes:
    """Translate HTTP requests into service calls and results into JSON."""

    def __init__(self, server: FastMCP, service: LunaVitaService) -> None:
        self.server = server
        self.service = service
        self._register()

    @classmethod
    def json_value(cls, value: Any) -> Any:
        """Convert service values into JSON-compatible primitives."""
        if isinstance(value, BaseModel):
            return cls.json_value(value.model_dump())
        if isinstance(value, BaseException):
            return str(value)
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
    def response(cls, value: Any, status: int = 200) -> Response:
        if isinstance(value, Response):
            return value
        if status == NO_CONTENT:
            return Response(status_code=NO_CONTENT)
        return JSONResponse(cls.json_value(value), status_code=status)

    @classmethod
    def error(cls, error: Exception) -> Response:
        if isinstance(error, ValidationError):
            return cls.response({"error": "Invalid request", "details": error.errors()}, 422)
        if isinstance(error, NotFoundError):
            return cls.response({"error": str(error) or "Not found"}, 404)
        if isinstance(error, (ValueError, TypeError)):
            return cls.response({"error": str(error)}, 400)
        return cls.response({"error": str(error)}, 500)

    @staticmethod
    async def payload(request: Request, model: type[BaseModel]) -> Any:
        return model.model_validate(await request.json())

    @staticmethod
    def path_id(request: Request) -> int:
        return int(request.path_params["entry_id"])

    @staticmethod
    def path_day(request: Request) -> date:
        return date.fromisoformat(request.path_params["day"])

    @staticmethod
    def query_date(request: Request, name: str) -> date | None:
        value = request.query_params.get(name)
        return date.fromisoformat(value) if value else None

    @staticmethod
    def bounded_limit(request: Request) -> int:
        limit = int(request.query_params.get("limit", "100"))
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        return limit

    @staticmethod
    def found(value: Any, message: str) -> Any:
        """Return ``value``, raising a 404 when the target row did not exist."""
        if value is None or value is False:
            raise NotFoundError(message)
        return value

    def route(self, method: str, path: str, handler: Handler, status: int = 200) -> None:
        """Register ``handler`` with uniform error translation."""

        async def endpoint(request: Request) -> Response:
            try:
                return self.response(await handler(request), status)
            except Exception as error:
                return self.error(error)

        self.server.custom_route(path, methods=[method])(endpoint)

    def _register(self) -> None:
        self.route("GET", "/health", self.health)
        self._register_food()
        self._register_measurements()
        self._register_days()

    async def health(self, request: Request) -> dict:
        return {"status": "ok", "service": "luna-vita"}

    def _register_food(self) -> None:
        food = self.service.food
        missing = "Food entry not found"

        async def create(request: Request):
            return food.record(await self.payload(request, FoodEntryCreate))

        async def read(request: Request):
            return food.list(
                self.query_date(request, "start"),
                self.query_date(request, "end"),
                self.bounded_limit(request),
            )

        async def replace(request: Request):
            entry = await self.payload(request, FoodEntryCreate)
            return self.found(food.update(self.path_id(request), entry), missing)

        async def delete(request: Request):
            self.found(food.remove(self.path_id(request)), missing)

        self.route("POST", "/api/food", create, 201)
        self.route("GET", "/api/food", read)
        self.route("PUT", "/api/food/{entry_id}", replace)
        self.route("DELETE", "/api/food/{entry_id}", delete, NO_CONTENT)

    def _register_measurements(self) -> None:
        measurements = self.service.measurements
        missing = "Measurement not found"

        async def create(request: Request):
            return measurements.record(await self.payload(request, HealthMeasurementCreate))

        async def create_batch(request: Request):
            batch = await self.payload(request, HealthMeasurementBatchCreate)
            return measurements.record_many(batch.measurements)

        async def read(request: Request):
            return measurements.list(
                request.query_params.get("metric"), self.bounded_limit(request)
            )

        async def replace(request: Request):
            entry = await self.payload(request, HealthMeasurementCreate)
            return self.found(measurements.update(self.path_id(request), entry), missing)

        async def delete(request: Request):
            self.found(measurements.remove(self.path_id(request)), missing)

        self.route("POST", "/api/measurements", create, 201)
        self.route("POST", "/api/measurements/batch", create_batch, 201)
        self.route("GET", "/api/measurements", read)
        self.route("PUT", "/api/measurements/{entry_id}", replace)
        self.route("DELETE", "/api/measurements/{entry_id}", delete, NO_CONTENT)

    def _register_days(self) -> None:
        service = self.service

        async def food_analysis(request: Request):
            return service.analysis.analyze(
                self.query_date(request, "start"), self.query_date(request, "end")
            )

        async def displayed_analysis(request: Request):
            return service.analysis.analyze_displayed(self.query_date(request, "day"))

        async def recommendations(request: Request):
            return service.profile.get()

        async def summary(request: Request):
            return service.food.totals(self.path_day(request))

        async def read_day(request: Request):
            return service.days.get(self.path_day(request))

        async def save_day(request: Request):
            entry = await self.payload(request, DailyLogUpsert)
            return service.days.save(self.path_day(request), entry)

        async def daily_report(request: Request):
            day = self.path_day(request)
            filename = service.reports.filename(day)
            return Response(
                service.reports.daily_pdf(day),
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

        self.route("GET", "/api/analysis", food_analysis)
        self.route("GET", "/api/analysis/displayed", displayed_analysis)
        self.route("GET", "/api/recommendations", recommendations)
        self.route("GET", "/api/summary/{day}", summary)
        self.route("GET", "/api/days/{day}", read_day)
        self.route("PUT", "/api/days/{day}", save_day)
        self.route("GET", "/api/reports/daily/{day}", daily_report)
