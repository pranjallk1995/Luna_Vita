"""Workout section: the day's status, what it trained, and its logged exercises."""

import inspect
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

from services.api import LunaVitaAPI
from domain.workouts import ExerciseLog, WorkoutCalendar, WorkoutTypes
from views.shared import LunaVitaView, SectionHeader


class ExerciseDialog:
    """Modal form for logging one exercise on the selected day."""

    def __init__(self, api: LunaVitaAPI) -> None:
        self.api = api

    @st.dialog("Add exercise", width="large")
    def open(self, day: date) -> None:
        name_col, type_col = st.columns([2, 1])
        exercise = name_col.text_input("Exercise :red[*]", max_chars=120, placeholder="Barbell squat")
        kind = type_col.selectbox(
            "Type",
            [None, *WorkoutTypes.TYPES],
            format_func=lambda kind: "None" if kind is None else WorkoutTypes.label(kind),
        )
        sets_col, reps_col, weight_col, duration_col = st.columns(4)
        values = {
            "exercise": exercise,
            "type": kind and WorkoutTypes.label(kind),
            "sets": sets_col.number_input("Sets", min_value=1, max_value=100, step=1, value=None),
            "reps": reps_col.number_input("Reps", min_value=1, max_value=1000, step=1, value=None),
            "weight_kg": weight_col.number_input(
                "Weight (kg)", min_value=0.0, max_value=1000.0, step=0.5, value=None
            ),
            "duration_min": duration_col.number_input(
                "Duration (min)", min_value=0.5, max_value=1440.0, step=0.5, value=None
            ),
            "notes": st.text_input("Notes", max_chars=2000),
        }
        if not st.button(
            "Save exercise",
            type="primary",
            icon=":material/save:",
            width="stretch",
            key=f"submit-exercise-{day.isoformat()}",
        ):
            return
        if not exercise.strip():
            st.warning("Exercise name is required.")
            return
        self.api.add_exercises([ExerciseLog.payload(values, day)])
        st.toast("Exercise saved; the day is marked done")
        st.rerun()


class WorkoutView(LunaVitaView):
    """Record the selected day's workout and exercises; the Monthly tab shows the calendar."""

    LABELS = {
        "done": ":material/check: Done",
        "skipped": ":material/close: Skipped",
    }

    # Widget callbacks run before the next script pass, so the page rendered
    # on that pass already shows the change.
    @staticmethod
    def save(api: LunaVitaAPI, day: date, key: str, record: dict[str, Any] | None) -> None:
        status = st.session_state.get(key)
        notes = record.get("notes") if record else None
        if status is None:  # clicking the active segment clears the record
            api.delete_workout(day)
        elif status == "done":
            types = record.get("types") if record and record["done"] else None
            api.record_workout(day, True, notes, types)
        else:  # a skipped day trained nothing
            api.record_workout(day, False, notes)

    @staticmethod
    def save_types(api: LunaVitaAPI, day: date, key: str, record: dict[str, Any]) -> None:
        api.record_workout(day, True, record.get("notes"), st.session_state.get(key) or [])

    @staticmethod
    def stretch(widget, options: dict[str, Any]) -> dict[str, Any]:
        if "width" in inspect.signature(widget).parameters:
            options["width"] = "stretch"
        return options

    def __init__(self, api: LunaVitaAPI) -> None:
        super().__init__(api)
        self.dialog = ExerciseDialog(api)

    def render(self, day: date) -> None:
        SectionHeader.with_add_button(
            "Workout",
            "Mark the day done or skipped, pick what you trained, and log your exercises.",
            key=f"open-exercise-entry-{day.isoformat()}",
            on_add=lambda: self.dialog.open(day),
        )
        records = self.api.workouts(day, day)
        record = records[0] if records else None
        current = WorkoutCalendar.statuses(records).get(day)
        # Keyed by the stored status so the control follows records made elsewhere (the assistant).
        key = f"workout-{day.isoformat()}-{current}"
        options = {
            "options": list(self.LABELS),
            "format_func": self.LABELS.__getitem__,
            "default": current,
            "label_visibility": "collapsed",
            "key": key,
            "on_change": self.save,
            "args": (self.api, day, key, record),
        }
        with st.container(key="workout_status"):
            st.segmented_control(
                f"Workout on {day:%d %b}", **self.stretch(st.segmented_control, options)
            )
        if current == "done":
            self.render_types(day, record)
        self.render_exercises(day)

    def render_types(self, day: date, record: dict[str, Any]) -> None:
        """Multi-select of what the done workout trained, e.g. back and biceps."""
        types = list(record.get("types") or [])
        key = f"workout-types-{day.isoformat()}-{'-'.join(types)}"
        with st.container(key="workout_types"):
            st.pills(
                f"Trained on {day:%d %b}",
                list(WorkoutTypes.TYPES),
                selection_mode="multi",
                format_func=WorkoutTypes.label,
                default=types,
                label_visibility="collapsed",
                key=key,
                on_change=self.save_types,
                args=(self.api, day, key, record),
            )

    @staticmethod
    def column_config() -> dict[str, Any]:
        number = st.column_config.NumberColumn
        return {
            "remove": st.column_config.CheckboxColumn("Delete", help="Select rows to delete, then save."),
            "exercise": st.column_config.TextColumn("Exercise", required=True, width="medium"),
            "type": st.column_config.SelectboxColumn(
                "Type", options=list(ExerciseLog.TYPE_BY_LABEL)
            ),
            "sets": number("Sets", min_value=1, max_value=100, step=1, format="%d"),
            "reps": number("Reps", min_value=1, max_value=1000, step=1, format="%d"),
            "weight_kg": number("Weight (kg)", min_value=0.0, max_value=1000.0, step=0.5),
            "duration_min": number("Duration (min)", min_value=0.5, max_value=1440.0, step=0.5),
            "notes": st.column_config.TextColumn("Notes", width="medium"),
        }

    def save_exercises(self, day: date, edited: pd.DataFrame) -> None:
        rows = edited.to_dict("records")
        errors = ExerciseLog.errors(rows)
        if errors:
            st.error("Please correct the exercises before saving:\n\n- " + "\n- ".join(errors))
            return
        for row in rows:
            entry_id = int(row["id"])
            if row["remove"]:
                self.api.delete_exercise(entry_id)
            else:
                self.api.update_exercise(entry_id, ExerciseLog.payload(row, day))
        st.toast("Exercises saved")
        st.rerun()

    def render_exercises(self, day: date) -> None:
        """Editable table of the day's exercises with a save action."""
        rows = self.api.exercises(day, day)
        if not rows:
            st.caption("No exercises logged for this day yet. Use Add entry to log one.")
            return
        frame = pd.DataFrame(ExerciseLog.editor_rows(rows))
        # Float columns keep empty cells editable; sets and reps display as whole numbers.
        for field in ExerciseLog.NUMBER_FIELDS:
            frame[field] = pd.to_numeric(frame[field]).astype(float)
        edited = st.data_editor(
            frame,
            hide_index=True,
            use_container_width=True,
            disabled=["id"],
            column_order=["exercise", "type", "sets", "reps", "weight_kg", "duration_min", "notes", "remove"],
            column_config=self.column_config(),
            key=f"exercise-editor-{day.isoformat()}",
        )
        if st.button(
            "Save exercises",
            type="primary",
            icon=":material/save:",
            width="stretch",
            key=f"save-exercises-{day.isoformat()}",
        ):
            self.save_exercises(day, edited)
