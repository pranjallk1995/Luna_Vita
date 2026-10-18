"""Tests for the per-day nutrient charts in the monthly overview."""

import unittest

from domain.nutrition import NUTRIENTS
from views.monthly_view import DailyTrendChart

CALORIES = next(n for n in NUTRIENTS if n.key == "calories")


class DailyTrendChartTests(unittest.TestCase):
    DAYS = [
        {"date": "2026-10-01", "logged": True, "calories": 2600.0},
        {"date": "2026-10-02", "logged": False},
        {"date": "2026-10-03", "logged": True, "calories": 1200.0},
    ]

    def test_bars_only_for_logged_days_with_tooltips(self) -> None:
        html = DailyTrendChart.html(CALORIES, self.DAYS, average=1900, target=2400)

        self.assertEqual(html.count('class="nutrient-trend-bar"'), 2)
        self.assertEqual(html.count('class="nutrient-trend-hit"'), 3)
        self.assertIn("<title>1 Oct · 2,600 kcal</title>", html)
        self.assertIn("<title>2 Oct · not logged</title>", html)
        self.assertIn('class="nutrient-trend-target"', html)

    def test_chart_uses_the_same_color_classes_as_its_card(self) -> None:
        over_target = DailyTrendChart.html(CALORIES, self.DAYS, average=2500, target=2400)

        self.assertIn('class="nutrition-card nutrient-trend calories danger"', over_target)

    def test_axis_labels_first_middle_and_last_day(self) -> None:
        html = DailyTrendChart.html(CALORIES, self.DAYS, average=1900, target=2400)

        self.assertIn("<span>1 Oct</span><span>2 Oct</span><span>3 Oct</span>", html)


if __name__ == "__main__":
    unittest.main()
