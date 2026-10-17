"""Shared Streamlit building blocks for the Luna Vita views."""

from collections.abc import Callable
from datetime import date

import streamlit as st

from api import LunaVitaAPI


class LunaVitaView:
    """Base class giving every view the API client it renders from."""

    def __init__(self, api: LunaVitaAPI) -> None:
        self.api = api

    def render(self, day: date) -> None:
        raise NotImplementedError


class SectionHeader:
    """A section title with an optional description and "Add entry" button."""

    @staticmethod
    def heading(title: str, description: str | None = None) -> None:
        body = f"<p>{description}</p>" if description else ""
        st.markdown(
            f'<div class="food-log-heading"><h2>{title}</h2>{body}</div>',
            unsafe_allow_html=True,
        )

    @classmethod
    def with_add_button(
        cls, title: str, description: str, key: str, on_add: Callable[[], None]
    ) -> None:
        title_column, action_column = st.columns(
            [5, 1], vertical_alignment="center", gap="medium"
        )
        with title_column:
            cls.heading(title, description)
        with action_column:
            if st.button(
                "Add entry",
                icon=":material/add:",
                type="primary",
                width="stretch",
                key=key,
            ):
                on_add()
