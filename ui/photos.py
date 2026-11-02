"""Food photos stored in Luna Visia, fitted to the table's 3:2 format and encoded once."""

from __future__ import annotations

import re
from collections import OrderedDict
from io import BytesIO

from PIL import Image, ImageOps

from config import UIConfig

VISIA_IMAGE_PATH = re.compile(r"/api/public/images/[0-9a-fA-F-]{36}/?$")


class FoodPhotos:
    def __init__(self) -> None:
        self.fitted: OrderedDict[str, bytes] = OrderedDict()

    @staticmethod
    def visia_image_path(url: str) -> str | None:
        """The path of a public Visia image link on Visia's internal API; None for anything else."""
        match = VISIA_IMAGE_PATH.search(url)
        return match.group(0) if match else None

    def cached(self, path: str) -> bytes | None:
        data = self.fitted.get(path)
        if data is not None:
            self.fitted.move_to_end(path)
        return data

    def fit(self, path: str, source: bytes) -> bytes:
        with Image.open(BytesIO(source)) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
        fitted = ImageOps.fit(image, UIConfig.FOOD_PHOTO_SIZE, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        encoded = BytesIO()
        fitted.save(encoded, "WEBP", quality=UIConfig.FOOD_PHOTO_QUALITY)
        data = encoded.getvalue()
        self.fitted[path] = data
        self.fitted.move_to_end(path)
        while len(self.fitted) > UIConfig.FOOD_PHOTO_CACHE_ENTRIES:
            self.fitted.popitem(last=False)
        return data
