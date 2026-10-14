CREATE TABLE IF NOT EXISTS food_entries (
    id BIGSERIAL PRIMARY KEY,
    consumed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    consumed_date DATE NOT NULL DEFAULT CURRENT_DATE,
    time_label TEXT,
    food_name TEXT NOT NULL CHECK (length(trim(food_name)) > 0),
    quantity TEXT,
    meal_type TEXT NOT NULL DEFAULT 'other'
        CHECK (meal_type IN ('breakfast', 'lunch', 'dinner', 'snack', 'other')),
    calories INTEGER NOT NULL CHECK (calories >= 0),
    protein_g NUMERIC(8,2) NOT NULL DEFAULT 0 CHECK (protein_g >= 0),
    carbs_g NUMERIC(8,2) NOT NULL DEFAULT 0 CHECK (carbs_g >= 0),
    fat_g NUMERIC(8,2) NOT NULL DEFAULT 0 CHECK (fat_g >= 0),
    natural_sugar_g NUMERIC(8,2) NOT NULL DEFAULT 0 CHECK (natural_sugar_g >= 0),
    added_sugar_g NUMERIC(8,2) NOT NULL DEFAULT 0 CHECK (added_sugar_g >= 0),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE food_entries ADD COLUMN IF NOT EXISTS consumed_date DATE;
UPDATE food_entries
SET consumed_date = (consumed_at AT TIME ZONE 'Asia/Kolkata')::date
WHERE consumed_date IS NULL;
ALTER TABLE food_entries ALTER COLUMN consumed_date SET DEFAULT CURRENT_DATE;
ALTER TABLE food_entries ALTER COLUMN consumed_date SET NOT NULL;

CREATE INDEX IF NOT EXISTS food_entries_consumed_at_idx ON food_entries (consumed_at DESC);
CREATE INDEX IF NOT EXISTS food_entries_consumed_date_idx ON food_entries (consumed_date DESC);

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
