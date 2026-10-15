"""MCP-facing report artifacts for Luna Vita."""

import base64
from datetime import date, datetime
from zoneinfo import ZoneInfo

from mcp.types import BlobResourceContents, EmbeddedResource

from .services import LunaVitaService


class CurrentLogPdfTool:
    """Generate the current local day's log as an embedded PDF resource."""

    LOCAL_TIMEZONE = ZoneInfo("Asia/Kolkata")

    def __init__(self, service: LunaVitaService) -> None:
        self.service = service

    @classmethod
    def current_day(cls) -> date:
        return datetime.now(cls.LOCAL_TIMEZONE).date()

    def generate(self) -> EmbeddedResource:
        day = self.current_day()
        filename = f"lunavita-{day.isoformat()}.pdf"
        encoded_pdf = base64.b64encode(self.service.daily_report(day)).decode("ascii")
        return EmbeddedResource(
            type="resource",
            resource=BlobResourceContents(
                uri=f"lunavita://reports/daily/{filename}",
                mimeType="application/pdf",
                blob=encoded_pdf,
                _meta={"filename": filename},
            ),
        )
