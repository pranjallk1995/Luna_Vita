"""PostgreSQL persistence for Luna Vita, one repository per aggregate."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.core.clock import LocalClock
from app.data.database import Database
from app.core.models import (
    DailyLogUpsert,
    DailyRecommendationsUpsert,
    FoodEntryCreate,
    HealthMeasurementCreate,
)

Row = dict[str, Any]
MAX_PAGE_SIZE = 500


class Repository:
    """Shared query helpers that serialize rows into JSON-friendly dicts."""

    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def serialize_value(value: Any) -> Any:
        if isinstance(value, datetime):
            return LocalClock.localize(value).isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        return value

    @classmethod
    def serialize(cls, row: Row | None) -> Row | None:
        if row is None:
            return None
        return {key: cls.serialize_value(value) for key, value in row.items()}

    @staticmethod
    def page_size(limit: int) -> int:
        return min(max(limit, 1), MAX_PAGE_SIZE)

    def fetch_one(self, sql: str, params: Any = ()) -> Row | None:
        with self.database.cursor() as cursor:
            cursor.execute(sql, params)
            return self.serialize(cursor.fetchone())

    def fetch_all(self, sql: str, params: Any = ()) -> list[Row]:
        with self.database.cursor() as cursor:
            cursor.execute(sql, params)
            return [self.serialize(row) for row in cursor.fetchall()]

    def affects_row(self, sql: str, params: Any = ()) -> bool:
        """Run a statement ending in RETURNING and report whether a row matched."""
        with self.database.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchone() is not None


class FoodRepository(Repository):
    """Food and supplement entries plus their per-day totals."""

    @staticmethod
    def entry_values(entry: FoodEntryCreate) -> tuple:
        return (
            entry.food_name,
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
            entry.effective_consumed_date,
            entry.time_label,
            entry.notes,
        )

    def add(self, entry: FoodEntryCreate) -> Row:
        return self.fetch_one(
            """
            INSERT INTO food_entries
                (food_name, quantity, meal_type, calories, protein_g, carbs_g, fat_g,
                 natural_sugar_g, added_sugar_g, image_url, consumed_at,
                 consumed_date, time_label, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    COALESCE(%s, NOW()), %s, %s, %s)
            RETURNING *
            """,
            self.entry_values(entry),
        )

    def update(self, entry_id: int, entry: FoodEntryCreate) -> Row | None:
        return self.fetch_one(
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
            (*self.entry_values(entry), entry_id),
        )

    def set_image(self, entry_id: int, image_url: str | None) -> Row | None:
        return self.fetch_one(
            "UPDATE food_entries SET image_url=%s WHERE id=%s RETURNING *",
            (image_url, entry_id),
        )

    def delete(self, entry_id: int, expected_day: date | None = None) -> bool:
        return self.affects_row(
            """
            DELETE FROM food_entries
            WHERE id=%s
              AND (%s::date IS NULL OR consumed_date=%s)
            RETURNING id
            """,
            (entry_id, expected_day, expected_day),
        )

    def list(
        self,
        start: date | None = None,
        end: date | None = None,
        limit: int = 100,
    ) -> list[Row]:
        return self.fetch_all(
            """
            SELECT * FROM food_entries
            WHERE (%s::date IS NULL OR consumed_date >= %s)
              AND (%s::date IS NULL OR consumed_date <= %s)
            ORDER BY consumed_at DESC, id DESC
            LIMIT %s
            """,
            (start, start, end, end, self.page_size(limit)),
        )

    def list_between(self, start: date | None = None, end: date | None = None) -> list[Row]:
        """Every entry in an optional inclusive range, without a page-size cap."""
        return self.fetch_all(
            """
            SELECT * FROM food_entries
            WHERE (%s::date IS NULL OR consumed_date >= %s)
              AND (%s::date IS NULL OR consumed_date <= %s)
            ORDER BY consumed_at, id
            """,
            (start, start, end, end),
        )

    def names(self) -> list[str]:
        return [row["food_name"] for row in self.fetch_all("SELECT DISTINCT food_name FROM food_entries")]

    def rename(self, entry_ids: list[int], food_name: str) -> int:
        """Rename the given entries in one transaction; return how many changed."""
        with self.database.cursor() as cursor:
            cursor.execute(
                "UPDATE food_entries SET food_name=%s WHERE id = ANY(%s)",
                (food_name, entry_ids),
            )
            return cursor.rowcount

    def daily_totals(self, day: date) -> Row:
        totals = self.fetch_one(
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
        return {**totals, "date": day.isoformat()}


class MeasurementRepository(Repository):
    """Body measurements stored one metric per row."""

    @staticmethod
    def entry_values(entry: HealthMeasurementCreate) -> tuple:
        return (
            entry.metric,
            entry.value,
            entry.unit,
            entry.measured_at,
            entry.time_label,
            entry.notes,
        )

    def add_many(self, entries: list[HealthMeasurementCreate]) -> list[Row]:
        """Insert every entry in one transaction so a batch saves atomically."""
        with self.database.cursor() as cursor:
            results = []
            for entry in entries:
                cursor.execute(
                    """
                    INSERT INTO health_measurements
                        (metric, value, unit, measured_at, time_label, notes)
                    VALUES (%s, %s, %s, COALESCE(%s, NOW()), %s, %s)
                    RETURNING *
                    """,
                    self.entry_values(entry),
                )
                results.append(self.serialize(cursor.fetchone()))
            return results

    def list(self, metric: str | None = None, limit: int = 100) -> list[Row]:
        normalized_metric = metric.lower() if metric else None
        return self.fetch_all(
            """
            SELECT * FROM health_measurements
            WHERE (%s::text IS NULL OR metric=%s)
            ORDER BY measured_at DESC, id DESC
            LIMIT %s
            """,
            (normalized_metric, normalized_metric, self.page_size(limit)),
        )

    def list_between(self, start: date, end: date, metrics: list[str]) -> list[Row]:
        """Return the given metrics measured on local days ``start``..``end`` inclusive."""
        return self.fetch_all(
            """
            SELECT * FROM health_measurements
            WHERE (measured_at AT TIME ZONE 'Asia/Kolkata')::date BETWEEN %s AND %s
              AND metric = ANY(%s)
            ORDER BY measured_at, id
            """,
            (start, end, metrics),
        )

    def list_for_day(self, day: date) -> list[Row]:
        """Return measurements belonging to a local calendar day."""
        return self.fetch_all(
            """
            SELECT * FROM health_measurements
            WHERE (measured_at AT TIME ZONE 'Asia/Kolkata')::date=%s
            ORDER BY measured_at, id
            """,
            (day,),
        )

    def update(self, entry_id: int, entry: HealthMeasurementCreate) -> Row | None:
        return self.fetch_one(
            """
            UPDATE health_measurements
            SET metric=%s, value=%s, unit=%s,
                measured_at=COALESCE(%s, measured_at),
                time_label=%s, notes=%s
            WHERE id=%s
            RETURNING *
            """,
            (*self.entry_values(entry), entry_id),
        )

    def delete(self, entry_id: int) -> bool:
        return self.affects_row(
            "DELETE FROM health_measurements WHERE id=%s RETURNING id",
            (entry_id,),
        )


class DailyLogRepository(Repository):
    """Date-specific goals, reported totals, and free-form daily context."""

    def get(self, day: date) -> Row:
        row = self.fetch_one("SELECT * FROM daily_logs WHERE log_date=%s", (day,))
        return row or {"log_date": day.isoformat()}

    def upsert(self, day: date, entry: DailyLogUpsert) -> Row:
        fields = list(DailyLogUpsert.model_fields)
        columns = ", ".join(["log_date", *fields])
        placeholders = ", ".join(["%s"] * (len(fields) + 1))
        updates = ", ".join(f"{field}=EXCLUDED.{field}" for field in fields)
        return self.fetch_one(
            f"""
            INSERT INTO daily_logs ({columns})
            VALUES ({placeholders})
            ON CONFLICT (log_date)
            DO UPDATE SET {updates}, updated_at=NOW()
            RETURNING *
            """,
            [day, *(getattr(entry, field) for field in fields)],
        )


class VerdictRepository(Repository):
    """Explicit prefer/avoid/neutral ratings keyed by normalized food name."""

    def list(self) -> list[Row]:
        return self.fetch_all("SELECT * FROM food_verdicts ORDER BY food_name")

    def get(self, food_key: str) -> Row | None:
        return self.fetch_one("SELECT * FROM food_verdicts WHERE food_key=%s", (food_key,))

    def upsert(self, food_key: str, food_name: str, verdict: str, reason: str) -> Row:
        return self.fetch_one(
            """
            INSERT INTO food_verdicts (food_key, food_name, verdict, reason)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (food_key) DO UPDATE SET
                food_name=EXCLUDED.food_name,
                verdict=EXCLUDED.verdict,
                reason=EXCLUDED.reason,
                updated_at=NOW()
            RETURNING *
            """,
            (food_key, food_name, verdict, reason),
        )

    def delete(self, food_key: str) -> bool:
        return self.affects_row(
            "DELETE FROM food_verdicts WHERE food_key=%s RETURNING food_key", (food_key,)
        )


class AnalysisRangeRepository(Repository):
    """The single saved date range for the Monthly Tracking tab."""

    def get(self) -> Row | None:
        return self.fetch_one("SELECT * FROM analysis_range WHERE range_id=1")

    def upsert(self, start: date, end: date) -> Row:
        return self.fetch_one(
            """
            INSERT INTO analysis_range (range_id, start_date, end_date)
            VALUES (1, %s, %s)
            ON CONFLICT (range_id) DO UPDATE SET
                start_date=EXCLUDED.start_date,
                end_date=EXCLUDED.end_date,
                updated_at=NOW()
            RETURNING *
            """,
            (start, end),
        )

    def delete(self) -> bool:
        return self.affects_row("DELETE FROM analysis_range WHERE range_id=1 RETURNING range_id")


class RecommendationRepository(Repository):
    """The single-row nutrition recommendations and body profile."""

    AGE_COLUMN = "EXTRACT(YEAR FROM age(CURRENT_DATE, birth_date))::int AS age"

    def get(self) -> Row | None:
        return self.fetch_one(
            f"SELECT *, {self.AGE_COLUMN} FROM daily_recommendations WHERE profile_id=1"
        )

    def body_fat_target(self) -> float | None:
        row = self.fetch_one(
            "SELECT body_fat_target_percent FROM daily_recommendations WHERE profile_id=1"
        )
        return float(row["body_fat_target_percent"]) if row else None

    def update_body_fat_target(self, percent: float) -> Row | None:
        return self.fetch_one(
            f"""
            UPDATE daily_recommendations
            SET body_fat_target_percent=%s, updated_at=NOW()
            WHERE profile_id=1
            RETURNING *, {self.AGE_COLUMN}
            """,
            (percent,),
        )

    def upsert(self, entry: DailyRecommendationsUpsert) -> Row:
        return self.fetch_one(
            f"""
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
            RETURNING *, {self.AGE_COLUMN}
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

    def update_body_profile(
        self,
        *,
        height_cm: float | None = None,
        birth_date: date | None = None,
        sex: str | None = None,
        weight_kg: float | None = None,
    ) -> Row | None:
        return self.fetch_one(
            f"""
            UPDATE daily_recommendations SET
                height_cm=COALESCE(%s, height_cm),
                birth_date=COALESCE(%s, birth_date),
                sex=COALESCE(%s, sex),
                weight_kg=COALESCE(%s, weight_kg),
                updated_at=NOW()
            WHERE profile_id=1
            RETURNING *, {self.AGE_COLUMN}
            """,
            (height_cm, birth_date, sex, weight_kg),
        )
