from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from .database import connection
from .models import DailyLogUpsert, FoodEntryCreate, HealthMeasurementCreate


def _serialize(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value.isoformat() if isinstance(value, (date, datetime))
        else float(value) if hasattr(value, "as_tuple") else value
        for key, value in row.items()
    }


def add_food_entry(entry: FoodEntryCreate) -> dict[str, Any]:
    with connection() as cursor:
        cursor.execute(
            """
            INSERT INTO food_entries
                (food_name, quantity, meal_type, calories, protein_g, carbs_g, fat_g,
                 natural_sugar_g, added_sugar_g, consumed_at, time_label, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s, NOW()), %s, %s)
            RETURNING *
            """,
            (entry.food_name.strip(), entry.quantity, entry.meal_type, entry.calories,
             entry.protein_g, entry.carbs_g, entry.fat_g, entry.natural_sugar_g,
             entry.added_sugar_g, entry.consumed_at, entry.time_label, entry.notes),
        )
        return _serialize(cursor.fetchone())


def update_food_entry(entry_id: int, entry: FoodEntryCreate) -> dict[str, Any] | None:
    with connection() as cursor:
        cursor.execute(
            """
            UPDATE food_entries
            SET food_name=%s, quantity=%s, meal_type=%s, calories=%s,
                protein_g=%s, carbs_g=%s, fat_g=%s, natural_sugar_g=%s,
                added_sugar_g=%s, consumed_at=COALESCE(%s, consumed_at),
                time_label=%s, notes=%s
            WHERE id=%s RETURNING *
            """,
            (entry.food_name.strip(), entry.quantity, entry.meal_type, entry.calories,
             entry.protein_g, entry.carbs_g, entry.fat_g, entry.natural_sugar_g,
             entry.added_sugar_g, entry.consumed_at, entry.time_label, entry.notes, entry_id),
        )
        row=cursor.fetchone()
        return _serialize(row) if row else None


def delete_food_entry(entry_id: int, expected_day: date | None=None) -> bool:
    start_at=datetime.combine(expected_day,time.min,tzinfo=timezone.utc) if expected_day else None
    end_at=start_at+timedelta(days=1) if start_at else None
    with connection() as cursor:
        cursor.execute(
            """DELETE FROM food_entries WHERE id=%s
               AND (%s::timestamptz IS NULL OR consumed_at >= %s)
               AND (%s::timestamptz IS NULL OR consumed_at < %s)""",
            (entry_id,start_at,start_at,end_at,end_at),
        )
        return cursor.rowcount==1


def list_food_entries(start: date | None=None, end: date | None=None, limit: int=100) -> list[dict[str,Any]]:
    start_at=datetime.combine(start,time.min,tzinfo=timezone.utc) if start else None
    end_at=datetime.combine(end+timedelta(days=1),time.min,tzinfo=timezone.utc) if end else None
    with connection() as cursor:
        cursor.execute(
            """SELECT * FROM food_entries
               WHERE (%s::timestamptz IS NULL OR consumed_at >= %s)
                 AND (%s::timestamptz IS NULL OR consumed_at < %s)
               ORDER BY consumed_at DESC,id DESC LIMIT %s""",
            (start_at,start_at,end_at,end_at,min(max(limit,1),500)),
        )
        return [_serialize(row) for row in cursor.fetchall()]


def upsert_daily_log(day: date, entry: DailyLogUpsert) -> dict[str,Any]:
    fields=list(entry.model_fields)
    values=[getattr(entry,f) for f in fields]
    columns=", ".join(["log_date",*fields])
    placeholders=", ".join(["%s"]*(len(fields)+1))
    updates=", ".join([f"{f}=EXCLUDED.{f}" for f in fields])
    with connection() as cursor:
        cursor.execute(
            f"""INSERT INTO daily_logs ({columns}) VALUES ({placeholders})
                ON CONFLICT (log_date) DO UPDATE SET {updates}, updated_at=NOW()
                RETURNING *""",
            [day,*values],
        )
        return _serialize(cursor.fetchone())


def get_daily_log(day: date) -> dict[str,Any]:
    with connection() as cursor:
        cursor.execute("SELECT * FROM daily_logs WHERE log_date=%s",(day,))
        row=cursor.fetchone()
        return _serialize(row) if row else {"log_date":day.isoformat()}


def add_health_measurement(entry: HealthMeasurementCreate) -> dict[str,Any]:
    with connection() as cursor:
        cursor.execute(
            """INSERT INTO health_measurements (metric,value,unit,measured_at,time_label,notes)
               VALUES (%s,%s,%s,COALESCE(%s,NOW()),%s,%s) RETURNING *""",
            (entry.metric.strip().lower(),entry.value,entry.unit.strip(),
             entry.measured_at,entry.time_label,entry.notes),
        )
        return _serialize(cursor.fetchone())


def list_health_measurements(metric: str | None=None, limit: int=100) -> list[dict[str,Any]]:
    with connection() as cursor:
        cursor.execute(
            """SELECT * FROM health_measurements
               WHERE (%s::text IS NULL OR metric=%s)
               ORDER BY measured_at DESC,id DESC LIMIT %s""",
            (metric.lower() if metric else None,metric.lower() if metric else None,min(max(limit,1),500)),
        )
        return [_serialize(row) for row in cursor.fetchall()]


def daily_summary(day: date) -> dict[str,Any]:
    start_at=datetime.combine(day,time.min,tzinfo=timezone.utc)
    end_at=start_at+timedelta(days=1)
    with connection() as cursor:
        cursor.execute(
            """SELECT COUNT(*) AS entries, COALESCE(SUM(calories),0)::int AS calories,
                      COALESCE(SUM(protein_g),0) AS protein_g,
                      COALESCE(SUM(carbs_g),0) AS carbs_g,
                      COALESCE(SUM(fat_g),0) AS fat_g,
                      COALESCE(SUM(natural_sugar_g),0) AS natural_sugar_g,
                      COALESCE(SUM(added_sugar_g),0) AS added_sugar_g
               FROM food_entries WHERE consumed_at >= %s AND consumed_at < %s""",
            (start_at,end_at),
        )
        result=_serialize(cursor.fetchone())
        result["date"]=day.isoformat()
        return result
