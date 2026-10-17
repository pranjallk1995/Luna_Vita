"""Shared Streamlit building blocks for the Luna Vita views."""

from collections.abc import Callable
from datetime import date

import streamlit as st

from api import LunaVitaAPI
from nutrition import NUTRIENTS, Nutrient, NutritionStatus


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


class NutrientCards:
    """The five nutrient cards comparing intake with daily targets."""

    @staticmethod
    def targets(recommendations: dict) -> dict[str, float]:
        return {n.key: float(recommendations[n.target_field]) for n in NUTRIENTS}

    @staticmethod
    def classes(nutrient: Nutrient, value: float, target: float) -> str:
        """The nutrient and status classes that set a card's accent color."""
        return f"{nutrient.key} {nutrient.status(value, target)}"

    @classmethod
    def card_html(cls, nutrient: Nutrient, value: float, target: float) -> str:
        percent = NutritionStatus.percentage(value, target)
        ring_degrees = min(max(percent, 0), 100) * 3.6
        current = f"{value:,.{nutrient.decimals}f} {nutrient.unit}"
        target_text = f"{target:,.0f} {nutrient.unit}{nutrient.target_suffix}"
        return (
            f'<div class="nutrition-card {cls.classes(nutrient, value, target)}">'
            "<div>"
            f'<div class="nutrition-card-label"><span class="nutrition-card-icon">'
            f"{nutrient.icon}</span>{nutrient.label}</div>"
            f'<div class="nutrition-card-value">{current}</div>'
            f'<div class="nutrition-card-target">Target {target_text}</div>'
            "</div>"
            f'<div class="nutrition-ring" style="--ring-value:{ring_degrees:.1f}deg">'
            f"<span>{percent}%</span></div>"
            "</div>"
        )

    @classmethod
    def html(
        cls,
        values: dict[str, float],
        targets: dict[str, float],
        footers: dict[str, str] | None = None,
    ) -> str:
        """Render the card row; each footer sits under its card at the same width."""
        cells = []
        for nutrient in NUTRIENTS:
            card = cls.card_html(nutrient, values[nutrient.key], targets[nutrient.key])
            footer = (footers or {}).get(nutrient.key)
            cells.append(f'<div class="nutrient-stack">{card}{footer}</div>' if footer else card)
        return f'<div class="nutrition-cards">{"".join(cells)}</div>'
