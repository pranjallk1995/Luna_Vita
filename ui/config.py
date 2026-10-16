"""Environment-backed configuration for the Luna Vita UI."""

import os
import base64
import re
import unicodedata
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import ClassVar

import httpx
import streamlit as st
from PIL import Image, ImageOps


@dataclass(frozen=True)
class UIConfig:
    UI_ROOT: ClassVar[Path] = Path(__file__).resolve().parent
    LOGO_PATH: ClassVar[Path] = UI_ROOT / "assets" / "lunavita_logo.png"
    FOOD_IMAGE_DISPLAY_SIZE: ClassVar[tuple[int, int]] = (360, 240)
    FOOD_IMAGE_COLUMN_WIDTH: ClassVar[int] = 96
    FOOD_IMAGE_ROW_HEIGHT: ClassVar[int] = 64
    EMOJI_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        "[\U0001F1E6-\U0001F1FF\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]"
    )

    api_url: str
    timeout: float = 10.0

    @classmethod
    def text_validation_error(
        cls,
        value: object,
        label: str,
        *,
        required: bool = False,
        max_length: int,
    ) -> str | None:
        """Return a user-facing error for unsafe editable text."""
        text = "" if value is None else str(value).strip()
        if required and not text:
            return f"{label} cannot be blank."
        if len(text) > max_length:
            return f"{label} must be {max_length} characters or fewer."
        if cls.EMOJI_PATTERN.search(text):
            return f"{label} cannot contain emojis."
        if any(
            unicodedata.category(character).startswith("C")
            and character not in {"\n", "\t"}
            for character in text
        ):
            return f"{label} contains unsupported control characters."
        return None

    @staticmethod
    @st.cache_data(show_spinner=False, max_entries=256)
    def food_image_preview(source: str) -> str:
        """Return a distortion-free 3:2 preview while preserving its source."""
        if not source:
            return source
        try:
            if source.startswith("data:image/"):
                encoded = source.partition(",")[2]
                image_bytes = base64.b64decode(encoded, validate=True)
            elif source.startswith(("https://", "http://")):
                response = httpx.get(source, follow_redirects=True, timeout=10.0)
                response.raise_for_status()
                image_bytes = response.content
            else:
                return source

            with Image.open(BytesIO(image_bytes)) as opened:
                image = ImageOps.exif_transpose(opened).convert("RGB")
                image = ImageOps.fit(
                    image,
                    UIConfig.FOOD_IMAGE_DISPLAY_SIZE,
                    method=Image.Resampling.LANCZOS,
                    centering=(0.5, 0.5),
                )
            output = BytesIO()
            image.save(output, format="JPEG", quality=85, optimize=True)
            encoded = base64.b64encode(output.getvalue()).decode("ascii")
            return f"data:image/jpeg;base64,{encoded}"
        except (ValueError, OSError, httpx.HTTPError):
            return source

    @classmethod
    def from_env(cls) -> "UIConfig":
        return cls(
            os.getenv("LUNAVITA_API_URL", "http://localhost:18001").rstrip("/")
        )
