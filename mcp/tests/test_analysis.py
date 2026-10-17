"""Tests for the period food analysis."""

import unittest
from datetime import date

import json

from app.analysis import FoodAnalysis, FoodGroup, FoodName, MacroQuality, PeriodWindow


def entry(name, day="2026-10-15", calories=100, protein=0, carbs=0, fat=0, added=0):
    return {
        "food_name": name,
        "consumed_date": day,
        "calories": calories,
        "protein_g": protein,
        "carbs_g": carbs,
        "fat_g": fat,
        "natural_sugar_g": 0,
        "added_sugar_g": added,
    }


def group(*rows) -> FoodGroup:
    food = FoodGroup(key="x")
    for row in rows:
        food.add(row)
    return food


class PeriodWindowTests(unittest.TestCase):
    def test_month_window_spans_the_whole_calendar_month(self) -> None:
        window = PeriodWindow.month_of(date(2026, 10, 17))

        self.assertEqual((window.start, window.end), (date(2026, 10, 1), date(2026, 10, 31)))
        self.assertEqual(window.length, 31)

    def test_month_window_handles_leap_february(self) -> None:
        self.assertEqual(PeriodWindow.month_of(date(2028, 2, 10)).end, date(2028, 2, 29))


class FoodNameTests(unittest.TestCase):
    def test_case_spacing_and_plural_variants_share_a_key(self) -> None:
        self.assertEqual(FoodName.key("Parathas"), FoodName.key("  paratha "))
        self.assertEqual(FoodName.key("Whey Protein"), FoodName.key("whey protein"))

    def test_distinct_foods_and_double_s_words_stay_distinct(self) -> None:
        self.assertNotEqual(FoodName.key("Aloo paratha with ketchup"), FoodName.key("Paratha"))
        self.assertEqual(FoodName.key("Hummus"), "hummus")
        self.assertEqual(FoodName.key("Mixed grass"), "mixed grass")
        self.assertEqual(FoodName.key("Max Protein Chips"), "max protein chip")


class MacroQualityTests(unittest.TestCase):
    def test_protein_dense_low_carb_food_is_preferred(self) -> None:
        whey = group(entry("Whey", calories=120, protein=25, carbs=3, fat=1.5))

        self.assertEqual(MacroQuality.verdict(whey).kind, "prefer")

    def test_sugary_food_is_avoided_with_sugar_reason(self) -> None:
        coffee = group(entry("Coffee", calories=177, protein=5, carbs=28, fat=5, added=20))

        verdict = MacroQuality.verdict(coffee)
        self.assertEqual(verdict.kind, "avoid")
        self.assertIn("added sugar", verdict.reason)

    def test_low_protein_starch_is_avoided_and_names_the_heavier_macro(self) -> None:
        rice = group(entry("Rice", calories=130, protein=2.7, carbs=28, fat=0.3))

        verdict = MacroQuality.verdict(rice)
        self.assertEqual(verdict.kind, "avoid")
        self.assertIn("from carbs", verdict.reason)

    def test_low_calorie_items_are_not_rated(self) -> None:
        creatine = group(entry("Creatine", calories=0))

        self.assertEqual(MacroQuality.verdict(creatine).kind, "neutral")

    def test_score_ranks_whey_above_paneer_above_rice(self) -> None:
        whey = group(entry("Whey", calories=120, protein=25, carbs=3, fat=1.5))
        paneer = group(entry("Paneer", calories=345, protein=20, carbs=10, fat=25))
        rice = group(entry("Rice", calories=130, protein=2.7, carbs=28, fat=0.3))

        scores = [MacroQuality.score(food) for food in (whey, paneer, rice)]
        self.assertEqual(scores, sorted(scores, reverse=True))


class FoodAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        rows = [
            entry("Paratha", "2026-10-14", calories=300, protein=8, carbs=45, fat=10),
            entry("parathas", "2026-10-15", calories=300, protein=8, carbs=45, fat=10),
            entry("Whey protein", "2026-10-15", calories=120, protein=25, carbs=3, fat=1.5),
            entry("Chai", "2026-10-15", calories=90, protein=3, carbs=12, fat=3, added=6),
        ]
        self.analysis = FoodAnalysis(rows, PeriodWindow.month_of(date(2026, 10, 17)))

    def test_counts_group_variants_and_sort_by_frequency(self) -> None:
        first = self.analysis.foods[0]

        self.assertEqual((first.name, first.count, len(first.days)), ("Paratha", 2, 2))
        self.assertEqual(len(self.analysis.foods), 3)

    def test_daily_averages_use_logged_days_only(self) -> None:
        self.assertEqual(self.analysis.days_logged, 2)
        self.assertAlmostEqual(self.analysis.daily_averages()["calories"], 405)

    def test_top_contributors_report_share_of_week(self) -> None:
        top_protein = self.analysis.top_contributors("protein_g")

        self.assertEqual(top_protein[0].name, "Whey protein")
        self.assertAlmostEqual(top_protein[0].share, 25 / 44)
        self.assertEqual(self.analysis.top_contributors("natural_sugar_g"), [])

    def test_prefer_and_avoid_lists(self) -> None:
        self.assertEqual([f.name for f, _ in self.analysis.prefer()], ["Whey protein"])
        self.assertEqual([f.name for f, _ in self.analysis.avoid()], ["Chai"])

    def test_override_replaces_rule_verdict_but_keeps_score(self) -> None:
        overrides = {"paratha": {"verdict": "prefer", "reason": "Homemade with little ghee"}}
        analysis = FoodAnalysis(
            [entry("Paratha", calories=300, protein=6, carbs=45, fat=10)],
            PeriodWindow.month_of(date(2026, 10, 17)),
            overrides,
        )

        verdict = analysis.verdicts["paratha"]
        self.assertEqual((verdict.kind, verdict.source), ("prefer", "override"))
        self.assertEqual(verdict.reason, "Homemade with little ghee")
        self.assertLess(verdict.score, 0)
        self.assertEqual([f.name for f, _ in analysis.prefer()], ["Paratha"])

    def test_daily_totals_cover_every_day_and_mark_unlogged_ones(self) -> None:
        days = self.analysis.daily_totals()

        self.assertEqual(len(days), 31)
        self.assertEqual(days[0], {"date": "2026-10-01", "logged": False})
        october_15 = days[14]
        self.assertTrue(october_15["logged"])
        self.assertEqual(october_15["calories"], 300 + 120 + 90)

    def test_to_dict_is_json_ready(self) -> None:
        payload = self.analysis.to_dict()

        json.dumps(payload)
        self.assertEqual(payload["window"]["days"], 31)
        self.assertEqual(payload["foods"][0]["count"], 2)
        self.assertEqual(payload["foods"][0]["spellings"], {"Paratha": 1, "parathas": 1})
        self.assertEqual(payload["prefer"][0]["verdict"]["source"], "rule")
        self.assertEqual(payload["top_contributors"]["protein_g"][0]["name"], "Whey protein")


if __name__ == "__main__":
    unittest.main()
