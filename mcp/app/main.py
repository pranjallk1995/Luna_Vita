from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, HTTPException, Query, Response
from mcp.server.fastmcp import FastMCP

from .database import close_pool, open_pool
from .inference import (
    NutritionInferenceRequest,
    NutritionInferenceUnavailable,
    infer_nutrition,
)
from .models import DailyLogUpsert, FoodEntryCreate, HealthMeasurementCreate
from .repository import (
    add_food_entry,
    add_health_measurement,
    delete_food_entry,
    daily_summary,
    get_daily_log,
    list_food_entries,
    list_health_measurements,
    update_food_entry,
    upsert_daily_log,
)
from .reports import daily_report_pdf


mcp = FastMCP("LunaVita", stateless_http=True, json_response=True)


@mcp.tool()
def record_food(
    food_name: str, calories: int, quantity: str | None = None,
    meal_type: str = "other", protein_g: float = 0, carbs_g: float = 0,
    fat_g: float = 0, natural_sugar_g: float = 0, added_sugar_g: float = 0,
    consumed_at: str | None = None, time_label: str | None = None,
    notes: str | None = None,
) -> dict:
    """Record food and its calories/macronutrients."""
    payload = FoodEntryCreate(
        food_name=food_name, quantity=quantity, calories=calories, meal_type=meal_type,
        protein_g=protein_g, carbs_g=carbs_g, fat_g=fat_g,
        natural_sugar_g=natural_sugar_g, added_sugar_g=added_sugar_g,
        consumed_at=consumed_at, time_label=time_label, notes=notes,
    )
    return add_food_entry(payload)


@mcp.tool()
def get_food_log(start_date: str | None = None, end_date: str | None = None, limit: int = 100) -> list[dict]:
    """List food entries, optionally within an inclusive YYYY-MM-DD date range."""
    start = date.fromisoformat(start_date) if start_date else None
    end = date.fromisoformat(end_date) if end_date else None
    return list_food_entries(start, end, limit)


@mcp.tool()
def update_food(
    entry_id: int, food_name: str, calories: int, quantity: str | None = None,
    meal_type: str = "other", protein_g: float = 0, carbs_g: float = 0,
    fat_g: float = 0, natural_sugar_g: float = 0, added_sugar_g: float = 0,
    consumed_at: str | None = None, time_label: str | None = None,
    notes: str | None = None,
) -> dict:
    """Update an existing food entry by its id."""
    entry = FoodEntryCreate(food_name=food_name, quantity=quantity, calories=calories, meal_type=meal_type,
                            protein_g=protein_g, carbs_g=carbs_g, fat_g=fat_g,
                            natural_sugar_g=natural_sugar_g, added_sugar_g=added_sugar_g,
                            consumed_at=consumed_at, time_label=time_label, notes=notes)
    updated = update_food_entry(entry_id, entry)
    return {"updated": updated is not None, "entry": updated}


@mcp.tool()
def remove_food(entry_id: int, expected_date: str | None = None) -> dict:
    """Remove a food entry by id, optionally requiring it to belong to a YYYY-MM-DD date."""
    day = date.fromisoformat(expected_date) if expected_date else None
    return {"deleted": delete_food_entry(entry_id, day), "entry_id": entry_id}


@mcp.tool()
def record_health_measurement(
    metric: str, value: float, unit: str, measured_at: str | None = None, notes: str | None = None
) -> dict:
    """Record a health measurement such as weight, steps, sleep, or blood pressure."""
    return add_health_measurement(
        HealthMeasurementCreate(metric=metric, value=value, unit=unit, measured_at=measured_at, notes=notes)
    )


@mcp.tool()
def get_health_measurements(metric: str | None = None, limit: int = 100) -> list[dict]:
    """List recent health measurements, optionally filtered by metric name."""
    return list_health_measurements(metric, limit)


@mcp.tool()
def get_daily_nutrition_summary(day: str) -> dict:
    """Return total calories and macronutrients for a YYYY-MM-DD date."""
    return daily_summary(date.fromisoformat(day))


@mcp.tool()
def get_day_context(day: str) -> dict:
    """Get daily goals, reported totals, activity, supplements, notes, and report caveats."""
    return get_daily_log(date.fromisoformat(day))


@mcp.tool()
def save_day_context(day: str, context: dict) -> dict:
    """Save daily goals, reported totals, activity, supplements, notes, and report caveats."""
    return upsert_daily_log(date.fromisoformat(day), DailyLogUpsert.model_validate(context))


mcp_app = mcp.streamable_http_app()


@asynccontextmanager
async def lifespan(app: FastAPI):
    open_pool()
    async with mcp.session_manager.run():
        yield
    close_pool()


app = FastAPI(title="LunaVita API", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/nutrition/infer")
def infer_food_nutrition(request: NutritionInferenceRequest) -> dict:
    try:
        return infer_nutrition(request).model_dump()
    except NutritionInferenceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/food")
def create_food(entry: FoodEntryCreate) -> dict:
    return add_food_entry(entry)


@app.put("/api/food/{entry_id}")
def replace_food(entry_id: int, entry: FoodEntryCreate) -> dict:
    updated = update_food_entry(entry_id, entry)
    if updated is None:
        raise HTTPException(status_code=404, detail="Food entry not found")
    return updated


@app.delete("/api/food/{entry_id}", status_code=204)
def remove_food_api(entry_id: int) -> Response:
    if not delete_food_entry(entry_id):
        raise HTTPException(status_code=404, detail="Food entry not found")
    return Response(status_code=204)


@app.get("/api/food")
def read_food(start: date | None = None, end: date | None = None, limit: int = Query(100, ge=1, le=500)) -> list[dict]:
    return list_food_entries(start, end, limit)


@app.post("/api/measurements")
def create_measurement(entry: HealthMeasurementCreate) -> dict:
    return add_health_measurement(entry)


@app.get("/api/measurements")
def read_measurements(metric: str | None = None, limit: int = Query(100, ge=1, le=500)) -> list[dict]:
    return list_health_measurements(metric, limit)


@app.get("/api/summary/{day}")
def read_summary(day: date) -> dict:
    return daily_summary(day)


@app.get("/api/days/{day}")
def read_day(day: date) -> dict:
    return get_daily_log(day)


@app.put("/api/days/{day}")
def save_day(day: date, entry: DailyLogUpsert) -> dict:
    return upsert_daily_log(day, entry)


@app.get("/api/reports/daily/{day}")
def daily_pdf(day: date) -> Response:
    return Response(content=daily_report_pdf(day), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="lunavita-{day.isoformat()}.pdf"'})


app.mount("/", mcp_app)
