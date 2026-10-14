from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


MealType = Literal["breakfast", "lunch", "dinner", "snack", "other"]


class FoodEntryCreate(BaseModel):
    food_name: str = Field(min_length=1, max_length=200)
    quantity: str | None = Field(default=None, max_length=300)
    meal_type: MealType = "other"
    calories: int = Field(ge=0, le=100_000)
    protein_g: float = Field(default=0, ge=0, le=10_000)
    carbs_g: float = Field(default=0, ge=0, le=10_000)
    fat_g: float = Field(default=0, ge=0, le=10_000)
    natural_sugar_g: float = Field(default=0, ge=0, le=10_000)
    added_sugar_g: float = Field(default=0, ge=0, le=10_000)
    consumed_at: datetime | None = None
    consumed_date: date | None = None
    time_label: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=2_000)


class HealthMeasurementCreate(BaseModel):
    metric: str = Field(min_length=1, max_length=100)
    value: float
    unit: str = Field(min_length=1, max_length=50)
    measured_at: datetime | None = None
    time_label: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=2_000)



class HealthMeasurementBatchCreate(BaseModel):
    measurements: list[HealthMeasurementCreate] = Field(min_length=1, max_length=20)


class DailyLogUpsert(BaseModel):
    calorie_goal: int | None = Field(default=None, ge=0)
    protein_goal_g: float | None = Field(default=None, ge=0)
    carbs_goal_g: float | None = Field(default=None, ge=0)
    fat_goal_min_g: float | None = Field(default=None, ge=0)
    fat_goal_max_g: float | None = Field(default=None, ge=0)
    added_sugar_goal_g: float | None = Field(default=None, ge=0)
    added_sugar_max_g: float | None = Field(default=None, ge=0)
    reported_calories: int | None = Field(default=None, ge=0)
    reported_protein_g: float | None = Field(default=None, ge=0)
    reported_carbs_g: float | None = Field(default=None, ge=0)
    reported_fat_g: float | None = Field(default=None, ge=0)
    reported_natural_sugar_g: float | None = Field(default=None, ge=0)
    reported_added_sugar_g: float | None = Field(default=None, ge=0)
    activity_notes: str | None = None
    supplement_notes: str | None = None
    daily_notes: str | None = None
    report_caveats: str | None = None
