"""Calendar of done / skipped workout days across whole months."""

import calendar
from datetime import date, timedelta
from typing import Any


class WorkoutCalendar:
    """Monday-first month grids with a marker on every recorded day."""

    WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
    MARKERS = {
        "done": ("check", "Workout done"),
        "skipped": ("close", "Workout skipped"),
        "none": ("", "Not recorded"),
    }

    @staticmethod
    def statuses(records: list[dict[str, Any]]) -> dict[date, str]:
        return {
            date.fromisoformat(row["workout_date"]): "done" if row["done"] else "skipped"
            for row in records
        }

    @staticmethod
    def span(start: date, end: date, selected: date) -> tuple[date, date]:
        """Whole months covering the range and the selected day.

        Including the selected day keeps a day just marked on the Daily tab
        visible even when a saved range ends before it.
        """
        first, last = min(start, selected), max(end, selected)
        return first.replace(day=1), last.replace(day=calendar.monthrange(last.year, last.month)[1])

    @staticmethod
    def months(start: date, end: date) -> list[date]:
        """The first day of every month the range touches."""
        first, months = start.replace(day=1), []
        while first <= end:
            months.append(first)
            first = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
        return months

    @staticmethod
    def weeks(month: date) -> list[list[date | None]]:
        """The month's weeks, with ``None`` padding days outside the month."""
        return [
            [cell if cell.month == month.month else None for cell in week]
            for week in calendar.Calendar(firstweekday=0).monthdatescalendar(month.year, month.month)
        ]

    @classmethod
    def cell_html(cls, cell: date | None, status: str, selected: date, today: date) -> str:
        if cell is None:
            return '<div class="workout-day outside"></div>'
        icon, label = cls.MARKERS[status]
        classes = " ".join(
            name
            for name, applies in (
                ("workout-day", True),
                (status, True),
                ("selected", cell == selected),
                ("today", cell == today),
            )
            if applies
        )
        marker = f'<span class="workout-marker">{icon}</span>' if icon else ""
        return (
            f'<div class="{classes}" title="{cell:%a %d %b} · {label}">'
            f'<span class="workout-date">{cell.day}</span>{marker}</div>'
        )

    @classmethod
    def month_html(
        cls, month: date, statuses: dict[date, str], selected: date, today: date
    ) -> str:
        head = "".join(f'<div class="workout-weekday">{name}</div>' for name in cls.WEEKDAYS)
        cells = "".join(
            cls.cell_html(cell, statuses.get(cell, "none"), selected, today)
            for week in cls.weeks(month)
            for cell in week
        )
        return (
            '<div class="workout-month">'
            f'<div class="workout-month-label">{month:%B %Y}</div>'
            f'<div class="workout-grid">{head}{cells}</div></div>'
        )

    @classmethod
    def html(
        cls, records: list[dict[str, Any]], start: date, end: date, selected: date, today: date
    ) -> str:
        """Every month from ``start`` to ``end``; counts cover the months shown."""
        statuses = {
            day: status for day, status in cls.statuses(records).items() if start <= day <= end
        }
        done = sum(status == "done" for status in statuses.values())
        skipped = len(statuses) - done
        months = "".join(
            cls.month_html(month, statuses, selected, today)
            for month in cls.months(start, end)
        )
        return (
            '<div class="workout-calendar">'
            '<div class="workout-calendar-head">'
            "<strong>Workouts</strong>"
            '<span class="workout-legend">'
            f'<span><i class="workout-key done"></i>{done} done</span>'
            f'<span><i class="workout-key skipped"></i>{skipped} skipped</span>'
            "</span></div>"
            f'<div class="workout-months">{months}</div></div>'
        )
