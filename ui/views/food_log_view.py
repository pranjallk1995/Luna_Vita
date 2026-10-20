"""Food and nutrition section: editable daily log, add dialog, macro chart."""

from datetime import date
from typing import Any

import httpx
import pandas as pd
import streamlit as st

from services.api import LunaVitaAPI
from domain.clock import LunaVitaClock
from config import UIConfig
from domain.food_entries import FoodEntryPayload, FoodEntryTime
from services.images import FoodImages
from domain.nutrition import MacroBreakdown
from domain.validation import FoodRowValidator
from views.shared import LunaVitaView, SectionHeader


class MacroDistributionChart:
    """Donut chart and legend of the day's macro shares."""

    @staticmethod
    def segment_html(label: str, grams: float, percentage: int, color: str, offset: int) -> str:
        return (
            '<g class="macro-slice">'
            '<circle class="macro-segment" cx="60" cy="60" r="48" '
            'pathLength="100" '
            f'stroke="{color}" color="{color}" '
            f'stroke-dasharray="{percentage} {100 - percentage}" '
            f'stroke-dashoffset="{-offset}" transform="rotate(-90 60 60)"/>'
            '<text class="macro-tooltip" x="60" y="56" text-anchor="middle">'
            f'<tspan x="60">{label} {percentage}%</tspan>'
            f'<tspan class="macro-tooltip-value" x="60" dy="10">'
            f"{grams:,.1f} g"
            "</tspan></text></g>"
        )

    @classmethod
    def render(cls, rows: list[dict[str, Any]]) -> None:
        breakdown = MacroBreakdown(rows)
        offset = 0
        segments, legend = [], []
        for macro, grams, percentage in breakdown.slices():
            segments.append(cls.segment_html(macro.label, grams, percentage, macro.color, offset))
            legend.append(
                '<div class="macro-row">'
                f'<span class="macro-dot" style="--dot:{macro.color}"></span>'
                f"<span>{macro.label}</span><strong>{percentage}%</strong></div>"
            )
            offset += percentage
        SectionHeader.heading("Macro distribution")
        st.markdown(
            '<section class="macro-content">'
            f'<div class="macro-legend">{"".join(legend)}</div>'
            '<div class="macro-donut"><svg viewBox="0 0 120 120" '
            'role="img" aria-label="Macro distribution">'
            '<circle class="macro-track" cx="60" cy="60" r="48"/>'
            f'{"".join(segments)}</svg>'
            f'<div class="macro-center">{breakdown.calories:,.0f}<small>kcal</small></div>'
            "</div></section>",
            unsafe_allow_html=True,
        )


class FoodEntryDialog:
    """Modal form for recording one food or supplement entry."""

    def __init__(self, api: LunaVitaAPI) -> None:
        self.api = api

    @staticmethod
    def nutrition_inputs() -> dict[str, float]:
        columns = st.columns(6)
        return {
            "calories": columns[0].number_input("Calories kcal", min_value=0, step=1),
            "protein_g": columns[1].number_input("Protein g", min_value=0.0, step=0.5),
            "carbs_g": columns[2].number_input("Carbs g", min_value=0.0, step=0.5),
            "fat_g": columns[3].number_input("Fat g", min_value=0.0, step=0.5),
            "natural_sugar_g": columns[4].number_input(
                "Natural sugar", min_value=0.0, step=0.5
            ),
            "added_sugar_g": columns[5].number_input(
                "Added sugar", min_value=0.0, step=0.5
            ),
        }

    @staticmethod
    def consumed_time_input(day: date):
        date_column, toggle_column, time_column = st.columns(
            [1.35, 1.05, 1.2], vertical_alignment="bottom"
        )
        consumed_date = date_column.date_input("Consumed date", value=day)
        include_time = toggle_column.toggle(
            "Include consumed time",
            value=True,
            key=f"include-consumed-time-{day.isoformat()}",
        )
        if include_time:
            consumed_time = time_column.time_input(
                "Consumed time", LunaVitaClock.current_minute(), step=60
            )
        else:
            consumed_time = None
            time_column.text_input("Consumed time", value="Not recorded", disabled=True)
        return consumed_date, consumed_time

    @st.dialog("Add food or supplement", width="large")
    def open(self, day: date) -> None:
        name_column, quantity_column = st.columns([2, 1.2])
        name = name_column.text_input("Food / supplement :red[*]")
        quantity = quantity_column.text_input(
            "Quantity :red[*]", placeholder="30 g, 1 serving..."
        )
        consumed_date, consumed_time = self.consumed_time_input(day)
        time_label = st.text_input("Time label", placeholder="Morning, ~4:30 PM...")
        uploaded_image = st.file_uploader(
            "Food photo (optional)",
            type=["jpg", "jpeg", "png", "webp"],
            help="Choose a photo from this device. It will be resized before saving.",
        )
        nutrition = self.nutrition_inputs()
        notes = st.text_input("Notes", max_chars=2000)
        if not st.button(
            "Record food",
            type="primary",
            width="stretch",
            key=f"record-food-{day.isoformat()}",
        ):
            return
        if not name.strip() or not quantity.strip():
            st.warning("Food name and quantity are required.")
            return
        try:
            image_url = (
                FoodImages.uploaded_data_url(uploaded_image)
                if uploaded_image is not None
                else None
            )
        except ValueError as exc:
            st.warning(str(exc))
            return
        self.api.create_food(
            FoodEntryPayload.from_form(
                food_name=name,
                quantity=quantity,
                nutrition=nutrition,
                image_url=image_url,
                consumed_date=consumed_date,
                consumed_time=consumed_time,
                time_label=time_label,
                notes=notes,
            )
        )
        st.toast("Food saved to database")
        st.rerun()


class FoodLogView(LunaVitaView):
    """Editable table of the day's food entries with save and PDF actions."""

    COLUMNS = [
        "id",
        "consumed_date",
        "consumed_at",
        "time_label",
        "food_name",
        "quantity",
        "calories",
        "protein_g",
        "carbs_g",
        "fat_g",
        "natural_sugar_g",
        "added_sugar_g",
        "image_url",
        "notes",
    ]
    COLUMN_ORDER = [
        "display_time",
        "display_image",
        "food_name",
        "quantity",
        "calories",
        "protein_g",
        "carbs_g",
        "fat_g",
        "natural_sugar_g",
        "added_sugar_g",
        "notes",
        "remove",
    ]

    def __init__(self, api: LunaVitaAPI) -> None:
        super().__init__(api)
        self.dialog = FoodEntryDialog(api)

    @staticmethod
    def column_config() -> dict[str, Any]:
        number = st.column_config.NumberColumn
        return {
            "remove": st.column_config.CheckboxColumn(
                "Delete", help="Select rows to delete, then save."
            ),
            "display_time": st.column_config.TextColumn("Time", pinned=True),
            "display_image": st.column_config.ImageColumn(
                "Image",
                help="Optional food image",
                width=UIConfig.FOOD_IMAGE_COLUMN_WIDTH,
                pinned=True,
            ),
            "food_name": st.column_config.TextColumn(
                "Food / supplement", required=True, width="large"
            ),
            "quantity": st.column_config.TextColumn(
                "↪ Quantity", required=True, width="medium"
            ),
            "calories": number("♨ Calories", min_value=0, step=1),
            "protein_g": number("≋ Protein", min_value=0.0),
            "carbs_g": number("≋ Carbs", min_value=0.0),
            "fat_g": number("◉ Fat", min_value=0.0),
            "natural_sugar_g": number("◇ Natural sugar", min_value=0.0),
            "added_sugar_g": number("◇ Added sugar", min_value=0.0),
            "notes": st.column_config.TextColumn("Notes", width="large"),
        }

    @classmethod
    def editor_frame(cls, rows: list[dict[str, Any]]) -> pd.DataFrame:
        frame = pd.DataFrame(FoodEntryTime.rows_by_time(rows))[cls.COLUMNS]
        frame["display_time"] = frame.apply(FoodEntryTime.display, axis=1)
        frame["display_image"] = frame["image_url"].fillna("").map(FoodImages.preview)
        frame.insert(0, "remove", False)
        return frame

    def render_editor(self, day: date, rows: list[dict[str, Any]]) -> pd.DataFrame:
        frame = self.editor_frame(rows)
        return st.data_editor(
            frame,
            hide_index=True,
            use_container_width=True,
            disabled=["id", "image_url", "display_image"],
            height=min(760, 88 + (UIConfig.FOOD_IMAGE_ROW_HEIGHT + 2) * len(frame)),
            row_height=UIConfig.FOOD_IMAGE_ROW_HEIGHT,
            column_order=self.COLUMN_ORDER,
            column_config=self.column_config(),
            key=f"food-editor-{day.isoformat()}",
        )

    def save_rows(self, rows: list[dict[str, Any]], edited: pd.DataFrame) -> None:
        original = {int(row["id"]): row for row in rows}
        edited_rows = edited.to_dict("records")
        errors = FoodRowValidator.errors(edited_rows)
        if errors:
            st.error("Please correct the daily log before saving:\n\n- " + "\n- ".join(errors))
            return

        for row in edited_rows:
            entry_id = int(row["id"])
            if row["remove"]:
                self.api.delete_food(entry_id)
            else:
                self.api.update_food(
                    entry_id, FoodEntryPayload.from_editor_row(row, original[entry_id])
                )
        st.toast("Daily log saved")
        st.rerun()

    def render_actions(
        self, day: date, rows: list[dict[str, Any]], edited: pd.DataFrame | None
    ) -> None:
        save_column, download_column = st.columns(2, gap="medium")
        if save_column.button(
            "Save daily log",
            type="primary",
            icon=":material/save:",
            width="stretch",
            disabled=edited is None,
        ):
            self.save_rows(rows, edited)
        try:
            download_column.download_button(
                "Download daily PDF",
                self.api.report(day),
                file_name=f"lunavita-{day.isoformat()}.pdf",
                mime="application/pdf",
                icon=":material/download:",
                width="stretch",
            )
        except httpx.HTTPError:
            download_column.caption("Daily PDF is temporarily unavailable.")

    def render(self, day: date) -> None:
        SectionHeader.with_add_button(
            "Food and nutrition",
            "Log your meals, snacks and supplements for the day.",
            key=f"open-food-entry-{day.isoformat()}",
            on_add=lambda: self.dialog.open(day),
        )
        rows = self.api.food(day)
        edited = None
        if rows:
            edited = self.render_editor(day, rows)
        else:
            st.info("No food entries for this day yet.")
        self.render_actions(day, rows, edited)
        MacroDistributionChart.render(rows)
