"""Luna Vita's single source of local calendar time."""

from datetime import date, datetime

from app.core.config import AppConfig


class LocalClock:
    """Resolve dates and timestamps in the Asia/Kolkata calendar day."""

    @classmethod
    def now(cls) -> datetime:
        return datetime.now(AppConfig.TIMEZONE)

    @classmethod
    def today(cls) -> date:
        return cls.now().date()

    @classmethod
    def localize(cls, value: datetime) -> datetime:
        """Treat naive timestamps as local time and convert aware ones to it."""
        if value.tzinfo is None:
            return value.replace(tzinfo=AppConfig.TIMEZONE)
        return value.astimezone(AppConfig.TIMEZONE)
