"""Monthly tracking: item counts, top contributors, and foods to prefer or avoid."""

from datetime import date
from html import escape
from typing import Any

import httpx
import pandas as pd
import streamlit as st

from services.api import LunaVitaAPI
from domain.body_trends import BodyTrendChart, Reading
from domain.clock import LunaVitaClock
from domain.nutrition import NUTRIENTS, Nutrient
from domain.workouts import WorkoutCalendar
from views.shared import LunaVitaView, NutrientCards, SectionHeader

Analysis = dict[str, Any]
RANGE_ERROR_KEY = "analysis-range-error"

# (summary field, label, unit, material icon) for the contributor panels.
CONTRIBUTOR_NUTRIENTS = (
    ("calories", "Calories", "kcal", "local_fire_department"),
    ("protein_g", "Protein", "g", "fitness_center"),
    ("carbs_g", "Carbs", "g", "grain"),
    ("fat_g", "Fat", "g", "water_drop"),
    ("added_sugar_g", "Added sugar", "g", "nutrition"),
)
VERDICT_LABELS = {"prefer": "Prefer", "avoid": "Avoid", "neutral": ""}
OVERRIDE_LABEL = "Your rating"


class DailyTrendChart:
    """Per-day columns for one nutrient, drawn inside a card-colored panel."""

    SLOT = 10  # viewBox units per day
    HEIGHT = 60
    BAR_WIDTH = 7

    @staticmethod
    def amount(nutrient: Nutrient, value: float) -> str:
        return f"{value:,.{nutrient.decimals}f} {nutrient.unit}"

    @staticmethod
    def day_label(iso_day: str) -> str:
        day = date.fromisoformat(iso_day)
        return f"{day.day} {day:%b}"

    @classmethod
    def svg(cls, nutrient: Nutrient, days: list[dict[str, Any]], target: float) -> str:
        values = [day.get(nutrient.summary_field, 0.0) for day in days if day["logged"]]
        scale_max = max([target, *values, 1.0]) * 1.08
        width = cls.SLOT * len(days)

        def y(value: float) -> float:
            return cls.HEIGHT - value / scale_max * cls.HEIGHT

        columns = []
        for index, day in enumerate(days):
            x = index * cls.SLOT
            if day["logged"]:
                value = day[nutrient.summary_field]
                tip = f"{cls.day_label(day['date'])} · {cls.amount(nutrient, value)}"
                bar_top = y(value)
                bar = (
                    f'<rect class="nutrient-trend-bar" x="{x + (cls.SLOT - cls.BAR_WIDTH) / 2}" '
                    f'y="{bar_top:.2f}" width="{cls.BAR_WIDTH}" '
                    f'height="{cls.HEIGHT - bar_top:.2f}"/>'
                )
            else:
                tip, bar = f"{cls.day_label(day['date'])} · not logged", ""
            columns.append(
                f'<g class="nutrient-trend-day"><title>{escape(tip)}</title>'
                f'<rect class="nutrient-trend-hit" x="{x}" y="0" '
                f'width="{cls.SLOT}" height="{cls.HEIGHT}"/>{bar}</g>'
            )
        target_y = y(target)
        return (
            f'<svg class="nutrient-trend-plot" viewBox="0 0 {width} {cls.HEIGHT}" '
            f'preserveAspectRatio="none" role="img" '
            f'aria-label="{nutrient.label} per day">'
            f'<line class="nutrient-trend-base" x1="0" x2="{width}" '
            f'y1="{cls.HEIGHT}" y2="{cls.HEIGHT}"/>'
            f'{"".join(columns)}'
            f'<line class="nutrient-trend-target" x1="0" x2="{width}" '
            f'y1="{target_y:.2f}" y2="{target_y:.2f}"/></svg>'
        )

    @classmethod
    def html(
        cls, nutrient: Nutrient, days: list[dict[str, Any]], average: float, target: float
    ) -> str:
        middle = days[len(days) // 2]["date"]
        return (
            f'<div class="nutrition-card nutrient-trend {NutrientCards.classes(nutrient, average, target)}">'
            '<div class="nutrient-trend-head"><span>Per day</span>'
            '<span><i class="nutrient-trend-key"></i>'
            f"Target {target:,.0f} {nutrient.unit}</span></div>"
            f"{cls.svg(nutrient, days, target)}"
            '<div class="nutrient-trend-axis">'
            f"<span>{cls.day_label(days[0]['date'])}</span>"
            f"<span>{cls.day_label(middle)}</span>"
            f"<span>{cls.day_label(days[-1]['date'])}</span></div></div>"
        )


class MonthlyView(LunaVitaView):
    """Render the backend's analysis of the saved range or the selected month."""

    def __init__(self, api: LunaVitaAPI) -> None:
        super().__init__(api)
        self.period = "month"

    @property
    def custom_range(self) -> bool:
        return self.period == "range"

    @property
    def span(self) -> str:
        return "in this range" if self.custom_range else "this month"

    @property
    def title(self) -> str:
        return "Overview"

    @staticmethod
    def amount(value: float, unit: str) -> str:
        return f"{value:,.0f} {unit}" if unit == "kcal" else f"{value:,.1f} {unit}"

    @staticmethod
    def verdict_label(food: dict[str, Any]) -> str:
        verdict = food["verdict"]
        label = VERDICT_LABELS[verdict["kind"]]
        if verdict["source"] == "override":
            return f"{label} ({OVERRIDE_LABEL.lower()})" if label else OVERRIDE_LABEL
        return label

    def render_overview(self, analysis: Analysis) -> None:
        window = analysis["window"]
        source_note = " · custom range" if self.custom_range else ""
        SectionHeader.heading(
            self.title,
            f"{window['label']}{source_note} · {analysis['entries']} entries · "
            f"{len(analysis['foods'])} different foods · "
            f"{analysis['days_logged']} of {window['days']} days logged",
        )
        body_card = self.body_card_html(window)
        recommendations = self.api.recommendations()
        if not recommendations:
            st.markdown(body_card, unsafe_allow_html=True)
            return
        averages = analysis["daily_averages"]
        values = {n.key: averages[n.summary_field] for n in NUTRIENTS}
        targets = NutrientCards.targets(recommendations)
        charts = {
            n.key: DailyTrendChart.html(
                n, analysis["daily_totals"], values[n.key], targets[n.key]
            )
            for n in NUTRIENTS
        }
        # One grid so the body card matches the height of a macro card + chart stack.
        st.markdown(
            '<div class="analysis-caption">Daily average across logged days, '
            "with each day below</div>"
            f'<div class="overview-grid">{NutrientCards.html(values, targets, charts)}{body_card}</div>',
            unsafe_allow_html=True,
        )

    @classmethod
    def item_frame(cls, analysis: Analysis) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "Food": food["name"],
                    "Times had": food["count"],
                    "Days": food["days"],
                    "kcal": round(food["totals"]["calories"]),
                    "Protein": food["totals"]["protein_g"],
                    "Carbs": food["totals"]["carbs_g"],
                    "Fat": food["totals"]["fat_g"],
                    "Added sugar": food["totals"]["added_sugar_g"],
                    "Protein %": round(food["protein_share"] * 100),
                    "Verdict": cls.verdict_label(food),
                }
                for food in analysis["foods"]
            ]
        )

    def render_item_counts(self, analysis: Analysis) -> None:
        SectionHeader.heading(
            "What you had",
            f"How many times each food was logged {self.span}, most frequent first.",
        )
        grams = st.column_config.NumberColumn(format="%.1f g", width="small")
        st.dataframe(
            self.item_frame(analysis),
            hide_index=True,
            width="stretch",
            column_config={
                "Food": st.column_config.TextColumn(width="medium"),
                "Times had": st.column_config.ProgressColumn(
                    format="%d×",
                    width="small",
                    min_value=0,
                    max_value=max(food["count"] for food in analysis["foods"]),
                ),
                "Protein": grams,
                "Carbs": grams,
                "Fat": grams,
                "Added sugar": st.column_config.NumberColumn(format="%.1f g", width=104),
                "Protein %": st.column_config.NumberColumn(
                    format="%d%%", width="small", help="Share of the food's calories from protein"
                ),
                "Days": st.column_config.NumberColumn(width="small"),
                "kcal": st.column_config.NumberColumn(width="small"),
                "Verdict": st.column_config.TextColumn(width="small"),
            },
        )

    def contributor_panel_html(
        self, analysis: Analysis, field: str, label: str, unit: str, icon: str
    ) -> str:
        rows = "".join(
            f'<div class="analysis-bar-row" title="{escape(c["name"])}: '
            f'{self.amount(c["amount"], unit)} ({c["share"]:.0%} of the {self.period})">'
            f'<div class="analysis-bar-name">{escape(c["name"])}</div>'
            '<div class="analysis-bar-line"><div class="analysis-bar-track">'
            f'<div class="analysis-bar-fill" style="width:{c["share"] * 100:.1f}%"></div>'
            f'</div><strong>{c["share"]:.0%}</strong></div></div>'
            for c in analysis["top_contributors"][field]
        ) or f'<p class="analysis-empty">None logged {self.span}.</p>'
        return (
            '<div class="analysis-panel">'
            f'<h3><span class="analysis-icon">{icon}</span>{label}</h3>'
            '<div class="analysis-panel-total">'
            f"{self.amount(analysis['totals'][field], unit)} {self.span}</div>"
            f"{rows}</div>"
        )

    def render_contributors(self, analysis: Analysis) -> None:
        SectionHeader.heading(
            "Top contributors",
            f"Which foods supplied the most of each nutrient, as a share of the {self.period}'s total.",
        )
        panels = "".join(
            self.contributor_panel_html(analysis, *spec) for spec in CONTRIBUTOR_NUTRIENTS
        )
        st.markdown(f'<section class="analysis-contributors">{panels}</section>', unsafe_allow_html=True)

    @staticmethod
    def suggestion_item_html(food: dict[str, Any]) -> str:
        verdict = food["verdict"]
        badge = (
            f'<span class="analysis-badge">{OVERRIDE_LABEL}</span>'
            if verdict["source"] == "override"
            else ""
        )
        return (
            "<li>"
            f'<span class="analysis-food">{escape(food["name"])}{badge}</span>'
            f'<span class="analysis-meta">{food["count"]}× · '
            f'{food["totals"]["calories"]:,.0f} kcal</span>'
            f'<span class="analysis-reason">{escape(verdict["reason"])}</span>'
            "</li>"
        )

    @classmethod
    def suggestion_html(
        cls, kind: str, icon: str, title: str, description: str,
        foods: list[dict[str, Any]], empty: str,
    ) -> str:
        entries = "".join(cls.suggestion_item_html(food) for food in foods)
        body = f"<ul>{entries}</ul>" if entries else f'<p class="analysis-empty">{empty}</p>'
        return (
            f'<div class="analysis-suggestions {kind}">'
            f'<h3><span class="analysis-icon">{icon}</span>{title}</h3>'
            f"<p>{description}</p>{body}</div>"
        )

    def render_suggestions(self, analysis: Analysis) -> None:
        rules = analysis["rules"]
        SectionHeader.heading(
            "Food choices",
            "Rated on macros: protein share of calories, carbs, and added sugar. "
            f'"{OVERRIDE_LABEL}" marks ratings set through the assistant.',
        )
        prefer = self.suggestion_html(
            "prefer", "thumb_up", "Prefer",
            f"At least {rules['prefer_min_protein_share']:.0%} of calories from protein, "
            f"at most {rules['prefer_max_carb_share']:.0%} from carbs, little added sugar.",
            analysis["prefer"],
            f"Nothing {self.span} met the high-protein, low-carb bar.",
        )
        avoid = self.suggestion_html(
            "avoid", "thumb_down", "Avoid",
            f"{rules['avoid_min_added_sugar_share']:.0%}+ of calories from added sugar, or under "
            f"{rules['avoid_max_protein_share']:.0%} from protein. Biggest calorie impact first.",
            analysis["avoid"],
            f"Nothing {self.span} was sugar-heavy or protein-poor.",
        )
        st.markdown(f'<section class="analysis-choices">{prefer}{avoid}</section>', unsafe_allow_html=True)

    def body_card_html(self, window: dict[str, Any]) -> str:
        """Weight and body fat % bars for the window, styled as an overview card."""
        start, end = date.fromisoformat(window["start"]), date.fromisoformat(window["end"])
        data = self.api.body_composition(start, end)
        return BodyTrendChart.html(
            Reading.parse(data["weight"]),
            Reading.parse(data["body_fat"]),
            start,
            end,
            float(data["body_fat_target_percent"]),
        )

    def render_workouts(self, window: dict[str, Any], day: date) -> None:
        """Done / skipped markers for the window's months, under the body card."""
        start, end = WorkoutCalendar.span(
            date.fromisoformat(window["start"]), date.fromisoformat(window["end"]), day
        )
        st.markdown(
            WorkoutCalendar.html(
                self.api.workouts(start, end), start, end, day, LunaVitaClock.today()
            ),
            unsafe_allow_html=True,
        )

    @staticmethod
    def range_error(error: httpx.HTTPError) -> str:
        """The backend's validation message, e.g. for a range longer than a year."""
        if isinstance(error, httpx.HTTPStatusError):
            try:
                body = error.response.json()
                details = body.get("details") or []
                return details[0].get("msg", body["error"]) if details else body["error"]
            except (ValueError, KeyError, AttributeError):
                pass
        return f"Could not update the date range: {error}"

    # Widget callbacks run before the next script pass; failures are kept in
    # session state and shown under the picker on that pass.
    @staticmethod
    def save_range(api: LunaVitaAPI, key: str) -> None:
        picked = st.session_state.get(key) or ()
        if len(picked) != 2:  # the user has picked only the start date so far
            return
        try:
            api.set_analysis_range(*picked)
            st.session_state.pop(RANGE_ERROR_KEY, None)
        except httpx.HTTPError as error:
            st.session_state[RANGE_ERROR_KEY] = MonthlyView.range_error(error)

    @staticmethod
    def reset_range(api: LunaVitaAPI) -> None:
        try:
            api.reset_analysis_range()
            st.session_state.pop(RANGE_ERROR_KEY, None)
        except httpx.HTTPError as error:
            st.session_state[RANGE_ERROR_KEY] = MonthlyView.range_error(error)

    def render_range_picker(self, window: dict[str, Any]) -> None:
        """Date range shared with the assistant; "This month" clears a custom range."""
        start, end = date.fromisoformat(window["start"]), date.fromisoformat(window["end"])
        # Keyed by the window so the picker follows ranges set elsewhere (the assistant).
        key = f"analysis-range-{start.isoformat()}-{end.isoformat()}"
        with st.container(key="analysis_range_bar"):
            picker_column, reset_column, _ = st.columns([2.2, 1.3, 3.8], vertical_alignment="bottom")
            picker_column.date_input(
                "Date range",
                value=(start, end),
                format="DD/MM/YYYY",
                key=key,
                on_change=self.save_range,
                args=(self.api, key),
            )
            if self.custom_range:
                reset_column.button(
                    "This month",
                    icon=":material/calendar_month:",
                    use_container_width=True,
                    on_click=self.reset_range,
                    args=(self.api,),
                )
        if st.session_state.get(RANGE_ERROR_KEY):
            st.error(st.session_state[RANGE_ERROR_KEY])

    def render(self, day: date) -> None:
        analysis = self.api.analysis(day)
        self.period = "range" if analysis["range_source"] == "saved" else "month"
        self.render_range_picker(analysis["window"])
        if not analysis["foods"]:
            SectionHeader.heading(self.title, analysis["window"]["label"])
            st.markdown(self.body_card_html(analysis["window"]), unsafe_allow_html=True)
            self.render_workouts(analysis["window"], day)
            st.info(f"No food entries {self.span} yet.")
            return
        self.render_overview(analysis)
        self.render_workouts(analysis["window"], day)
        self.render_item_counts(analysis)
        self.render_contributors(analysis)
        self.render_suggestions(analysis)
