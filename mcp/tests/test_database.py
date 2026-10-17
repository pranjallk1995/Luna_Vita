"""Safety checks for the embedded Luna Vita database schema."""

import unittest

from app.database import SCHEMA_SQL


class DatabaseSchemaTests(unittest.TestCase):
    """Verify the embedded schema remains complete and data-free."""

    def test_schema_creates_every_application_table_idempotently(self) -> None:
        for table in (
            "food_entries",
            "daily_logs",
            "health_measurements",
            "daily_recommendations",
            "food_verdicts",
            "analysis_range",
        ):
            with self.subTest(table=table):
                self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", SCHEMA_SQL)

    def test_schema_contains_no_seeded_personal_data(self) -> None:
        normalized = SCHEMA_SQL.upper()

        self.assertNotIn("INSERT INTO", normalized)
        self.assertNotIn("COPY ", normalized)


if __name__ == "__main__":
    unittest.main()
