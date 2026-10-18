"""Tests for the weight / body fat bar card in the monthly overview."""

import unittest
from datetime import date

from body_trends import BodyTrendChart, Reading

WEIGHT = [
    {"measured_at": "2026-10-15T11:04:00+05:30", "value": 73.65, "time_label": "Morning"},
    {"measured_at": "2026-10-15T23:59:00+05:30", "value": 74.15, "time_label": "Night"},
    {"measured_at": "2026-10-18T08:46:00+05:30", "value": 73.45, "time_label": ""},
]
FAT = [
    {"measured_at": "2026-10-15T11:04:00+05:30", "value": 21.7, "time_label": "Morning", "estimated": True},
    {"measured_at": "2026-10-18T08:46:00+05:30", "value": 22.6, "time_label": "morning", "estimated": True},
]
START, END = date(2026, 10, 1), date(2026, 10, 31)


class BodyTrendChartTests(unittest.TestCase):
    def html(self, weight=WEIGHT, fat=FAT, target=18.0):
        return BodyTrendChart.html(Reading.parse(weight), Reading.parse(fat), START, END, target)

    def test_period_comes_from_label_or_local_hour(self):
        morning, night, unlabeled = Reading.parse(WEIGHT)
        self.assertEqual((morning.period, night.period, unlabeled.period), ("Morning", "Night", "Morning"))

    def test_morning_and_night_bars_share_a_day(self):
        html = self.html()
        self.assertEqual(html.count('class="body-trend-bar morning"'), 4)  # 2 weight + 2 fat
        self.assertEqual(html.count('class="body-trend-bar night"'), 1)
        self.assertIn("15 Oct · Morning 73.65 kg · Night 74.15 kg", html)

    def test_weight_bars_rise_from_a_whole_kg_floor(self):
        self.assertEqual(BodyTrendChart.weight_range(Reading.parse(WEIGHT)), (72, 75))
        self.assertIn("Bars from 72 kg", self.html())

    def test_fat_target_line_and_estimate_marking(self):
        html = self.html(target=18.0)
        self.assertIn("Target 18.0%", html)
        self.assertEqual(html.count('class="nutrient-trend-target"'), 1)
        self.assertIn("22.6% (est.)", html)

    def test_one_slot_per_day_in_window(self):
        self.assertEqual(self.html().count('class="nutrient-trend-day"'), 62)  # 31 days x 2 charts

    def test_no_card_without_data(self):
        self.assertEqual(self.html(weight=[], fat=[]), "")

    def test_empty_section_is_left_out(self):
        html = self.html(fat=[])
        self.assertIn("Weight", html)
        self.assertNotIn("Body fat", html)


if __name__ == "__main__":
    unittest.main()
