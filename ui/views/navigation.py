"""Daily/Monthly period selector that survives repeated clicks."""

import inspect

import streamlit as st


class PeriodNavigation:
    """Segmented control whose active segment cannot be toggled off."""

    KEY = "nutrition-period"
    LAST_KEY = "nutrition-period-last"
    DEFAULT = "daily"
    LABELS = {
        "daily": ":material/today: Daily Tracking",
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
        last = st.session_state.get(cls.LAST_KEY, cls.DEFAULT)
        return last if last in cls.LABELS else cls.DEFAULT

    @classmethod
    def drop_retired_selection(cls) -> None:
        """Forget a stored period that is no longer offered (e.g. the old Weekly tab)."""
        for key in (cls.KEY, cls.LAST_KEY):
            if st.session_state.get(key) not in (None, *cls.LABELS):
                del st.session_state[key]

    @classmethod
    def render(cls) -> str:
        cls.drop_retired_selection()
        container = st.container(key="nutrition_navigation")
        # The stored value can be None after reruns started by other widgets.
        active = st.session_state.get(cls.KEY) or cls.last_selection()
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
