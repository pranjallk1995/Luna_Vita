/** Workout types, the done / skipped calendar, and exercise rows. */

import type { Exercise, WorkoutRecord } from "./api";

export const WORKOUT_TYPES: Record<string, { label: string; body: string }> = {
  legs: { label: "Legs", body: '<path d="M8.5 2.5c-.5 2.8-.3 5.6.7 8.2.3.8.3 1.7.1 2.5l-1.1 4.6c-.3 1.4-1.6 2.4-3 2.4H15l-.6-3.4c-.2-1.2 0-2.4.5-3.5.7-1.6.7-3.3 0-4.9.4-2 .3-4.1 0-6"/>' },
  back: { label: "Back", body: '<path d="M5 5.5c2.2-1.6 4.6-2 7-2s4.8.4 7 2l-2.4 6.5.9 8.5H6.5l.9-8.5z"/><path d="M12 6v13"/><path d="M8.5 9.5c1 1 2 1.5 3.5 1.5s2.5-.5 3.5-1.5"/>' },
  chest: { label: "Chest", body: '<path d="M5 5.5c2.2-1.6 4.6-2 7-2s4.8.4 7 2l-2.4 6.5.9 8.5H6.5l.9-8.5z"/><path d="M6.6 7.6c1.6 2.6 3.6 3.2 5.4 2 1.8 1.2 3.8.6 5.4-2"/><path d="M12 13.5v.01M12 16.5v.01"/>' },
  shoulders: { label: "Shoulders", body: '<circle cx="12" cy="5.5" r="2.5"/><path d="M3.5 20v-5.5A4.5 4.5 0 0 1 8 10h8a4.5 4.5 0 0 1 4.5 4.5V20"/><path d="M5 13.2c.8-1.6 2.3-2.4 4-2.2"/><path d="M19 13.2c-.8-1.6-2.3-2.4-4-2.2"/>' },
  biceps: { label: "Biceps", body: '<path d="M3 12.5c1.6-.6 2.7-1.7 4.2-2.9 2.4-1.8 5.6-1.5 7.5.7l1-4.4-1.9-1.7c.2-1 1-1.7 2-1.7h1.7c1 0 1.9.7 2.1 1.7l.4 2.2c.5 2.8.5 5.6.1 8.4-.3 2-2 3.4-4 3.4H3"/>' },
  triceps: { label: "Triceps", body: '<path transform="matrix(1 0 0 -1 0 24)" d="M3 12.5c1.6-.6 2.7-1.7 4.2-2.9 2.4-1.8 5.6-1.5 7.5.7l1-4.4-1.9-1.7c.2-1 1-1.7 2-1.7h1.7c1 0 1.9.7 2.1 1.7l.4 2.2c.5 2.8.5 5.6.1 8.4-.3 2-2 3.4-4 3.4H3"/>' },
  forearms: { label: "Forearms", body: '<path d="M3 18 12.5 9.5l1.8-3c.5-.9 1.4-1.5 2.5-1.5h1.7C20 5 21 6.1 21 7.5v2.5c0 1.4-1.1 2.5-2.5 2.5h-2.3L7 21"/><path d="m12.5 9.5 3.7 3"/>' },
  core: { label: "Core", body: '<rect x="6" y="3" width="12" height="18" rx="4"/><path d="M12 3v18M6.5 9h11M6.5 15h11"/>' },
  cardio: { label: "Cardio", body: '<path d="M12 20s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.3a4.3 4.3 0 0 1 7.5 2.5C19.5 15.4 12 20 12 20z"/><path d="M5 12h3.5l1.5-2.5 2.5 5 1.5-2.5H19"/>' },
  full_body: { label: "Full body", body: '<circle cx="12" cy="4.5" r="2"/><path d="M4.5 9.5 12 9l7.5.5"/><path d="M12 9v6.5"/><path d="M8.5 21l3.5-5.5 3.5 5.5"/>' },
};

export type DayStatus = "done" | "skipped" | "none";

export const statusOf = (record?: WorkoutRecord): DayStatus => (record ? (record.done ? "done" : "skipped") : "none");

/** Whole months covering the range and the selected day, so a day just marked stays visible. */
export function calendarSpan(start: string, end: string, selected: string): [string, string] {
  const first = start < selected ? start : selected;
  const last = end > selected ? end : selected;
  const [year, month] = last.split("-").map(Number);
  return [`${first.slice(0, 7)}-01`, new Date(Date.UTC(year, month, 0)).toISOString().slice(0, 10)];
}

/** The first day of every month the range touches. */
export function monthsBetween(start: string, end: string): string[] {
  const months: string[] = [];
  let [year, month] = start.split("-").map(Number);
  const last = end.slice(0, 7);
  for (;;) {
    const current = `${year}-${String(month).padStart(2, "0")}`;
    if (current > last) return months;
    months.push(`${current}-01`);
    month += 1;
    if (month > 12) [year, month] = [year + 1, 1];
  }
}

/** A month's Monday-first weeks, with null padding days outside the month. */
export function monthWeeks(first: string): (string | null)[][] {
  const [year, month] = first.split("-").map(Number);
  const count = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const lead = (new Date(Date.UTC(year, month - 1, 1)).getUTCDay() + 6) % 7;
  const cells: (string | null)[] = Array(lead).fill(null);
  for (let day = 1; day <= count; day += 1) cells.push(`${first.slice(0, 8)}${String(day).padStart(2, "0")}`);
  while (cells.length % 7) cells.push(null);
  return Array.from({ length: cells.length / 7 }, (_, week) => cells.slice(week * 7, week * 7 + 7));
}

export const monthLabel = (first: string) =>
  new Date(`${first}T00:00:00Z`).toLocaleDateString("en-GB", { month: "long", year: "numeric", timeZone: "UTC" });

export const cellLabel = (day: string) =>
  new Date(`${day}T00:00:00Z`).toLocaleDateString("en-GB", { weekday: "short", day: "2-digit", month: "short", timeZone: "UTC" }).replace(",", "");

export type ExerciseDraft = {
  id: number;
  remove: boolean;
  exercise: string;
  type: string;
  sets: string;
  reps: string;
  weight_kg: string;
  duration_min: string;
  notes: string;
};

const text = (value: unknown) => (value === null || value === undefined ? "" : String(value));

export function exerciseDraft(row: Exercise): ExerciseDraft {
  return {
    id: row.id,
    remove: false,
    exercise: row.exercise,
    type: row.type && row.type in WORKOUT_TYPES ? row.type : "",
    sets: text(row.sets),
    reps: text(row.reps),
    weight_kg: text(row.weight_kg),
    duration_min: text(row.duration_min),
    notes: text(row.notes),
  };
}

const whole = (value: string) => (value.trim() ? Math.trunc(Number(value)) : null);
const decimal = (value: string) => (value.trim() ? Number(value) : null);

/** An exercise payload from a dialog or table row; blanks become nulls. */
export const exercisePayload = (row: Omit<ExerciseDraft, "id" | "remove">, day: string) => ({
  day,
  exercise: row.exercise.trim(),
  type: row.type || null,
  notes: row.notes.trim() || null,
  sets: whole(row.sets),
  reps: whole(row.reps),
  weight_kg: decimal(row.weight_kg),
  duration_min: decimal(row.duration_min),
});

export const exerciseErrors = (rows: ExerciseDraft[]) =>
  rows.flatMap((row, index) => (!row.remove && !row.exercise.trim() ? [`Row ${index + 1}: exercise name is required.`] : []));
