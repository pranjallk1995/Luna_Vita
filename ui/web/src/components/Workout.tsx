import { useQueryClient } from "@tanstack/react-query";
import { Check, Save, X } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { useAct, useExercises, useWorkouts, vita, type WorkoutRecord } from "../api";
import { messageOf } from "../lib";
import { WORKOUT_TYPES, exerciseDraft, exerciseErrors, exercisePayload, statusOf, type ExerciseDraft } from "../workouts";
import { Dialog } from "./Dialog";
import { SectionWithAdd } from "./shared";
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

function ExerciseDialog({ day, onClose }: { day: string; onClose: () => void }) {
  const act = useAct();
  const toast = useToast();
  const [error, setError] = useState("");

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
        await vita.addExercises([payload]);
        toast("Exercise saved; the day is marked done");
        onClose();
      } catch (failure) {
        setError(messageOf(failure, "The exercise could not be saved."));
      }
    });
  };

  return (
    <Dialog title="Add exercise" size="large" onClose={onClose}>
      <form className="lv-form" onSubmit={submit}>
        <div className="vt-form-2-1">
          <label className="lv-field">
            Exercise
            <input className="lv-input" name="exercise" maxLength={120} placeholder="Barbell squat" autoFocus />
          </label>
          <label className="lv-field">
            Type
            <select className="lv-select" name="type">
              <TypeOptions />
            </select>
          </label>
        </div>
        <div className="lv-form-row">
          <label className="lv-field">
            Sets
            <input className="lv-input" name="sets" type="number" min="1" max="100" step="1" />
          </label>
          <label className="lv-field">
            Reps
            <input className="lv-input" name="reps" type="number" min="1" max="1000" step="1" />
          </label>
          <label className="lv-field">
            Weight (kg)
            <input className="lv-input" name="weight_kg" type="number" min="0" max="1000" step="0.5" />
          </label>
          <label className="lv-field">
            Duration (min)
            <input className="lv-input" name="duration_min" type="number" min="0.5" max="1440" step="0.5" />
          </label>
        </div>
        <label className="lv-field">
          Notes
          <input className="lv-input" name="notes" maxLength={2000} />
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

function Exercises({ day }: { day: string }) {
  const { data } = useExercises(day);
  const act = useAct();
  const toast = useToast();
  const rows = data ?? [];
  const [drafts, setDrafts] = useState<ExerciseDraft[]>([]);
  const [errors, setErrors] = useState<string[]>([]);
  const table = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!table.current?.contains(window.document.activeElement)) setDrafts((data ?? []).map(exerciseDraft));
  }, [data]);

  if (data && !rows.length) return <p className="lv-caption">No exercises logged for this day yet. Use Add entry to log one.</p>;
  if (!rows.length) return null;

  const change = (id: number, field: keyof ExerciseDraft, value: string | boolean) =>
    setDrafts(drafts.map((draft) => (draft.id === id ? { ...draft, [field]: value } : draft)));

  const save = async () => {
    const problems = exerciseErrors(drafts);
    setErrors(problems);
    if (problems.length) return;
    const originals = new Map(rows.map((row) => [row.id, row]));
    const saved = await act(async () => {
      for (const draft of drafts) {
        const original = originals.get(draft.id);
        if (draft.remove) await vita.deleteExercise(draft.id);
        else if (!original || JSON.stringify(draft) !== JSON.stringify(exerciseDraft(original))) {
          await vita.updateExercise(draft.id, exercisePayload(draft, day));
        }
      }
    }, "The exercises could not be saved.");
    if (saved) toast("Exercises saved");
  };

  const numeric = (draft: ExerciseDraft, at: string, field: "sets" | "reps" | "weight_kg" | "duration_min", label: string, min: string, max: string, step: string) => (
    <td>
      <input type="number" min={min} max={max} step={step} aria-label={`${at} ${label}`} value={draft[field]} onChange={(event) => change(draft.id, field, event.target.value)} />
    </td>
  );

  return (
    <>
      <div className="lv-panel lv-table-scroll" ref={table}>
        <table className="lv-table">
          <thead>
            <tr>
              {["Exercise", "Type", "Sets", "Reps", "Weight (kg)", "Duration (min)", "Notes", "Delete"].map((label) => (
                <th key={label}>{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {drafts.map((draft, index) => {
              const at = `Exercise ${index + 1}`;
              return (
                <tr key={draft.id}>
                  <td>
                    <input className="vt-wide" aria-label={`${at} name`} value={draft.exercise} onChange={(event) => change(draft.id, "exercise", event.target.value)} />
                  </td>
                  <td>
                    <select aria-label={`${at} type`} value={draft.type} onChange={(event) => change(draft.id, "type", event.target.value)}>
                      <TypeOptions />
                    </select>
                  </td>
                  {numeric(draft, at, "sets", "sets", "1", "100", "1")}
                  {numeric(draft, at, "reps", "reps", "1", "1000", "1")}
                  {numeric(draft, at, "weight_kg", "weight", "0", "1000", "0.5")}
                  {numeric(draft, at, "duration_min", "duration", "0.5", "1440", "0.5")}
                  <td>
                    <input className="vt-wide" aria-label={`${at} notes`} value={draft.notes} onChange={(event) => change(draft.id, "notes", event.target.value)} />
                  </td>
                  <td>
                    <input type="checkbox" aria-label={`${at} delete`} checked={draft.remove} onChange={(event) => change(draft.id, "remove", event.target.checked)} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {errors.length > 0 && (
        <div className="vt-errors" role="alert">
          Please correct the exercises before saving:
          <ul>
            {errors.map((problem) => (
              <li key={problem}>{problem}</li>
            ))}
          </ul>
        </div>
      )}
      <button className="lv-button lv-button-primary lv-button-wide" type="button" onClick={save}>
        <Save size={17} />
        Save exercises
      </button>
    </>
  );
}

export function Workout({ day }: { day: string }) {
  const { data } = useWorkouts(day, day);
  const act = useAct();
  const client = useQueryClient();
  const [adding, setAdding] = useState(false);
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
    <>
      <SectionWithAdd
        title="Workout"
        description="Mark the day done or skipped, pick what you trained, and log your exercises."
        onAdd={() => setAdding(true)}
      />
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
      <Exercises day={day} />
      {adding && <ExerciseDialog day={day} onClose={() => setAdding(false)} />}
    </>
  );
}
