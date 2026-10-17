"""Luna Vita's single source of local calendar time."""

from datetime import date, datetime
from zoneinfo import ZoneInfo


class LocalClock:
    """Resolve dates and timestamps in the Asia/Kolkata calendar day."""

    TIMEZONE = ZoneInfo("Asia/Kolkata")

    @classmethod
    def now(cls) -> datetime:
        return datetime.now(cls.TIMEZONE)

    @classmethod
    def today(cls) -> date:
        return cls.now().date()

    @classmethod
    def localize(cls, value: datetime) -> datetime:
        """Treat naive timestamps as local time and convert aware ones to it."""
        if value.tzinfo is None:
            return value.replace(tzinfo=cls.TIMEZONE)
        return value.astimezone(cls.TIMEZONE)
