"""Body weight and body fat % per day, as morning/night bars in one overview card.

The backend pairs readings, estimates body fat, and supplies the target
(see ``/api/body-composition``); this module only draws them.
"""

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from html import escape
from typing import Any

from domain.clock import LunaVitaClock

PERIODS = ("Morning", "Night")


@dataclass(frozen=True)
class Reading:
    at: datetime
    value: float
    label: str = ""
    estimated: bool = False

    @classmethod
    def parse(cls, readings: list[dict[str, Any]]) -> list["Reading"]:
        """Readings from the backend's ``/api/body-composition`` series."""
        return [
            cls(
                at=datetime.fromisoformat(item["measured_at"]).astimezone(LunaVitaClock.LOCAL_TIMEZONE),
                value=float(item["value"]),
                label=item.get("time_label") or "",
                estimated=bool(item.get("estimated")),
            )
            for item in readings
        ]

    @property
    def period(self) -> str:
        """Morning or Night, from the reading's label or else its local hour."""
        label = self.label.lower()
        if "morning" in label or "am" in label:
            return "Morning"
        if "night" in label or "evening" in label or "pm" in label:
            return "Night"
        return "Morning" if self.at.hour < 12 else "Night"


@dataclass(frozen=True)
class Metric:
    label: str
    unit: str
    decimals: int
    icon: str

    def amount(self, value: float) -> str:
        spacer = "" if self.unit == "%" else " "
        return f"{value:.{self.decimals}f}{spacer}{self.unit}"


WEIGHT = Metric("Weight", "kg", 2, "monitor_weight")
BODY_FAT = Metric("Body fat", "%", 1, "accessibility_new")


class BodyTrendChart:
    """Weight above body fat %, each with a morning and a night bar per day."""

    SLOT = 10  # viewBox units per day, as in the macro trend charts
    HEIGHT = 60
    BAR_WIDTH = 3.6
    BAR_GAP = 0.8
    WEIGHT_STEP = 1.0  # weight bars rise from a whole-kg floor below the lowest reading

    @staticmethod
    def day_label(day: date) -> str:
        return f"{day.day} {day:%b}"

    @staticmethod
    def days(start: date, end: date) -> list[date]:
        return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]

    @staticmethod
    def by_day(readings: list[Reading]) -> dict[date, dict[str, Reading]]:
        """The latest Morning and Night reading of each local day."""
        grouped: dict[date, dict[str, Reading]] = {}
        for reading in sorted(readings, key=lambda item: item.at):
            grouped.setdefault(reading.at.date(), {})[reading.period] = reading
        return grouped

    @classmethod
    def weight_range(cls, readings: list[Reading]) -> tuple[float, float]:
        values = [reading.value for reading in readings]
        floor = math.floor(min(values) - 0.5)
        return floor, max(math.ceil(max(values) + 0.5), floor + cls.WEIGHT_STEP)

    @classmethod
    def svg(
        cls,
        metric: Metric,
        readings: list[Reading],
        days: list[date],
        low: float,
        high: float,
        target: float | None = None,
    ) -> str:
        def y(value: float) -> float:
            return cls.HEIGHT - (value - low) / (high - low) * cls.HEIGHT

        grouped = cls.by_day(readings)
        width = cls.SLOT * len(days)
        inset = (cls.SLOT - 2 * cls.BAR_WIDTH - cls.BAR_GAP) / 2
        columns = []
        for index, day in enumerate(days):
            x = index * cls.SLOT
            periods = grouped.get(day, {})
            bars, tips = [], [cls.day_label(day)]
            for slot, period in enumerate(PERIODS):
                reading = periods.get(period)
                if reading is None:
                    continue
                top = y(reading.value)
                bar_x = x + inset + slot * (cls.BAR_WIDTH + cls.BAR_GAP)
                bars.append(
                    f'<rect class="body-trend-bar {period.lower()}" x="{bar_x:.2f}" y="{top:.2f}" '
                    f'width="{cls.BAR_WIDTH}" height="{cls.HEIGHT - top:.2f}"/>'
                )
                estimated = " (est.)" if reading.estimated else ""
                tips.append(f"{period} {metric.amount(reading.value)}{estimated}")
            if not bars:
                tips.append("not recorded")
            columns.append(
                f'<g class="nutrient-trend-day"><title>{escape(" · ".join(tips))}</title>'
                f'<rect class="nutrient-trend-hit" x="{x}" y="0" width="{cls.SLOT}" '
                f'height="{cls.HEIGHT}"/>{"".join(bars)}</g>'
            )
        target_line = ""
        if target is not None:
            target_y = y(target)
            target_line = (
                f'<line class="nutrient-trend-target" x1="0" x2="{width}" '
                f'y1="{target_y:.2f}" y2="{target_y:.2f}"/>'
            )
        return (
            f'<svg class="nutrient-trend-plot body-trend-plot" viewBox="0 0 {width} {cls.HEIGHT}" '
            f'preserveAspectRatio="none" role="img" aria-label="{metric.label} per day">'
            f'<line class="nutrient-trend-base" x1="0" x2="{width}" '
            f'y1="{cls.HEIGHT}" y2="{cls.HEIGHT}"/>{"".join(columns)}{target_line}</svg>'
        )

    @staticmethod
    def head_html(metric: Metric, latest: Reading, note: str) -> str:
        value = f"<strong>{metric.amount(latest.value)}{' (est.)' if latest.estimated else ''}</strong>"
        return (
            '<div class="body-trend-head">'
            f'<span class="nutrition-card-label"><span class="nutrition-card-icon">{metric.icon}</span>'
            f"{metric.label}</span>{value}<span class=\"body-trend-note\">{note}</span></div>"
        )

    @classmethod
    def weight_section(cls, readings: list[Reading], days: list[date]) -> str:
        if not readings:
            return ""
        low, high = cls.weight_range(readings)
        keys = "".join(
            f'<span><i class="body-trend-key {period.lower()}"></i>{period}</span>' for period in PERIODS
        )
        head = cls.head_html(WEIGHT, readings[-1], f"{keys}<span>Bars from {low:.0f} kg</span>")
        return (
            f'<div class="body-trend-section">{head}'
            f"{cls.svg(WEIGHT, readings, days, low, high)}</div>"
        )

    @classmethod
    def fat_section(cls, readings: list[Reading], days: list[date], target: float) -> str:
        if not readings:
            return ""
        high = max([target, *(reading.value for reading in readings)]) * 1.08
        head = cls.head_html(
            BODY_FAT,
            readings[-1],
            f'<i class="nutrient-trend-key"></i>Target {BODY_FAT.amount(target)}',
        )
        return (
            f'<div class="body-trend-section">{head}'
            f"{cls.svg(BODY_FAT, readings, days, 0, high, target)}</div>"
        )

    @staticmethod
    def average(readings: list[Reading]) -> float | None:
        """Arithmetic mean of the readings displayed in the current window."""
        if not readings:
            return None
        return sum(reading.value for reading in readings) / len(readings)

    @classmethod
    def average_card(
        cls, metric: Metric, readings: list[Reading], target: float | None = None
    ) -> str:
        average = cls.average(readings)
        if average is None:
            return ""
        status = " danger" if target is not None and average > target else ""
        return (
            f'<div class="body-average-card{status}">'
            f'<span class="nutrition-card-label"><span class="nutrition-card-icon">'
            f"{metric.icon}</span>Average {metric.label.lower()}</span>"
            f'<strong>{metric.amount(average)}</strong>'
            f'<small>{len(readings)} reading{"s" if len(readings) != 1 else ""}</small>'
            "</div>"
        )

    @classmethod
    def html(
        cls, weight: list[Reading], fat: list[Reading], start: date, end: date, target: float
    ) -> str:
        """The card, without any empty section; nothing at all when there is no data."""
        if not weight and not fat:
            return ""
        days = cls.days(start, end)
        middle = days[len(days) // 2]
        averages = (
            '<div class="body-trend-averages">'
            f"{cls.average_card(WEIGHT, weight)}{cls.average_card(BODY_FAT, fat, target)}"
            "</div>"
        )
        return (
            '<div class="nutrition-card body-trend-card">'
            f"{cls.weight_section(weight, days)}{cls.fat_section(fat, days, target)}"
            '<div class="nutrient-trend-axis">'
            f"<span>{cls.day_label(start)}</span><span>{cls.day_label(middle)}</span>"
            f"<span>{cls.day_label(end)}</span></div>{averages}</div>"
        )
