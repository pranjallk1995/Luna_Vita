"""Timezone-aware dates and timestamps for the UI."""

from datetime import date, datetime, time

from config import UIConfig


class LunaVitaClock:
    """Resolve dates and timestamps in the Asia/Kolkata calendar day."""

    @classmethod
    def now(cls) -> datetime:
        return datetime.now(UIConfig.LOCAL_TIMEZONE)

    @classmethod
    def today(cls) -> date:
        return cls.now().date()

    @classmethod
    def current_minute(cls) -> time:
        """The current local clock time, truncated for time-input defaults."""
        return cls.now().replace(second=0, microsecond=0).time()

    @classmethod
    def combine(cls, day: date, clock_time: time) -> datetime:
        return datetime.combine(day, clock_time, tzinfo=UIConfig.LOCAL_TIMEZONE)
