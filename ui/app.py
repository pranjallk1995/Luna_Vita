"""Luna Vita Streamlit application entry point."""

import hashlib

import httpx
import streamlit as st
from PIL import Image

from api import LunaVitaAPI
from clock import LunaVitaClock
from config import UIConfig
from styles import LunaStyle
from views.food_log_view import FoodLogView
from views.measurements_view import MeasurementsView
from views.navigation import PeriodNavigation
from views.summary_view import SummaryView


class SourceReloadMonitor:
    """Track deployed UI source and notify existing Streamlit sessions."""

    @staticmethod
    def revision() -> str:
        source_files = sorted(UIConfig.UI_ROOT.rglob("*.py"))
        source_files.append(UIConfig.UI_ROOT / ".streamlit" / "config.toml")
        source_files.append(UIConfig.LOGO_PATH)
        digest = hashlib.sha256()
        for source_file in source_files:
            if source_file.is_file():
                digest.update(source_file.relative_to(UIConfig.UI_ROOT).as_posix().encode())
                digest.update(source_file.read_bytes())
        return digest.hexdigest()

    @classmethod
    def notify(cls) -> None:
        revision = cls.revision()
        previous_revision = st.session_state.get("ui_source_revision")
        st.session_state.ui_source_revision = revision
        if previous_revision is not None and previous_revision != revision:
            st.toast("Luna Vita updated", icon=":material/refresh:")


class LunaVitaApp:
    """Compose and render the Luna Vita nutrition tracker."""

    DAILY_VIEWS = (SummaryView, FoodLogView, MeasurementsView)
    PLACEHOLDERS = {
        "weekly": "Not enough data for the weekly view yet.",
        "monthly": "Not enough data for the monthly view yet.",
    }

    def __init__(self) -> None:
        self.config = UIConfig.from_env()
        self.api = LunaVitaAPI(self.config)

    def render(self) -> None:
        LunaStyle.apply()
        SourceReloadMonitor.notify()
        selected_day = LunaStyle.header(LunaVitaClock.today(), UIConfig.LOGO_PATH)
        period = PeriodNavigation.render()
        if period in self.PLACEHOLDERS:
            st.info(self.PLACEHOLDERS[period])
            return
        for view_class in self.DAILY_VIEWS:
            view_class(self.api).render(selected_day)

    @classmethod
    def run(cls) -> None:
        st.set_page_config(
            page_title="Luna Vita",
            page_icon=Image.open(UIConfig.LOGO_PATH),
            layout="wide",
            initial_sidebar_state="collapsed",
        )
        try:
            cls().render()
        except httpx.HTTPError as exc:
            st.error(f"The Luna Vita service is unavailable: {exc}")


if __name__ == "__main__":
    LunaVitaApp.run()
