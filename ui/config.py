"""Validated presentation and service settings for the Streamlit UI."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar
from urllib.parse import urlparse
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class SSOConfig:
    """Single sign-on through Luna Sentia; this block is identical in every Luna app's config.py."""

    COOKIE_NAME: ClassVar[str] = "luna_sso"
    SESSION_HEADER: ClassVar[str] = "X-Luna-Session"
    # How long a confirmed session is trusted before asking Sentia again, so a sign-out
    # in another app takes effect here within this many seconds.
    RECHECK_SECONDS: ClassVar[int] = 60
    LOOKUP_TIMEOUT_SECONDS: ClassVar[float] = 5.0

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
    """Immutable UI layout and backend-connection settings."""

    UI_ROOT: ClassVar[Path] = Path(__file__).resolve().parent
    LOGO_PATH: ClassVar[Path] = UI_ROOT / "assets" / "lunavita_logo.png"
    FOOD_IMAGE_DISPLAY_SIZE: ClassVar[tuple[int, int]] = (360, 240)
    FOOD_IMAGE_COLUMN_WIDTH: ClassVar[int] = 96
    FOOD_IMAGE_ROW_HEIGHT: ClassVar[int] = 64
    # Calendar days and logged times all resolve in this timezone, as in the backend.
    LOCAL_TIMEZONE: ClassVar[ZoneInfo] = ZoneInfo("Asia/Kolkata")
    IMAGE_FETCH_TIMEOUT_SECONDS: ClassVar[float] = 10.0
    IMAGE_CACHE_ENTRIES: ClassVar[int] = 256

    api_url: str
    allowed_emails: frozenset[str]
    sso: SSOConfig
    timeout: float = 10.0

    @classmethod
    def from_env(cls) -> "UIConfig":
        api_url = os.getenv("LUNAVITA_API_URL", "http://localhost:18001").rstrip("/")
        parsed = urlparse(api_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise RuntimeError("LUNAVITA_API_URL must be a valid HTTP(S) URL.")
        allowed_emails = frozenset(
            email.strip().casefold()
            for email in os.getenv("LUNAVITA_ALLOWED_EMAILS", "").split(",")
            if email.strip()
        )
        if not allowed_emails:
            raise RuntimeError("LUNAVITA_ALLOWED_EMAILS must list at least one account.")
        return cls(api_url=api_url, allowed_emails=allowed_emails, sso=SSOConfig.from_env())
