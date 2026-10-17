"""Tests for MCP report artifacts."""

import base64
import unittest
from datetime import date
from unittest.mock import patch

from app.report_tools import CurrentLogPdfTool


class FakeReportService:
    """Capture report requests without requiring PostgreSQL."""

    def __init__(self) -> None:
        self.requested_day: date | None = None

    def daily_pdf(self, day: date) -> bytes:
        self.requested_day = day
        return b"%PDF-current-log"


class CurrentLogPdfToolTests(unittest.TestCase):
    """Verify that the current report is returned as a PDF resource."""

    def test_generate_returns_current_day_pdf_resource(self) -> None:
        service = FakeReportService()
        tool = CurrentLogPdfTool(service)
        current_day = date(2026, 10, 15)

        with patch.object(tool, "current_day", return_value=current_day):
            result = tool.generate()

        self.assertEqual(service.requested_day, current_day)
        self.assertEqual(result.resource.mimeType, "application/pdf")
        self.assertEqual(
            str(result.resource.uri),
            "lunavita://reports/daily/lunavita-2026-10-15.pdf",
        )
        self.assertEqual(
            base64.b64decode(result.resource.blob),
            b"%PDF-current-log",
        )
        self.assertEqual(
            result.resource.meta,
            {"filename": "lunavita-2026-10-15.pdf"},
        )


if __name__ == "__main__":
    unittest.main()
