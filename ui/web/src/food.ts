/** Pure conversions between stored food entries and their editable form, and the backend's rules. */

import type { FoodEntry } from "./api";
import { combine, moment, type Zone } from "./clock";

export const NOT_RECORDED = "Not recorded";

/** A recorded time, or its historical label; a midnight stamp with a label means no clock was logged. */
export function displayTime(entry: Pick<FoodEntry, "consumed_at" | "time_label">, zone: Zone): string {
  const at = moment(entry.consumed_at, zone);
  const label = (entry.time_label ?? "").trim();
  if (at && !(at.hour === 0 && at.minute === 0 && label)) {
    const hour = at.hour % 12 || 12;
    return `${hour}:${String(at.minute).padStart(2, "0")} ${at.hour < 12 ? "AM" : "PM"}`;
  }
  return label || NOT_RECORDED;
}

/** Timed entries chronologically; label-only rows come last. */
export function byTime<T extends Pick<FoodEntry, "id" | "consumed_at" | "time_label">>(rows: T[], zone: Zone): T[] {
  const key = (row: T): [number, number, number] => {
    const at = moment(row.consumed_at, zone);
    const label = (row.time_label ?? "").trim();
    if (!at || (at.hour === 0 && at.minute === 0 && label)) return [1, Infinity, row.id];
    return [0, at.hour * 60 + at.minute, row.id];
  };
  return [...rows].sort((left, right) => {
    const [a, b] = [key(left), key(right)];
    return a[0] - b[0] || a[1] - b[1] || a[2] - b[2];
  });
}

/** An edited clock time such as "7:30 PM" or "19:30" as HH:MM; null for free-form text. */
export function parseClock(text: string): string | null {
  const match = /^(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)?$/i.exec(text.trim());
  if (!match) return null;
  const meridiem = match[3]?.[0].toLowerCase();
  if (!match[2] && !meridiem) return null;
  let hour = Number(match[1]);
  const minute = Number(match[2] ?? 0);
  if (minute > 59 || hour > (meridiem ? 12 : 23) || (meridiem && hour === 0)) return null;
  if (meridiem === "p" && hour < 12) hour += 12;
  if (meridiem === "a" && hour === 12) hour = 0;
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

/** An edited time cell as the stored timestamp and label, on the entry's own day. */
export function resolveTime(text: string, originalConsumedAt: string, zone: Zone): { consumed_at: string; time_label: string | null } {
  const day = moment(originalConsumedAt, zone)?.day ?? originalConsumedAt.slice(0, 10);
  const midnight = combine(day, "00:00", zone);
  const value = text.trim();
  if (!value || value.toLowerCase() === NOT_RECORDED.toLowerCase()) return { consumed_at: midnight, time_label: NOT_RECORDED };
  const clock = parseClock(value);
  return clock ? { consumed_at: combine(day, clock, zone), time_label: null } : { consumed_at: midnight, time_label: value };
}

const EMOJI = /[\u{1F1E6}-\u{1F1FF}\u{1F300}-\u{1FAFF}\u2600-\u27BF\uFE0F\u200D]/u;
const CONTROL = /[\p{C}]/u;

export function textError(value: unknown, label: string, required: boolean, maxLength: number): string | null {
  const text = String(value ?? "").trim();
  if (required && !text) return `${label} cannot be blank.`;
  if (text.length > maxLength) return `${label} must be ${maxLength} characters or fewer.`;
  if (EMOJI.test(text)) return `${label} cannot contain emojis.`;
  if (CONTROL.test(text.replace(/[\n\t]/g, ""))) return `${label} contains unsupported control characters.`;
  return null;
}

export function numberError(value: unknown, label: string, maximum: number, whole: boolean): string | null {
  const text = String(value ?? "").trim();
  const parsed = text === "" ? NaN : Number(text);
  if (!Number.isFinite(parsed)) return `${label} must be a valid number.`;
  if (parsed < 0) return `${label} cannot be negative.`;
  if (parsed > maximum) return `${label} cannot exceed ${maximum.toLocaleString("en-US")}.`;
  if (whole && !Number.isInteger(parsed)) return `${label} must be a whole number.`;
  return null;
}

export type FoodDraft = {
  id: number;
  remove: boolean;
  time: string;
  food_name: string;
  quantity: string;
  calories: string;
  protein_g: string;
  carbs_g: string;
  fat_g: string;
  natural_sugar_g: string;
  added_sugar_g: string;
  notes: string;
};

const NUMBER_FIELDS = [
  ["calories", "Calories", 100_000, true],
  ["protein_g", "Protein", 10_000, false],
  ["carbs_g", "Carbs", 10_000, false],
  ["fat_g", "Fat", 10_000, false],
  ["natural_sugar_g", "Natural sugar", 10_000, false],
  ["added_sugar_g", "Added sugar", 10_000, false],
] as const;

/** Every problem in rows that are not marked for deletion. */
export function foodErrors(rows: FoodDraft[]): string[] {
  return rows.flatMap((row, index) => {
    if (row.remove) return [];
    const at = `Row ${index + 1}`;
    return [
      textError(row.food_name, `${at} Food / supplement`, true, 200),
      textError(row.quantity, `${at} Quantity`, true, 300),
      textError(row.time, `${at} Time`, false, 100),
      textError(row.notes, `${at} Notes`, false, 2000),
      ...NUMBER_FIELDS.map(([field, label, maximum, whole]) => numberError(row[field], `${at} ${label}`, maximum, whole)),
    ].filter((error): error is string => error !== null);
  });
}

export function draftOf(entry: FoodEntry, zone: Zone): FoodDraft {
  return {
    id: entry.id,
    remove: false,
    time: displayTime(entry, zone),
    food_name: entry.food_name,
    quantity: entry.quantity,
    calories: String(entry.calories),
    protein_g: String(entry.protein_g),
    carbs_g: String(entry.carbs_g),
    fat_g: String(entry.fat_g),
    natural_sugar_g: String(entry.natural_sugar_g),
    added_sugar_g: String(entry.added_sugar_g),
    notes: entry.notes ?? "",
  };
}

/** An edited row merged onto the stored entry it came from. */
export function payloadOf(draft: FoodDraft, original: FoodEntry, zone: Zone) {
  return {
    food_name: draft.food_name.trim(),
    quantity: draft.quantity.trim(),
    meal_type: original.meal_type,
    calories: Math.trunc(Number(draft.calories)),
    protein_g: Number(draft.protein_g),
    carbs_g: Number(draft.carbs_g),
    fat_g: Number(draft.fat_g),
    natural_sugar_g: Number(draft.natural_sugar_g),
    added_sugar_g: Number(draft.added_sugar_g),
    image_url: original.image_url ?? null,
    consumed_date: original.consumed_date,
    notes: draft.notes.trim() ? draft.notes : null,
    ...resolveTime(draft.time, original.consumed_at, zone),
  };
}
