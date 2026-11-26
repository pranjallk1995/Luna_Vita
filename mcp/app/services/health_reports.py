"""Health reports from Luna Lexia: each result against its range, and each test across reports."""

import re
from typing import Any

from app.integrations.lexia import LexiaHealthReports

STATUSES = ("low", "high", "abnormal", "normal", "unknown")
# Text results a lab prints for a test that found nothing.
NORMAL_TEXT = re.compile(r"^(negative|nil|absent|not detected|normal|clear|non[- ]?reactive)$", re.IGNORECASE)


def test_key(name: str | None) -> str:
    """A test name without case, spacing, punctuation, or a plural "s"; matches Lexia's own merging."""
    return re.sub(r"[^0-9a-z]+", "", (name or "").casefold()).removesuffix("s")


def status_of(result: dict[str, Any]) -> str:
    """low, high, abnormal, normal, or unknown: the printed flag, else the value against its range.

    A text result (Negative, Yellow) is normal when it matches the printed range, or reads
    as a finding of nothing; any other text against a text range is abnormal.
    """
    flag = result.get("flag")
    if flag in STATUSES:
        return flag
    value, low, high = result.get("value"), result.get("reference_low"), result.get("reference_high")
    if value is not None and (low is not None or high is not None):
        if low is not None and value < low:
            return "low"
        if high is not None and value > high:
            return "high"
        return "normal"
    text, expected = (result.get("value_text") or "").strip(), (result.get("reference_range") or "").strip()
    if text and expected and not any(character.isdigit() for character in expected):
        return "normal" if text.casefold() == expected.casefold() else "abnormal"
    if text and NORMAL_TEXT.match(text):
        return "normal"
    return "unknown"


class HealthReportService:
    """The person's lab reports, read live from Luna Lexia each time."""

    def __init__(self, lexia: LexiaHealthReports) -> None:
        self.lexia = lexia

    @property
    def enabled(self) -> bool:
        return self.lexia.enabled

    def reports(self, test_name: str | None = None, only_out_of_range: bool = False) -> dict[str, Any]:
        """Every report, newest first, each result with its status and its earlier values."""
        reports = self.lexia.reports()
        history = self.history(reports)
        wanted = test_key(test_name) if test_name else ""
        for report in reports:
            for result in report["results"]:
                result["status"] = status_of(result)
                result["history"] = [
                    point for point in history.get(test_key(result["test_name"]), [])
                    if point["document_id"] != report["document_id"] and (point["date"] or "") < (report["date"] or "")
                ]
            counts = {status: 0 for status in STATUSES}
            for result in report["results"]:
                counts[result["status"]] += 1
            report["counts"] = {"tests": len(report["results"]), **counts, "out_of_range": counts["low"] + counts["high"] + counts["abnormal"]}
            if wanted or only_out_of_range:
                report["results"] = [
                    result for result in report["results"]
                    if (not wanted or wanted in test_key(result["test_name"]))
                    and (not only_out_of_range or result["status"] in ("low", "high", "abnormal"))
                ]
        return {"reports": reports, "count": len(reports)}

    @staticmethod
    def history(reports: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        """Every dated value of each test, oldest first: from each report, and earlier values they print."""
        points: dict[str, dict[tuple[str, Any], dict[str, Any]]] = {}
        for report in reports:
            for result in report["results"]:
                key = test_key(result["test_name"])
                if result.get("value") is not None and report["date"]:
                    points.setdefault(key, {})[(report["date"], result["value"])] = {
                        "date": report["date"], "value": result["value"], "unit": result.get("unit"),
                        "document_id": report["document_id"], "status": status_of(result),
                    }
                if result.get("previous_value") is not None and result.get("previous_date"):
                    points.setdefault(key, {}).setdefault((result["previous_date"], result["previous_value"]), {
                        "date": result["previous_date"], "value": result["previous_value"], "unit": result.get("unit"),
                        "document_id": None, "status": None,
                    })
        return {key: sorted(found.values(), key=lambda point: point["date"]) for key, found in points.items()}

    def trend(self, test_name: str) -> dict[str, Any]:
        """One test's values across every report, oldest first, with the latest range."""
        key = test_key(test_name)
        if not key:
            raise ValueError("Name a test, such as LDL cholesterol or HbA1c.")
        reports = self.lexia.reports()
        names = {test_key(result["test_name"]): result["test_name"] for report in reports for result in report["results"]}
        matches = [name for name in names if name == key] or [name for name in names if key in name]
        if not matches:
            raise ValueError(f"No health report has a test named like {test_name!r}.")
        chosen = min(matches, key=len)
        latest = next(
            (result for report in reports for result in report["results"] if test_key(result["test_name"]) == chosen), {}
        )
        return {
            "test_name": names[chosen],
            "unit": latest.get("unit"),
            "reference_range": latest.get("reference_range"),
            "reference_low": latest.get("reference_low"),
            "reference_high": latest.get("reference_high"),
            "points": self.history(reports).get(chosen, []),
            "other_matches": sorted(names[name] for name in matches if name != chosen),
        }

    def file(self, document_id: str) -> tuple[bytes, str, str]:
        return self.lexia.file(document_id)
