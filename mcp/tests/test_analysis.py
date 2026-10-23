"""Tests for the period food analysis."""

import unittest
from datetime import date

import json

from app.services.analysis import (
    DuplicateFinder,
    FoodAnalysis,
    FoodCatalog,
    FoodGroup,
    FoodName,
    MacroQuality,
    PeriodWindow,
)


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


class FoodCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = FoodCatalog(
            {"on gold standard whey": "Whey protein"},
            {"Paratha": 5, "parathas": 1, "Whey protein": 3, "ON Gold Standard Whey": 2},
        )

    def test_spellings_resolve_to_the_most_used_existing_name(self) -> None:
        self.assertEqual(self.catalog.canonical("PARATHAS "), "Paratha")
        self.assertEqual(self.catalog.canonical("  Dosa "), "Dosa")

    def test_aliases_win_over_history(self) -> None:
        self.assertEqual(self.catalog.canonical("on gold standard whey"), "Whey protein")
        self.assertEqual(self.catalog.key("ON Gold Standard Whey"), "whey protein")

    def test_names_merge_spellings_and_aliases(self) -> None:
        names = self.catalog.names()
        self.assertEqual([food["name"] for food in names], ["Paratha", "Whey protein"])
        self.assertEqual(names[0]["aliases"], ["parathas"])
        self.assertEqual(names[1]["entries"], 5)
        self.assertEqual(
            names[1]["aliases"], ["ON Gold Standard Whey", "on gold standard whey"]
        )

    def test_resolve_reports_where_the_canonical_name_came_from(self) -> None:
        alias = self.catalog.resolve("ON gold standard whey")
        self.assertEqual((alias["canonical_name"], alias["source"], alias["entries"]),
                         ("Whey protein", "alias", 5))
        self.assertEqual(self.catalog.resolve("parathas")["source"], "existing")
        self.assertEqual(self.catalog.resolve(" Dosa ")["canonical_name"], "Dosa")
        self.assertEqual(self.catalog.resolve("Dosa")["source"], "new")

    def test_analysis_groups_aliased_entries_under_the_canonical_name(self) -> None:
        rows = [entry("Whey protein", protein=24), entry("ON Gold Standard Whey", protein=24)]
        analysis = FoodAnalysis(rows, PeriodWindow.month_of(date(2026, 10, 17)), catalog=self.catalog)
        self.assertEqual(len(analysis.foods), 1)
        self.assertEqual(analysis.foods[0].name, "Whey protein")
        self.assertEqual(analysis.foods[0].count, 2)


class DuplicateFinderTests(unittest.TestCase):
    @staticmethod
    def food(name, entries):
        return {"name": name, "entries": entries, "aliases": []}

    def test_typos_and_contained_names_are_suggested_most_similar_first(self) -> None:
        foods = [
            self.food("Chicken breast", 6),
            self.food("Chiken breast", 1),
            self.food("Whey protein", 4),
            self.food("Whey", 2),
            self.food("Banana", 3),
        ]

        pairs = DuplicateFinder.suggest(foods, limit=10)

        self.assertEqual([(p["keep"], p["merge"], p["reason"]) for p in pairs], [
            ("Chicken breast", "Chiken breast", "similar spelling"),
            ("Whey protein", "Whey", "one name contains the other"),
        ])
        self.assertEqual(pairs[1]["entries"], {"Whey protein": 4, "Whey": 2})

    def test_unrelated_foods_and_the_limit_are_respected(self) -> None:
        foods = [self.food("Banana", 1), self.food("Paneer", 1), self.food("Rice", 1)]
        self.assertEqual(DuplicateFinder.suggest(foods, limit=10), [])
        pairs = [self.food("Egg", 1), self.food("Eggs boiled", 1), self.food("Egg curry", 1)]
        self.assertEqual(len(DuplicateFinder.suggest(pairs, limit=1)), 1)


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

    def test_gallery_image_is_the_latest_entry_image(self) -> None:
        visia = "https://visia.example/api/public/images/"
        rows = [
            {**entry("Paratha"), "image_url": f"{visia}aaa"},
            {**entry("Paratha"), "image_url": f"{visia}placeholder"},
            entry("Paratha"),
            entry("Whey protein"),
        ]
        analysis = FoodAnalysis(rows, PeriodWindow.month_of(date(2026, 10, 17)))

        images = {food["name"]: food["image_url"] for food in analysis.to_dict()["foods"]}
        self.assertEqual(images, {"Paratha": f"{visia}placeholder", "Whey protein": None})

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
