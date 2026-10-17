"""Client-side mirrors of the backend's food-entry validation rules."""

import math
import re
import unicodedata
from typing import Any

import pandas as pd


class TextRules:
    """Reject blank, oversized, emoji, or control-character text."""

    EMOJI_PATTERN = re.compile(
        "[\U0001F1E6-\U0001F1FF\U0001F300-\U0001FAFF☀-➿️‍]"
    )

    @classmethod
    def error(
        cls,
        value: object,
        label: str,
        *,
        required: bool = False,
        max_length: int,
    ) -> str | None:
        """Return a user-facing error for unsafe editable text."""
        text = "" if value is None else str(value).strip()
        if required and not text:
            return f"{label} cannot be blank."
        if len(text) > max_length:
            return f"{label} must be {max_length} characters or fewer."
        if cls.EMOJI_PATTERN.search(text):
            return f"{label} cannot contain emojis."
        if any(
            unicodedata.category(character).startswith("C")
            and character not in {"\n", "\t"}
            for character in text
        ):
            return f"{label} contains unsupported control characters."
        return None


class NumberRules:
    """Reject non-finite, negative, oversized, or fractional-when-whole numbers."""

    @staticmethod
    def error(value: Any, label: str, *, maximum: int, whole_number: bool) -> str | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = math.nan
        if not math.isfinite(number):
            return f"{label} must be a valid number."
        if number < 0:
            return f"{label} cannot be negative."
        if number > maximum:
            return f"{label} cannot exceed {maximum:,}."
        if whole_number and not number.is_integer():
            return f"{label} must be a whole number."
        return None


class FoodRowValidator:
    """Validate every editable food-log row before any mutation is applied."""

    TEXT_FIELDS = (
        ("food_name", "Food / supplement", True, 200),
        ("quantity", "Quantity", True, 300),
        ("display_time", "Time", False, 100),
        ("notes", "Notes", False, 2_000),
    )
    NUMBER_FIELDS = (
        ("calories", "Calories", 100_000, True),
        ("protein_g", "Protein", 10_000, False),
        ("carbs_g", "Carbs", 10_000, False),
        ("fat_g", "Fat", 10_000, False),
        ("natural_sugar_g", "Natural sugar", 10_000, False),
        ("added_sugar_g", "Added sugar", 10_000, False),
    )

    @classmethod
    def row_errors(cls, position: int, row: dict[str, Any]) -> list[str]:
        errors = []
        for key, label, required, max_length in cls.TEXT_FIELDS:
            value = row.get(key)
            error = TextRules.error(
                "" if pd.isna(value) else value,
                f"Row {position} {label}",
                required=required,
                max_length=max_length,
            )
            errors.append(error)
        for key, label, maximum, whole_number in cls.NUMBER_FIELDS:
            errors.append(
                NumberRules.error(
                    row.get(key),
                    f"Row {position} {label}",
                    maximum=maximum,
                    whole_number=whole_number,
                )
            )
        return [error for error in errors if error]

    @classmethod
    def errors(cls, rows: list[dict[str, Any]]) -> list[str]:
        """Return every problem in rows that are not marked for deletion."""
        return [
            error
            for position, row in enumerate(rows, start=1)
            if not row.get("remove")
            for error in cls.row_errors(position, row)
        ]
