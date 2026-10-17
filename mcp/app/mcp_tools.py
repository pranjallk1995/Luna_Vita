"""MCP tools that let LLM clients track Luna Vita nutrition and measurements."""

from datetime import date
from typing import Any

from mcp.server.fastmcp import FastMCP

from .models import (
    BodyProfileUpdate,
    DailyLogUpsert,
    DailyRecommendationsUpsert,
    FoodEntryCreate,
    HealthMeasurementCreate,
)
from .report_tools import CurrentLogPdfTool
from .services import LunaVitaService


class LunaVitaMCPTools:
    """Register Luna Vita's MCP tool surface on a FastMCP server."""

    def __init__(self, server: FastMCP, service: LunaVitaService) -> None:
        self.server = server
        self.service = service
        self._register_food_tools()
        self._register_measurement_tools()
        self._register_day_tools()
        self._register_profile_tools()

    @staticmethod
    def optional_date(value: str | None) -> date | None:
        return date.fromisoformat(value) if value else None

    @staticmethod
    def update_result(entry: dict[str, Any] | None) -> dict[str, Any]:
        return {"updated": entry is not None, "entry": entry}

    def _register_food_tools(self) -> None:
        server, food = self.server, self.service.food
        optional_date, update_result = self.optional_date, self.update_result

        @server.tool()
        def record_food(
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
            Always search Luna Visia for an appropriate representative image before
            calling this tool. Prefer a verified immutable image-ID URL returned by
            Luna Visia when a suitable match exists. Only pass null when that search
            finds no suitable image; never invent or construct a filename-based URL.
            """
            return food.record(
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

        @server.tool()
        def log_consumed_food(
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
            complete stated quantity before calling the tool. Always search Luna
            Visia for an appropriate representative image first and prefer its
            verified immutable image-ID URL when a suitable match exists. Only pass
            null when that search finds no suitable image; never invent or construct
            a filename-based URL. Use the
            current date/time when the user says "now"; otherwise preserve the
            stated time.
            """
            return food.log_consumed(
                description,
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
                ),
            )

        @server.tool()
        def get_food_log(
            start_date: str | None = None,
            end_date: str | None = None,
            limit: int = 100,
        ) -> list[dict[str, Any]]:
            """List food entries within an optional inclusive YYYY-MM-DD range."""
            return food.list(optional_date(start_date), optional_date(end_date), limit)

        @server.tool()
        def update_food(
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
            return update_result(food.update(entry_id, entry))

        @server.tool()
        def set_food_image(entry_id: int, image_url: str | None = None) -> dict[str, Any]:
            """Set, replace, or clear the optional image URL for a food entry."""
            return update_result(food.set_image(entry_id, image_url))

        @server.tool()
        def remove_food(entry_id: int, expected_date: str | None = None) -> dict[str, Any]:
            """Remove food by id, optionally requiring an expected YYYY-MM-DD date."""
            return {
                "deleted": food.remove(entry_id, optional_date(expected_date)),
                "entry_id": entry_id,
            }

        @server.tool()
        def get_daily_nutrition_summary(day: str) -> dict[str, Any]:
            """Return kcal and macronutrient totals for a YYYY-MM-DD date."""
            return food.totals(date.fromisoformat(day))

    def _register_measurement_tools(self) -> None:
        server, measurements = self.server, self.service.measurements
        update_result = self.update_result

        @server.tool()
        def record_health_measurement(
            metric: str,
            value: float,
            unit: str,
            measured_at: str | None = None,
            time_label: str | None = None,
            notes: str | None = None,
        ) -> dict[str, Any]:
            """Record a health measurement such as weight, BMI, BMR, or water ratio."""
            return measurements.record(
                HealthMeasurementCreate(
                    metric=metric,
                    value=value,
                    unit=unit,
                    measured_at=measured_at,
                    time_label=time_label,
                    notes=notes,
                )
            )

        @server.tool()
        def get_health_measurements(
            metric: str | None = None, limit: int = 100
        ) -> list[dict[str, Any]]:
            """List recent health measurements, optionally filtered by metric."""
            return measurements.list(metric, limit)

        @server.tool()
        def update_health_measurement(
            entry_id: int,
            metric: str,
            value: float,
            unit: str,
            measured_at: str | None = None,
            time_label: str | None = None,
            notes: str | None = None,
        ) -> dict[str, Any]:
            """Replace an entire body-measurement entry by its database id."""
            entry = HealthMeasurementCreate(
                metric=metric,
                value=value,
                unit=unit,
                measured_at=measured_at,
                time_label=time_label,
                notes=notes,
            )
            return update_result(measurements.update(entry_id, entry))

        @server.tool()
        def remove_health_measurement(entry_id: int) -> dict[str, Any]:
            """Remove an entire body-measurement entry by its database id."""
            return {"deleted": measurements.remove(entry_id), "entry_id": entry_id}

    def _register_day_tools(self) -> None:
        server, days = self.server, self.service.days
        current_log_pdf = CurrentLogPdfTool(self.service.reports)

        @server.tool()
        def get_current_log_pdf():
            """Generate and return today's complete Luna Vita log as a PDF.

            The current day is determined in the Asia/Kolkata timezone. The PDF is
            generated from the latest saved food, context, and measurement data and
            returned as an embedded application/pdf resource.
            """
            return current_log_pdf.generate()

        @server.tool()
        def get_day_context(day: str) -> dict[str, Any]:
            """Get goals, reported totals, activity, supplements, and daily notes."""
            return days.get(date.fromisoformat(day))

        @server.tool()
        def save_day_context(day: str, context: dict) -> dict[str, Any]:
            """Save goals, reported totals, activity, supplements, and daily notes."""
            return days.save(date.fromisoformat(day), DailyLogUpsert.model_validate(context))

    def _register_profile_tools(self) -> None:
        server, profile = self.server, self.service.profile

        @server.tool()
        def update_daily_recommendations(
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
            return profile.replace(entry)

        @server.tool()
        def get_daily_recommendations() -> dict[str, Any] | None:
            """Return the current daily nutrition recommendations and body profile."""
            return profile.get()

        @server.tool()
        def update_body_profile(
            height_cm: float | None = None,
            date_of_birth: str | None = None,
            sex: str | None = None,
            weight_kg: float | None = None,
        ) -> dict[str, Any]:
            """Update any supplied body-profile fields while preserving the rest.

            Store date_of_birth as YYYY-MM-DD. Age is calculated dynamically from
            that date, so it automatically changes on the person's birthday.
            """
            entry = BodyProfileUpdate(
                height_cm=height_cm,
                birth_date=date_of_birth or None,
                sex=sex,
                weight_kg=weight_kg,
            )
            return profile.update_body(entry)
