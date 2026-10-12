import os
from datetime import date, datetime

import pandas as pd
import requests
import streamlit as st


API_URL = os.getenv("LUNAVITA_API_URL", "http://localhost:18001").rstrip("/")
TIMEOUT = 10

st.set_page_config(page_title="LunaVita", page_icon="LV", layout="wide")
st.title("LunaVita")
st.caption("Private nutrition and health tracking")


def api_request(method: str, path: str, **kwargs):
    response = requests.request(method, f"{API_URL}{path}", timeout=TIMEOUT, **kwargs)
    response.raise_for_status()
    return response.json() if response.content else None


today = date.today()
try:
    summary = api_request("GET", f"/api/summary/{today.isoformat()}")
    cols = st.columns(6)
    cols[0].metric("Calories today", f"{summary['calories']:,}")
    cols[1].metric("Protein", f"{summary['protein_g']:.1f} g")
    cols[2].metric("Carbohydrates", f"{summary['carbs_g']:.1f} g")
    cols[3].metric("Fat", f"{summary['fat_g']:.1f} g")
    cols[4].metric("Natural sugar", f"{summary['natural_sugar_g']:.1f} g")
    cols[5].metric("Added sugar", f"{summary['added_sugar_g']:.1f} g")
except requests.RequestException as exc:
    st.error(f"The LunaVita service is unavailable: {exc}")
    st.stop()

food_tab, daily_tab, measurement_tab, history_tab = st.tabs(
    ["Add food", "Daily log", "Add measurement", "Measurements"]
)

with food_tab:
    nutrition_fields = {
        "calories": "food_calories",
        "protein_g": "food_protein",
        "carbs_g": "food_carbs",
        "fat_g": "food_fat",
        "natural_sugar_g": "food_natural_sugar",
        "added_sugar_g": "food_added_sugar",
    }
    if st.session_state.pop("clear_food_form", False):
        for key in [
            "food_name", "food_quantity", "food_time_label", "food_meal_type",
            "food_calories", "food_protein", "food_carbs", "food_fat",
            "food_natural_sugar", "food_added_sugar", "food_consumed_date",
            "food_consumed_time", "food_notes",
        ]:
            st.session_state.pop(key, None)
    pending = st.session_state.pop("pending_nutrition", None)
    if pending:
        for field, value in pending.items():
            widget_key = nutrition_fields[field]
            if st.session_state.get(widget_key) is None:
                st.session_state[widget_key] = value
    inference_note = st.session_state.get("nutrition_inference_note")
    if inference_note:
        st.info(inference_note)

    with st.form("food_entry", clear_on_submit=False):
        food_name = st.text_input("Food", key="food_name")
        quantity = st.text_input("Quantity", placeholder="30 g, 1 serving, 150 ml...", key="food_quantity")
        time_label = st.text_input("Time label", placeholder="~4:30 PM, late evening...", key="food_time_label")
        meal_type = st.selectbox(
            "Meal", ["breakfast", "lunch", "dinner", "snack", "other"], key="food_meal_type"
        )
        calories = st.number_input("Calories", min_value=0, step=1, value=None, key="food_calories")
        macro_cols = st.columns(3)
        protein = macro_cols[0].number_input(
            "Protein (g)", min_value=0.0, step=0.5, value=None, key="food_protein"
        )
        carbs = macro_cols[1].number_input(
            "Carbohydrates (g)", min_value=0.0, step=0.5, value=None, key="food_carbs"
        )
        fat = macro_cols[2].number_input(
            "Fat (g)", min_value=0.0, step=0.5, value=None, key="food_fat"
        )
        sugar_cols = st.columns(2)
        natural_sugar = sugar_cols[0].number_input(
            "Natural sugar (g)", min_value=0.0, step=0.5, value=None, key="food_natural_sugar"
        )
        added_sugar = sugar_cols[1].number_input(
            "Added sugar (g)", min_value=0.0, step=0.5, value=None, key="food_added_sugar"
        )
        consumed_date_col, consumed_time_col = st.columns(2)
        consumed_date = consumed_date_col.date_input("Consumed date", value=date.today(), key="food_consumed_date")
        consumed_time = consumed_time_col.time_input(
            "Consumed time", value=datetime.now().time(), key="food_consumed_time"
        )
        consumed_at = datetime.combine(consumed_date, consumed_time)
        notes = st.text_area("Notes", max_chars=2000, key="food_notes")
        action_cols = st.columns(2)
        infer_clicked = action_cols[0].form_submit_button("Infer missing nutrition")
        record_clicked = action_cols[1].form_submit_button("Record food", type="primary")

    if infer_clicked:
        current_values = {
            "calories": calories,
            "protein_g": protein,
            "carbs_g": carbs,
            "fat_g": fat,
            "natural_sugar_g": natural_sugar,
            "added_sugar_g": added_sugar,
        }
        missing = [field for field, value in current_values.items() if value is None]
        if not food_name.strip():
            st.warning("Enter a food or supplement name before requesting an estimate.")
        elif not missing:
            st.info("All nutrition fields already have values. Clear any field you want AI to estimate.")
        else:
            try:
                estimate = api_request("POST", "/api/nutrition/infer", json={
                    "food_name": food_name.strip(), "quantity": quantity.strip() or None,
                })
                st.session_state["pending_nutrition"] = {
                    field: estimate[field] for field in missing
                }
                st.session_state["nutrition_inference_note"] = (
                    f"AI estimate ({estimate['confidence']} confidence): {estimate['assumptions']} "
                    "Review and edit every value before recording."
                )
                st.rerun()
            except requests.RequestException:
                st.error("Nutrition inference is unavailable. You can still enter values manually.")

    if record_clicked:
        try:
            api_request("POST", "/api/food", json={
                "food_name": food_name, "quantity": quantity or None, "time_label": time_label or None,
                "meal_type": meal_type, "calories": calories or 0,
                "protein_g": protein or 0, "carbs_g": carbs or 0, "fat_g": fat or 0,
                "natural_sugar_g": natural_sugar or 0, "added_sugar_g": added_sugar or 0,
                "consumed_at": consumed_at.isoformat(), "notes": notes or None,
            })
            st.session_state.pop("nutrition_inference_note", None)
            st.session_state["clear_food_form"] = True
            st.rerun()
        except requests.RequestException as exc:
            st.error(f"Could not record food: {exc}")

with daily_tab:
    selected_day = st.date_input("Day", value=today, key="daily_log_day")
    day_rows = api_request("GET", "/api/food", params={
        "start": selected_day.isoformat(), "end": selected_day.isoformat(), "limit": 500,
    })
    st.caption("Edit cells, mark rows for removal, then save all changes to the database.")
    columns = ["id", "time_label", "meal_type", "food_name", "quantity", "calories",
               "protein_g", "carbs_g", "fat_g", "natural_sugar_g", "added_sugar_g", "notes"]
    frame = pd.DataFrame(day_rows)
    if frame.empty:
        st.info("No food entries for this day yet. Use Add food to create one.")
    else:
        frame = frame[columns]
        frame.insert(0, "remove", False)
        edited = st.data_editor(
            frame, hide_index=True, use_container_width=True, disabled=["id"],
            column_config={
                "remove": st.column_config.CheckboxColumn("Remove"),
                "meal_type": st.column_config.SelectboxColumn(
                    "Meal", options=["breakfast", "lunch", "dinner", "snack", "other"], required=True
                ),
                "time_label": st.column_config.TextColumn("Time"),
                "food_name": st.column_config.TextColumn("Food / supplement", required=True),
                "quantity": st.column_config.TextColumn("Quantity"),
                "calories": st.column_config.NumberColumn("Calories", min_value=0, step=1, required=True),
                "protein_g": st.column_config.NumberColumn("Protein (g)", min_value=0.0),
                "carbs_g": st.column_config.NumberColumn("Carbs (g)", min_value=0.0),
                "fat_g": st.column_config.NumberColumn("Fat (g)", min_value=0.0),
                "natural_sugar_g": st.column_config.NumberColumn("Natural sugar (g)", min_value=0.0),
                "added_sugar_g": st.column_config.NumberColumn("Added sugar (g)", min_value=0.0),
                "notes": st.column_config.TextColumn("Notes"),
            },
            key=f"editor-{selected_day.isoformat()}",
        )
        if st.button("Save daily log", type="primary"):
            original_by_id = {int(row["id"]): row for row in day_rows}
            try:
                for row in edited.to_dict("records"):
                    entry_id = int(row["id"])
                    if row["remove"]:
                        api_request("DELETE", f"/api/food/{entry_id}")
                        continue
                    original = original_by_id[entry_id]
                    api_request("PUT", f"/api/food/{entry_id}", json={
                        "food_name": row["food_name"], "meal_type": row["meal_type"],
                        "quantity": None if pd.isna(row["quantity"]) else row["quantity"],
                        "time_label": None if pd.isna(row["time_label"]) else row["time_label"],
                        "calories": int(row["calories"]), "protein_g": float(row["protein_g"]),
                        "carbs_g": float(row["carbs_g"]), "fat_g": float(row["fat_g"]),
                        "natural_sugar_g": float(row["natural_sugar_g"]),
                        "added_sugar_g": float(row["added_sugar_g"]),
                        "consumed_at": original["consumed_at"],
                        "notes": None if pd.isna(row["notes"]) else row["notes"],
                    })
                st.success("Daily log saved.")
                st.rerun()
            except (requests.RequestException, ValueError, TypeError) as exc:
                st.error(f"Could not save the daily log: {exc}")

    try:
        report = requests.get(f"{API_URL}/api/reports/daily/{selected_day.isoformat()}", timeout=TIMEOUT)
        report.raise_for_status()
        st.download_button("Download daily PDF", data=report.content,
                           file_name=f"lunavita-{selected_day.isoformat()}.pdf", mime="application/pdf")
    except requests.RequestException as exc:
        st.warning(f"PDF report is unavailable: {exc}")

with measurement_tab:
    with st.form("health_measurement", clear_on_submit=True):
        metric = st.text_input("Metric", placeholder="weight, steps, sleep...")
        value = st.number_input("Value", step=0.1)
        unit = st.text_input("Unit", placeholder="kg, steps, hours...")
        measured_date_col, measured_time_col = st.columns(2)
        measured_date = measured_date_col.date_input("Measured date", value=date.today())
        measured_time = measured_time_col.time_input("Measured time", value=datetime.now().time())
        measured_at = datetime.combine(measured_date, measured_time)
        measurement_time_label = st.text_input("Measurement time label", placeholder="Morning, night (10:59 PM)...")
        notes = st.text_area("Measurement notes", max_chars=2000)
        if st.form_submit_button("Record measurement", type="primary"):
            try:
                api_request("POST", "/api/measurements", json={
                    "metric": metric, "value": value, "unit": unit,
                    "measured_at": measured_at.isoformat(), "time_label": measurement_time_label or None,
                    "notes": notes or None,
                })
                st.success("Measurement recorded.")
                st.rerun()
            except requests.RequestException as exc:
                st.error(f"Could not record measurement: {exc}")

with history_tab:
    st.subheader("Health measurements")
    measurement_rows = api_request("GET", "/api/measurements", params={"limit": 100})
    if measurement_rows:
        measurement_frame = pd.DataFrame(measurement_rows)
        st.dataframe(measurement_frame[["measured_at", "time_label", "metric", "value", "unit", "notes"]],
                     use_container_width=True, hide_index=True)
    else:
        st.info("No health measurements yet.")
