"""Validated runtime configuration for the Luna Vita backend."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    """Immutable backend settings loaded from environment variables."""

    database_url: str
    host: str = "0.0.0.0"
    port: int = 8000

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Build and validate backend configuration from the environment."""
        database_url = os.getenv("DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeError("DATABASE_URL is required.")
        return cls(database_url=database_url)
