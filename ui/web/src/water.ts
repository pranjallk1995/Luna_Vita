/** Water: amounts, the day's progress against the goal, and the quick-add sizes. */

import { moment, type Zone } from "./clock";

/** One tap adds a glass, a bottle, or a large bottle. */
export const QUICK_ADD_ML = [250, 500, 750] as const;
export const MAX_DRINK_ML = 5000;
export const GOAL_LIMITS_ML = [500, 10000] as const;

/** "1,250 ml", or "1.25 L" from a litre up when ``litres`` is set. */
export function formatMl(ml: number, litres = false): string {
  if (litres && ml >= 1000) return `${Number((ml / 1000).toFixed(2))} L`;
  return `${Math.round(ml).toLocaleString("en-IN")} ml`;
}

/** How full the day's bar is (0 to 100), and whether the goal is reached. */
export function progressOf(total: number, goal: number): { width: number; reached: boolean } {
  if (goal <= 0) return { width: 0, reached: false };
  return { width: Math.min(100, Math.round((100 * total) / goal)), reached: total >= goal };
}

/** A typed drink amount in ml, or an error message. */
export function drinkAmount(text: string): number | string {
  const ml = Number(text);
  if (!text.trim() || !Number.isInteger(ml) || ml <= 0) return "Enter the amount in whole millilitres.";
  if (ml > MAX_DRINK_ML) return `One drink is at most ${formatMl(MAX_DRINK_ML)}.`;
  return ml;
}

/** A typed daily goal in ml, or an error message. */
export function goalAmount(text: string): number | string {
  const ml = Number(text);
  const [low, high] = GOAL_LIMITS_ML;
  if (!Number.isInteger(ml) || ml < low || ml > high) return `The goal must be between ${formatMl(low)} and ${formatMl(high)}.`;
  return ml;
}

/** "9:05 AM" for a drink with a time; "" when only its day is known. */
export function drinkTime(drankAt: string | null | undefined, zone: Zone): string {
  const at = moment(drankAt, zone);
  if (!at) return "";
  return `${at.hour % 12 || 12}:${String(at.minute).padStart(2, "0")} ${at.hour < 12 ? "AM" : "PM"}`;
}
