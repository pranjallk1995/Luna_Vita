"""Tests for the workout calendar on the monthly overview."""

import unittest
from datetime import date

from domain.workouts import ExerciseLog, WorkoutCalendar, WorkoutTypes

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


class WorkoutTypeIconTests(unittest.TestCase):
    def test_done_days_show_an_icon_per_type_instead_of_the_check(self):
        records = [{"workout_date": "2026-10-17", "done": True, "types": ["back", "biceps"]}]
        html = WorkoutCalendar.html(records, date(2026, 10, 1), date(2026, 10, 31), SELECTED, TODAY)
        self.assertEqual(html.count('class="workout-type-icon"'), 2)
        self.assertIn('aria-label="Back"', html)
        self.assertIn("Workout done: Back, Biceps", html)
        self.assertNotIn('<span class="workout-marker">check</span>', html)

    def test_done_days_without_types_keep_the_check_marker(self):
        html = WorkoutCalendar.html(RECORDS, date(2026, 10, 1), date(2026, 10, 31), SELECTED, TODAY)
        self.assertIn('<span class="workout-marker">check</span>', html)
        self.assertNotIn("workout-type-icon", html)

    def test_extra_types_collapse_into_a_count_and_unknown_ones_are_ignored(self):
        html = WorkoutTypes.icons(["legs", "back", "chest", "core", "cardio", "yoga"])
        self.assertEqual(html.count('class="workout-type-icon"'), WorkoutTypes.MAX_ICONS)
        self.assertIn("+2", html)


class ExerciseLogTests(unittest.TestCase):
    ROW = {
        "id": 7, "workout_date": "2026-10-21", "exercise": "Hammer curl", "type": "biceps",
        "sets": 3, "reps": 12, "weight_kg": 12.5, "duration_min": None, "notes": None,
    }

    def test_editor_rows_show_type_labels(self):
        [row] = ExerciseLog.editor_rows([self.ROW])
        self.assertEqual((row["type"], row["remove"]), ("Biceps", False))

    def test_payload_maps_labels_back_and_blanks_to_null(self):
        row = {**ExerciseLog.editor_rows([self.ROW])[0], "sets": 3.0, "duration_min": float("nan"), "notes": ""}
        payload = ExerciseLog.payload(row, date(2026, 10, 21))
        self.assertEqual(payload["type"], "biceps")
        self.assertEqual((payload["sets"], payload["duration_min"], payload["notes"]), (3, None, None))
        self.assertIsInstance(payload["sets"], int)

    def test_rows_without_a_name_are_errors_unless_deleted(self):
        rows = [{"exercise": " ", "remove": False}, {"exercise": "", "remove": True}]
        self.assertEqual(ExerciseLog.errors(rows), ["Row 1: exercise name is required."])
