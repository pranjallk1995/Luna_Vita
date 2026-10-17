"""Validated request models shared by the MCP tools and HTTP routes."""

import re
import unicodedata
from datetime import date, datetime
from typing import ClassVar, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .clock import LocalClock

MealType = Literal["breakfast", "lunch", "dinner", "snack", "other"]
Sex = Literal["male", "female", "other"]


class LocalTimestampModel(BaseModel):
    """Interpret timezone-free client timestamps as Asia/Kolkata local time."""

    @field_validator("consumed_at", "measured_at", check_fields=False)
    @classmethod
    def localize_timestamp(cls, value: datetime | None) -> datetime | None:
        return LocalClock.localize(value) if value is not None else None


class FoodEntryCreate(LocalTimestampModel):
    EMOJI_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        "[\U0001F1E6-\U0001F1FF\U0001F300-\U0001FAFF☀-➿️‍]"
    )
    food_name: str = Field(min_length=1, max_length=200)
    quantity: str = Field(min_length=1, max_length=300)
    meal_type: MealType = "other"
    calories: int = Field(ge=0, le=100_000)
    protein_g: float = Field(ge=0, le=10_000)
    carbs_g: float = Field(ge=0, le=10_000)
    fat_g: float = Field(ge=0, le=10_000)
    natural_sugar_g: float = Field(ge=0, le=10_000)
    added_sugar_g: float = Field(ge=0, le=10_000)
    image_url: str | None = Field(default=None, max_length=2_000_000)
    consumed_at: datetime | None = None
    consumed_date: date | None = None
    time_label: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=2_000)

    @field_validator("food_name", "quantity", "time_label", "notes")
    @classmethod
    def reject_unsafe_text(cls, value: str | None) -> str | None:
        """Reject emojis and control characters from editable food text."""
        if value is None:
            return None
        text = value.strip()
        if cls.EMOJI_PATTERN.search(text):
            raise ValueError("Food entry text cannot contain emojis.")
        if any(
            unicodedata.category(character).startswith("C")
            and character not in {"\n", "\t"}
            for character in text
        ):
            raise ValueError("Food entry text contains unsupported characters.")
        return text

    @field_validator("food_name", "quantity")
    @classmethod
    def require_nonblank_text(cls, value: str) -> str:
        if not value:
            raise ValueError("Food name and quantity cannot be blank.")
        return value

    @property
    def effective_consumed_date(self) -> date:
        """The calendar day this entry belongs to, defaulting to today."""
        if self.consumed_date:
            return self.consumed_date
        return self.consumed_at.date() if self.consumed_at else LocalClock.today()


class HealthMeasurementCreate(LocalTimestampModel):
    metric: str = Field(min_length=1, max_length=100)
    value: float
    unit: str = Field(min_length=1, max_length=50)
    measured_at: datetime | None = None
    time_label: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=2_000)

    @field_validator("metric")
    @classmethod
    def normalize_metric(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("unit")
    @classmethod
    def normalize_unit(cls, value: str) -> str:
        return value.strip()


class HealthMeasurementBatchCreate(BaseModel):
    measurements: list[HealthMeasurementCreate] = Field(min_length=1, max_length=20)


class DailyRecommendationsUpsert(BaseModel):
    calories_kcal: int = Field(gt=0, le=10_000)
    protein_g: float = Field(gt=0, le=1_000)
    carbs_g: float = Field(gt=0, le=2_000)
    fat_g: float = Field(gt=0, le=1_000)
    sugars_g: float = Field(ge=0, le=1_000)
    height_cm: float = Field(gt=0, le=300)
    sex: Sex
    birth_date: date | None = None
    weight_kg: float | None = Field(default=None, gt=0, le=1_000)
    goal: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2_000)


class BodyProfileUpdate(BaseModel):
    """A partial body-profile change; omitted fields keep their stored values."""

    height_cm: float | None = Field(default=None, gt=0, le=300)
    birth_date: date | None = None
    sex: Sex | None = None
    weight_kg: float | None = Field(default=None, gt=0, le=1_000)

    @field_validator("birth_date")
    @classmethod
    def reject_future_birth_date(cls, value: date | None) -> date | None:
        if value is not None and value > LocalClock.today():
            raise ValueError("date_of_birth cannot be in the future.")
        return value

    @model_validator(mode="after")
    def require_any_field(self) -> "BodyProfileUpdate":
        if all(value is None for value in self.model_dump().values()):
            raise ValueError("Provide at least one body-profile field.")
        return self


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
