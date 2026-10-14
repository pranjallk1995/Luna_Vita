"""Luna Vita Streamlit application."""

import os
import base64
import hashlib
import inspect
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import streamlit as st
from PIL import Image

UI_ROOT = Path(__file__).resolve().parent
LOGO_PATH = UI_ROOT / "assets" / "luna-vita-logo.png"


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

    def recommendations(self) -> dict[str, Any] | None:
        return self.request("GET", "/api/recommendations")

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

    def create_measurements(self, payloads: list[dict[str, Any]]) -> None:
        self.request("POST", "/api/measurements/batch", json={"measurements": payloads})

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
            :root { --bg:#111111; --panel:rgba(255,255,255,.055); --control:rgba(255,255,255,.07); --control-hover:rgba(255,255,255,.12); --text:#f5f5f5; --muted:#a3a3a3; --border:rgba(255,255,255,.14); --strong:rgba(255,255,255,.34); --accent:#f5f5f5; --soft:rgba(255,255,255,.09); }
            .stApp { color:var(--text); background:radial-gradient(circle at 82% -10%,rgba(255,255,255,.07),transparent 30rem),var(--bg); }
            .block-container { max-width:1180px; padding-top:1.35rem; padding-bottom:3rem; }
            header[data-testid="stHeader"] { background:transparent; }
            #MainMenu,footer,div[data-testid="stDecoration"] { display:none; }
            div[data-testid="stHorizontalBlock"]:has(.lv-header) { align-items:center; margin-bottom:.55rem; }
            div[data-testid="stHorizontalBlock"]:has(.lv-header) .stButton > button { white-space:nowrap; }
            div[data-testid="stHorizontalBlock"]:has(.lv-header) > div:last-child div[data-testid="stDateInput"] { width:100%; margin-left:auto; }
            div[data-testid="stHorizontalBlock"]:has(.lv-header) > div:last-child div[data-testid="stDateInput"] > div { width:100%; }
            div[data-testid="stHorizontalBlock"]:has(.lv-header) > div:last-child div[data-baseweb="input"] { min-height:2.625rem; border-color:var(--strong)!important; background:var(--control)!important; }
            .lv-header { display:flex; align-items:center; gap:1rem; min-height:4.5rem; margin-bottom:1rem; }
            .lv-date-anchor { height:0; overflow:hidden; }
            div[data-testid="stButtonGroup"] { gap:.2rem; margin:.2rem 0 1.15rem; padding:.4rem; border:1px solid var(--border); border-radius:.9rem; background:var(--panel); }
            div[data-testid="stButtonGroup"] button { min-height:2.55rem!important; border:0!important; border-radius:.65rem!important; box-shadow:none!important; }
            .st-key-nutrition_navigation div[data-testid="stButtonGroup"] button { margin-inline:.16rem!important; padding-inline:1rem!important; border:0!important; background:transparent!important; box-shadow:none!important; transition:background 140ms ease,transform 140ms ease!important; }
            .st-key-nutrition_navigation div[data-testid="stButtonGroup"] button:hover { background:transparent!important; transform:translateY(-1px)!important; }
            .st-key-nutrition_navigation div[data-testid="stButtonGroup"] button[aria-pressed="true"] { background:rgba(255,255,255,.12)!important; }
            .lv-mark { display:block; flex:0 0 5.75rem; width:5.75rem; height:4.5rem; border:0; border-radius:0; object-fit:contain; object-position:center; box-shadow:none; }
            .lv-title { margin:0; color:var(--text); font-family:inherit; font-size:clamp(1.65rem,3vw,2.15rem); font-weight:720; letter-spacing:-.04em; line-height:1; }
            .lv-subtitle { margin:.32rem 0 0; color:var(--muted); font-size:.84rem; }
            .vita-section { margin:1.2rem 0 .75rem; }
            .vita-eyebrow { color:var(--accent); font-size:.72rem; font-weight:700; letter-spacing:.13em; text-transform:uppercase; }
            .vita-section h2 { margin:.25rem 0; color:var(--text); font-size:1.3rem; letter-spacing:-.025em; }
            .vita-section p { margin:0; color:var(--muted); font-size:.88rem; }
            div[data-testid="stMetric"] { min-height:7rem; padding:1rem; border:1px solid var(--border); border-radius:14px; background:var(--panel); box-shadow:0 10px 30px rgba(0,0,0,.12); }
            div[data-testid="stMetricValue"] { color:var(--text); letter-spacing:-.04em; }
            .nutrition-panel { padding:0; margin:.35rem 0 1.15rem; border:0; border-radius:0; background:transparent; box-shadow:none; }
            .nutrition-head { display:flex; align-items:end; justify-content:space-between; gap:2rem; margin-bottom:.9rem; }
            .nutrition-title h2 { margin:0; color:var(--text); font-size:1.08rem; letter-spacing:-.02em; }
            .nutrition-title p { margin:.22rem 0 0; color:var(--muted); font-size:.72rem; }
            .nutrition-overall { width:min(31%,20rem); min-width:15rem; }
            .nutrition-overall-row { display:flex; justify-content:space-between; gap:.8rem; margin-bottom:.38rem; color:var(--text); font-size:.72rem; }
            .nutrition-overall-row strong { color:#fb7185; }
            .nutrition-track { height:.42rem; overflow:hidden; border-radius:999px; background:rgba(255,255,255,.10); }
            .nutrition-fill { height:100%; border-radius:inherit; background:linear-gradient(90deg,#fb7185,#f43f5e); box-shadow:0 0 12px rgba(244,63,94,.35); }
            .nutrition-cards { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:.65rem; }
            .nutrition-card { --card-accent:#94a3b8; --card-rgb:148,163,184; display:grid; grid-template-columns:minmax(0,1fr) 3.45rem; align-items:center; min-width:0; min-height:5.9rem; padding:.8rem .75rem; border:1px solid rgba(var(--card-rgb),.12); border-radius:12px; background:linear-gradient(135deg,rgba(var(--card-rgb),.13),rgba(var(--card-rgb),.035)); }
            .nutrition-card.calories,.nutrition-card.protein,.nutrition-card.carbs,.nutrition-card.fat,.nutrition-card.sugars { --card-accent:#f5f5f5; --card-rgb:245,245,245; }
            .nutrition-card.warning { --card-accent:#facc15; --card-rgb:250,204,21; border-color:rgba(250,204,21,.28); }
            .nutrition-card.danger { --card-accent:#fb7185; --card-rgb:251,113,133; border-color:rgba(251,113,133,.34); }
            .nutrition-card.success { --card-accent:#4ade80; --card-rgb:74,222,128; border-color:rgba(74,222,128,.28); }
            .nutrition-card-label { display:flex; align-items:center; gap:.38rem; color:#d4d4d4; font-size:.72rem; white-space:nowrap; }
            .nutrition-card-icon { color:var(--card-accent); font-family:"Material Symbols Rounded","Material Symbols Outlined"; font-size:1.05rem; font-weight:400; font-style:normal; line-height:1; letter-spacing:normal; text-transform:none; white-space:nowrap; word-wrap:normal; direction:ltr; font-feature-settings:"liga"; -webkit-font-feature-settings:"liga"; -webkit-font-smoothing:antialiased; }
            .nutrition-card-value { margin:.32rem 0 .18rem; color:var(--card-accent); font-size:1.18rem; font-weight:700; letter-spacing:-.03em; white-space:nowrap; }
            .nutrition-card-target { color:var(--muted); font-size:.66rem; white-space:nowrap; }
            .nutrition-ring { --ring-value:0deg; position:relative; display:grid; place-items:center; width:3.15rem; height:3.15rem; margin-left:auto; border-radius:50%; background:conic-gradient(var(--card-accent) var(--ring-value),rgba(255,255,255,.10) 0); }
            .nutrition-ring::after { content:""; position:absolute; inset:.38rem; border-radius:50%; background:#13171d; }
            .nutrition-ring span { position:relative; z-index:1; color:var(--card-accent); font-size:.68rem; font-weight:750; }
            @media (max-width:900px) { .nutrition-cards { grid-template-columns:repeat(2,minmax(0,1fr)); } .nutrition-head { align-items:start; flex-direction:column; gap:.8rem; } .nutrition-overall { width:100%; min-width:0; } }
            @media (max-width:520px) { .nutrition-cards { grid-template-columns:1fr; } }
            div[data-testid="stDataFrame"],div[data-testid="stDataEditor"] { border:1px solid var(--border); border-radius:14px; overflow:hidden; }
            div[data-testid="stForm"],div[data-testid="stExpander"] { border-color:var(--border); border-radius:14px; background:var(--panel); }
            div[data-baseweb="input"] > div,div[data-baseweb="select"] > div { border-color:var(--border)!important; border-radius:.5rem!important; background:var(--panel)!important; }
            .stButton > button,.stDownloadButton > button,div[data-testid="stFormSubmitButton"] > button { min-height:2.625rem!important; border:1px solid var(--border)!important; border-radius:.5rem!important; background:var(--control)!important; color:var(--text)!important; font-weight:650!important; }
            .stButton > button:hover,.stDownloadButton > button:hover,div[data-testid="stFormSubmitButton"] > button:hover { border-color:var(--strong)!important; background:var(--control-hover)!important; transform:translateY(-1px); }
            button[kind="primary"] { border-color:rgba(255,255,255,.28)!important; background:rgba(255,255,255,.16)!important; }
            div[data-testid="stAlert"] { border-radius:.85rem; border-color:var(--border); }
            @media (max-width:700px) { .block-container { padding:.85rem .8rem 2rem; } div[data-testid="stHorizontalBlock"]:has(.lv-header) { flex-wrap:wrap!important; } div[data-testid="stHorizontalBlock"]:has(.lv-header) > div[data-testid="stColumn"] { flex:1 1 100%!important; width:100%!important; } .lv-subtitle { display:none; } }
            </style>
            """,
            unsafe_allow_html=True,
        )

    @staticmethod
    def header(default_day: date) -> date:
        logo_data = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
        brand_column, date_column = st.columns(
            [5, 4], vertical_alignment="center", gap="medium"
        )
        with brand_column:
            st.markdown(
                f"""
                <div class="lv-header">
                    <img class="lv-mark"
                         src="data:image/png;base64,{logo_data}"
                         alt="Luna Vita logo">
                    <div>
                        <h1 class="lv-title">Luna Vita</h1>
                        <p class="lv-subtitle">Private AI-managed nutrition tracking</p>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with date_column:
            st.markdown('<div class="lv-date-anchor"></div>', unsafe_allow_html=True)
            return st.date_input(
                "Log date",
                value=default_day,
                key="header-log-date",
                label_visibility="collapsed",
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
            return (
                datetime.combine(original.date(), time.min).isoformat(),
                "Not recorded",
            )
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
                            "consumed_date": original[entry_id]["consumed_date"],
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

    def render(self, day: date) -> None:
        LunaStyle.section(
            "Body measurements",
            "Morning and night check-ins",
            "Weight, BMR, health score, body age, BMI, and water ratio for the selected day.",
        )
        rows = self.api.measurements()
        frame = pd.DataFrame(rows)
        if not frame.empty:
            frame["measured_at"] = pd.to_datetime(frame["measured_at"])
            frame = frame[
                frame["metric"].isin(self.METRICS)
                & (frame["measured_at"].dt.date == day)
            ].copy()
            frame["period"] = frame.apply(self.period, axis=1)

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
            pd.DataFrame(display_rows), hide_index=True, use_container_width=True
        )
        self.add_form(day)

    def add_form(self, day: date) -> None:
        with st.expander("Record body measurements"):
            with st.form("body-measurement-entry", clear_on_submit=True):
                date_col, period_col, time_col = st.columns(3)
                measured_date = date_col.date_input("Measured date", value=day)
                period = period_col.selectbox("Period", ["Morning", "Night"])
                default_time = time(8, 0) if period == "Morning" else time(22, 0)
                measured_time = time_col.time_input("Time", default_time, step=60)

                first_row = st.columns(3)
                weight = first_row[0].number_input(
                    "Weight (kg)", min_value=0.0, step=0.1, value=None
                )
                bmr = first_row[1].number_input(
                    "BMR (kcal/day)", min_value=0, step=1, value=None
                )
                health_score = first_row[2].number_input(
                    "Health score (/100)",
                    min_value=0,
                    max_value=100,
                    step=1,
                    value=None,
                )

                second_row = st.columns(3)
                body_age = second_row[0].number_input(
                    "Body age (years)", min_value=0, step=1, value=None
                )
                bmi = second_row[1].number_input(
                    "BMI", min_value=0.0, step=0.1, value=None
                )
                water_ratio = second_row[2].number_input(
                    "Water ratio (%)",
                    min_value=0.0,
                    max_value=100.0,
                    step=0.1,
                    value=None,
                )
                notes = st.text_input("Notes", max_chars=2000)
                submitted = st.form_submit_button(
                    "Save body measurements", type="primary"
                )

            if submitted:
                measured_at = datetime.combine(measured_date, measured_time).isoformat()
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
    def __init__(self) -> None:
        self.api = LunaVitaAPI(AppConfig.from_env())

    def render(self) -> None:
        LunaStyle.apply()
        SourceReloadMonitor.notify()
        selected_day = LunaStyle.header(date.today())
        period_labels = {
            "daily": ":material/today: Daily Tracking",
            "weekly": ":material/date_range: Weekly Tracking",
            "monthly": ":material/calendar_month: Monthly Tracking",
        }
        navigation_container = st.container(key="nutrition_navigation")
        navigation_options = {
            "options": list(period_labels),
            "default": "daily",
            "format_func": period_labels.__getitem__,
            "label_visibility": "collapsed",
            "key": "nutrition-period",
        }
        if "width" in inspect.signature(st.segmented_control).parameters:
            navigation_options["width"] = "stretch"
        period = navigation_container.segmented_control(
            "Nutrition period",
            **navigation_options,
        )
        if period == "daily":
            SummaryView(self.api).render(selected_day)
            FoodLogView(self.api).render(selected_day)
            WeightView(self.api).render(selected_day)

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
        except requests.RequestException as exc:
            st.error(f"The Luna Vita service is unavailable: {exc}")


if __name__ == "__main__":
    LunaVitaApp.run()
