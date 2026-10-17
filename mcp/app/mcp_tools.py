"""MCP tools that let LLM clients track Luna Vita nutrition and measurements."""

from datetime import date
from typing import Any

from mcp.server.fastmcp import FastMCP

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
        self._register_analysis_tools()

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

    def _register_analysis_tools(self) -> None:
        server, analysis = self.server, self.service.analysis
        optional_date = self.optional_date

        @server.tool()
        def get_food_analysis(
            start_date: str | None = None, end_date: str | None = None
        ) -> dict[str, Any]:
            """Return Luna Vita's food analysis for the Monthly Tracking tab.

            With no dates, returns exactly what the tab currently shows: the saved
            range from set_monthly_range, or the current calendar month. With both
            YYYY-MM-DD dates that range is analysed; with one date, that date's
            calendar month. Neither changes what the tab shows. The result lists
            every food with its count, days eaten, macro totals, calorie shares,
            and verdict (source "rule" or "override"), plus top contributors per
            nutrient, the prefer/avoid lists, and range_source ("saved", "month",
            or "requested"). Call this before renaming foods or changing verdicts.
            """
            if start_date or end_date:
                return analysis.analyze(optional_date(start_date), optional_date(end_date))
            return analysis.analyze_displayed()

        @server.tool()
        def set_monthly_range(start_date: str, end_date: str) -> dict[str, Any]:
            """Choose the inclusive YYYY-MM-DD date range the Monthly tab shows.

            Use this when the user wants the Monthly Tracking view to cover a
            specific period, such as "the last 3 days", "1-15 October", or "since I
            started tracking". The range stays until reset_monthly_range is called
            and can cover at most 366 days. Resolve relative phrases to dates in
            the Asia/Kolkata timezone. Returns the range now shown.
            """
            return analysis.set_range(
                AnalysisRange(start_date=start_date, end_date=end_date)
            )

        @server.tool()
        def reset_monthly_range() -> dict[str, Any]:
            """Return the Monthly tab to the calendar month of the selected date."""
            return analysis.reset_range()

        @server.tool()
        def get_monthly_range() -> dict[str, Any]:
            """Report the date range the Monthly tab shows and whether it was saved."""
            return analysis.range_status()

        @server.tool()
        def rename_food(
            current_name: str,
            new_name: str,
            start_date: str | None = None,
            end_date: str | None = None,
        ) -> dict[str, Any]:
            """Rename every food entry matching current_name, optionally within dates.

            Matching ignores case, punctuation, spacing, and a trailing plural "s",
            so "parathas" also matches "Paratha". Use this to fix a misspelling or
            to merge duplicates (for example rename "ON Gold Standard Whey" to
            "Whey protein"). Counts, macro totals, top contributors, and rule-based
            verdicts are derived from the entries, so they update automatically.
            A verdict override moves to the new name once no entry uses the old
            one. Returns the number renamed and the merged food's new summary.
            """
            return analysis.rename(
                FoodRename(
                    current_name=current_name,
                    new_name=new_name,
                    start_date=optional_date(start_date),
                    end_date=optional_date(end_date),
                )
            )

        @server.tool()
        def set_food_verdict(food_name: str, verdict: str, reason: str) -> dict[str, Any]:
            """Set a food's Food choices verdict, replacing the macro-based rating.

            verdict is "prefer", "avoid", or "neutral" ("neutral" removes it from
            both lists). reason is the short explanation shown in the UI, for
            example "Homemade, so far less oil than the macros suggest". The
            override applies to every period and to all spellings of the name.
            """
            return analysis.set_verdict(
                FoodVerdictUpsert(food_name=food_name, verdict=verdict, reason=reason)
            )

        @server.tool()
        def clear_food_verdict(food_name: str) -> dict[str, Any]:
            """Remove a verdict override so the food is rated by its macros again."""
            return {"cleared": analysis.clear_verdict(food_name), "food_name": food_name}

        @server.tool()
        def list_food_verdicts() -> list[dict[str, Any]]:
            """List every verdict override with its food name, verdict, and reason."""
            return analysis.list_verdicts()
