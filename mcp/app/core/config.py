"""Validated runtime configuration for the Luna Vita backend."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar
from urllib.parse import urlparse
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class AppConfig:
    """Immutable backend settings loaded from environment variables."""

    ASSET_DIR: ClassVar[Path] = Path(__file__).resolve().parent.parent / "assets"
    # Calendar days, "today", and logged times all resolve in this timezone.
    TIMEZONE: ClassVar[ZoneInfo] = ZoneInfo("Asia/Kolkata")
    MAX_PAGE_SIZE: ClassVar[int] = 500
    MAX_WINDOW_DAYS: ClassVar[int] = 366
    MAX_SERIES_DAYS: ClassVar[int] = 366

    database_url: str
    visia_api_url: str = "http://luna-visia-mcp:8000"
    # The food placeholder image stored in Luna Visia, shown when no Visia image fits a food.
    # Set LUNAVITA_PLACEHOLDER_IMAGE_ID to its ID once it is stored.
    placeholder_image_id: str = "b7adf6ae-30b3-4750-8381-5dc6ab393de6"
    host: str = "0.0.0.0"
    port: int = 8000
    # Public HTTPS origin of this MCP server, used for icon URLs ("" = embedded icons only).
    mcp_public_url: str = ""

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Build and validate backend configuration from the environment."""
        database_url = os.getenv("DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeError("DATABASE_URL is required.")
        visia_api_url = os.getenv("LUNAVISIA_API_URL", cls.visia_api_url).strip().rstrip("/")
        parsed = urlparse(visia_api_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise RuntimeError("LUNAVISIA_API_URL must be a valid HTTP(S) URL.")
        placeholder_image_id = os.getenv(
            "LUNAVITA_PLACEHOLDER_IMAGE_ID", cls.placeholder_image_id
        ).strip()
        if not placeholder_image_id:
            raise RuntimeError("LUNAVITA_PLACEHOLDER_IMAGE_ID cannot be blank.")
        mcp_public_url = os.getenv("MCP_PUBLIC_URL", "").strip().rstrip("/")
        if mcp_public_url:
            parsed_public_url = urlparse(mcp_public_url)
            if parsed_public_url.scheme != "https" or not parsed_public_url.netloc:
                raise RuntimeError("MCP_PUBLIC_URL must be a valid HTTPS URL.")
        return cls(
            mcp_public_url=mcp_public_url,
            database_url=database_url,
            visia_api_url=visia_api_url,
            placeholder_image_id=placeholder_image_id,
        )
