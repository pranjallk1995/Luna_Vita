"""Daily nutrition summary: overall calorie bar and per-nutrient cards."""

from datetime import date

import streamlit as st

from nutrition import NUTRIENTS, NutritionStatus
from views.shared import LunaVitaView, NutrientCards


class SummaryView(LunaVitaView):
    """Compare the day's running totals with the configured recommendations."""

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
        targets = NutrientCards.targets(recommendations)
        st.markdown(
            '<section class="nutrition-panel">'
            '<div class="nutrition-head">'
            '<div class="nutrition-title">'
            "<h2>Today's Nutrition</h2>"
            "<p>Running totals from today's food log</p>"
            "</div>"
            f'{self.overall_html(values["calories"], targets["calories"])}'
            "</div>"
            f"{NutrientCards.html(values, targets)}"
            "</section>",
            unsafe_allow_html=True,
        )
