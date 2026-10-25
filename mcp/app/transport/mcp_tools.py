"""MCP tools that let LLM clients track Luna Vita nutrition and measurements."""

from datetime import date, timedelta
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.core.clock import LocalClock
from app.core.models import (
    BodyFatTargetUpdate,
    AnalysisRange,
    BodyProfileUpdate,
    DailyLogUpsert,
    DailyRecommendationsUpsert,
    ExerciseBatch,
    ExerciseEntry,
    FoodAliasUpsert,
    FoodEntryCreate,
    FoodRename,
    FoodVerdictUpsert,
    HealthMeasurementCreate,
    WorkoutBatch,
    WorkoutRecord,
    WorkoutType,
)
from app.transport.report_tools import CurrentLogPdfTool
from app.services.application import LunaVitaService


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
        self._register_workout_tools()
        self._register_average_tools()

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
            image_url: str | None = None,
            meal_type: str = "other",
            consumed_at: str | None = None,
            consumed_date: str | None = None,
            time_label: str | None = None,
            notes: str | None = None,
        ) -> dict[str, Any]:
            """Record a food item after completing its nutrition estimate.

            Food name and quantity are mandatory. When the user omits kcal,
            protein, carbs, fat, natural sugar, or added sugar, infer those values
            from the stated food and complete quantity before calling this tool.
            Name the food the way it has been logged before: call list_food_names
            first and reuse an existing name for the same food (e.g. "Paratha",
            not "parathas" or "Aloo paratha (homemade)"); put brand, preparation,
            or size details in quantity or notes instead. The saved name is
            normalized against earlier entries and food aliases anyway, and the
            returned entry shows the name actually stored.
            Always search Luna Visia for a representative image of the food first
            and pass the public_url it returns as image_url (an immutable
            .../api/public/images/<image-id> URL). If that search finds no suitable
            image, omit image_url: the entry then shows the Luna Vita placeholder,
            which asks the user to add something relevant in Luna Visia. Never
            invent a URL or pass a filename-based URL or data URI; a supplied URL is
            checked against Luna Visia and the entry is rejected if it is not found.
            """
            return food.record_with_visia_image(
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
            image_url: str | None = None,
            consumed_at: str | None = None,
            consumed_date: str | None = None,
        ) -> dict[str, Any]:
            """Log food reported conversationally by the user.

            Use this tool when the user says they ate or drank something and wants
            LunaVita to track it, including natural statements such as "I had 4
            parathas of 40 g each right now". Food name and quantity are mandatory.
            Infer kcal, protein, carbs, fat, natural sugar, and added sugar for the
            complete stated quantity before calling the tool.
            Name the food the way it has been logged before: call list_food_names
            first and reuse an existing name for the same food (e.g. "Paratha",
            not "parathas" or "Aloo paratha (homemade)"); put brand, preparation,
            or size details in quantity or notes instead. The saved name is
            normalized against earlier entries and food aliases anyway, and the
            returned entry shows the name actually stored.
            Always search Luna Visia for a representative image of the food first
            and pass the public_url it returns as image_url (an immutable
            .../api/public/images/<image-id> URL). If that search finds no suitable
            image, omit image_url: the entry then shows the Luna Vita placeholder,
            which asks the user to add something relevant in Luna Visia. Never
            invent a URL or pass a filename-based URL or data URI; a supplied URL is
            checked against Luna Visia and the entry is rejected if it is not found.
            Use the current date/time when the user says "now"; otherwise preserve
            the stated time.
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
            """Update an existing food entry by its id.

            To change what a food is called across entries, use rename_food rather
            than updating entries one by one.
            """
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
        def set_food_image(
            entry_id: int, image_url: str | None = None
        ) -> dict[str, Any]:
            """Set, replace, or clear the optional image URL for a food entry."""
            return update_result(food.set_image(entry_id, image_url))

        @server.tool()
        def remove_food(
            entry_id: int, expected_date: str | None = None
        ) -> dict[str, Any]:
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

        body = self.service.body

        @server.tool()
        def get_body_composition(
            start_date: str | None = None, end_date: str | None = None
        ) -> dict[str, Any]:
            """Get weight (kg) and body fat % for every weigh-in between two YYYY-MM-DD dates (inclusive; defaults to the last 30 days), plus the body fat % target.

            Body fat uses recorded values when present; otherwise it is estimated
            from that weigh-in's total body water and flagged "estimated": true.
            "body_fat_estimate_method" explains the estimate and its accuracy.
            """
            end = date.fromisoformat(end_date) if end_date else LocalClock.today()
            start = (
                date.fromisoformat(start_date)
                if start_date
                else end - timedelta(days=29)
            )
            return body.series(start, end)

        @server.tool()
        def set_body_fat_target(percent: float) -> dict[str, Any]:
            """Set the body fat % target shown as the target line on the monthly body chart."""
            return body.set_fat_target(BodyFatTargetUpdate(percent=percent).percent)

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
            return days.save(
                date.fromisoformat(day), DailyLogUpsert.model_validate(context)
            )

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
                return analysis.analyze(
                    optional_date(start_date), optional_date(end_date)
                )
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
            "Whey protein"). Entries already aliased to current_name are renamed
            too. Counts, macro totals, top contributors, and rule-based verdicts
            are derived from the entries, so they update automatically. A verdict
            override moves to the new name once no entry uses the old one. Without
            dates the old name also becomes an alias of the new one, so later logs
            under the old name are saved as the new name (alias_recorded). Returns
            the number renamed and the merged food's new summary.
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
        def list_food_names(query: str | None = None) -> list[dict[str, Any]]:
            """List the canonical food names already in use, most logged first.

            This is the canonical-food registry. Each item has the name, its entry
            count, and the aliases (other spellings or merged names) that resolve
            to it. query filters by a case-insensitive substring of the name or an
            alias. Call this before logging food so a food keeps one consistent
            name; use suggest_duplicate_foods to find near-duplicates to merge.
            """
            return analysis.list_food_names(query)

        @server.tool()
        def resolve_food_name(name: str) -> dict[str, Any]:
            """Show the canonical name a food logged as name would be saved under.

            source is "alias" (a registered alias), "existing" (a spelling variant
            of a food already logged), or "new" (no match; saved as given). Also
            returns the canonical food's entry count and aliases. Use it when
            unsure whether a food was logged before; it changes nothing.
            """
            return analysis.resolve_food_name(name)

        @server.tool()
        def suggest_duplicate_foods(limit: int = 20) -> list[dict[str, Any]]:
            """Suggest canonical foods that look like duplicates of each other.

            Each pair names the food to keep (the more logged one), the one to
            merge, a 0-1 similarity, and the reason: "similar spelling" (likely a
            typo, e.g. "Chiken breast") or "one name contains the other" (e.g.
            "Whey" and "Whey protein", which may also be genuinely different
            foods such as "Paratha" and "Aloo paratha"). Nothing is merged: confirm
            with the user, then call rename_food(merge, keep) to rewrite the
            entries and register the alias, or set_food_alias to merge without
            rewriting them.
            """
            return analysis.suggest_duplicates(limit)

        @server.tool()
        def set_food_alias(alias: str, canonical_name: str) -> dict[str, Any]:
            """Make another name for a food resolve to its canonical name.

            Future entries logged as alias are saved as canonical_name, and the
            Monthly Tracking analysis counts existing alias entries under
            canonical_name without changing them (use rename_food to rewrite
            them). Matching ignores case, punctuation, and a trailing plural "s".
            Aliases that pointed at alias move to canonical_name, and alias's
            verdict override moves too unless canonical_name already has one.
            """
            return analysis.set_alias(
                FoodAliasUpsert(alias=alias, canonical_name=canonical_name)
            )

        @server.tool()
        def remove_food_alias(alias: str) -> dict[str, Any]:
            """Stop alias resolving to another food, so it shows as its own food again."""
            return {"removed": analysis.remove_alias(alias), "alias": alias}

        @server.tool()
        def set_food_verdict(
            food_name: str, verdict: str, reason: str
        ) -> dict[str, Any]:
            """Set a food's Food choices verdict, replacing the macro-based rating.

            verdict is "prefer", "avoid", or "neutral" ("neutral" removes it from
            both lists). reason is the short explanation shown in the UI, for
            example "Homemade, so far less oil than the macros suggest". The
            override applies to every period and to all spellings and aliases of
            the name.
            """
            return analysis.set_verdict(
                FoodVerdictUpsert(food_name=food_name, verdict=verdict, reason=reason)
            )

        @server.tool()
        def clear_food_verdict(food_name: str) -> dict[str, Any]:
            """Remove a verdict override so the food is rated by its macros again."""
            return {
                "cleared": analysis.clear_verdict(food_name),
                "food_name": food_name,
            }

        @server.tool()
        def list_food_verdicts() -> list[dict[str, Any]]:
            """List every verdict override with its food name, verdict, and reason."""
            return analysis.list_verdicts()

    def _register_average_tools(self) -> None:
        server, averages, optional_date = self.server, self.service.averages, self.optional_date

        @server.tool()
        def get_running_averages(
            windows: list[int] | None = None, end_date: str | None = None
        ) -> dict[str, Any]:
            """Get running averages of daily macros, weight, and body fat % in one call.

            For each window length in days (default 7, 14, and 30) ending on
            end_date (YYYY-MM-DD, default today in Asia/Kolkata), returns:
            macros (calories, protein_g, carbs_g, fat_g, natural_sugar_g,
            added_sugar_g) averaged per logged day, with the daily target,
            percent_of_target, and logged_days; weight_kg and body_fat_percent
            with their average, measured_days, first and latest values; and for
            every value the change from the same-length window just before it.
            Today is left out of macro averages while it is still being logged.
            Use this for questions like "how am I trending this week?".
            """
            return averages.summary(windows or [7, 14, 30], optional_date(end_date))

        @server.tool()
        def get_running_average_series(
            window_days: int = 7, start_date: str | None = None, end_date: str | None = None
        ) -> dict[str, Any]:
            """Get the trailing running average for every day in a date range.

            Each day carries the average of the window_days days ending on it
            (default 7) for every macro, weight_kg, and body_fat_percent, plus how
            many days were logged in that window. Dates are YYYY-MM-DD; end_date
            defaults to today and start_date to 29 days before end_date (at most
            366 days). Use this to chart or describe how the smoothed trend moved.
            """
            end = optional_date(end_date) or LocalClock.today()
            start = optional_date(start_date) or end - timedelta(days=29)
            return averages.series(window_days, start, end)

    def _register_workout_tools(self) -> None:
        server, tracker = self.server, self.service.workouts
        update_result = self.update_result

        @server.tool()
        def record_workout(
            done: bool,
            day: str | None = None,
            notes: str | None = None,
            types: list[WorkoutType] | None = None,
        ) -> dict[str, Any]:
            """Record whether the user worked out on a YYYY-MM-DD day (default today).

            done is true when the workout was done and false when it was skipped.
            types lists what a done workout trained, any of legs, back, chest,
            shoulders, biceps, triceps, core, cardio, full_body (e.g. ["back",
            "biceps"]); a skipped day has none. Recording a day again replaces
            its earlier record, types and notes included. The UI shows each
            record as a marker on the workout calendar, with an icon per type.
            Resolve relative days in the Asia/Kolkata timezone.
            """
            workout_day = date.fromisoformat(day) if day else LocalClock.today()
            return tracker.record(
                workout_day, WorkoutRecord(done=done, notes=notes, types=types or [])
            )

        @server.tool()
        def record_workouts(workouts: list[dict]) -> list[dict[str, Any]]:
            """Record several days' workouts at once, e.g. backfilling a week.

            Each item is {"day": "YYYY-MM-DD", "done": true|false, "notes": optional,
            "types": optional list of workout types as in record_workout}.
            Every day may appear once; existing records for those days are
            replaced. All days save together or none do.
            """
            return tracker.record_many(WorkoutBatch(workouts=workouts))

        @server.tool()
        def get_workout_summary(
            start_date: str | None = None, end_date: str | None = None
        ) -> dict[str, Any]:
            """Summarise workouts between two YYYY-MM-DD dates (inclusive; defaults to the last 30 days).

            Returns done, skipped, and unrecorded day counts, done_rate (done
            share of recorded days, null when nothing is recorded),
            current_streak (consecutive done days ending at end_date; an
            unrecorded end_date does not break it), longest_streak, type_counts
            (done days per workout type, most trained first), and every record
            in the range.
            """
            end = date.fromisoformat(end_date) if end_date else LocalClock.today()
            start = (
                date.fromisoformat(start_date)
                if start_date
                else end - timedelta(days=29)
            )
            return tracker.summary(start, end)

        @server.tool()
        def get_workouts(
            start_date: str | None = None, end_date: str | None = None
        ) -> list[dict[str, Any]]:
            """List workout records between two YYYY-MM-DD dates (inclusive; defaults to the last 30 days).

            Days without a record are omitted; they are neither done nor skipped.
            """
            end = date.fromisoformat(end_date) if end_date else LocalClock.today()
            start = (
                date.fromisoformat(start_date)
                if start_date
                else end - timedelta(days=29)
            )
            return tracker.list(start, end)

        @server.tool()
        def remove_workout(day: str) -> dict[str, Any]:
            """Remove a YYYY-MM-DD day's workout record so it shows as unrecorded.

            Exercises logged on that day are kept; remove them with remove_workout_exercise.
            """
            return {"deleted": tracker.remove(date.fromisoformat(day)), "day": day}

        @server.tool()
        def add_workout_exercises(exercises: list[dict]) -> dict[str, Any]:
            """Log the exercises of a workout session, up to 50 at once.

            Each item is {"day": "YYYY-MM-DD", "exercise": "Barbell squat",
            "type": optional workout type as in record_workout, "sets": optional
            int, "reps": optional int (per set), "weight_kg": optional number,
            "duration_min": optional number (for cardio), "notes": optional}.
            Logging an exercise marks its day done and adds its type to the
            day's workout types, keeping existing types and notes. All
            exercises save together or none do. Returns the stored exercises
            with their ids and the updated workout days.
            """
            return tracker.add_exercises(ExerciseBatch(exercises=exercises))

        @server.tool()
        def get_workout_exercises(
            start_date: str | None = None, end_date: str | None = None
        ) -> list[dict[str, Any]]:
            """List logged exercises between two YYYY-MM-DD dates (inclusive; defaults to today).

            Each has its id, workout_date, exercise, type, sets, reps,
            weight_kg, duration_min, and notes, ordered by day then entry.
            """
            end = date.fromisoformat(end_date) if end_date else LocalClock.today()
            start = date.fromisoformat(start_date) if start_date else end
            return tracker.list_exercises(start, end)

        @server.tool()
        def update_workout_exercise(entry_id: int, exercise: dict) -> dict[str, Any]:
            """Replace one logged exercise, found by its id from get_workout_exercises.

            exercise has the same fields as an add_workout_exercises item and
            replaces every field; omitted optional fields are cleared. The
            day is marked done with the exercise's type added.
            """
            return update_result(tracker.update_exercise(entry_id, ExerciseEntry(**exercise)))

        @server.tool()
        def remove_workout_exercise(entry_id: int) -> dict[str, Any]:
            """Delete one logged exercise by its id; the day's done status and types are unchanged."""
            return {"deleted": tracker.remove_exercise(entry_id), "entry_id": entry_id}
