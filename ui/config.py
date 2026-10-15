"""Environment-backed configuration for the Luna Vita UI."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class UIConfig:
    api_url: str
    timeout: float = 10.0

    @classmethod
    def from_env(cls) -> "UIConfig":
        return cls(
            os.getenv("LUNAVITA_API_URL", "http://localhost:18001").rstrip("/")
        )
