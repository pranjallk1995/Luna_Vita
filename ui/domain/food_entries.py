"""Pure conversions between stored food entries and their editable UI form."""

from datetime import date, datetime, time
from typing import Any

import pandas as pd

from config import UIConfig
from domain.clock import LunaVitaClock

NOT_RECORDED = "Not recorded"


class FoodEntryTime:
    """Display, order, and parse a food entry's consumed time."""

    @staticmethod
    def sort_key(row: dict[str, Any]) -> tuple[int, time, int]:
        """Return an IST clock key, placing free-form label-only rows last."""
        timestamp_text = str(row.get("consumed_at") or "")
        label = str(row.get("time_label") or "").strip()
        entry_id = int(row.get("id") or 0)
        try:
            timestamp = datetime.fromisoformat(timestamp_text)
            if timestamp.tzinfo is not None:
                timestamp = timestamp.astimezone(UIConfig.LOCAL_TIMEZONE)
            clock_time = timestamp.time().replace(tzinfo=None)
        except ValueError:
            return (1, time.max, entry_id)
        if clock_time == time.min and label:
            return (1, time.max, entry_id)
        return (0, clock_time, entry_id)

    @classmethod
    def rows_by_time(cls, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Order timed entries chronologically and keep label-only rows last."""
        return sorted(rows, key=cls.sort_key)

    @staticmethod
    def display(row: pd.Series) -> str:
        """Prefer a recorded time and fall back to its historical label."""
        consumed_at = pd.to_datetime(row.get("consumed_at"), errors="coerce")
        time_label = row.get("time_label")
        has_label = not pd.isna(time_label) and bool(str(time_label).strip())
        if not pd.isna(consumed_at) and not (
            consumed_at.hour == 0 and consumed_at.minute == 0 and has_label
        ):
            return consumed_at.strftime("%I:%M %p").lstrip("0")
        return str(time_label).strip() if has_label else NOT_RECORDED

    @staticmethod
    def resolve(value: Any, original_consumed_at: str) -> tuple[str, str | None]:
        """Convert an edited clock time or free-form label into stored values."""
        original_day = pd.to_datetime(original_consumed_at).date()
        midnight = LunaVitaClock.combine(original_day, time.min).isoformat()
        text = "" if pd.isna(value) else str(value).strip()
        if not text or text.lower() == NOT_RECORDED.lower():
            return midnight, NOT_RECORDED
        parsed = pd.to_datetime(text, errors="coerce")
        if not pd.isna(parsed):
            return LunaVitaClock.combine(original_day, parsed.time()).isoformat(), None
        return midnight, text


class FoodEntryPayload:
    """Build the backend's food-entry JSON from UI inputs."""

    NUTRITION_FIELDS = (
        "protein_g",
        "carbs_g",
        "fat_g",
        "natural_sugar_g",
        "added_sugar_g",
    )

    @staticmethod
    def nullable(value: Any) -> Any:
        return None if pd.isna(value) else value

    @classmethod
    def nutrition(cls, values: dict[str, Any]) -> dict[str, Any]:
        return {
            "calories": int(values["calories"]),
            **{field: float(values[field]) for field in cls.NUTRITION_FIELDS},
        }

    @classmethod
    def from_editor_row(cls, row: dict[str, Any], original: dict[str, Any]) -> dict[str, Any]:
        """Merge an edited table row onto the stored entry it came from."""
        consumed_at, time_label = FoodEntryTime.resolve(
            row["display_time"], original["consumed_at"]
        )
        return {
            "food_name": str(row["food_name"]).strip(),
            "quantity": str(row["quantity"]).strip(),
            "meal_type": original["meal_type"],
            **cls.nutrition(row),
            "image_url": cls.nullable(row["image_url"]),
            "consumed_at": consumed_at,
            "consumed_date": original["consumed_date"],
            "time_label": time_label,
            "notes": cls.nullable(row["notes"]),
        }

    @classmethod
    def from_form(
        cls,
        *,
        food_name: str,
        quantity: str,
        nutrition: dict[str, Any],
        image_url: str | None,
        consumed_date: date,
        consumed_time: time | None,
        time_label: str,
        notes: str,
    ) -> dict[str, Any]:
        """Build a new entry; an omitted time is stored as midnight plus a label."""
        return {
            "food_name": food_name.strip(),
            "quantity": quantity.strip(),
            "meal_type": "other",
            **cls.nutrition(nutrition),
            "image_url": image_url,
            "consumed_at": LunaVitaClock.combine(
                consumed_date, consumed_time or time.min
            ).isoformat(),
            "consumed_date": consumed_date.isoformat(),
            "time_label": time_label.strip()
            or (None if consumed_time is not None else NOT_RECORDED),
            "notes": notes.strip() or None,
        }
