"""Verify food-image URLs against the Luna Visia image catalog."""

import re
from urllib.parse import urlparse

import httpx

from app.core.errors import NotFoundError


class VisiaUnavailableError(RuntimeError):
    """Raised when Luna Visia cannot be reached to verify an image."""


class VisiaImageCatalog:
    """Resolve an image URL to the canonical public URL of a visible Visia image.

    Only immutable image-ID URLs (``.../api/public/images/<uuid>``) are accepted,
    because filenames can change in Visia while image IDs never do. The ID must
    belong to a visible image, and the URL Visia publishes for it is returned.
    """

    PUBLIC_PATH = re.compile(
        r"/api/public/images/"
        r"(?P<image_id>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/?$",
        re.IGNORECASE,
    )
    SEARCH_HINT = (
        "Search Luna Visia for a matching image and pass the public_url it returns; "
        "if none fits, omit image_url to use the Luna Vita food placeholder image."
    )

    def __init__(self, api_url: str, placeholder_image_id: str, timeout: float = 10.0) -> None:
        self.api_url = api_url.rstrip("/")
        self.placeholder_image_id = placeholder_image_id.lower()
        self.timeout = timeout

    @classmethod
    def image_id(cls, image_url: str) -> str:
        """Extract the image ID, rejecting data URIs and filename-based URLs."""
        parsed = urlparse(image_url.strip())
        match = cls.PUBLIC_PATH.search(parsed.path)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or not match:
            raise ValueError(
                "image_url must be a Luna Visia image-ID URL ending in "
                f"/api/public/images/<image-id>. {cls.SEARCH_HINT}"
            )
        return match["image_id"].lower()

    def images(self) -> list[dict]:
        try:
            response = httpx.get(f"{self.api_url}/api/metadata", timeout=self.timeout)
            response.raise_for_status()
            return response.json()["images"]
        except (httpx.HTTPError, ValueError, KeyError) as error:
            raise VisiaUnavailableError(
                f"Luna Visia is unavailable, so the food image cannot be verified: {error}"
            ) from error

    def resolve(self, image_url: str) -> str:
        """Return Visia's canonical public URL for the image ``image_url`` names."""
        return self.resolve_id(self.image_id(image_url))

    def placeholder_url(self) -> str:
        """The public URL of the food placeholder image in Visia."""
        try:
            return self.resolve_id(self.placeholder_image_id)
        except NotFoundError as error:
            raise NotFoundError(
                f"The Luna Vita food placeholder image ({self.placeholder_image_id}) is missing "
                "from Luna Visia; restore it or set LUNAVITA_PLACEHOLDER_IMAGE_ID."
            ) from error

    def resolve_id(self, image_id: str) -> str:
        for image in self.images():
            if str(image.get("image_id", "")).lower() == image_id and not image.get("hidden"):
                return image["public_url"]
        raise NotFoundError(f"No visible Luna Visia image has ID {image_id}. {self.SEARCH_HINT}")
