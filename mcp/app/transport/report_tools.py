"""MCP-facing report artifacts for Luna Vita."""

import base64
from datetime import date

from mcp.types import BlobResourceContents, EmbeddedResource

from app.core.clock import LocalClock
from app.services.application import ReportService


class CurrentLogPdfTool:
    """Generate the current local day's log as an embedded PDF resource."""

    def __init__(self, reports: ReportService) -> None:
        self.reports = reports

    @staticmethod
    def current_day() -> date:
        return LocalClock.today()

    def generate(self) -> EmbeddedResource:
        day = self.current_day()
        filename = ReportService.filename(day)
        encoded_pdf = base64.b64encode(self.reports.daily_pdf(day)).decode("ascii")
        return EmbeddedResource(
            type="resource",
            resource=BlobResourceContents(
                uri=f"lunavita://reports/daily/{filename}",
                mimeType="application/pdf",
                blob=encoded_pdf,
                _meta={"filename": filename},
            ),
        )
