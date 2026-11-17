"""Daily water intake: the model's rules, the service's totals and goal, and the MCP tools."""

import unittest
from datetime import date, datetime, timedelta
from typing import Any
from unittest import mock

from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from app.core.clock import LocalClock
from app.core.models import WaterEntryCreate, WaterGoalUpdate
from app.services.application import WaterService
from app.transport.mcp_tools import LunaVitaMCPTools

DAY = date(2026, 11, 16)


class FakeWater:
    """Water rows in memory, serialized as the real repository returns them."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.stored_goal: int | None = None

    def add(self, entry: WaterEntryCreate) -> dict[str, Any]:
        row = {"id": len(self.rows) + 1, "drank_on": entry.drank_on.isoformat(),
               "drank_at": entry.drank_at.isoformat() if entry.drank_at else None,
               "amount_ml": entry.amount_ml, "notes": entry.notes}
        self.rows.append(row)
        return row

    def list_between(self, start: date, end: date) -> list[dict[str, Any]]:
        return [row for row in self.rows if start.isoformat() <= row["drank_on"] <= end.isoformat()]

    def daily_totals(self, start: date, end: date) -> list[dict[str, Any]]:
        days: dict[str, dict[str, Any]] = {}
        for row in self.list_between(start, end):
            day = days.setdefault(row["drank_on"], {"drank_on": row["drank_on"], "total_ml": 0, "drinks": 0})
            day["total_ml"] += row["amount_ml"]
            day["drinks"] += 1
        return sorted(days.values(), key=lambda day: day["drank_on"])

    def delete(self, entry_id: int) -> bool:
        before = len(self.rows)
        self.rows = [row for row in self.rows if row["id"] != entry_id]
        return len(self.rows) < before

    def goal(self) -> int | None:
        return self.stored_goal

    def set_goal(self, goal_ml: int) -> dict[str, Any]:
        self.stored_goal = goal_ml
        return {"goal_ml": goal_ml}


class WaterModelTests(unittest.TestCase):
    def test_a_drink_needs_a_sensible_amount(self) -> None:
        for amount in (0, -250, 5_001):
            with self.assertRaises(ValidationError):
                WaterEntryCreate(amount_ml=amount)
        with self.assertRaises(ValidationError):
            WaterGoalUpdate(goal_ml=100)

    def test_the_day_comes_from_the_time_or_today_and_must_match_it(self) -> None:
        self.assertEqual(WaterEntryCreate(amount_ml=250).drank_on, LocalClock.today())
        timed = WaterEntryCreate(amount_ml=250, drank_at="2026-11-15T22:30:00")
        self.assertEqual(timed.drank_on, date(2026, 11, 15))
        self.assertEqual(timed.drank_at.utcoffset(), timedelta(hours=5, minutes=30))
        with self.assertRaises(ValidationError):
            WaterEntryCreate(amount_ml=250, drank_on=DAY, drank_at="2026-11-15T22:30:00")


class WaterServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = FakeWater()
        self.water = WaterService(self.repository)

    def test_each_drink_adds_to_the_day_against_the_goal(self) -> None:
        self.water.record(WaterEntryCreate(amount_ml=500, drank_on=DAY))
        result = self.water.record(WaterEntryCreate(amount_ml=250, drank_on=DAY, notes="with lunch"))
        self.assertEqual(result["entry"]["notes"], "with lunch")
        self.assertEqual((result["total_ml"], result["goal_ml"], result["remaining_ml"], result["percent"]),
                         (750, 3_000, 2_250, 25))
        self.assertEqual(len(result["entries"]), 2)

    def test_a_drink_today_without_a_time_is_now_and_a_past_one_stays_untimed(self) -> None:
        today = self.water.record(WaterEntryCreate(amount_ml=250))["entry"]
        self.assertEqual(datetime.fromisoformat(today["drank_at"]).date(), LocalClock.today())
        past = self.water.record(WaterEntryCreate(amount_ml=250, drank_on=DAY - timedelta(days=30)))["entry"]
        self.assertIsNone(past["drank_at"])

    def test_the_goal_is_3000_ml_until_set_and_nothing_is_left_once_reached(self) -> None:
        self.assertEqual(self.water.goal(), 3_000)
        self.water.set_goal(2_000)
        self.water.record(WaterEntryCreate(amount_ml=2_500, drank_on=DAY))
        day = self.water.day(DAY)
        self.assertEqual((day["goal_ml"], day["remaining_ml"], day["percent"]), (2_000, 0, 125))

    def test_history_fills_empty_days_and_averages_only_logged_ones(self) -> None:
        self.water.set_goal(2_000)
        self.water.record(WaterEntryCreate(amount_ml=2_000, drank_on=DAY))
        self.water.record(WaterEntryCreate(amount_ml=1_000, drank_on=DAY - timedelta(days=2)))
        history = self.water.history(DAY - timedelta(days=2), DAY)
        self.assertEqual([(d["date"], d["total_ml"], d["reached"]) for d in history["days"]],
                         [("2026-11-14", 1_000, False), ("2026-11-15", 0, False), ("2026-11-16", 2_000, True)])
        self.assertEqual((history["days_logged"], history["days_reached"], history["average_ml"]), (2, 1, 1_500))
        with self.assertRaises(ValueError):
            self.water.history(DAY, DAY - timedelta(days=1))

    def test_a_drink_can_be_deleted(self) -> None:
        entry = self.water.record(WaterEntryCreate(amount_ml=250, drank_on=DAY))["entry"]
        self.assertTrue(self.water.remove(entry["id"]))
        self.assertFalse(self.water.remove(entry["id"]))
        self.assertEqual(self.water.day(DAY)["total_ml"], 0)


class WaterToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.water = WaterService(FakeWater())
        service = mock.MagicMock()
        service.water = self.water
        self.server = FastMCP("test")
        LunaVitaMCPTools(self.server, service)

    def tool(self, name: str):
        return self.server._tool_manager.get_tool(name).fn

    def test_an_assistant_logs_water_and_reads_the_day(self) -> None:
        logged = self.tool("log_water")(amount_ml=500, day="2026-11-16")
        self.assertEqual(logged["total_ml"], 500)
        self.assertEqual(self.tool("get_water_intake")(day="2026-11-16")["remaining_ml"], 2_500)
        self.assertEqual(self.tool("set_water_goal")(goal_ml=4_000)["goal_ml"], 4_000)
        with self.assertRaises(ValidationError):
            self.tool("set_water_goal")(goal_ml=50)
        self.assertEqual(self.tool("delete_water_entry")(entry_id=logged["entry"]["id"]), {"deleted": 1})
        with self.assertRaises(ValueError):
            self.tool("delete_water_entry")(entry_id=99)
        history = self.tool("get_water_history")(start_date="2026-11-10", end_date="2026-11-16")
        self.assertEqual(len(history["days"]), 7)


if __name__ == "__main__":
    unittest.main()
