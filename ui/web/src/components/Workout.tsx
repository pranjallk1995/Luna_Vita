import { useQueryClient } from "@tanstack/react-query";
import { Check, Dumbbell, Pencil, Plus, Save, Trash2, X } from "lucide-react";
import { useState, type FormEvent } from "react";

import { useAct, useExercises, useWorkouts, vita, type Exercise, type WorkoutRecord } from "../api";
import { messageOf } from "../lib";
import { WORKOUT_TYPES, exerciseDraft, exercisePayload, statusOf } from "../workouts";
import { Dialog } from "./Dialog";
import { useToast } from "./Toasts";

function TypeOptions() {
  return (
    <>
      <option value="">None</option>
      {Object.entries(WORKOUT_TYPES).map(([kind, { label }]) => (
        <option value={kind} key={kind}>
          {label}
        </option>
      ))}
    </>
  );
}

/** Adds an exercise, or edits one when ``exercise`` is given. */
function ExerciseDialog({ day, exercise, onClose }: { day: string; exercise?: Exercise; onClose: () => void }) {
  const act = useAct();
  const toast = useToast();
  const [error, setError] = useState("");
  const initial = exercise ? exerciseDraft(exercise) : null;

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    const text = (name: string) => String(fields.get(name) ?? "");
    if (!text("exercise").trim()) return setError("Exercise name is required.");
    setError("");
    const payload = exercisePayload(
      { exercise: text("exercise"), type: text("type"), sets: text("sets"), reps: text("reps"), weight_kg: text("weight_kg"), duration_min: text("duration_min"), notes: text("notes") },
      day,
    );
    await act(async () => {
      try {
        if (exercise) {
          await vita.updateExercise(exercise.id, payload);
          toast(`${payload.exercise} saved`);
        } else {
          await vita.addExercises([payload]);
          toast("Exercise saved; the day is marked done");
        }
        onClose();
      } catch (failure) {
        setError(messageOf(failure, "The exercise could not be saved."));
      }
    });
  };

  return (
    <Dialog title={exercise ? `Edit ${exercise.exercise}` : "Add exercise"} size="large" onClose={onClose}>
      <form className="lv-form" onSubmit={submit}>
        <div className="vt-form-2-1">
          <label className="lv-field">
            Exercise
            <input className="lv-input" name="exercise" maxLength={120} placeholder="Barbell squat" defaultValue={initial?.exercise} autoFocus />
          </label>
          <label className="lv-field">
            Type
            <select className="lv-select" name="type" defaultValue={initial?.type ?? ""}>
              <TypeOptions />
            </select>
          </label>
        </div>
        <div className="lv-form-row">
          <label className="lv-field">
            Sets
            <input className="lv-input" name="sets" type="number" min="1" max="100" step="1" defaultValue={initial?.sets} />
          </label>
          <label className="lv-field">
            Reps
            <input className="lv-input" name="reps" type="number" min="1" max="1000" step="1" defaultValue={initial?.reps} />
          </label>
          <label className="lv-field">
            Weight (kg)
            <input className="lv-input" name="weight_kg" type="number" min="0" max="1000" step="0.5" defaultValue={initial?.weight_kg} />
          </label>
          <label className="lv-field">
            Duration (min)
            <input className="lv-input" name="duration_min" type="number" min="0.5" max="1440" step="0.5" defaultValue={initial?.duration_min} />
          </label>
        </div>
        <label className="lv-field">
          Notes
          <input className="lv-input" name="notes" maxLength={2000} defaultValue={initial?.notes} />
        </label>
        {error && <p className="lv-alert lv-alert-error">{error}</p>}
        <button className="lv-button lv-button-primary" type="submit">
          <Save size={17} />
          Save exercise
        </button>
      </form>
    </Dialog>
  );
}

/** "3 × 10 · 40 kg · 12 min", leaving out what was not recorded. */
function detailOf(row: Exercise): string {
  const parts = [
    row.sets && row.reps ? `${row.sets} × ${row.reps}` : row.sets ? `${row.sets} sets` : row.reps ? `${row.reps} reps` : "",
    row.weight_kg ? `${row.weight_kg} kg` : "",
    row.duration_min ? `${row.duration_min} min` : "",
  ].filter(Boolean);
  const kind = row.type && WORKOUT_TYPES[row.type] ? WORKOUT_TYPES[row.type].label : "";
  return [kind, ...parts].filter(Boolean).join(" · ");
}

function Exercises({ day, onEdit }: { day: string; onEdit: (row: Exercise) => void }) {
  const { data } = useExercises(day);
  const act = useAct();
  const toast = useToast();
  const rows = data ?? [];
  if (!rows.length) return null;

  const remove = async (row: Exercise) => {
    const removed = await act(() => vita.deleteExercise(row.id), `${row.exercise} could not be deleted.`);
    // Undo adds it back; the backend gives it a new id.
    const restore = exercisePayload(exerciseDraft(row), day);
    if (removed) toast(`${row.exercise} deleted`, { label: "Undo", run: () => act(() => vita.addExercises([restore]), `${row.exercise} could not be restored.`) });
  };

  return (
    <ul className="vt-exercises" aria-label="Exercises">
      {rows.map((row) => (
        <li key={row.id}>
          <div>
            <strong>{row.exercise}</strong>
            {detailOf(row) && <span>{detailOf(row)}</span>}
          </div>
          <button className="lv-icon-button" type="button" aria-label={`Edit ${row.exercise}`} title="Edit" onClick={() => onEdit(row)}>
            <Pencil size={15} />
          </button>
          <button className="lv-icon-button" type="button" aria-label={`Delete ${row.exercise}`} title="Delete" onClick={() => remove(row)}>
            <Trash2 size={15} />
          </button>
        </li>
      ))}
    </ul>
  );
}

export function Workout({ day }: { day: string }) {
  const { data } = useWorkouts(day, day);
  const act = useAct();
  const client = useQueryClient();
  const [dialog, setDialog] = useState<{ exercise?: Exercise } | null>(null);
  const record = data?.[0];
  const status = statusOf(record);
  const key = ["workouts", day, day];

  /** Show the new state at once, and put it back if the backend refuses. */
  const change = (next: WorkoutRecord[], run: () => Promise<unknown>) => {
    const previous = client.getQueryData<WorkoutRecord[]>(key);
    client.setQueryData(key, next);
    return act(async () => {
      try {
        await run();
      } catch (failure) {
        client.setQueryData(key, previous);
        throw failure;
      }
    }, "The workout could not be saved.");
  };

  const choose = (choice: "done" | "skipped") => {
    // Clicking the active segment clears the record.
    if (status === choice) return change([], () => vita.deleteWorkout(day));
    const done = choice === "done";
    // A skipped day trained nothing.
    const types = done && record?.done ? (record.types ?? []) : [];
    return change([{ workout_date: day, done, notes: record?.notes, types }], () => vita.recordWorkout(day, done, record?.notes, types));
  };

  const toggleType = (kind: string) => {
    const current = record?.types ?? [];
    const types = current.includes(kind) ? current.filter((other) => other !== kind) : [...current, kind];
    return change([{ workout_date: day, done: true, notes: record?.notes, types }], () => vita.recordWorkout(day, true, record?.notes, types));
  };

  return (
    <section className="vt-card" aria-labelledby="workout-title">
      <h3 id="workout-title">
        <Dumbbell size={16} />
        Workout
      </h3>
      <div className="vt-segments" role="group" aria-label={`Workout on ${day}`}>
        <button className={status === "done" ? "vt-segment vt-segment-done" : "vt-segment"} type="button" aria-pressed={status === "done"} onClick={() => choose("done")}>
          <Check size={16} />
          Done
        </button>
        <button className={status === "skipped" ? "vt-segment vt-segment-skipped" : "vt-segment"} type="button" aria-pressed={status === "skipped"} onClick={() => choose("skipped")}>
          <X size={16} />
          Skipped
        </button>
      </div>
      {status === "done" && (
        <div className="vt-pills" role="group" aria-label="Trained">
          {Object.entries(WORKOUT_TYPES).map(([kind, { label }]) => {
            const active = record?.types?.includes(kind) ?? false;
            return (
              <button className={active ? "vt-pill vt-pill-active" : "vt-pill"} type="button" aria-pressed={active} key={kind} onClick={() => toggleType(kind)}>
                {label}
              </button>
            );
          })}
        </div>
      )}
      <Exercises day={day} onEdit={(exercise) => setDialog({ exercise })} />
      <button className="lv-button vt-wide" type="button" onClick={() => setDialog({})}>
        <Plus size={16} />
        Add exercise
      </button>
      {dialog && <ExerciseDialog day={day} exercise={dialog.exercise} onClose={() => setDialog(null)} />}
    </section>
  );
}
