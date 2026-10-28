"""Running (trailing-window) averages of daily macros, weight, and body fat %."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import date, datetime, timedelta
from statistics import fmean
from typing import Any

from app.core.clock import LocalClock
from app.services.analysis import NUTRIENT_FIELDS
from app.services.body_composition import BodyComposition
from app.core.config import AppConfig

Row = dict[str, Any]

# Nutrient field -> its daily target column in daily_recommendations.
TARGET_FIELDS = {
    "calories": "calories_kcal",
    "protein_g": "protein_g",
    "carbs_g": "carbs_g",
    "fat_g": "fat_g",
    "added_sugar_g": "sugars_g",
}
BODY_METRICS = ["weight", "total_body_water", *sorted(BodyComposition.FAT_METRICS)]


class RunningAverages:
    """Average each trailing window of days, the way the Overview tab averages a month.

    Macros are averaged over logged days only, so unlogged days do not dilute
    them, and today is left out while it is still being logged (unless it is
    the window's only logged day). Weight and body fat % are averaged per day
    first, so a day with three weigh-ins counts once.
    """

    def __init__(self, food, measurements, recommendations, today: Callable[[], date] = LocalClock.today) -> None:
        self.food = food
        self.measurements = measurements
        self.recommendations = recommendations
        self.today = today

    def summary(self, windows: list[int], end: date | None = None) -> Row:
        """Averages for each trailing window ending on ``end``, with the change from the window before."""
        end = end or self.today()
        windows = sorted({self._check_window(days) for days in windows})
        if not windows:
            raise ValueError("Give at least one window length in days.")
        # Twice the longest window, so each window can be compared with the one before it.
        data = self._load(end - timedelta(days=2 * windows[-1] - 1), end)
        targets = self._targets()
        result = []
        for days in windows:
            current = data.window(end, days)
            previous = data.window(end - timedelta(days=days), days)
            result.append(
                {
                    "days": days,
                    "start_date": (end - timedelta(days=days - 1)).isoformat(),
                    "end_date": end.isoformat(),
                    "macros": self._macros(current, previous, targets),
                    "weight_kg": self._body(current.weights, previous.weights),
                    "body_fat_percent": {
                        **self._body(current.body_fat, previous.body_fat),
                        "estimated_days": current.estimated_fat_days,
                    },
                }
            )
        return {
            "today": data.today.isoformat(),
            "windows": result,
            "notes": [
                "Macro averages are per logged day; today is excluded while it is being logged.",
                "change compares each average with the same-length window just before it.",
                BodyComposition.ESTIMATE_METHOD,
            ],
        }

    def series(self, window_days: int, start: date, end: date) -> Row:
        """The trailing ``window_days`` average on every day from ``start`` to ``end``."""
        window_days = self._check_window(window_days)
        if end < start:
            raise ValueError("end_date must be on or after start_date.")
        if (end - start).days + 1 > AppConfig.MAX_SERIES_DAYS:
            raise ValueError(f"A series covers at most {AppConfig.MAX_SERIES_DAYS} days.")
        data = self._load(start - timedelta(days=window_days - 1), end)
        days = []
        for offset in range((end - start).days + 1):
            day = start + timedelta(days=offset)
            window = data.window(day, window_days)
            macros = window.macro_averages()
            days.append(
                {
                    "date": day.isoformat(),
                    "logged_days": window.macro_days,
                    **{field: self._round(macros.get(field)) for field in NUTRIENT_FIELDS},
                    "weight_kg": self._round(window.mean(window.weights), 2),
                    "body_fat_percent": self._round(window.mean(window.body_fat), 1),
                }
            )
        return {
            "window_days": window_days,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "today": data.today.isoformat(),
            "days": days,
        }

    # Pieces

    def _check_window(self, days: int) -> int:
        if not 1 <= int(days) <= AppConfig.MAX_WINDOW_DAYS:
            raise ValueError(f"Window lengths must be 1-{AppConfig.MAX_WINDOW_DAYS} days.")
        return int(days)

    def _load(self, start: date, end: date) -> _DailyData:
        food = self.food.list_between(start, end)
        body = BodyComposition.series(self.measurements.list_between(start, end, BODY_METRICS))
        return _DailyData(food, body, self.today())

    def _targets(self) -> dict[str, float]:
        profile = self.recommendations.get() or {}
        return {
            field: float(profile[column])
            for field, column in TARGET_FIELDS.items()
            if profile.get(column) is not None
        }

    def _macros(self, current: _Window, previous: _Window, targets: dict[str, float]) -> Row:
        now, before = current.macro_averages(), previous.macro_averages()
        nutrients = {}
        for field in NUTRIENT_FIELDS:
            average = now.get(field)
            entry: Row = {"average": self._round(average)}
            if field in targets:
                entry["daily_target"] = targets[field]
                entry["percent_of_target"] = (
                    self._round(average / targets[field] * 100) if average is not None and targets[field] else None
                )
            entry["change"] = self._change(average, before.get(field))
            nutrients[field] = entry
        return {"logged_days": current.macro_days, "today_excluded": current.today_excluded, **nutrients}

    def _body(self, current: dict[date, float], previous: dict[date, float]) -> Row:
        average = _Window.mean(current)
        ordered = sorted(current.items())
        return {
            "average": self._round(average, 2),
            "measured_days": len(current),
            "first": self._round(ordered[0][1], 2) if ordered else None,
            "latest": self._round(ordered[-1][1], 2) if ordered else None,
            "change": self._change(average, _Window.mean(previous), 2),
        }

    @classmethod
    def _change(cls, now: float | None, before: float | None, digits: int = 1) -> float | None:
        return cls._round(now - before, digits) if now is not None and before is not None else None

    @staticmethod
    def _round(value: float | None, digits: int = 1) -> float | None:
        return None if value is None else round(value, digits)


class _DailyData:
    """Per-day macro totals and per-day mean weight and body fat % over a span."""

    def __init__(self, food_rows: list[Row], body: Row, today: date) -> None:
        self.today = today
        self.macros: dict[date, dict[str, float]] = defaultdict(lambda: dict.fromkeys(NUTRIENT_FIELDS, 0.0))
        for row in food_rows:
            day = row["consumed_date"]
            day = date.fromisoformat(day) if isinstance(day, str) else day
            for field in NUTRIENT_FIELDS:
                self.macros[day][field] += float(row.get(field) or 0)
        self.weights = self._daily_means(body["weight"])
        self.body_fat = self._daily_means(body["body_fat"])
        self.estimated_fat = {self._day(reading) for reading in body["body_fat"] if reading.get("estimated")}

    @staticmethod
    def _day(reading: Row) -> date:
        return datetime.fromisoformat(reading["measured_at"]).date()

    @classmethod
    def _daily_means(cls, readings: list[Row]) -> dict[date, float]:
        by_day: dict[date, list[float]] = defaultdict(list)
        for reading in readings:
            by_day[cls._day(reading)].append(float(reading["value"]))
        return {day: fmean(values) for day, values in by_day.items()}

    def window(self, end: date, days: int) -> _Window:
        start = end - timedelta(days=days - 1)

        def inside(values: dict) -> dict:
            return {day: value for day, value in values.items() if start <= day <= end}

        return _Window(
            inside(self.macros),
            inside(self.weights),
            inside(self.body_fat),
            sum(1 for day in self.estimated_fat if start <= day <= end),
            self.today,
        )


class _Window:
    def __init__(self, macros, weights, body_fat, estimated_fat_days: int, today: date) -> None:
        completed = {day: totals for day, totals in macros.items() if day != today}
        # Today is left out while it is being logged, unless it is all there is.
        self.today_excluded = bool(completed) and today in macros
        self.macro_rows = completed or macros
        self.macro_days = len(self.macro_rows)
        self.weights = weights
        self.body_fat = body_fat
        self.estimated_fat_days = estimated_fat_days

    def macro_averages(self) -> dict[str, float]:
        if not self.macro_rows:
            return {}
        return {
            field: fmean(totals[field] for totals in self.macro_rows.values()) for field in NUTRIENT_FIELDS
        }

    @staticmethod
    def mean(values: dict[date, float]) -> float | None:
        return fmean(values.values()) if values else None
