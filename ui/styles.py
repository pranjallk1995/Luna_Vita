"""Shared presentation styles and branded header for Luna Vita."""

import base64
from datetime import date
from pathlib import Path

import streamlit as st


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
            .food-log-heading { margin:1.2rem 0 .75rem; }
            .food-log-heading h2 { margin:0; color:var(--text); font-size:1.3rem; letter-spacing:-.025em; }
            .food-log-heading p { margin:.25rem 0 0; color:var(--muted); font-size:.78rem; }
            div[data-testid="stHorizontalBlock"]:has(.food-log-heading) { align-items:center; }
            div[data-testid="stHorizontalBlock"]:has(.food-log-heading) .stButton > button { width:100%; }
            div[data-testid="stDataFrame"],div[data-testid="stDataEditor"] { border:1px solid var(--border); border-radius:14px; overflow:hidden; background:rgba(255,255,255,.025); box-shadow:0 12px 30px rgba(0,0,0,.16); }
            .macro-content { display:grid; grid-template-columns:minmax(12rem,1fr) minmax(12rem,1fr); align-items:center; gap:2rem; width:100%; margin:.1rem 0 .4rem; }
            .macro-donut { position:relative; grid-column:2; grid-row:1; width:10rem; height:10rem; margin:auto; }
            .macro-donut svg { display:block; width:100%; height:100%; overflow:visible; }
            .macro-track { fill:none; stroke:rgba(255,255,255,.10); stroke-width:16; }
            .macro-segment { fill:none; stroke-width:16; cursor:help; transition:stroke-width 140ms ease,filter 140ms ease; }
            .macro-slice:hover .macro-segment { stroke-width:21; filter:drop-shadow(0 0 7px currentColor); }
            .macro-tooltip { opacity:0; pointer-events:none; fill:var(--text); font-family:inherit; font-size:7px; font-weight:650; transition:opacity 100ms ease; }
            .macro-tooltip .macro-tooltip-value { fill:var(--muted); font-size:6px; font-weight:500; }
            .macro-slice:hover .macro-tooltip { opacity:1; }
            .macro-center { position:absolute; inset:0; display:grid; place-content:center; text-align:center; pointer-events:none; color:var(--text); font-size:1.1rem; font-weight:750; transition:opacity 100ms ease; }
            .macro-donut:has(.macro-slice:hover) .macro-center { opacity:0; }
            .macro-center small { display:block; margin-top:.1rem; color:var(--muted); font-size:.68rem; font-weight:500; }
            .macro-legend { grid-column:1; grid-row:1; display:grid; gap:.65rem; width:min(100%,20rem); }
            .macro-row { display:grid; grid-template-columns:.65rem 1fr auto; align-items:center; gap:.5rem; color:var(--text); font-size:.75rem; }
            .macro-dot { width:.62rem; height:.62rem; border-radius:50%; background:var(--dot); }
            @media (max-width:620px) { .macro-content { grid-template-columns:1fr; } .macro-legend,.macro-donut { grid-column:1; grid-row:auto; } }
            div[data-testid="stForm"],div[data-testid="stExpander"] { border-color:var(--border); border-radius:14px; background:var(--panel); }
            div[data-baseweb="input"] > div,div[data-baseweb="select"] > div { border-color:var(--border)!important; border-radius:.5rem!important; background:var(--panel)!important; }
            div[data-testid="stNumberInput"] button { background:rgba(255,255,255,.09)!important; color:#d4d4d4!important; border-color:rgba(255,255,255,.14)!important; }
            div[data-testid="stNumberInput"] button:hover { background:rgba(255,255,255,.15)!important; color:#f5f5f5!important; }
            div[data-testid="stNumberInput"] button svg { fill:currentColor!important; stroke:currentColor!important; color:inherit!important; opacity:1!important; }
            div[data-testid="stToggle"] input { accent-color:#8f8f8f!important; }
            div[data-testid="stToggle"] [data-baseweb="checkbox"] > div,
            div[data-testid="stToggle"] input:not(:checked) + div { background:#737373!important; border-color:#8a8a8a!important; }
            div[data-testid="stToggle"] input:checked + div { background:#a3a3a3!important; border-color:#b8b8b8!important; }
            div[data-testid="stToggle"] [data-baseweb="checkbox"] > div::before,
            div[data-testid="stToggle"] input + div::before { background:#d4d4d4!important; }
            .stButton > button,.stDownloadButton > button,div[data-testid="stFormSubmitButton"] > button { min-height:2.625rem!important; border:1px solid var(--border)!important; border-radius:.5rem!important; background:var(--control)!important; color:var(--text)!important; font-weight:650!important; }
            .stButton > button:hover,.stDownloadButton > button:hover,div[data-testid="stFormSubmitButton"] > button:hover { border-color:var(--strong)!important; background:var(--control-hover)!important; transform:translateY(-1px); }
            button[kind="primary"] { border-color:rgba(255,255,255,.28)!important; background:rgba(255,255,255,.16)!important; }
            div[data-testid="stAlert"] { border-radius:.85rem; border-color:var(--border); }
            .st-key-mobile_weight_actions { display:none; }
            @media (max-width:700px) {
                .block-container { padding:.85rem .8rem 2rem; }
                div[data-testid="stHorizontalBlock"]:has(.lv-header) { flex-wrap:wrap!important; }
                div[data-testid="stHorizontalBlock"]:has(.lv-header) > div[data-testid="stColumn"] { flex:1 1 100%!important; width:100%!important; }
                .lv-header { flex-wrap:nowrap!important; gap:.65rem; min-width:0; }
                .lv-header > div { min-width:0; flex:1 1 auto; }
                .lv-mark { flex:0 0 4.25rem; width:4.25rem; height:3.5rem; }
                .lv-title { white-space:nowrap; font-size:clamp(1.55rem,8vw,2rem); }
                .lv-subtitle { display:none; }
                .st-key-nutrition_navigation div[data-testid="stButtonGroup"] button { padding-inline:.55rem!important; }
                .st-key-nutrition_navigation div[data-testid="stButtonGroup"] button p { font-size:0!important; line-height:0!important; }
                .st-key-nutrition_navigation div[data-testid="stButtonGroup"] button span[data-testid="stIconMaterial"],
                .st-key-nutrition_navigation div[data-testid="stButtonGroup"] button .material-symbols-rounded { font-size:1.25rem!important; line-height:1!important; }
                .st-key-desktop_weight_actions { display:none; }
                .st-key-mobile_weight_actions { display:block; }
                .st-key-mobile_weight_actions div[data-testid="stHorizontalBlock"] { flex-wrap:nowrap!important; }
                .st-key-mobile_weight_actions div[data-testid="stColumn"] { min-width:0!important; }
                .st-key-mobile_weight_actions .stButton > button { white-space:nowrap!important; padding-inline:.55rem!important; }
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
    @staticmethod
    def header(default_day: date, logo_path: Path) -> date:
        logo_data = base64.b64encode(logo_path.read_bytes()).decode("ascii")
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
