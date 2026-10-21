"""PostgreSQL schema and connection pool for Luna Vita."""

from collections.abc import Iterator
from contextlib import contextmanager

from psycopg import Cursor
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS food_entries (
    id BIGSERIAL PRIMARY KEY,
    consumed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    consumed_date DATE NOT NULL DEFAULT
        (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata')::date,
    time_label TEXT,
    food_name TEXT NOT NULL CHECK (length(trim(food_name)) > 0),
    quantity TEXT NOT NULL CHECK (length(trim(quantity)) > 0),
    meal_type TEXT NOT NULL DEFAULT 'other'
        CHECK (meal_type IN ('breakfast', 'lunch', 'dinner', 'snack', 'other')),
    calories INTEGER NOT NULL CHECK (calories >= 0),
    protein_g NUMERIC(8,2) NOT NULL DEFAULT 0 CHECK (protein_g >= 0),
    carbs_g NUMERIC(8,2) NOT NULL DEFAULT 0 CHECK (carbs_g >= 0),
    fat_g NUMERIC(8,2) NOT NULL DEFAULT 0 CHECK (fat_g >= 0),
    natural_sugar_g NUMERIC(8,2) NOT NULL DEFAULT 0 CHECK (natural_sugar_g >= 0),
    added_sugar_g NUMERIC(8,2) NOT NULL DEFAULT 0 CHECK (added_sugar_g >= 0),
    image_url TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE food_entries ADD COLUMN IF NOT EXISTS consumed_date DATE;
UPDATE food_entries
SET consumed_date = (consumed_at AT TIME ZONE 'Asia/Kolkata')::date
WHERE consumed_date IS NULL;
ALTER TABLE food_entries ALTER COLUMN consumed_date SET DEFAULT
    (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata')::date;
ALTER TABLE food_entries ALTER COLUMN consumed_date SET NOT NULL;
ALTER TABLE food_entries ADD COLUMN IF NOT EXISTS image_url TEXT;
UPDATE food_entries
SET quantity = 'Not specified'
WHERE quantity IS NULL OR length(trim(quantity)) = 0;
ALTER TABLE food_entries ALTER COLUMN quantity SET NOT NULL;

CREATE INDEX IF NOT EXISTS food_entries_consumed_at_idx
    ON food_entries (consumed_at DESC);
CREATE INDEX IF NOT EXISTS food_entries_consumed_date_idx
    ON food_entries (consumed_date DESC);

CREATE TABLE IF NOT EXISTS daily_logs (
    log_date DATE PRIMARY KEY,
    calorie_goal INTEGER,
    protein_goal_g NUMERIC(8,2),
    carbs_goal_g NUMERIC(8,2),
    fat_goal_min_g NUMERIC(8,2),
    fat_goal_max_g NUMERIC(8,2),
    added_sugar_goal_g NUMERIC(8,2),
    added_sugar_max_g NUMERIC(8,2),
    reported_calories INTEGER,
    reported_protein_g NUMERIC(8,2),
    reported_carbs_g NUMERIC(8,2),
    reported_fat_g NUMERIC(8,2),
    reported_natural_sugar_g NUMERIC(8,2),
    reported_added_sugar_g NUMERIC(8,2),
    activity_notes TEXT,
    supplement_notes TEXT,
    daily_notes TEXT,
    report_caveats TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS health_measurements (
    id BIGSERIAL PRIMARY KEY,
    measured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    time_label TEXT,
    metric TEXT NOT NULL CHECK (length(trim(metric)) > 0),
    value NUMERIC(12,3) NOT NULL,
    unit TEXT NOT NULL CHECK (length(trim(unit)) > 0),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS health_measurements_metric_time_idx
    ON health_measurements (metric, measured_at DESC);

CREATE TABLE IF NOT EXISTS workouts (
    workout_date DATE PRIMARY KEY,
    done BOOLEAN NOT NULL,
    notes TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS food_verdicts (
    food_key TEXT PRIMARY KEY CHECK (length(trim(food_key)) > 0),
    food_name TEXT NOT NULL CHECK (length(trim(food_name)) > 0),
    verdict TEXT NOT NULL CHECK (verdict IN ('prefer', 'avoid', 'neutral')),
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS analysis_range (
    range_id SMALLINT PRIMARY KEY DEFAULT 1 CHECK (range_id = 1),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL CHECK (end_date >= start_date),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS daily_recommendations (
    profile_id SMALLINT PRIMARY KEY DEFAULT 1 CHECK (profile_id = 1),
    calories_kcal INTEGER NOT NULL CHECK (calories_kcal > 0),
    protein_g NUMERIC(8,2) NOT NULL CHECK (protein_g > 0),
    carbs_g NUMERIC(8,2) NOT NULL CHECK (carbs_g > 0),
    fat_g NUMERIC(8,2) NOT NULL CHECK (fat_g > 0),
    sugars_g NUMERIC(8,2) NOT NULL CHECK (sugars_g >= 0),
    height_cm NUMERIC(6,2) NOT NULL CHECK (height_cm > 0),
    sex TEXT NOT NULL CHECK (sex IN ('male', 'female', 'other')),
    birth_date DATE,
    weight_kg NUMERIC(6,2) CHECK (weight_kg > 0),
    goal TEXT,
    notes TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE daily_recommendations
    ADD COLUMN IF NOT EXISTS body_fat_target_percent NUMERIC(4,1) NOT NULL DEFAULT 18
    CHECK (body_fat_target_percent > 0 AND body_fat_target_percent < 75);
"""


class Database:
    """Own the connection pool; each cursor block runs in one transaction."""

    def __init__(self, url: str, min_size: int = 1, max_size: int = 8) -> None:
        self.pool = ConnectionPool(url, min_size=min_size, max_size=max_size, open=False)

    def open(self) -> None:
        self.pool.open(wait=True)

    def close(self) -> None:
        self.pool.close()

    def initialize_schema(self) -> None:
        """Create or upgrade the complete idempotent Luna Vita schema."""
        with self.cursor() as cursor:
            cursor.execute(SCHEMA_SQL)

    @contextmanager
    def cursor(self) -> Iterator[Cursor]:
        with self.pool.connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                yield cursor
