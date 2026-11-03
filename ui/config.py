"""Validated settings for the UI gateway and the browser app it serves."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar
from urllib.parse import urlparse


@dataclass(frozen=True)
class SSOConfig:
    """Single sign-on through Luna Sentia; this block is identical in every Luna app's config.py."""

    COOKIE_NAME: ClassVar[str] = "luna_sso"
    SESSION_HEADER: ClassVar[str] = "X-Luna-Session"
    # How long a confirmed session is trusted before asking Sentia again, so a sign-out
    # in another app takes effect here within this many seconds.
    RECHECK_SECONDS: ClassVar[int] = 60
    LOOKUP_TIMEOUT_SECONDS: ClassVar[float] = 5.0
    SESSION_CACHE_ENTRIES: ClassVar[int] = 256

    public_url: str
    internal_url: str = "http://luna-sentia-auth:8000"

    @classmethod
    def from_env(cls) -> "SSOConfig":
        public_url = os.getenv("LUNA_SSO_URL", "").strip().rstrip("/")
        if not public_url:
            raise RuntimeError("LUNA_SSO_URL must be the public address of Luna Sentia's auth service.")
        internal_url = os.getenv("LUNA_SSO_INTERNAL_URL", "").strip().rstrip("/")
        return cls(public_url=public_url, internal_url=internal_url or cls.internal_url)


@dataclass(frozen=True)
class UIConfig:
    """Immutable gateway settings."""

    UI_ROOT: ClassVar[Path] = Path(__file__).resolve().parent
    # The built React app; the Dockerfile puts it here.
    STATIC_DIR: ClassVar[Path] = UI_ROOT / "static"
    API_TIMEOUT_SECONDS: ClassVar[float] = 10.0
    # A food photo reaches the backend inside its entry, already fitted by the browser.
    MAX_REQUEST_BYTES: ClassVar[int] = 4 * 1024 * 1024
    # Calendar days and logged times all resolve in this zone, as in the backend.
    TIME_ZONE: ClassVar[str] = "Asia/Kolkata"
    UTC_OFFSET: ClassVar[str] = "+05:30"
    # 3:2 photos in the food table and the Monthly gallery.
    FOOD_PHOTO_SIZE: ClassVar[tuple[int, int]] = (360, 240)
    FOOD_PHOTO_LARGE_SIZE: ClassVar[tuple[int, int]] = (1280, 1280)
    FOOD_PHOTO_QUALITY: ClassVar[int] = 85
    FOOD_PHOTO_CACHE_ENTRIES: ClassVar[int] = 256
    FOOD_PHOTO_TIMEOUT_SECONDS: ClassVar[float] = 10.0
    PHOTO_UPLOAD_TYPES: ClassVar[tuple[str, ...]] = ("jpg", "jpeg", "png", "webp")
    MAX_FOOD_ROWS: ClassVar[int] = 500
    MAX_MEASUREMENT_ROWS: ClassVar[int] = 500
    # Hashed bundles never change under the same name.
    IMMUTABLE_CACHE_CONTROL: ClassVar[str] = "private, max-age=31536000, immutable"
    CONTENT_SECURITY_POLICY: ClassVar[str] = (
        # Food photos may be stored as data URLs or as links elsewhere.
        "default-src 'self'; img-src 'self' data: https: http:; font-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    )

    api_url: str
    api_token: str
    allowed_emails: frozenset[str]
    sso: SSOConfig
    # Luna Visia's API on the private network, where stored food photos are fetched from.
    visia_api_url: str = "http://luna-visia-mcp:8000"

    @classmethod
    def from_env(cls) -> "UIConfig":
        """Build and validate gateway configuration from environment variables."""
        api_url = os.getenv("LUNAVITA_API_URL", "http://luna-vita-mcp:8000").rstrip("/")
        parsed = urlparse(api_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise RuntimeError("LUNAVITA_API_URL must be a valid HTTP(S) URL.")
        api_token = os.getenv("LUNAVITA_API_TOKEN", "").strip()
        if len(api_token) < 32:
            raise RuntimeError("LUNAVITA_API_TOKEN must contain at least 32 characters.")
        allowed_emails = frozenset(
            email.strip().casefold()
            for email in os.getenv("LUNAVITA_ALLOWED_EMAILS", "").split(",")
            if email.strip()
        )
        if not allowed_emails:
            raise RuntimeError("LUNAVITA_ALLOWED_EMAILS must list at least one account.")
        return cls(
            api_url=api_url,
            api_token=api_token,
            allowed_emails=allowed_emails,
            sso=SSOConfig.from_env(),
            visia_api_url=os.getenv("LUNAVISIA_INTERNAL_URL", cls.visia_api_url).rstrip("/"),
        )
