"""Tests for Luna Vita food-log presentation ordering."""

import unittest

from app import FoodLogView


class FoodLogViewTests(unittest.TestCase):
    """Verify daily rows are ordered by their displayed IST time."""

    def test_rows_are_sorted_by_ist_time_with_label_only_rows_last(self) -> None:
        rows = [
            {"id": 3, "consumed_at": "2026-10-15T00:00:00+05:30", "time_label": "Evening"},
            {"id": 2, "consumed_at": "2026-10-15T07:30:00+00:00", "time_label": None},
            {"id": 1, "consumed_at": "2026-10-15T08:00:00+05:30", "time_label": None},
        ]

        ordered = FoodLogView.rows_by_time(rows)

        self.assertEqual([row["id"] for row in ordered], [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
