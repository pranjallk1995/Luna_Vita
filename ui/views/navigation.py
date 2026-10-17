"""Daily/Weekly/Monthly period selector that survives repeated clicks."""

import inspect

import streamlit as st


class PeriodNavigation:
    """Segmented control whose active segment cannot be toggled off."""

    KEY = "nutrition-period"
    LAST_KEY = "nutrition-period-last"
    DEFAULT = "daily"
    LABELS = {
        "daily": ":material/today: Daily Tracking",
        "weekly": ":material/date_range: Weekly Tracking",
        "monthly": ":material/calendar_month: Monthly Tracking",
    }

    @classmethod
    def preserve_selection(cls) -> None:
        """Clicking the active segment clears it, so restore the last choice."""
        selected = st.session_state.get(cls.KEY)
        if selected is None:
            st.session_state[cls.KEY] = st.session_state.get(cls.LAST_KEY, cls.DEFAULT)
        else:
            st.session_state[cls.LAST_KEY] = selected

    @classmethod
    def last_selection(cls) -> str:
        return st.session_state.get(cls.LAST_KEY, cls.DEFAULT)

    @classmethod
    def render(cls) -> str:
        container = st.container(key="nutrition_navigation")
        active = st.session_state.get(cls.KEY, cls.last_selection())
        # The marker lets the stylesheet highlight the active segment reliably.
        container.markdown(f'<span class="lv-selected-{active}"></span>', unsafe_allow_html=True)
        options = {
            "options": list(cls.LABELS),
            "format_func": cls.LABELS.__getitem__,
            "label_visibility": "collapsed",
            "key": cls.KEY,
            "on_change": cls.preserve_selection,
        }
        if cls.KEY not in st.session_state:
            options["default"] = cls.DEFAULT
        if "width" in inspect.signature(st.segmented_control).parameters:
            options["width"] = "stretch"
        period = container.segmented_control("Nutrition period", **options)
        return period or cls.last_selection()
