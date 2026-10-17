"""Validated presentation and service settings for the Streamlit UI."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar
from urllib.parse import urlparse


@dataclass(frozen=True)
class UIConfig:
    """Immutable UI layout and backend-connection settings."""

    UI_ROOT: ClassVar[Path] = Path(__file__).resolve().parent
    LOGO_PATH: ClassVar[Path] = UI_ROOT / "assets" / "lunavita_logo.png"
    FOOD_IMAGE_DISPLAY_SIZE: ClassVar[tuple[int, int]] = (360, 240)
    FOOD_IMAGE_COLUMN_WIDTH: ClassVar[int] = 96
    FOOD_IMAGE_ROW_HEIGHT: ClassVar[int] = 64

    api_url: str
    timeout: float = 10.0

    @classmethod
    def from_env(cls) -> "UIConfig":
        api_url = os.getenv("LUNAVITA_API_URL", "http://localhost:18001").rstrip("/")
        parsed = urlparse(api_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise RuntimeError("LUNAVITA_API_URL must be a valid HTTP(S) URL.")
        return cls(api_url=api_url)
