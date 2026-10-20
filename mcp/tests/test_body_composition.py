"""Tests for weight / body fat series shaping and the body fat estimate."""

import unittest

from datetime import date

from app.services.body_composition import BodyComposition
from app.core.errors import NotFoundError
from app.services.application import BodyCompositionService


def row(metric, value, at="2026-10-18T08:46:00+05:30", label="morning"):
    return {"metric": metric, "value": value, "measured_at": at, "time_label": label}


class BodyCompositionTests(unittest.TestCase):
    def test_estimate_uses_fat_free_mass_hydration(self):
        # 41.6 kg water / 0.732 = 56.83 kg fat-free mass of 73.45 kg -> 22.6% fat
        self.assertEqual(BodyComposition.estimate_body_fat(73.45, 41.6), 22.6)
        self.assertIsNone(BodyComposition.estimate_body_fat(50, 45))

    def test_estimates_body_fat_from_same_weigh_in(self):
        series = BodyComposition.series([row("weight", 73.45), row("total_body_water", 41.6)])
        self.assertEqual(series["weight"][0]["value"], 73.45)
        self.assertEqual(series["body_fat"], [{
            "measured_at": "2026-10-18T08:46:00+05:30", "value": 22.6,
            "time_label": "morning", "estimated": True,
        }])

    def test_recorded_body_fat_wins_over_estimate(self):
        series = BodyComposition.series([
            row("weight", 73.45), row("total_body_water", 41.6), row("Body_Fat_Percent", 21.0),
        ])
        self.assertEqual([(r["value"], r["estimated"]) for r in series["body_fat"]], [(21.0, False)])

    def test_water_without_matching_weight_is_not_estimated(self):
        series = BodyComposition.series([
            row("weight", 73.45), row("total_body_water", 41.6, at="2026-10-18T20:00:00+05:30"),
        ])
        self.assertEqual(series["body_fat"], [])

    def test_duplicate_readings_collapse_and_sort_by_time(self):
        series = BodyComposition.series([
            row("weight", 73.0, at="2026-10-17T20:00:00+05:30"),
            row("weight", 72.0, at="2026-10-16T08:00:00+05:30"),
            row("weight", 72.0, at="2026-10-16T08:00:00+05:30"),
        ])
        self.assertEqual([r["value"] for r in series["weight"]], [72.0, 73.0])


class FakeMeasurements:
    def list_between(self, start, end, metrics):
        self.metrics = metrics
        return [row("weight", 73.45), row("total_body_water", 41.6)]


class FakeRecommendations:
    def __init__(self, target=None):
        self.target = target

    def body_fat_target(self):
        return self.target

    def update_body_fat_target(self, percent):
        return None if self.target is None else {"body_fat_target_percent": percent}


class BodyCompositionServiceTests(unittest.TestCase):
    def test_series_includes_target_with_default(self):
        service = BodyCompositionService(FakeMeasurements(), FakeRecommendations())
        result = service.series(date(2026, 10, 1), date(2026, 10, 31))
        self.assertEqual(result["body_fat_target_percent"], 18.0)
        self.assertEqual(result["body_fat"][0]["value"], 22.6)

    def test_stored_target_is_used_and_updatable(self):
        service = BodyCompositionService(FakeMeasurements(), FakeRecommendations(16.5))
        self.assertEqual(service.fat_target(), 16.5)
        self.assertEqual(service.set_fat_target(15)["body_fat_target_percent"], 15)

    def test_setting_target_requires_recommendations(self):
        service = BodyCompositionService(FakeMeasurements(), FakeRecommendations())
        with self.assertRaises(NotFoundError):
            service.set_fat_target(15)

    def test_rejects_reversed_range(self):
        service = BodyCompositionService(FakeMeasurements(), FakeRecommendations())
        with self.assertRaises(ValueError):
            service.series(date(2026, 10, 31), date(2026, 10, 1))


if __name__ == "__main__":
    unittest.main()
