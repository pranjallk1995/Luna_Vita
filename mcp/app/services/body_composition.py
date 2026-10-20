"""Weight and body fat % series, with body fat estimated when not recorded."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.clock import LocalClock

Row = dict[str, Any]


class BodyComposition:
    """Shape measurement rows into weight and body fat % readings.

    Body fat comes from recorded measurements when present. Otherwise it is
    estimated from the same weigh-in's total body water using the standard
    fat-free-mass hydration constant: fat-free mass ≈ body water ÷ 0.732.
    """

    FAT_METRICS = frozenset(
        {
            "body_fat",
            "body_fat_percent",
            "body_fat_percentage",
            "body_fat_ratio",
            "body_fat_rate",
            "fat_ratio",
        }
    )
    HYDRATION = 0.732
    ESTIMATE_METHOD = (
        "Estimated from total body water at the same weigh-in: "
        "body fat % = (1 - body water / 0.732 / weight) x 100. "
        "Typically within about 3-5 percentage points."
    )

    @classmethod
    def estimate_body_fat(cls, weight_kg: float, body_water_kg: float) -> float | None:
        if weight_kg <= 0 or body_water_kg <= 0:
            return None
        percent = (1 - body_water_kg / cls.HYDRATION / weight_kg) * 100
        return round(percent, 1) if 0 < percent < 75 else None

    @classmethod
    def _by_metric(cls, rows: list[Row]) -> dict[str, dict[datetime, Row]]:
        """``{metric: {timestamp: row}}``; repeated readings at one timestamp collapse."""
        grouped: dict[str, dict[datetime, Row]] = {}
        for row in rows:
            moment = row["measured_at"]
            if isinstance(moment, str):
                moment = datetime.fromisoformat(moment)
            metric = str(row["metric"]).lower()
            metric = "body_fat" if metric in cls.FAT_METRICS else metric
            grouped.setdefault(metric, {})[LocalClock.localize(moment)] = row
        return grouped

    @staticmethod
    def _reading(moment: datetime, value: float, row: Row, **extra: Any) -> Row:
        return {
            "measured_at": moment.isoformat(),
            "value": round(float(value), 2),
            "time_label": row.get("time_label"),
            **extra,
        }

    @classmethod
    def series(cls, rows: list[Row]) -> dict[str, Any]:
        grouped = cls._by_metric(rows)
        weights = grouped.get("weight", {})
        fat = {
            moment: cls._reading(moment, row["value"], row, estimated=False)
            for moment, row in grouped.get("body_fat", {}).items()
        }
        for moment, water in grouped.get("total_body_water", {}).items():
            if moment in fat or moment not in weights:
                continue
            estimate = cls.estimate_body_fat(
                float(weights[moment]["value"]), float(water["value"])
            )
            if estimate is not None:
                fat[moment] = cls._reading(moment, estimate, water, estimated=True)
        return {
            "weight": [
                cls._reading(moment, row["value"], row, unit="kg")
                for moment, row in sorted(weights.items())
            ],
            "body_fat": [reading for _, reading in sorted(fat.items())],
            "body_fat_estimate_method": cls.ESTIMATE_METHOD,
        }
