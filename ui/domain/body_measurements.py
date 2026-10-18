"""Pure shaping of body measurements into Morning/Night tables and payloads."""

from datetime import date
from typing import Any

import pandas as pd

PERIODS = ("Morning", "Night")


class BodyMetrics:
    """The tracked body metrics and how each is displayed."""

    METRICS = {
        "weight": ("Weight", "kg"),
        "bmr": ("BMR", "kcal/day"),
        "health_score": ("Health score", "/100"),
        "body_age": ("Body age", "years"),
        "bmi": ("BMI", "index"),
        "water_ratio": ("Water ratio", "%"),
    }
    DISPLAY_COLUMNS = ["Measurement", *PERIODS]

    @staticmethod
    def period(row: pd.Series) -> str:
        label = str(row.get("time_label") or "").lower()
        if "morning" in label or "am" in label:
            return "Morning"
        if "night" in label or "evening" in label or "pm" in label:
            return "Night"
        return "Morning" if row["measured_at"].hour < 12 else "Night"

    @staticmethod
    def format_value(metric: str, value: float, unit: str) -> str:
        if metric == "health_score":
            return f"{value:g}/100"
        if metric == "bmi":
            return f"{value:g}"
        return f"{value:g} {unit}"

    @classmethod
    def measurement_frame(cls, rows: list[dict[str, Any]], day: date) -> pd.DataFrame:
        """Normalize measurements and safely retain only the selected day."""
        frame = pd.DataFrame(rows)
        if frame.empty:
            return pd.DataFrame(
                columns=["metric", "value", "unit", "measured_at", "period"]
            )

        frame["measured_at"] = pd.to_datetime(frame["measured_at"], errors="coerce")
        frame = frame[
            frame["metric"].isin(cls.METRICS)
            & frame["measured_at"].notna()
            & (frame["measured_at"].dt.date == day)
        ].copy()
        if frame.empty:
            frame["period"] = pd.Series(index=frame.index, dtype="object")
        else:
            frame["period"] = frame.apply(cls.period, axis=1)
        return frame

    @classmethod
    def display_frame(cls, frame: pd.DataFrame) -> pd.DataFrame:
        """Build the measurement table with Morning permanently before Night."""
        display_rows = []
        for metric, (label, _) in cls.METRICS.items():
            display = {"Measurement": label, **{period: "Not recorded" for period in PERIODS}}
            if not frame.empty:
                metric_rows = frame[frame["metric"] == metric]
                for period in PERIODS:
                    matches = metric_rows[metric_rows["period"] == period].sort_values(
                        "measured_at"
                    )
                    if not matches.empty:
                        row = matches.iloc[-1]
                        display[period] = cls.format_value(
                            metric, float(row["value"]), str(row["unit"])
                        )
            display_rows.append(display)
        return pd.DataFrame(display_rows, columns=cls.DISPLAY_COLUMNS)

    @staticmethod
    def rows_for_period(frame: pd.DataFrame, period: str) -> list[dict[str, Any]]:
        if frame.empty:
            return []
        return frame[frame["period"] == period].to_dict("records")

    @classmethod
    def payloads(
        cls,
        values: dict[str, float | None],
        *,
        measured_at: str,
        period: str,
        notes: str,
    ) -> list[dict[str, Any]]:
        """One payload per entered metric; blank metrics are skipped."""
        return [
            {
                "metric": metric,
                "value": float(values[metric]),
                "unit": unit,
                "measured_at": measured_at,
                "time_label": period,
                "notes": notes.strip() or None,
            }
            for metric, (_, unit) in cls.METRICS.items()
            if values.get(metric) is not None
        ]
