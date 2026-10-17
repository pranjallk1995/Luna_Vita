"""Food-photo normalization for storage and table previews."""

import base64
from io import BytesIO
from typing import Any

import httpx
import streamlit as st
from PIL import Image, ImageOps, UnidentifiedImageError

from config import UIConfig


class FoodImages:
    """Fit food photos to the 3:2 table format and encode them as data URLs."""

    BACKGROUND = (17, 17, 17)

    @staticmethod
    def fitted_jpeg_data_url(image: Image.Image) -> str:
        fitted = ImageOps.fit(
            image,
            UIConfig.FOOD_IMAGE_DISPLAY_SIZE,
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        output = BytesIO()
        fitted.save(output, format="JPEG", quality=85, optimize=True)
        encoded = base64.b64encode(output.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"

    @classmethod
    def uploaded_data_url(cls, uploaded_file: Any) -> str:
        """Normalize an uploaded photo into a compact database-safe data URL."""
        try:
            image = ImageOps.exif_transpose(Image.open(uploaded_file))
            if image.mode in {"RGBA", "LA"}:
                rgba = image.convert("RGBA")
                background = Image.new("RGB", rgba.size, cls.BACKGROUND)
                background.paste(rgba, mask=rgba.getchannel("A"))
                image = background
            else:
                image = image.convert("RGB")
            return cls.fitted_jpeg_data_url(image)
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ValueError("Choose a valid JPG, PNG, or WebP food photo.") from exc

    @staticmethod
    @st.cache_data(show_spinner=False, max_entries=256)
    def preview(source: str) -> str:
        """Return a distortion-free 3:2 preview while preserving its source."""
        if not source:
            return source
        try:
            if source.startswith("data:image/"):
                image_bytes = base64.b64decode(source.partition(",")[2], validate=True)
            elif source.startswith(("https://", "http://")):
                response = httpx.get(source, follow_redirects=True, timeout=10.0)
                response.raise_for_status()
                image_bytes = response.content
            else:
                return source
            with Image.open(BytesIO(image_bytes)) as opened:
                image = ImageOps.exif_transpose(opened).convert("RGB")
                return FoodImages.fitted_jpeg_data_url(image)
        except (ValueError, OSError, httpx.HTTPError):
            return source
