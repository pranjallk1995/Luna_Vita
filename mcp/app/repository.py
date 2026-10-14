from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from .database import Database
from .models import (
    DailyLogUpsert,
    DailyRecommendationsUpsert,
    FoodEntryCreate,
    HealthMeasurementCreate,
)


class LunaVitaRepository:
    """Persist and retrieve LunaVita domain records."""

    LOCAL_TIMEZONE = ZoneInfo("Asia/Kolkata")

    def __init__(self, database: Database) -> None:
        self.database = database

    def ensure_schema(self) -> None:
        """Apply additive migrations required by the running application."""
        with self.database.cursor() as cursor:
            cursor.execute(
                "ALTER TABLE food_entries ADD COLUMN IF NOT EXISTS image_url TEXT"
            )
            cursor.execute(
                """
                UPDATE food_entries
                SET quantity='Not specified'
                WHERE quantity IS NULL OR length(trim(quantity))=0
                """
            )
            cursor.execute(
                "ALTER TABLE food_entries ALTER COLUMN quantity SET NOT NULL"
            )

    @staticmethod
    def serialize(row: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value.isoformat()
            if isinstance(value, (date, datetime))
            else float(value)
            if hasattr(value, "as_tuple")
            else value
            for key, value in row.items()
        }

    def add_food_entry(self, entry: FoodEntryCreate) -> dict[str, Any]:
        consumed_date = entry.consumed_date or (
            entry.consumed_at.date()
            if entry.consumed_at
            else datetime.now(self.LOCAL_TIMEZONE).date()
        )
        with self.database.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO food_entries
                    (food_name, quantity, meal_type, calories, protein_g, carbs_g, fat_g,
                     natural_sugar_g, added_sugar_g, image_url, consumed_at,
                     consumed_date, time_label, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        COALESCE(%s, NOW()), %s, %s, %s)
                RETURNING *
                """,
                (
                    entry.food_name.strip(),
                    entry.quantity,
                    entry.meal_type,
                    entry.calories,
                    entry.protein_g,
                    entry.carbs_g,
                    entry.fat_g,
                    entry.natural_sugar_g,
                    entry.added_sugar_g,
                    entry.image_url,
                    entry.consumed_at,
                    consumed_date,
                    entry.time_label,
                    entry.notes,
                ),
            )
            return self.serialize(cursor.fetchone())

    def update_food_entry(
        self, entry_id: int, entry: FoodEntryCreate
    ) -> dict[str, Any] | None:
        consumed_date = entry.consumed_date or (
            entry.consumed_at.date()
            if entry.consumed_at
            else datetime.now(self.LOCAL_TIMEZONE).date()
        )
        with self.database.cursor() as cursor:
            cursor.execute(
                """
                UPDATE food_entries
                SET food_name=%s, quantity=%s, meal_type=%s, calories=%s,
                    protein_g=%s, carbs_g=%s, fat_g=%s, natural_sugar_g=%s,
                    added_sugar_g=%s, image_url=%s,
                    consumed_at=COALESCE(%s, consumed_at),
                    consumed_date=%s, time_label=%s, notes=%s
                WHERE id=%s
                RETURNING *
                """,
                (
                    entry.food_name.strip(),
                    entry.quantity,
                    entry.meal_type,
                    entry.calories,
                    entry.protein_g,
                    entry.carbs_g,
                    entry.fat_g,
                    entry.natural_sugar_g,
                    entry.added_sugar_g,
                    entry.image_url,
                    entry.consumed_at,
                    consumed_date,
                    entry.time_label,
                    entry.notes,
                    entry_id,
                ),
            )
            row = cursor.fetchone()
            return self.serialize(row) if row else None

    def set_food_image(
        self, entry_id: int, image_url: str | None
    ) -> dict[str, Any] | None:
        with self.database.cursor() as cursor:
            cursor.execute(
                "UPDATE food_entries SET image_url=%s WHERE id=%s RETURNING *",
                (image_url, entry_id),
            )
            row = cursor.fetchone()
            return self.serialize(row) if row else None

    def delete_food_entry(
        self, entry_id: int, expected_day: date | None = None
    ) -> bool:
        with self.database.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM food_entries
                WHERE id=%s
                  AND (%s::date IS NULL OR consumed_date=%s)
                """,
                (entry_id, expected_day, expected_day),
            )
            return cursor.rowcount == 1

    def list_food_entries(
        self,
        start: date | None = None,
        end: date | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with self.database.cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM food_entries
                WHERE (%s::date IS NULL OR consumed_date >= %s)
                  AND (%s::date IS NULL OR consumed_date <= %s)
                ORDER BY consumed_at DESC, id DESC
                LIMIT %s
                """,
                (start, start, end, end, min(max(limit, 1), 500)),
            )
            return [self.serialize(row) for row in cursor.fetchall()]

    def upsert_daily_log(
        self, day: date, entry: DailyLogUpsert
    ) -> dict[str, Any]:
        fields = list(entry.model_fields)
        values = [getattr(entry, field) for field in fields]
        columns = ", ".join(["log_date", *fields])
        placeholders = ", ".join(["%s"] * (len(fields) + 1))
        updates = ", ".join([f"{field}=EXCLUDED.{field}" for field in fields])
        with self.database.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO daily_logs ({columns})
                VALUES ({placeholders})
                ON CONFLICT (log_date)
                DO UPDATE SET {updates}, updated_at=NOW()
                RETURNING *
                """,
                [day, *values],
            )
            return self.serialize(cursor.fetchone())

    def get_daily_log(self, day: date) -> dict[str, Any]:
        with self.database.cursor() as cursor:
            cursor.execute("SELECT * FROM daily_logs WHERE log_date=%s", (day,))
            row = cursor.fetchone()
            return self.serialize(row) if row else {"log_date": day.isoformat()}

    def add_health_measurement(
        self, entry: HealthMeasurementCreate
    ) -> dict[str, Any]:
        return self.add_health_measurements([entry])[0]

    def add_health_measurements(
        self, entries: list[HealthMeasurementCreate]
    ) -> list[dict[str, Any]]:
        results = []
        with self.database.cursor() as cursor:
            for entry in entries:
                cursor.execute(
                    """
                    INSERT INTO health_measurements
                        (metric, value, unit, measured_at, time_label, notes)
                    VALUES (%s, %s, %s, COALESCE(%s, NOW()), %s, %s)
                    RETURNING *
                    """,
                    (
                        entry.metric.strip().lower(),
                        entry.value,
                        entry.unit.strip(),
                        entry.measured_at,
                        entry.time_label,
                        entry.notes,
                    ),
                )
                results.append(self.serialize(cursor.fetchone()))
        return results

    def list_health_measurements(
        self, metric: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        normalized_metric = metric.lower() if metric else None
        with self.database.cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM health_measurements
                WHERE (%s::text IS NULL OR metric=%s)
                ORDER BY measured_at DESC, id DESC
                LIMIT %s
                """,
                (normalized_metric, normalized_metric, min(max(limit, 1), 500)),
            )
            return [self.serialize(row) for row in cursor.fetchall()]

    def update_health_measurement(
        self, entry_id: int, entry: HealthMeasurementCreate
    ) -> dict[str, Any] | None:
        with self.database.cursor() as cursor:
            cursor.execute(
                """
                UPDATE health_measurements
                SET metric=%s, value=%s, unit=%s,
                    measured_at=COALESCE(%s, measured_at),
                    time_label=%s, notes=%s
                WHERE id=%s
                RETURNING *
                """,
                (
                    entry.metric.strip().lower(),
                    entry.value,
                    entry.unit.strip(),
                    entry.measured_at,
                    entry.time_label,
                    entry.notes,
                    entry_id,
                ),
            )
            row = cursor.fetchone()
            return self.serialize(row) if row else None

    def delete_health_measurement(self, entry_id: int) -> bool:
        with self.database.cursor() as cursor:
            cursor.execute(
                "DELETE FROM health_measurements WHERE id=%s RETURNING id",
                (entry_id,),
            )
            return cursor.fetchone() is not None

    def list_health_measurements_for_day(
        self, day: date
    ) -> list[dict[str, Any]]:
        """Return measurements belonging to a local calendar day."""
        with self.database.cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM health_measurements
                WHERE (measured_at AT TIME ZONE 'Asia/Kolkata')::date=%s
                ORDER BY measured_at, id
                """,
                (day,),
            )
            return [self.serialize(row) for row in cursor.fetchall()]

    def upsert_daily_recommendations(
        self, entry: DailyRecommendationsUpsert
    ) -> dict[str, Any]:
        with self.database.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO daily_recommendations
                    (profile_id, calories_kcal, protein_g, carbs_g, fat_g,
                     sugars_g, height_cm, sex, birth_date, weight_kg, goal, notes)
                VALUES (1, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (profile_id) DO UPDATE SET
                    calories_kcal=EXCLUDED.calories_kcal,
                    protein_g=EXCLUDED.protein_g,
                    carbs_g=EXCLUDED.carbs_g,
                    fat_g=EXCLUDED.fat_g,
                    sugars_g=EXCLUDED.sugars_g,
                    height_cm=EXCLUDED.height_cm,
                    sex=EXCLUDED.sex,
                    birth_date=COALESCE(
                        EXCLUDED.birth_date,
                        daily_recommendations.birth_date
                    ),
                    weight_kg=EXCLUDED.weight_kg,
                    goal=EXCLUDED.goal,
                    notes=EXCLUDED.notes,
                    updated_at=NOW()
                RETURNING *,
                    EXTRACT(YEAR FROM age(CURRENT_DATE, birth_date))::int
                        AS age
                """,
                (
                    entry.calories_kcal,
                    entry.protein_g,
                    entry.carbs_g,
                    entry.fat_g,
                    entry.sugars_g,
                    entry.height_cm,
                    entry.sex,
                    entry.birth_date,
                    entry.weight_kg,
                    entry.goal,
                    entry.notes,
                ),
            )
            return self.serialize(cursor.fetchone())

    def update_body_profile(
        self,
        *,
        height_cm: float | None = None,
        birth_date: date | None = None,
        sex: str | None = None,
        weight_kg: float | None = None,
    ) -> dict[str, Any] | None:
        with self.database.cursor() as cursor:
            cursor.execute(
                """
                UPDATE daily_recommendations SET
                    height_cm=COALESCE(%s, height_cm),
                    birth_date=COALESCE(%s, birth_date),
                    sex=COALESCE(%s, sex),
                    weight_kg=COALESCE(%s, weight_kg),
                    updated_at=NOW()
                WHERE profile_id=1
                RETURNING *,
                    EXTRACT(YEAR FROM age(CURRENT_DATE, birth_date))::int
                        AS age
                """,
                (height_cm, birth_date, sex, weight_kg),
            )
            row = cursor.fetchone()
            return self.serialize(row) if row else None

    def get_daily_recommendations(self) -> dict[str, Any] | None:
        with self.database.cursor() as cursor:
            cursor.execute(
                """
                SELECT *,
                    EXTRACT(YEAR FROM age(CURRENT_DATE, birth_date))::int AS age
                FROM daily_recommendations
                WHERE profile_id=1
                """
            )
            row = cursor.fetchone()
            return self.serialize(row) if row else None

    def daily_summary(self, day: date) -> dict[str, Any]:
        with self.database.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) AS entries,
                       COALESCE(SUM(calories), 0)::int AS calories,
                       COALESCE(SUM(protein_g), 0) AS protein_g,
                       COALESCE(SUM(carbs_g), 0) AS carbs_g,
                       COALESCE(SUM(fat_g), 0) AS fat_g,
                       COALESCE(SUM(natural_sugar_g), 0) AS natural_sugar_g,
                       COALESCE(SUM(added_sugar_g), 0) AS added_sugar_g
                FROM food_entries
                WHERE consumed_date=%s
                """,
                (day,),
            )
            result = self.serialize(cursor.fetchone())
            result["date"] = day.isoformat()
            return result
