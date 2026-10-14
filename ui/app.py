"""Luna Vita Streamlit application."""

import os
import hashlib
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import streamlit as st


UI_ROOT = Path(__file__).resolve().parent


def source_revision() -> str:
    """Return a stable digest of UI source currently loaded by Streamlit."""
    source_files = sorted(UI_ROOT.rglob("*.py"))
    source_files.append(UI_ROOT / ".streamlit" / "config.toml")
    digest = hashlib.sha256()
    for source_file in source_files:
        if not source_file.is_file():
            continue
        digest.update(source_file.relative_to(UI_ROOT).as_posix().encode())
        digest.update(source_file.read_bytes())
    return digest.hexdigest()


def show_reload_notice() -> None:
    """Notify an existing session only when its loaded UI source changes."""
    revision = source_revision()
    previous_revision = st.session_state.get("ui_source_revision")
    st.session_state.ui_source_revision = revision
    if previous_revision is not None and previous_revision != revision:
        st.toast("Luna Vita updated", icon=":material/refresh:")

@dataclass(frozen=True)
class AppConfig:
    api_url: str
    timeout: float = 10.0

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(os.getenv("LUNAVITA_API_URL", "http://localhost:18001").rstrip("/"))


class LunaVitaAPI:
    """HTTP boundary between the UI and the Luna Vita service."""

    def __init__(self, config: AppConfig) -> None:
        self.base_url = config.api_url
        self.timeout = config.timeout

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = requests.request(
            method, f"{self.base_url}{path}", timeout=self.timeout, **kwargs
        )
        response.raise_for_status()
        return response.json() if response.content else None

    def summary(self, day: date) -> dict[str, Any]:
        return self.request("GET", f"/api/summary/{day.isoformat()}")

    def food(self, day: date) -> list[dict[str, Any]]:
        return self.request(
            "GET",
            "/api/food",
            params={"start": day.isoformat(), "end": day.isoformat(), "limit": 500},
        )

    def create_food(self, payload: dict[str, Any]) -> None:
        self.request("POST", "/api/food", json=payload)

    def update_food(self, entry_id: int, payload: dict[str, Any]) -> None:
        self.request("PUT", f"/api/food/{entry_id}", json=payload)

    def delete_food(self, entry_id: int) -> None:
        self.request("DELETE", f"/api/food/{entry_id}")

    def measurements(self) -> list[dict[str, Any]]:
        return self.request("GET", "/api/measurements", params={"limit": 500})

    def create_measurement(self, payload: dict[str, Any]) -> None:
        self.request("POST", "/api/measurements", json=payload)

    def report(self, day: date) -> bytes:
        response = requests.get(
            f"{self.base_url}/api/reports/daily/{day.isoformat()}", timeout=self.timeout
        )
        response.raise_for_status()
        return response.content


class LunaStyle:
    """Luna Vault-inspired presentation layer."""

    @staticmethod
    def apply() -> None:
        st.markdown(
            """
            <style>
            :root { --bg:#080c18; --panel:#11182a; --border:rgba(148,163,184,.18); --strong:rgba(52,211,153,.42); --muted:#9aa6bd; --accent:#34d399; --soft:rgba(52,211,153,.11); }
            .stApp { background:radial-gradient(circle at 82% -10%,rgba(16,185,129,.12),transparent 30rem),var(--bg); }
            .block-container { max-width:1240px; padding-top:1.35rem; padding-bottom:3rem; }
            header[data-testid="stHeader"] { background:transparent; }
            #MainMenu,footer,div[data-testid="stDecoration"] { display:none; }
            .vita-header { display:flex; align-items:center; gap:.9rem; margin-bottom:1rem; }
            .vita-mark { display:grid; place-items:center; width:2.65rem; height:2.65rem; border:1px solid var(--strong); border-radius:.85rem; background:linear-gradient(145deg,#0f766e,#064e3b); color:#ecfdf5; font-weight:800; box-shadow:0 12px 34px rgba(0,0,0,.22); }
            .vita-title { margin:0; color:#f8fafc; font-size:clamp(1.65rem,3vw,2.15rem); font-weight:720; letter-spacing:-.04em; line-height:1; }
            .vita-subtitle { margin:.32rem 0 0; color:var(--muted); font-size:.84rem; }
            .vita-section { margin:1.2rem 0 .75rem; }
            .vita-eyebrow { color:var(--accent); font-size:.72rem; font-weight:700; letter-spacing:.13em; text-transform:uppercase; }
            .vita-section h2 { margin:.25rem 0; color:#f1f5f9; font-size:1.3rem; letter-spacing:-.025em; }
            .vita-section p { margin:0; color:var(--muted); font-size:.88rem; }
            div[data-testid="stMetric"] { min-height:7rem; padding:1rem; border:1px solid var(--border); border-radius:14px; background:rgba(17,24,42,.68); box-shadow:0 10px 30px rgba(0,0,0,.12); }
            div[data-testid="stMetricValue"] { color:#f8fafc; letter-spacing:-.04em; }
            div[data-testid="stDataFrame"],div[data-testid="stDataEditor"] { border:1px solid var(--border); border-radius:14px; overflow:hidden; }
            div[data-testid="stForm"],div[data-testid="stExpander"] { border-color:var(--border); border-radius:14px; background:rgba(17,24,42,.62); }
            div[data-baseweb="input"] > div,div[data-baseweb="select"] > div { border-color:var(--border)!important; border-radius:.5rem!important; background:rgba(17,24,42,.84)!important; }
            .stButton > button,.stDownloadButton > button,div[data-testid="stFormSubmitButton"] > button { min-height:2.625rem!important; border:1px solid var(--border)!important; border-radius:.5rem!important; background:#121a2d!important; color:#e8edf7!important; font-weight:650!important; }
            .stButton > button:hover,.stDownloadButton > button:hover,div[data-testid="stFormSubmitButton"] > button:hover { border-color:var(--strong)!important; background:#17263a!important; transform:translateY(-1px); }
            button[kind="primary"] { border-color:transparent!important; background:linear-gradient(135deg,#10b981,#0f766e)!important; }
            div[data-testid="stAlert"] { border-radius:.85rem; border-color:var(--border); }
            @media (max-width:700px) { .block-container { padding:.85rem .8rem 2rem; } .vita-subtitle { display:none; } }
            </style>
            """,
            unsafe_allow_html=True,
        )

    @staticmethod
    def header() -> None:
        st.markdown(
            """
            <div class="vita-header">
              <div class="vita-mark">LV</div>
              <div><h1 class="vita-title">Luna Vita</h1>
              <p class="vita-subtitle">Private nutrition and health tracking</p></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    @staticmethod
    def section(eyebrow: str, title: str, description: str) -> None:
        st.markdown(
            f'<div class="vita-section"><div class="vita-eyebrow">{eyebrow}</div>'
            f"<h2>{title}</h2><p>{description}</p></div>",
            unsafe_allow_html=True,
        )


@dataclass
class SummaryView:
    api: LunaVitaAPI

    def render(self, day: date) -> None:
        summary = self.api.summary(day)
        sugar = float(summary["natural_sugar_g"]) + float(summary["added_sugar_g"])
        cards = [
            ("Calories", f"{int(summary['calories']):,} kcal"),
            ("Protein", f"{float(summary['protein_g']):.1f} g"),
            ("Carbs", f"{float(summary['carbs_g']):.1f} g"),
            ("Fat", f"{float(summary['fat_g']):.1f} g"),
            ("Sugars", f"{sugar:.1f} g"),
        ]
        for column, (label, value) in zip(st.columns(5), cards):
            column.metric(label, value)


@dataclass
class FoodLogView:
    api: LunaVitaAPI

    COLUMNS = [
        "id",
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
        "notes",
    ]

    @staticmethod
    def nullable(value: Any) -> Any:
        return None if pd.isna(value) else value

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
            return datetime.combine(original.date(), time.min).isoformat(), "Not recorded"
        parsed = pd.to_datetime(text, errors="coerce")
        if not pd.isna(parsed):
            return datetime.combine(original.date(), parsed.time()).isoformat(), None
        return datetime.combine(original.date(), time.min).isoformat(), text

    def render(self, day: date) -> None:
        LunaStyle.section(
            "Daily log",
            "Food and nutrition",
            "Edit cells directly. Tick Delete for unwanted rows, then select Save daily log.",
        )
        rows = self.api.food(day)
        if rows:
            frame = pd.DataFrame(rows)[self.COLUMNS]
            frame["display_time"] = frame.apply(self.display_time, axis=1)
            frame.insert(0, "remove", False)
            edited = st.data_editor(
                frame,
                hide_index=True,
                use_container_width=True,
                disabled=["id"],
                height=min(640, 88 + 35 * len(frame)),
                column_order=[
                    "remove",
                    "display_time",
                    "food_name",
                    "quantity",
                    "calories",
                    "protein_g",
                    "carbs_g",
                    "fat_g",
                    "natural_sugar_g",
                    "added_sugar_g",
                    "notes",
                ],
                column_config={
                    "remove": st.column_config.CheckboxColumn(
                        "Delete", help="Tick the row, then select Save daily log."
                    ),
                    "display_time": st.column_config.TextColumn("Consumed time"),
                    "food_name": st.column_config.TextColumn(
                        "Food / supplement", required=True, width="large"
                    ),
                    "quantity": st.column_config.TextColumn("Quantity", width="medium"),
                    "calories": st.column_config.NumberColumn(
                        "kcal", min_value=0, step=1
                    ),
                    "protein_g": st.column_config.NumberColumn(
                        "Protein g", min_value=0.0
                    ),
                    "carbs_g": st.column_config.NumberColumn("Carbs g", min_value=0.0),
                    "fat_g": st.column_config.NumberColumn("Fat g", min_value=0.0),
                    "natural_sugar_g": st.column_config.NumberColumn(
                        "Natural sugar g", min_value=0.0
                    ),
                    "added_sugar_g": st.column_config.NumberColumn(
                        "Added sugar g", min_value=0.0
                    ),
                    "notes": st.column_config.TextColumn("Notes", width="large"),
                },
                key=f"food-editor-{day.isoformat()}",
            )
            if st.button("Save daily log", type="primary"):
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
                            "quantity": self.nullable(row["quantity"]),
                            "meal_type": original[entry_id]["meal_type"],
                            "calories": int(row["calories"]),
                            "protein_g": float(row["protein_g"]),
                            "carbs_g": float(row["carbs_g"]),
                            "fat_g": float(row["fat_g"]),
                            "natural_sugar_g": float(row["natural_sugar_g"]),
                            "added_sugar_g": float(row["added_sugar_g"]),
                            "consumed_at": consumed_at,
                            "time_label": time_label,
                            "notes": self.nullable(row["notes"]),
                        },
                    )
                st.toast("Daily log saved")
                st.rerun()
        else:
            st.info("No food entries for this day yet.")
        self.add_form(day)
        try:
            st.download_button(
                "Download daily PDF",
                self.api.report(day),
                file_name=f"lunavita-{day.isoformat()}.pdf",
                mime="application/pdf",
            )
        except requests.RequestException:
            st.caption("Daily PDF is temporarily unavailable.")

    def add_form(self, day: date) -> None:
        with st.expander("Add food or supplement"):
            include_time = st.checkbox(
                "Include consumed time",
                value=True,
                key=f"include-consumed-time-{day.isoformat()}",
            )
            with st.form("food-entry", clear_on_submit=True):
                c1, c2 = st.columns([2, 1.2])
                name = c1.text_input("Food / supplement")
                quantity = c2.text_input("Quantity", placeholder="30 g, 1 serving...")
                consumed_date = st.date_input("Consumed date", value=day)
                if include_time:
                    consumed_time = st.time_input(
                        "Consumed time",
                        datetime.now().replace(second=0, microsecond=0).time(),
                        step=60,
                    )
                else:
                    consumed_time = None
                time_label = st.text_input(
                    "Time label", placeholder="Morning, ~4:30 PM..."
                )
                nutrients = st.columns(6)
                calories = nutrients[0].number_input(
                    "Calories kcal", min_value=0, step=1
                )
                protein = nutrients[1].number_input(
                    "Protein g", min_value=0.0, step=0.5
                )
                carbs = nutrients[2].number_input("Carbs g", min_value=0.0, step=0.5)
                fat = nutrients[3].number_input("Fat g", min_value=0.0, step=0.5)
                natural = nutrients[4].number_input(
                    "Natural sugar", min_value=0.0, step=0.5
                )
                added = nutrients[5].number_input(
                    "Added sugar", min_value=0.0, step=0.5
                )
                notes = st.text_input("Notes", max_chars=2000)
                submitted = st.form_submit_button("Record food", type="primary")
            if submitted:
                if not name.strip():
                    st.warning("Enter a food or supplement name.")
                    return
                self.api.create_food(
                    {
                        "food_name": name.strip(),
                        "quantity": quantity.strip() or None,
                        "meal_type": "other",
                        "calories": int(calories),
                        "protein_g": float(protein),
                        "carbs_g": float(carbs),
                        "fat_g": float(fat),
                        "natural_sugar_g": float(natural),
                        "added_sugar_g": float(added),
                        "consumed_at": datetime.combine(
                            consumed_date, consumed_time or time.min
                        ).isoformat(),
                        "time_label": time_label.strip() or (
                            None if include_time else "Not recorded"
                        ),
                        "notes": notes.strip() or None,
                    }
                )
                st.toast("Food saved to database")
                st.rerun()


@dataclass
class WeightView:
    api: LunaVitaAPI

    @staticmethod
    def period(row: pd.Series) -> str:
        label = str(row.get("time_label") or "").lower()
        if "morning" in label or "am" in label:
            return "Morning"
        if "night" in label or "evening" in label or "pm" in label:
            return "Night"
        return "Morning" if row["measured_at"].hour < 12 else "Night"

    def render(self, day: date) -> None:
        LunaStyle.section(
            "Body measurements",
            "Morning and night weigh-ins",
            "Weight measurements for the selected day, arranged like the daily report.",
        )
        rows = self.api.measurements()
        frame = pd.DataFrame(rows)
        if not frame.empty:
            frame["measured_at"] = pd.to_datetime(frame["measured_at"])
            frame = frame[
                (frame["metric"].str.lower() == "weight")
                & (frame["measured_at"].dt.date == day)
            ].copy()
        display = {
            "Measurement": "Weight",
            "Morning": "Not recorded",
            "Night": "Not recorded",
        }
        if not frame.empty:
            frame["period"] = frame.apply(self.period, axis=1)
            for period in ("Morning", "Night"):
                matches = frame[frame["period"] == period].sort_values("measured_at")
                if not matches.empty:
                    row = matches.iloc[-1]
                    display[period] = f"{float(row['value']):g} {row['unit']}"
        st.dataframe(pd.DataFrame([display]), hide_index=True, use_container_width=True)
        self.add_form(day)

    def add_form(self, day: date) -> None:
        with st.expander("Record weigh-in"):
            with st.form("weight-entry", clear_on_submit=True):
                date_col, period_col, value_col, time_col = st.columns(4)
                measured_date = date_col.date_input("Measured date", value=day)
                period = period_col.selectbox("Period", ["Morning", "Night"])
                value = value_col.number_input("Weight (kg)", min_value=0.0, step=0.1)
                default_time = time(8, 0) if period == "Morning" else time(22, 0)
                measured_time = time_col.time_input("Time", default_time, step=60)
                notes = st.text_input("Notes", max_chars=2000)
                submitted = st.form_submit_button("Record weigh-in", type="primary")
            if submitted:
                self.api.create_measurement(
                    {
                        "metric": "weight",
                        "value": float(value),
                        "unit": "kg",
                        "measured_at": datetime.combine(measured_date, measured_time).isoformat(),
                        "time_label": period,
                        "notes": notes.strip() or None,
                    }
                )
                st.toast("Weigh-in saved to database")
                st.rerun()


class LunaVitaApp:
    def __init__(self) -> None:
        self.api = LunaVitaAPI(AppConfig.from_env())

    def render(self) -> None:
        LunaStyle.apply()
        LunaStyle.header()
        show_reload_notice()
        today = date.today()
        LunaStyle.section(
            "Daily overview",
            "So far today",
            "Running nutrition totals calculated from today's saved food log.",
        )
        SummaryView(self.api).render(today)
        selected_day = st.date_input("Log date", value=today)
        FoodLogView(self.api).render(selected_day)
        WeightView(self.api).render(selected_day)


def main() -> None:
    st.set_page_config(
        page_title="Luna Vita",
        page_icon="LV",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    try:
        LunaVitaApp().render()
    except requests.RequestException as exc:
        st.error(f"The Luna Vita service is unavailable: {exc}")


if __name__ == "__main__":
    main()
