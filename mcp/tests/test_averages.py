"""Tests for running averages of macros, weight, and body fat %."""

import unittest
from datetime import date

from app.services.averages import RunningAverages

TODAY = date(2026, 10, 25)


def food(day, calories, protein=0):
    return {"consumed_date": day, "calories": calories, "protein_g": protein, "carbs_g": 0, "fat_g": 0,
            "natural_sugar_g": 0, "added_sugar_g": 0}


def reading(metric, value, at):
    return {"metric": metric, "value": value, "measured_at": at, "time_label": None}


class FakeFood:
    def __init__(self, rows):
        self.rows = rows

    def list_between(self, start, end):
        return [row for row in self.rows if start <= date.fromisoformat(row["consumed_date"]) <= end]


class FakeMeasurements:
    def __init__(self, rows):
        self.rows = rows

    def list_between(self, start, end, metrics):
        return [row for row in self.rows if start <= date.fromisoformat(row["measured_at"][:10]) <= end]


class FakeRecommendations:
    def get(self):
        return {"calories_kcal": 2000, "protein_g": 150, "carbs_g": 200, "fat_g": 60, "sugars_g": 25}


class RunningAverageTests(unittest.TestCase):
    def setUp(self):
        foods = [
            food("2026-10-18", 1800, 120),  # previous 7-day window
            food("2026-10-19", 2000, 130),
            food("2026-10-20", 2200, 140),
            food("2026-10-22", 1500, 100),
            food("2026-10-22", 500, 50),   # same day: totals 2000 / 150
            food("2026-10-24", 1600, 110),
            food("2026-10-25", 300, 20),   # today, still being logged
        ]
        body = [
            reading("weight", 74.0, "2026-10-12T08:00:00+05:30"),
            reading("weight", 73.0, "2026-10-20T08:00:00+05:30"),
            reading("weight", 72.0, "2026-10-24T07:00:00+05:30"),
            reading("weight", 72.4, "2026-10-24T21:00:00+05:30"),  # same day: one 72.2 reading
            reading("weight", 72.0, "2026-10-24T08:00:00+05:30"),
            reading("total_body_water", 41.6, "2026-10-24T08:00:00+05:30"),
        ]
        self.averages = RunningAverages(
            FakeFood(foods), FakeMeasurements(body), FakeRecommendations(), today=lambda: TODAY
        )

    def test_week_averages_logged_days_without_today(self):
        week = self.averages.summary([7])["windows"][0]
        macros = week["macros"]
        self.assertEqual((week["start_date"], week["end_date"]), ("2026-10-19", "2026-10-25"))
        self.assertEqual((macros["logged_days"], macros["today_excluded"]), (4, True))
        # 2000 + 2200 + 2000 + 1600 over 4 logged days
        self.assertEqual(macros["calories"]["average"], 1950.0)
        self.assertEqual(macros["calories"]["percent_of_target"], 97.5)
        self.assertEqual(macros["protein_g"]["daily_target"], 150.0)
        self.assertEqual(macros["calories"]["change"], 1950.0 - 1800.0)
        self.assertNotIn("daily_target", macros["natural_sugar_g"])

    def test_weight_counts_each_day_once_and_compares_with_the_week_before(self):
        weight = self.averages.summary([7])["windows"][0]["weight_kg"]
        # Days: 73.0 and mean(72.0, 72.4, 72.0) -> 72.13; average of the two days
        self.assertEqual(weight["measured_days"], 2)
        self.assertAlmostEqual(weight["average"], (73.0 + (72.0 + 72.4 + 72.0) / 3) / 2, places=2)
        self.assertEqual(weight["first"], 73.0)
        self.assertEqual(weight["change"], round(weight["average"] - 74.0, 2))

    def test_body_fat_estimate_is_counted(self):
        fat = self.averages.summary([7])["windows"][0]["body_fat_percent"]
        self.assertEqual((fat["measured_days"], fat["estimated_days"]), (1, 1))
        # Estimated from the 08:00 weigh-in: (1 - 41.6 / 0.732 / 72.0) x 100
        self.assertEqual(fat["average"], 21.1)

    def test_several_windows_and_bad_lengths(self):
        windows = self.averages.summary([30, 7, 7])["windows"]
        self.assertEqual([window["days"] for window in windows], [7, 30])
        with self.assertRaisesRegex(ValueError, "1-366"):
            self.averages.summary([0])

    def test_only_today_logged_is_still_averaged(self):
        averages = RunningAverages(FakeFood([food("2026-10-25", 300)]), FakeMeasurements([]),
                                   FakeRecommendations(), today=lambda: TODAY)
        macros = averages.summary([7])["windows"][0]["macros"]
        self.assertEqual((macros["calories"]["average"], macros["today_excluded"]), (300.0, False))

    def test_series_gives_the_trailing_average_for_each_day(self):
        series = self.averages.series(3, date(2026, 10, 20), date(2026, 10, 22))
        days = {day["date"]: day for day in series["days"]}
        self.assertEqual(days["2026-10-20"]["calories"], 2000.0)  # 18, 19, 20
        self.assertEqual(days["2026-10-21"]["calories"], 2100.0)  # 19, 20 (21 unlogged)
        self.assertEqual(days["2026-10-22"]["logged_days"], 2)
        self.assertEqual(days["2026-10-20"]["weight_kg"], 73.0)
        self.assertIsNone(days["2026-10-22"]["body_fat_percent"])
        with self.assertRaisesRegex(ValueError, "on or after"):
            self.averages.series(7, date(2026, 10, 22), date(2026, 10, 20))


if __name__ == "__main__":
    unittest.main()
