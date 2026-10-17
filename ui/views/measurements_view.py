"""Body measurements section: Morning/Night table, deletes, and add dialog."""

from datetime import date, time
from typing import Any

import streamlit as st

from api import LunaVitaAPI
from body_measurements import BodyMetrics
from clock import LunaVitaClock
from views.shared import LunaVitaView, SectionHeader


class MeasurementDialog:
    """Modal form for recording one Morning or Night weigh-in."""

    def __init__(self, api: LunaVitaAPI) -> None:
        self.api = api

    @staticmethod
    def metric_inputs() -> dict[str, float | None]:
        first_row = st.columns(3)
        second_row = st.columns(2)
        return {
            "bmr": first_row[0].number_input(
                "BMR (kcal/day)", min_value=0, step=1, value=None
            ),
            "health_score": first_row[1].number_input(
                "Health score (/100)", min_value=0, max_value=100, step=1, value=None
            ),
            "body_age": first_row[2].number_input(
                "Body age (years)", min_value=0, step=1, value=None
            ),
            "bmi": second_row[0].number_input("BMI", min_value=0.0, step=0.1, value=None),
            "water_ratio": second_row[1].number_input(
                "Water ratio (%)", min_value=0.0, max_value=100.0, step=0.1, value=None
            ),
        }

    @st.dialog("Add body measurements", width="large")
    def open(self, day: date) -> None:
        weight = st.number_input("Weight (kg) :red[*]", min_value=0.0, step=0.1, value=None)
        date_col, period_col, toggle_col, time_col = st.columns(
            [1.25, 1.05, 1.2, 1.15], vertical_alignment="bottom"
        )
        include_time = toggle_col.toggle(
            "Include measured time",
            value=True,
            key=f"include-measured-time-{day.isoformat()}",
        )
        measured_date = date_col.date_input("Measured date", value=day)
        period = period_col.selectbox("Morning / night :red[*]", ["Morning", "Night"], index=0)
        measured_time = (
            time_col.time_input("Measured time", LunaVitaClock.current_minute(), step=60)
            if include_time
            else None
        )
        values = {"weight": weight, **self.metric_inputs()}
        notes = st.text_input("Notes", max_chars=2000)
        if not st.button(
            "Save body measurements",
            type="primary",
            icon=":material/save:",
            width="stretch",
            key=f"submit-body-measurements-{day.isoformat()}",
        ):
            return
        if weight is None:
            st.warning("Weight is required.")
            return
        measured_at = LunaVitaClock.combine(measured_date, measured_time or time.min)
        payloads = BodyMetrics.payloads(
            values, measured_at=measured_at.isoformat(), period=period, notes=notes
        )
        self.api.create_measurements(payloads)
        st.toast("Body measurements saved to database")
        st.rerun()


class MeasurementsView(LunaVitaView):
    """Show the day's latest Morning and Night values and allow period deletes."""

    # Desktop and mobile buttons differ only in label; CSS shows one set.
    DELETE_LAYOUTS = (
        ("desktop", "medium", "Delete {period} weigh-in"),
        ("mobile", "small", "{Period}"),
    )

    def __init__(self, api: LunaVitaAPI) -> None:
        super().__init__(api)
        self.dialog = MeasurementDialog(api)

    def delete_period(self, rows: list[dict[str, Any]], period: str) -> None:
        for row in rows:
            self.api.delete_measurement(int(row["id"]))
        st.toast(f"{period} weigh-in deleted")
        st.rerun()

    def render_delete_actions(self, day: date, rows_by_period: dict[str, list]) -> None:
        for layout, gap, label in self.DELETE_LAYOUTS:
            with st.container(key=f"{layout}_weight_actions"):
                columns = st.columns(len(rows_by_period), gap=gap)
                for column, (period, rows) in zip(columns, rows_by_period.items()):
                    if column.button(
                        label.format(period=period.lower(), Period=period),
                        icon=":material/delete:",
                        width="stretch",
                        disabled=not rows,
                        key=f"delete-{period.lower()}-{layout}-{day.isoformat()}",
                    ):
                        self.delete_period(rows, period)

    def render(self, day: date) -> None:
        SectionHeader.with_add_button(
            "Body measurements",
            "Track morning and night weight, BMR, health score, body age, BMI, and water ratio.",
            key=f"open-body-entry-{day.isoformat()}",
            on_add=lambda: self.dialog.open(day),
        )
        frame = BodyMetrics.measurement_frame(self.api.measurements(), day)
        st.dataframe(
            BodyMetrics.display_frame(frame),
            column_order=tuple(BodyMetrics.DISPLAY_COLUMNS),
            hide_index=True,
            use_container_width=True,
        )
        rows_by_period = {
            period: BodyMetrics.rows_for_period(frame, period)
            for period in ("Morning", "Night")
        }
        self.render_delete_actions(day, rows_by_period)
