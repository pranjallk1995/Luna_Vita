"""Tests for the workout calendar on the monthly overview."""

import unittest
from datetime import date

from domain.workouts import WorkoutCalendar

RECORDS = [
    {"workout_date": "2026-10-16", "done": False},
    {"workout_date": "2026-10-17", "done": True},
]
SELECTED, TODAY = date(2026, 10, 17), date(2026, 10, 21)


class WorkoutCalendarTests(unittest.TestCase):
    def test_months_cover_every_month_the_range_touches(self):
        self.assertEqual(
            WorkoutCalendar.months(date(2026, 11, 20), date(2027, 1, 5)),
            [date(2026, 11, 1), date(2026, 12, 1), date(2027, 1, 1)],
        )

    def test_weeks_start_on_monday_and_pad_outside_days(self):
        weeks = WorkoutCalendar.weeks(date(2026, 10, 1))
        self.assertTrue(all(len(week) == 7 for week in weeks))
        self.assertEqual(weeks[0][:3], [None, None, None])  # 1 Oct 2026 is a Thursday
        self.assertEqual(weeks[0][3], date(2026, 10, 1))

    def test_recorded_days_get_markers_and_counts(self):
        html = WorkoutCalendar.html(RECORDS, date(2026, 10, 1), date(2026, 10, 31), SELECTED, TODAY)
        self.assertEqual(html.count('class="workout-day done selected"'), 1)
        self.assertEqual(html.count('class="workout-day skipped"'), 1)
        self.assertEqual(html.count('class="workout-day none today"'), 1)
        self.assertIn("1 done", html)
        self.assertIn("1 skipped", html)

    def test_span_covers_whole_months_and_the_selected_day(self):
        self.assertEqual(
            WorkoutCalendar.span(date(2026, 10, 14), date(2026, 10, 20), date(2026, 11, 2)),
            (date(2026, 10, 1), date(2026, 11, 30)),
        )

    def test_records_outside_the_shown_months_are_not_counted(self):
        records = [*RECORDS, {"workout_date": "2026-11-01", "done": True}]
        html = WorkoutCalendar.html(records, date(2026, 10, 1), date(2026, 10, 31), SELECTED, TODAY)
        self.assertIn("1 done", html)
