"""Luna Vita Streamlit application."""

import base64
import hashlib
import inspect
from io import BytesIO
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import httpx
import streamlit as st
from PIL import Image, ImageOps, UnidentifiedImageError

UI_ROOT = Path(__file__).resolve().parent
LOGO_PATH = UI_ROOT / "assets" / "lunavita_logo.png"


class LunaVitaClock:
    """Provide timezone-aware dates and timestamps for the UI."""

    LOCAL_TIMEZONE = ZoneInfo("Asia/Kolkata")

    @classmethod
    def now(cls) -> datetime:
        return datetime.now(cls.LOCAL_TIMEZONE)

    @classmethod
    def today(cls) -> date:
        return cls.now().date()

    @classmethod
    def combine(cls, day: date, clock_time: time) -> datetime:
        return datetime.combine(day, clock_time, tzinfo=cls.LOCAL_TIMEZONE)


class SourceReloadMonitor:
    """Track deployed UI source and notify existing Streamlit sessions."""

    @staticmethod
    def revision() -> str:
        source_files = sorted(UI_ROOT.rglob("*.py"))
        source_files.append(UI_ROOT / ".streamlit" / "config.toml")
        source_files.append(LOGO_PATH)
        digest = hashlib.sha256()
        for source_file in source_files:
            if not source_file.is_file():
                continue
            digest.update(source_file.relative_to(UI_ROOT).as_posix().encode())
            digest.update(source_file.read_bytes())
        return digest.hexdigest()

    @classmethod
    def notify(cls) -> None:
        revision = cls.revision()
        previous_revision = st.session_state.get("ui_source_revision")
        st.session_state.ui_source_revision = revision
        if previous_revision is not None and previous_revision != revision:
            st.toast("Luna Vita updated", icon=":material/refresh:")


from api import LunaVitaAPI
from config import UIConfig
from styles import LunaStyle


@dataclass
class SummaryView:
    api: LunaVitaAPI
    WARNING_THRESHOLD = 0.85

    @classmethod
    def limit_status(cls, value: float, target: float) -> str:
        if target <= 0:
            return ""
        ratio = value / target
        if ratio > 1:
            return "danger"
        return "warning" if ratio >= cls.WARNING_THRESHOLD else ""

    @staticmethod
    def protein_status(value: float, target: float) -> str:
        return "success" if target > 0 and value >= target else ""

    @staticmethod
    def percentage(value: float, target: float) -> int:
        return round((value / target) * 100) if target > 0 else 0

    @classmethod
    def card_html(
        cls,
        *,
        key: str,
        icon: str,
        label: str,
        value: str,
        target: str,
        amount: float,
        target_amount: float,
        status: str,
    ) -> str:
        percent = cls.percentage(amount, target_amount)
        ring_degrees = min(max(percent, 0), 100) * 3.6
        return (
            f'<div class="nutrition-card {key} {status}">'
            "<div>"
            f'<div class="nutrition-card-label"><span class="nutrition-card-icon">'
            f"{icon}</span>{label}</div>"
            f'<div class="nutrition-card-value">{value}</div>'
            f'<div class="nutrition-card-target">Target {target}</div>'
            "</div>"
            f'<div class="nutrition-ring" style="--ring-value:{ring_degrees:.1f}deg">'
            f"<span>{percent}%</span></div>"
            "</div>"
        )

    def render(self, day: date) -> None:
        summary = self.api.summary(day)
        recommendations = self.api.recommendations()
        if not recommendations:
            st.warning("Daily nutrition recommendations have not been configured.")
            return

        values = {
            "calories": float(summary["calories"]),
            "protein": float(summary["protein_g"]),
            "carbs": float(summary["carbs_g"]),
            "fat": float(summary["fat_g"]),
            "sugars": float(summary["added_sugar_g"]),
        }
        targets = {
            "calories": float(recommendations["calories_kcal"]),
            "protein": float(recommendations["protein_g"]),
            "carbs": float(recommendations["carbs_g"]),
            "fat": float(recommendations["fat_g"]),
            "sugars": float(recommendations["sugars_g"]),
        }
        statuses = {
            key: self.limit_status(values[key], targets[key])
            for key in ("calories", "carbs", "fat", "sugars")
        }
        statuses["protein"] = self.protein_status(values["protein"], targets["protein"])
        calorie_percent = self.percentage(values["calories"], targets["calories"])
        calorie_width = min(max(calorie_percent, 0), 100)
        specs = [
            ("calories", "local_fire_department", "Calories", "kcal", ""),
            ("protein", "fitness_center", "Protein", "g", ""),
            ("carbs", "grain", "Carbs", "g", ""),
            ("fat", "water_drop", "Fat", "g", ""),
            ("sugars", "nutrition", "Added sugar", "g", " max"),
        ]
        cards = []
        for key, icon, label, unit, suffix in specs:
            decimals = 0 if key == "calories" else 1
            current = f"{values[key]:,.{decimals}f} {unit}"
            target_decimals = 0
            target = f"{targets[key]:,.{target_decimals}f} {unit}{suffix}"
            cards.append(
                self.card_html(
                    key=key,
                    icon=icon,
                    label=label,
                    value=current,
                    target=target,
                    amount=values[key],
                    target_amount=targets[key],
                    status=statuses[key],
                )
            )
        panel_html = (
            '<section class="nutrition-panel">'
            '<div class="nutrition-head">'
            '<div class="nutrition-title">'
            "<h2>Today's Nutrition</h2>"
            "<p>Running totals from today's food log</p>"
            "</div>"
            '<div class="nutrition-overall">'
            '<div class="nutrition-overall-row">'
            f"<span>{values['calories']:,.0f} / {targets['calories']:,.0f} kcal</span>"
            f"<strong>{calorie_percent}%</strong>"
            "</div>"
            '<div class="nutrition-track">'
            f'<div class="nutrition-fill" style="width:{calorie_width}%"></div>'
            "</div></div></div>"
            f'<div class="nutrition-cards">{"".join(cards)}</div>'
            "</section>"
        )
        st.markdown(panel_html, unsafe_allow_html=True)


@dataclass
class FoodLogView:
    api: LunaVitaAPI

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

    @staticmethod
    def nullable(value: Any) -> Any:
        return None if pd.isna(value) else value

    @classmethod
    def row_time_sort_key(cls, row: dict[str, Any]) -> tuple[int, time, int]:
        """Return an IST clock key, placing free-form label-only rows last."""
        timestamp_text = str(row.get("consumed_at") or "")
        label = str(row.get("time_label") or "").strip()
        try:
            timestamp = datetime.fromisoformat(timestamp_text)
            if timestamp.tzinfo is not None:
                timestamp = timestamp.astimezone(LunaVitaClock.LOCAL_TIMEZONE)
            clock_time = timestamp.time().replace(tzinfo=None)
        except ValueError:
            return (1, time.max, int(row.get("id") or 0))
        if clock_time == time.min and label:
            return (1, time.max, int(row.get("id") or 0))
        return (0, clock_time, int(row.get("id") or 0))

    @classmethod
    def rows_by_time(cls, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Order timed entries chronologically and keep label-only rows last."""
        return sorted(rows, key=cls.row_time_sort_key)

    @staticmethod
    def uploaded_image_data_url(uploaded_file: Any) -> str:
        """Normalize an uploaded photo into a compact database-safe data URL."""
        try:
            image = ImageOps.exif_transpose(Image.open(uploaded_file))
            image.thumbnail((360, 360), Image.Resampling.LANCZOS)
            if image.mode in {"RGBA", "LA"}:
                rgba = image.convert("RGBA")
                background = Image.new("RGB", rgba.size, (17, 17, 17))
                background.paste(rgba, mask=rgba.getchannel("A"))
                image = background
            else:
                image = image.convert("RGB")
            output = BytesIO()
            image.save(output, format="JPEG", quality=85, optimize=True)
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ValueError("Choose a valid JPG, PNG, or WebP food photo.") from exc
        encoded = base64.b64encode(output.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"

    @staticmethod
    def display_time(row: pd.Series) -> str:
        """Prefer a recorded time and fall back to its historical label."""
        consumed_at = pd.to_datetime(row.get("consumed_at"), errors="coerce")
        time_label = row.get("time_label")
        has_label = not pd.isna(time_label) and bool(str(time_label).strip())
        if not pd.isna(consumed_at) and not (
            consumed_at.hour == 0 and consumed_at.minute == 0 and has_label
        ):
            return consumed_at.strftime("%I:%M %p").lstrip("0")
        return str(time_label).strip() if has_label else "Not recorded"

    @staticmethod
    def resolve_display_time(
        value: Any, original_consumed_at: str
    ) -> tuple[str, str | None]:
        """Convert an edited clock time or free-form label into stored values."""
        original = pd.to_datetime(original_consumed_at)
        text = "" if pd.isna(value) else str(value).strip()
        if not text or text.lower() == "not recorded":
            return (
                LunaVitaClock.combine(original.date(), time.min).isoformat(),
                "Not recorded",
            )
        parsed = pd.to_datetime(text, errors="coerce")
        if not pd.isna(parsed):
            return LunaVitaClock.combine(
                original.date(), parsed.time()
            ).isoformat(), None
        return LunaVitaClock.combine(original.date(), time.min).isoformat(), text

    @staticmethod
    def render_macro_distribution(rows: list[dict[str, Any]]) -> None:
        calories = sum(float(row["calories"]) for row in rows)
        values = [
            sum(float(row["protein_g"]) for row in rows),
            sum(float(row["carbs_g"]) for row in rows),
            sum(float(row["fat_g"]) for row in rows),
            sum(float(row["natural_sugar_g"]) for row in rows),
            sum(float(row["added_sugar_g"]) for row in rows),
        ]
        total = sum(values)
        percentages = (
            [round(value * 100 / total) for value in values]
            if total
            else [0, 0, 0, 0, 0]
        )
        if total:
            percentages[-1] += 100 - sum(percentages)
        colors = ["#4ade80", "#60a5fa", "#fbbf24", "#c084fc", "#fb7185"]
        labels = ["Protein", "Carbs", "Fat", "Natural sugar", "Added sugar"]
        cursor = 0
        segments = []
        for label, value, percentage, color in zip(labels, values, percentages, colors):
            segments.append(
                '<g class="macro-slice">'
                '<circle class="macro-segment" cx="60" cy="60" r="48" '
                'pathLength="100" '
                f'stroke="{color}" color="{color}" '
                f'stroke-dasharray="{percentage} {100 - percentage}" '
                f'stroke-dashoffset="{-cursor}" transform="rotate(-90 60 60)"/>'
                '<text class="macro-tooltip" x="60" y="56" text-anchor="middle">'
                f'<tspan x="60">{label} {percentage}%</tspan>'
                f'<tspan class="macro-tooltip-value" x="60" dy="10">'
                f"{value:,.1f} g"
                "</tspan></text></g>"
            )
            cursor += percentage
        legend = "".join(
            '<div class="macro-row">'
            f'<span class="macro-dot" style="--dot:{color}"></span>'
            f"<span>{label}</span><strong>{percentage}%</strong></div>"
            for label, percentage, color in zip(labels, percentages, colors)
        )
        st.markdown(
            '<div class="food-log-heading"><h2>Macro distribution</h2></div>',
            unsafe_allow_html=True,
        )
        html = (
            '<section class="macro-content">'
            f'<div class="macro-legend">{legend}</div>'
            '<div class="macro-donut"><svg viewBox="0 0 120 120" '
            'role="img" aria-label="Macro distribution">'
            '<circle class="macro-track" cx="60" cy="60" r="48"/>'
            f'{"".join(segments)}</svg>'
            f'<div class="macro-center">{calories:,.0f}<small>kcal</small></div>'
            "</div></section>"
        )
        st.markdown(html, unsafe_allow_html=True)

    def save_rows(self, rows: list[dict[str, Any]], edited: pd.DataFrame) -> None:
        original = {int(row["id"]): row for row in rows}
        for row in edited.to_dict("records"):
            entry_id = int(row["id"])
            if row["remove"]:
                self.api.delete_food(entry_id)
                continue
            consumed_at, time_label = self.resolve_display_time(
                row["display_time"], original[entry_id]["consumed_at"]
            )
            self.api.update_food(
                entry_id,
                {
                    "food_name": str(row["food_name"]).strip(),
                    "quantity": str(row["quantity"]).strip(),
                    "meal_type": original[entry_id]["meal_type"],
                    "calories": int(row["calories"]),
                    "protein_g": float(row["protein_g"]),
                    "carbs_g": float(row["carbs_g"]),
                    "fat_g": float(row["fat_g"]),
                    "natural_sugar_g": float(row["natural_sugar_g"]),
                    "added_sugar_g": float(row["added_sugar_g"]),
                    "image_url": self.nullable(row["image_url"]),
                    "consumed_at": consumed_at,
                    "consumed_date": original[entry_id]["consumed_date"],
                    "time_label": time_label,
                    "notes": self.nullable(row["notes"]),
                },
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
        title_column, action_column = st.columns(
            [5, 1], vertical_alignment="center", gap="medium"
        )
        with title_column:
            st.markdown(
                '<div class="food-log-heading"><h2>Food and nutrition</h2>'
                "<p>Log your meals, snacks and supplements for the day.</p></div>",
                unsafe_allow_html=True,
            )
        with action_column:
            self.add_form(day)
        rows = self.api.food(day)
        edited = None
        if rows:
            frame = pd.DataFrame(self.rows_by_time(rows))[self.COLUMNS]
            frame["display_time"] = frame.apply(self.display_time, axis=1)
            frame.insert(0, "remove", False)
            edited = st.data_editor(
                frame,
                hide_index=True,
                use_container_width=True,
                disabled=["id", "image_url"],
                height=min(680, 88 + 54 * len(frame)),
                row_height=52,
                column_order=[
                    "display_time",
                    "image_url",
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
                ],
                column_config={
                    "remove": st.column_config.CheckboxColumn(
                        "Delete", help="Select rows to delete, then save."
                    ),
                    "display_time": st.column_config.TextColumn("Time", pinned=True),
                    "image_url": st.column_config.ImageColumn(
                        "Image", help="Optional food image", width="small", pinned=True
                    ),
                    "food_name": st.column_config.TextColumn(
                        "Food / supplement", required=True, width="large"
                    ),
                    "quantity": st.column_config.TextColumn(
                        "\u21aa Quantity", required=True, width="medium"
                    ),
                    "calories": st.column_config.NumberColumn(
                        "\u2668 Calories", min_value=0, step=1
                    ),
                    "protein_g": st.column_config.NumberColumn(
                        "\u224b Protein", min_value=0.0
                    ),
                    "carbs_g": st.column_config.NumberColumn(
                        "\u224b Carbs", min_value=0.0
                    ),
                    "fat_g": st.column_config.NumberColumn("\u25c9 Fat", min_value=0.0),
                    "natural_sugar_g": st.column_config.NumberColumn(
                        "\u25c7 Natural sugar", min_value=0.0
                    ),
                    "added_sugar_g": st.column_config.NumberColumn(
                        "\u25c7 Added sugar", min_value=0.0
                    ),
                    "notes": st.column_config.TextColumn("Notes", width="large"),
                },
                key=f"food-editor-{day.isoformat()}",
            )
        else:
            st.info("No food entries for this day yet.")
        self.render_actions(day, rows, edited)
        self.render_macro_distribution(rows)

    def add_form(self, day: date) -> None:
        if st.button(
            "Add entry",
            icon=":material/add:",
            type="primary",
            width="stretch",
            key=f"open-food-entry-{day.isoformat()}",
        ):
            self.add_dialog(day)

    @st.dialog("Add food or supplement", width="large")
    def add_dialog(self, day: date) -> None:
        c1, c2 = st.columns([2, 1.2])
        name = c1.text_input("Food / supplement :red[*]")
        quantity = c2.text_input("Quantity :red[*]", placeholder="30 g, 1 serving...")

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
                "Consumed time",
                LunaVitaClock.now().replace(second=0, microsecond=0).time(),
                step=60,
            )
        else:
            consumed_time = None
            time_column.text_input(
                "Consumed time",
                value="Not recorded",
                disabled=True,
            )

        time_label = st.text_input("Time label", placeholder="Morning, ~4:30 PM...")
        uploaded_image = st.file_uploader(
            "Food photo (optional)",
            type=["jpg", "jpeg", "png", "webp"],
            help="Choose a photo from this device. It will be resized before saving.",
        )
        nutrients = st.columns(6)
        calories = nutrients[0].number_input("Calories kcal", min_value=0, step=1)
        protein = nutrients[1].number_input("Protein g", min_value=0.0, step=0.5)
        carbs = nutrients[2].number_input("Carbs g", min_value=0.0, step=0.5)
        fat = nutrients[3].number_input("Fat g", min_value=0.0, step=0.5)
        natural = nutrients[4].number_input("Natural sugar", min_value=0.0, step=0.5)
        added = nutrients[5].number_input("Added sugar", min_value=0.0, step=0.5)
        notes = st.text_input("Notes", max_chars=2000)
        submitted = st.button(
            "Record food",
            type="primary",
            width="stretch",
            key=f"record-food-{day.isoformat()}",
        )
        if submitted:
            if not name.strip() or not quantity.strip():
                st.warning("Food name and quantity are required.")
                return
            try:
                stored_image = (
                    self.uploaded_image_data_url(uploaded_image)
                    if uploaded_image is not None
                    else None
                )
            except ValueError as exc:
                st.warning(str(exc))
                return
            self.api.create_food(
                {
                    "food_name": name.strip(),
                    "quantity": quantity.strip(),
                    "meal_type": "other",
                    "calories": int(calories),
                    "protein_g": float(protein),
                    "carbs_g": float(carbs),
                    "fat_g": float(fat),
                    "natural_sugar_g": float(natural),
                    "added_sugar_g": float(added),
                    "image_url": stored_image,
                    "consumed_at": LunaVitaClock.combine(
                        consumed_date, consumed_time or time.min
                    ).isoformat(),
                    "consumed_date": consumed_date.isoformat(),
                    "time_label": time_label.strip()
                    or (None if include_time else "Not recorded"),
                    "notes": notes.strip() or None,
                }
            )
            st.toast("Food saved to database")
            st.rerun()


@dataclass
class WeightView:
    api: LunaVitaAPI

    METRICS = {
        "weight": ("Weight", "kg"),
        "bmr": ("BMR", "kcal/day"),
        "health_score": ("Health score", "/100"),
        "body_age": ("Body age", "years"),
        "bmi": ("BMI", "index"),
        "water_ratio": ("Water ratio", "%"),
    }

    @staticmethod
    def period(row: pd.Series) -> str:
        label = str(row.get("time_label") or "").lower()
        if "morning" in label or "am" in label:
            return "Morning"
        if "night" in label or "evening" in label or "pm" in label:
            return "Night"
        return "Morning" if row["measured_at"].hour < 12 else "Night"

    @classmethod
    def format_value(cls, metric: str, value: float, unit: str) -> str:
        if metric == "health_score":
            return f"{value:g}/100"
        if metric == "bmi":
            return f"{value:g}"
        return f"{value:g} {unit}"

    @classmethod
    def measurement_frame(cls, rows: list[dict[str, Any]], day: date) -> pd.DataFrame:
        """Normalize measurements and safely retain only the selected day."""
        frame = pd.DataFrame(rows)
        if frame.empty:
            return pd.DataFrame(
                columns=["metric", "value", "unit", "measured_at", "period"]
            )

        frame["measured_at"] = pd.to_datetime(frame["measured_at"], errors="coerce")
        frame = frame[
            frame["metric"].isin(cls.METRICS)
            & frame["measured_at"].notna()
            & (frame["measured_at"].dt.date == day)
        ].copy()
        if frame.empty:
            frame["period"] = pd.Series(index=frame.index, dtype="object")
        else:
            frame["period"] = frame.apply(cls.period, axis=1)
        return frame

    def render(self, day: date) -> None:
        title_column, action_column = st.columns(
            [5, 1], vertical_alignment="center", gap="medium"
        )
        with title_column:
            st.markdown(
                '<div class="food-log-heading"><h2>Body measurements</h2>'
                "<p>Track morning and night weight, BMR, health score, body age, BMI, and water ratio.</p></div>",
                unsafe_allow_html=True,
            )
        with action_column:
            self.add_form(day)

        frame = self.measurement_frame(self.api.measurements(), day)

        display_rows = []
        for metric, (label, _) in self.METRICS.items():
            display = {
                "Measurement": label,
                "Morning": "Not recorded",
                "Night": "Not recorded",
            }
            if not frame.empty:
                metric_rows = frame[frame["metric"] == metric]
                for period in ("Morning", "Night"):
                    matches = metric_rows[metric_rows["period"] == period].sort_values(
                        "measured_at"
                    )
                    if not matches.empty:
                        row = matches.iloc[-1]
                        display[period] = self.format_value(
                            metric, float(row["value"]), str(row["unit"])
                        )
            display_rows.append(display)

        st.dataframe(
            pd.DataFrame(display_rows),
            hide_index=True,
            use_container_width=True,
        )

        morning_rows = (
            frame[frame["period"] == "Morning"].to_dict("records")
            if not frame.empty
            else []
        )
        night_rows = (
            frame[frame["period"] == "Night"].to_dict("records")
            if not frame.empty
            else []
        )
        with st.container(key="desktop_weight_actions"):
            morning_column, night_column = st.columns(2, gap="medium")
            if morning_column.button(
                "Delete morning weigh-in",
                icon=":material/delete:",
                width="stretch",
                disabled=not morning_rows,
                key=f"delete-morning-desktop-{day.isoformat()}",
            ):
                self.delete_period(morning_rows, "Morning")
            if night_column.button(
                "Delete night weigh-in",
                icon=":material/delete:",
                width="stretch",
                disabled=not night_rows,
                key=f"delete-night-desktop-{day.isoformat()}",
            ):
                self.delete_period(night_rows, "Night")

        with st.container(key="mobile_weight_actions"):
            morning_column, night_column = st.columns(2, gap="small")
            if morning_column.button(
                "Morning",
                icon=":material/delete:",
                width="stretch",
                disabled=not morning_rows,
                key=f"delete-morning-mobile-{day.isoformat()}",
            ):
                self.delete_period(morning_rows, "Morning")
            if night_column.button(
                "Night",
                icon=":material/delete:",
                width="stretch",
                disabled=not night_rows,
                key=f"delete-night-mobile-{day.isoformat()}",
            ):
                self.delete_period(night_rows, "Night")

    def delete_period(self, rows: list[dict[str, Any]], period: str) -> None:
        for row in rows:
            self.api.delete_measurement(int(row["id"]))
        st.toast(f"{period} weigh-in deleted")
        st.rerun()

    def add_form(self, day: date) -> None:
        if st.button(
            "Add entry",
            icon=":material/add:",
            type="primary",
            width="stretch",
            key=f"open-body-entry-{day.isoformat()}",
        ):
            self.add_dialog(day)

    @st.dialog("Add body measurements", width="large")
    def add_dialog(self, day: date) -> None:
        weight = st.number_input(
            "Weight (kg) :red[*]",
            min_value=0.0,
            step=0.1,
            value=None,
        )

        date_col, period_col, toggle_col, time_col = st.columns(
            [1.25, 1.05, 1.2, 1.15], vertical_alignment="bottom"
        )
        include_time = toggle_col.toggle(
            "Include measured time",
            value=True,
            key=f"include-measured-time-{day.isoformat()}",
        )
        measured_date = date_col.date_input("Measured date", value=day)
        period = period_col.selectbox(
            "Morning / night :red[*]",
            ["Morning", "Night"],
            index=0,
        )
        if include_time:
            measured_time = time_col.time_input(
                "Measured time",
                LunaVitaClock.now().replace(second=0, microsecond=0).time(),
                step=60,
            )
        else:
            measured_time = None

        first_row = st.columns(3)
        bmr = first_row[0].number_input(
            "BMR (kcal/day)", min_value=0, step=1, value=None
        )
        health_score = first_row[1].number_input(
            "Health score (/100)",
            min_value=0,
            max_value=100,
            step=1,
            value=None,
        )
        body_age = first_row[2].number_input(
            "Body age (years)", min_value=0, step=1, value=None
        )

        second_row = st.columns(2)
        bmi = second_row[0].number_input("BMI", min_value=0.0, step=0.1, value=None)
        water_ratio = second_row[1].number_input(
            "Water ratio (%)",
            min_value=0.0,
            max_value=100.0,
            step=0.1,
            value=None,
        )
        notes = st.text_input("Notes", max_chars=2000)
        submitted = st.button(
            "Save body measurements",
            type="primary",
            icon=":material/save:",
            width="stretch",
            key=f"submit-body-measurements-{day.isoformat()}",
        )

        if submitted:
            effective_time = measured_time or time.min
            measured_at = LunaVitaClock.combine(
                measured_date, effective_time
            ).isoformat()
            if weight is None:
                st.warning("Weight is required.")
                return
            values = {
                "weight": (weight, "kg"),
                "bmr": (bmr, "kcal/day"),
                "health_score": (health_score, "/100"),
                "body_age": (body_age, "years"),
                "bmi": (bmi, "index"),
                "water_ratio": (water_ratio, "%"),
            }
            payloads = [
                {
                    "metric": metric,
                    "value": float(value),
                    "unit": unit,
                    "measured_at": measured_at,
                    "time_label": period,
                    "notes": notes.strip() or None,
                }
                for metric, (value, unit) in values.items()
                if value is not None
            ]
            if not payloads:
                st.warning("Enter at least one body measurement.")
                return
            self.api.create_measurements(payloads)
            st.toast("Body measurements saved to database")
            st.rerun()


class LunaVitaApp:
    PERIOD_KEY = "nutrition-period"
    LAST_PERIOD_KEY = "nutrition-period-last"

    def __init__(self) -> None:
        self.api = LunaVitaAPI(UIConfig.from_env())

    @classmethod
    def preserve_period_selection(cls) -> None:
        selected = st.session_state.get(cls.PERIOD_KEY)
        if selected is None:
            st.session_state[cls.PERIOD_KEY] = st.session_state.get(
                cls.LAST_PERIOD_KEY, "daily"
            )
        else:
            st.session_state[cls.LAST_PERIOD_KEY] = selected

    def render(self) -> None:
        LunaStyle.apply()
        SourceReloadMonitor.notify()
        selected_day = LunaStyle.header(LunaVitaClock.today(), LOGO_PATH)
        period_labels = {
            "daily": ":material/today: Daily Tracking",
            "weekly": ":material/date_range: Weekly Tracking",
            "monthly": ":material/calendar_month: Monthly Tracking",
        }
        navigation_container = st.container(key="nutrition_navigation")
        active_period = st.session_state.get(
            self.PERIOD_KEY,
            st.session_state.get(self.LAST_PERIOD_KEY, "daily"),
        )
        navigation_container.markdown(
            f'<span class="lv-selected-{active_period}"></span>',
            unsafe_allow_html=True,
        )
        navigation_options = {
            "options": list(period_labels),
            "format_func": period_labels.__getitem__,
            "label_visibility": "collapsed",
            "key": self.PERIOD_KEY,
            "on_change": self.preserve_period_selection,
        }
        if self.PERIOD_KEY not in st.session_state:
            navigation_options["default"] = "daily"
        if "width" in inspect.signature(st.segmented_control).parameters:
            navigation_options["width"] = "stretch"
        period = navigation_container.segmented_control(
            "Nutrition period",
            **navigation_options,
        )
        period = period or st.session_state.get(self.LAST_PERIOD_KEY, "daily")
        if period == "daily":
            SummaryView(self.api).render(selected_day)
            FoodLogView(self.api).render(selected_day)
            WeightView(self.api).render(selected_day)
        elif period == "weekly":
            st.info("Not enough data for the weekly view yet.")
        else:
            st.info("Not enough data for the monthly view yet.")

    @classmethod
    def run(cls) -> None:
        st.set_page_config(
            page_title="Luna Vita",
            page_icon=Image.open(LOGO_PATH),
            layout="wide",
            initial_sidebar_state="collapsed",
        )
        try:
            cls().render()
        except httpx.HTTPError as exc:
            st.error(f"The Luna Vita service is unavailable: {exc}")


if __name__ == "__main__":
    LunaVitaApp.run()
