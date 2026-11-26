"""Read the person's health reports from Luna Lexia, where their lab report PDFs are stored.

Lexia reads each lab report into its ``health_report`` schema: the lab, the dates, and
every test with its result, unit, and reference range. Vita reads them over Luna
Sentia's private network with Lexia's private token, naming the person whose reports
to read, the same way Luna Fiora reads Lexia; nothing is copied into Vita's database.
"""

import re
from typing import Any

import httpx

from app.core import tenancy
from app.core.errors import NotFoundError

DOCUMENT_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)


class LexiaUnavailableError(RuntimeError):
    """Raised when Luna Lexia cannot be reached or refuses Vita's token."""


class LexiaHealthReports:
    """The ``health_report`` documents one person keeps in Luna Lexia, and their files."""

    DOC_TYPE = "health_report"
    # What Vita keeps of each Lexia record.
    FIELDS = ("document_id", "name", "title", "summary", "document_date", "issuer", "review_flags", "public_url", "updated_at")

    def __init__(self, api_url: str, api_token: str, timeout: float = 15.0, transport: httpx.BaseTransport | None = None) -> None:
        self.api_url = api_url.rstrip("/")
        self.api_token = api_token
        self.timeout = timeout
        self.transport = transport

    @property
    def enabled(self) -> bool:
        return bool(self.api_url and self.api_token)

    def _get(self, path: str, **params: Any) -> httpx.Response:
        if not self.enabled:
            raise LexiaUnavailableError(
                "Health reports are off: set LUNALEXIA_API_TOKEN in Luna Vita to the same value as in Luna Lexia."
            )
        try:
            with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
                response = client.get(
                    f"{self.api_url}{path}",
                    params=params or None,
                    headers={"Authorization": f"Bearer {self.api_token}", tenancy.USER_HEADER: tenancy.current()},
                )
        except httpx.TransportError as error:
            raise LexiaUnavailableError(f"Luna Lexia is unavailable, so health reports cannot be read: {error}") from error
        if response.status_code == 401:
            raise LexiaUnavailableError("Luna Lexia rejected Luna Vita's LUNALEXIA_API_TOKEN; set the same value in both apps.")
        if response.status_code >= 400:
            raise LexiaUnavailableError(f"Luna Lexia could not read health reports (HTTP {response.status_code}).")
        return response

    def reports(self) -> list[dict[str, Any]]:
        """Every visible health report, with the results Lexia extracted, newest first."""
        try:
            documents = self._get("/api/metadata", doc_type=self.DOC_TYPE).json()["documents"]
        except (ValueError, KeyError) as error:
            raise LexiaUnavailableError(f"Luna Lexia answered with an unreadable document list: {error}") from error
        reports = [self.report(document) for document in documents if document.get("doc_type") == self.DOC_TYPE]
        return sorted(reports, key=lambda report: (report["date"] or "", report["updated_at"] or ""), reverse=True)

    @classmethod
    def report(cls, document: dict[str, Any]) -> dict[str, Any]:
        details = document.get("extracted") or {}
        report = {key: document.get(key) for key in cls.FIELDS}
        report["document_id"] = str(report["document_id"])
        report["review_flags"] = report["review_flags"] or []
        report["date"] = details.get("collection_date") or details.get("report_date") or document.get("document_date")
        for key in ("lab_name", "patient_name", "patient_age", "patient_gender", "package_name", "collection_date",
                    "report_date", "report_status", "referred_by", "sample_types"):
            report[key] = details.get(key)
        report["lab_name"] = report["lab_name"] or document.get("issuer")
        report["pending_tests"] = details.get("pending_tests") or []
        report["results"] = [dict(result) for result in details.get("results") or [] if result.get("test_name")]
        return report

    def lab_tests(self) -> dict[str, str]:
        """What each lab test measures, by test key, as Lexia explains them; empty when it cannot say.

        The explanations only add to the reports, so a Lexia without them (before 2.4.0),
        or one that fails to answer, leaves them out instead of failing the reports.
        """
        try:
            response = self._get("/api/lab-tests")
            tests = response.json().get("tests") or {}
        except (LexiaUnavailableError, ValueError, AttributeError):
            return {}
        return {
            key: entry["about"]
            for key, entry in tests.items()
            if isinstance(entry, dict) and isinstance(entry.get("about"), str) and entry["about"].strip()
        }

    def file(self, document_id: str) -> tuple[bytes, str, str]:
        """The original PDF of one of this person's health reports: bytes, media type, and filename."""
        if not DOCUMENT_ID.fullmatch(document_id or ""):
            raise NotFoundError("No such health report.")
        report = next((report for report in self.reports() if report["document_id"].lower() == document_id.lower()), None)
        if report is None:
            raise NotFoundError("No such health report in Luna Lexia.")
        response = self._get(f"/api/public/documents/{report['document_id']}")
        return response.content, response.headers.get("content-type", "application/pdf"), report["name"] or "health-report.pdf"
