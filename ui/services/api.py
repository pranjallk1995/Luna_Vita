"""UI-facing client for Luna Vita's HTTP routes."""

from datetime import date
from typing import Any

import httpx

from config import UIConfig


class LunaVitaAPI:
    """Keep HTTP details out of Streamlit view classes."""

    def __init__(self, config: UIConfig) -> None:
        self.base_url = config.api_url
        self.timeout = config.timeout

    def send(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        response = httpx.request(
            method, f"{self.base_url}{path}", timeout=self.timeout, **kwargs
        )
        response.raise_for_status()
        return response

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self.send(method, path, **kwargs)
        return response.json() if response.content else None

    def summary(self, day: date) -> dict[str, Any]:
        return self.request("GET", f"/api/summary/{day.isoformat()}")

    def recommendations(self) -> dict[str, Any] | None:
        return self.request("GET", "/api/recommendations")

    def food(self, day: date) -> list[dict[str, Any]]:
        return self.request(
            "GET",
            "/api/food",
            params={"start": day.isoformat(), "end": day.isoformat(), "limit": 500},
        )

    def analysis(self, day: date) -> dict[str, Any]:
        """The Monthly tab's analysis: the saved range, or the month of ``day``."""
        return self.request(
            "GET", "/api/analysis/displayed", params={"day": day.isoformat()}
        )

    def set_analysis_range(self, start: date, end: date) -> dict[str, Any]:
        """Save the Monthly tab's date range (shared with the assistant)."""
        return self.request(
            "PUT",
            "/api/analysis/range",
            json={"start_date": start.isoformat(), "end_date": end.isoformat()},
        )

    def reset_analysis_range(self) -> dict[str, Any]:
        """Return the Monthly tab to the calendar month of the selected day."""
        return self.request("DELETE", "/api/analysis/range")

    def create_food(self, payload: dict[str, Any]) -> None:
        self.request("POST", "/api/food", json=payload)

    def update_food(self, entry_id: int, payload: dict[str, Any]) -> None:
        self.request("PUT", f"/api/food/{entry_id}", json=payload)

    def delete_food(self, entry_id: int) -> None:
        self.request("DELETE", f"/api/food/{entry_id}")

    def measurements(self) -> list[dict[str, Any]]:
        return self.request("GET", "/api/measurements", params={"limit": 500})

    def body_composition(self, start: date, end: date) -> dict[str, Any]:
        """Weight and body fat % (recorded or estimated) for each weigh-in in the range."""
        return self.request(
            "GET",
            "/api/body-composition",
            params={"start": start.isoformat(), "end": end.isoformat()},
        )

    def create_measurement(self, payload: dict[str, Any]) -> None:
        self.request("POST", "/api/measurements", json=payload)

    def create_measurements(self, payloads: list[dict[str, Any]]) -> None:
        self.request("POST", "/api/measurements/batch", json={"measurements": payloads})

    def update_measurement(self, entry_id: int, payload: dict[str, Any]) -> None:
        self.request("PUT", f"/api/measurements/{entry_id}", json=payload)

    def delete_measurement(self, entry_id: int) -> None:
        self.request("DELETE", f"/api/measurements/{entry_id}")

    def workouts(self, start: date, end: date) -> list[dict[str, Any]]:
        """Done/skipped workout records for the inclusive range; unrecorded days are absent."""
        return self.request(
            "GET",
            "/api/workouts",
            params={"start": start.isoformat(), "end": end.isoformat()},
        )

    def record_workout(self, day: date, done: bool) -> None:
        self.request("PUT", f"/api/workouts/{day.isoformat()}", json={"done": done})

    def delete_workout(self, day: date) -> None:
        self.request("DELETE", f"/api/workouts/{day.isoformat()}")

    def report(self, day: date) -> bytes:
        return self.send("GET", f"/api/reports/daily/{day.isoformat()}").content
