"""Calendar of done / skipped workout days, with an icon per type trained."""

import calendar
import math
from datetime import date, timedelta
from typing import Any


class WorkoutTypes:
    """What a done workout trained, each with a label and a 24px line icon."""

    # Label and inline SVG body; Material Symbols has no muscle-group icons.
    TYPES = {
        "legs": (
            "Legs",
            '<path d="M8.5 2.5c-.5 2.8-.3 5.6.7 8.2.3.8.3 1.7.1 2.5l-1.1 4.6c-.3 1.4-1.6 2.4-3 2.4H15l-.6-3.4c-.2-1.2 0-2.4.5-3.5.7-1.6.7-3.3 0-4.9.4-2 .3-4.1 0-6"/>',
        ),
        "back": (
            "Back",
            '<path d="M5 5.5c2.2-1.6 4.6-2 7-2s4.8.4 7 2l-2.4 6.5.9 8.5H6.5l.9-8.5z"/><path d="M12 6v13"/><path d="M8.5 9.5c1 1 2 1.5 3.5 1.5s2.5-.5 3.5-1.5"/>',
        ),
        "chest": (
            "Chest",
            '<path d="M5 5.5c2.2-1.6 4.6-2 7-2s4.8.4 7 2l-2.4 6.5.9 8.5H6.5l.9-8.5z"/><path d="M6.6 7.6c1.6 2.6 3.6 3.2 5.4 2 1.8 1.2 3.8.6 5.4-2"/><path d="M12 13.5v.01M12 16.5v.01"/>',
        ),
        "shoulders": (
            "Shoulders",
            '<circle cx="12" cy="5.5" r="2.5"/><path d="M3.5 20v-5.5A4.5 4.5 0 0 1 8 10h8a4.5 4.5 0 0 1 4.5 4.5V20"/><path d="M5 13.2c.8-1.6 2.3-2.4 4-2.2"/><path d="M19 13.2c-.8-1.6-2.3-2.4-4-2.2"/>',
        ),
        "biceps": (
            "Biceps",
            '<path d="M3 12.5c1.6-.6 2.7-1.7 4.2-2.9 2.4-1.8 5.6-1.5 7.5.7l1-4.4-1.9-1.7c.2-1 1-1.7 2-1.7h1.7c1 0 1.9.7 2.1 1.7l.4 2.2c.5 2.8.5 5.6.1 8.4-.3 2-2 3.4-4 3.4H3"/>',
        ),
        "triceps": (
            "Triceps",
            '<path transform="matrix(1 0 0 -1 0 24)" d="M3 12.5c1.6-.6 2.7-1.7 4.2-2.9 2.4-1.8 5.6-1.5 7.5.7l1-4.4-1.9-1.7c.2-1 1-1.7 2-1.7h1.7c1 0 1.9.7 2.1 1.7l.4 2.2c.5 2.8.5 5.6.1 8.4-.3 2-2 3.4-4 3.4H3"/>',
        ),
        "core": (
            "Core",
            '<rect x="6" y="3" width="12" height="18" rx="4"/><path d="M12 3v18M6.5 9h11M6.5 15h11"/>',
        ),
        "cardio": (
            "Cardio",
            '<path d="M12 20s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.3a4.3 4.3 0 0 1 7.5 2.5C19.5 15.4 12 20 12 20z"/><path d="M5 12h3.5l1.5-2.5 2.5 5 1.5-2.5H19"/>',
        ),
        "full_body": (
            "Full body",
            '<circle cx="12" cy="4.5" r="2"/><path d="M4.5 9.5 12 9l7.5.5"/><path d="M12 9v6.5"/><path d="M8.5 21l3.5-5.5 3.5 5.5"/>',
        ),
    }
    # A day cell fits three icons; more collapse into a "+n" count.
    MAX_ICONS = 3

    @classmethod
    def label(cls, kind: str) -> str:
        return cls.TYPES[kind][0]

    @classmethod
    def icon(cls, kind: str) -> str:
        label, body = cls.TYPES[kind]
        return (
            f'<svg class="workout-type-icon" viewBox="0 0 24 24" fill="none" '
            f'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            f'stroke-linejoin="round" role="img" aria-label="{label}">{body}</svg>'
        )

    @classmethod
    def icons(cls, kinds: list[str]) -> str:
        known = [kind for kind in kinds if kind in cls.TYPES]
        shown = "".join(cls.icon(kind) for kind in known[: cls.MAX_ICONS])
        extra = len(known) - cls.MAX_ICONS
        more = f'<span class="workout-type-more">+{extra}</span>' if extra > 0 else ""
        return f'<span class="workout-types">{shown}{more}</span>'


class ExerciseLog:
    """Convert logged exercises to editor rows and back to API payloads."""

    NUMBER_FIELDS = {"sets": int, "reps": int, "weight_kg": float, "duration_min": float}
    COLUMNS = ["id", "exercise", "type", *NUMBER_FIELDS, "notes"]
    # The editor shows type labels; an empty cell means no type.
    TYPE_BY_LABEL = {label: kind for kind, (label, _) in WorkoutTypes.TYPES.items()}

    @staticmethod
    def blank(value: Any) -> bool:
        return value is None or (isinstance(value, float) and math.isnan(value)) or value == ""

    @classmethod
    def editor_rows(cls, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                **{column: row.get(column) for column in cls.COLUMNS},
                "type": WorkoutTypes.label(row["type"]) if row.get("type") in WorkoutTypes.TYPES else None,
                "remove": False,
            }
            for row in rows
        ]

    @classmethod
    def payload(cls, row: dict[str, Any], day: date) -> dict[str, Any]:
        """An exercise payload from a dialog or editor row; blanks become nulls."""
        payload: dict[str, Any] = {
            "day": day.isoformat(),
            "exercise": str(row.get("exercise") or "").strip(),
            "type": None if cls.blank(row.get("type")) else cls.TYPE_BY_LABEL.get(row["type"], row["type"]),
            "notes": None if cls.blank(row.get("notes")) else str(row["notes"]).strip() or None,
        }
        for field, cast in cls.NUMBER_FIELDS.items():
            value = row.get(field)
            payload[field] = None if cls.blank(value) else cast(value)
        return payload

    @classmethod
    def errors(cls, rows: list[dict[str, Any]]) -> list[str]:
        return [
            f"Row {number}: exercise name is required."
            for number, row in enumerate(rows, start=1)
            if not row.get("remove") and cls.blank(str(row.get("exercise") or "").strip())
        ]


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
    def types(records: list[dict[str, Any]]) -> dict[date, list[str]]:
        """Workout types of each done day; skipped days have none."""
        return {
            date.fromisoformat(row["workout_date"]): list(row.get("types") or [])
            for row in records
            if row["done"]
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
    def cell_html(
        cls,
        cell: date | None,
        status: str,
        selected: date,
        today: date,
        kinds: list[str] | None = None,
    ) -> str:
        if cell is None:
            return '<div class="workout-day outside"></div>'
        icon, label = cls.MARKERS[status]
        kinds = [kind for kind in kinds or [] if kind in WorkoutTypes.TYPES]
        if kinds:
            label = f"{label}: {', '.join(WorkoutTypes.label(kind) for kind in kinds)}"
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
        if kinds:
            marker = WorkoutTypes.icons(kinds)
        else:
            marker = f'<span class="workout-marker">{icon}</span>' if icon else ""
        return (
            f'<div class="{classes}" title="{cell:%a %d %b} · {label}">'
            f'<span class="workout-date">{cell.day}</span>{marker}</div>'
        )

    @classmethod
    def month_html(
        cls,
        month: date,
        statuses: dict[date, str],
        selected: date,
        today: date,
        types: dict[date, list[str]] | None = None,
    ) -> str:
        head = "".join(f'<div class="workout-weekday">{name}</div>' for name in cls.WEEKDAYS)
        cells = "".join(
            cls.cell_html(
                cell, statuses.get(cell, "none"), selected, today, (types or {}).get(cell)
            )
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
        types = cls.types(records)
        done = sum(status == "done" for status in statuses.values())
        skipped = len(statuses) - done
        months = "".join(
            cls.month_html(month, statuses, selected, today, types)
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
