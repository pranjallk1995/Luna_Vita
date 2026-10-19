"""Validated runtime configuration for the Luna Vita backend."""

import os
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class AppConfig:
    """Immutable backend settings loaded from environment variables."""

    database_url: str
    visia_api_url: str = "http://luna-visia-mcp:8000"
    # The "Add something relevant in Luna Visia" image stored in Luna Visia.
    placeholder_image_id: str = "b7adf6ae-30b3-4750-8381-5dc6ab393de6"
    host: str = "0.0.0.0"
    port: int = 8000

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
        return cls(
            database_url=database_url,
            visia_api_url=visia_api_url,
            placeholder_image_id=placeholder_image_id,
        )
