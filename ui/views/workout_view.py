"""Workout section: mark the selected day's workout done or skipped."""

import inspect
from datetime import date

import streamlit as st

from services.api import LunaVitaAPI
from domain.workouts import WorkoutCalendar
from views.shared import LunaVitaView, SectionHeader


class WorkoutView(LunaVitaView):
    """Record the selected day's workout; the Monthly tab shows the calendar."""

    LABELS = {
        "done": ":material/check: Done",
        "skipped": ":material/close: Skipped",
    }

    # Widget callbacks run before the next script pass, so the page rendered
    # on that pass already shows the change.
    @staticmethod
    def save(api: LunaVitaAPI, day: date, key: str) -> None:
        status = st.session_state.get(key)
        if status is None:  # clicking the active segment clears the record
            api.delete_workout(day)
        else:
            api.record_workout(day, status == "done")

    def render(self, day: date) -> None:
        SectionHeader.heading(
            "Workout",
            "Mark the selected day done or skipped; click the active choice again to clear it.",
        )
        current = WorkoutCalendar.statuses(self.api.workouts(day, day)).get(day)
        # Keyed by the stored status so the control follows records made elsewhere (the assistant).
        key = f"workout-{day.isoformat()}-{current}"
        options = {
            "options": list(self.LABELS),
            "format_func": self.LABELS.__getitem__,
            "default": current,
            "label_visibility": "collapsed",
            "key": key,
            "on_change": self.save,
            "args": (self.api, day, key),
        }
        if "width" in inspect.signature(st.segmented_control).parameters:
            options["width"] = "stretch"
        with st.container(key="workout_status"):
            st.segmented_control(f"Workout on {day:%d %b}", **options)
