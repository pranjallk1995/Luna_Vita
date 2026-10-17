"""Daily nutrition summary: overall calorie bar and per-nutrient cards."""

from datetime import date

import streamlit as st

from nutrition import NUTRIENTS, Nutrient, NutritionStatus
from views.shared import LunaVitaView


class SummaryView(LunaVitaView):
    """Compare the day's running totals with the configured recommendations."""

    @staticmethod
    def card_html(nutrient: Nutrient, value: float, target: float) -> str:
        percent = NutritionStatus.percentage(value, target)
        ring_degrees = min(max(percent, 0), 100) * 3.6
        current = f"{value:,.{nutrient.decimals}f} {nutrient.unit}"
        target_text = f"{target:,.0f} {nutrient.unit}{nutrient.target_suffix}"
        return (
            f'<div class="nutrition-card {nutrient.key} {nutrient.status(value, target)}">'
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

    @staticmethod
    def overall_html(calories: float, target: float) -> str:
        percent = NutritionStatus.percentage(calories, target)
        width = min(max(percent, 0), 100)
        return (
            '<div class="nutrition-overall">'
            '<div class="nutrition-overall-row">'
            f"<span>{calories:,.0f} / {target:,.0f} kcal</span>"
            f"<strong>{percent}%</strong>"
            "</div>"
            '<div class="nutrition-track">'
            f'<div class="nutrition-fill" style="width:{width}%"></div>'
            "</div></div>"
        )

    def render(self, day: date) -> None:
        summary = self.api.summary(day)
        recommendations = self.api.recommendations()
        if not recommendations:
            st.warning("Daily nutrition recommendations have not been configured.")
            return

        values = {n.key: float(summary[n.summary_field]) for n in NUTRIENTS}
        targets = {n.key: float(recommendations[n.target_field]) for n in NUTRIENTS}
        cards = "".join(
            self.card_html(n, values[n.key], targets[n.key]) for n in NUTRIENTS
        )
        st.markdown(
            '<section class="nutrition-panel">'
            '<div class="nutrition-head">'
            '<div class="nutrition-title">'
            "<h2>Today's Nutrition</h2>"
            "<p>Running totals from today's food log</p>"
            "</div>"
            f'{self.overall_html(values["calories"], targets["calories"])}'
            "</div>"
            f'<div class="nutrition-cards">{cards}</div>'
            "</section>",
            unsafe_allow_html=True,
        )
