/** Pure nutrition arithmetic behind the summary cards and macro chart. */

import { Apple, Droplet, Dumbbell, Flame, Wheat, type LucideIcon } from "lucide-react";

export const WARNING_THRESHOLD = 0.85;

/** Warn near a ceiling and flag when it is exceeded. */
export function limitStatus(value: number, target: number): string {
  if (target <= 0) return "";
  const ratio = value / target;
  if (ratio > 1) return "danger";
  return ratio >= WARNING_THRESHOLD ? "warning" : "";
}

/** Protein is a floor, so reaching it is a success rather than a warning. */
export const floorStatus = (value: number, target: number) => (target > 0 && value >= target ? "success" : "");

export const percentage = (value: number, target: number) => (target > 0 ? Math.round((value / target) * 100) : 0);

export type Nutrient = {
  key: string;
  icon: LucideIcon;
  label: string;
  unit: string;
  summaryField: string;
  targetField: string;
  targetSuffix?: string;
  decimals: number;
  isFloor?: boolean;
};

export const NUTRIENTS: Nutrient[] = [
  { key: "calories", icon: Flame, label: "Calories", unit: "kcal", summaryField: "calories", targetField: "calories_kcal", decimals: 0 },
  { key: "protein", icon: Dumbbell, label: "Protein", unit: "g", summaryField: "protein_g", targetField: "protein_g", decimals: 1, isFloor: true },
  { key: "carbs", icon: Wheat, label: "Carbs", unit: "g", summaryField: "carbs_g", targetField: "carbs_g", decimals: 1 },
  { key: "fat", icon: Droplet, label: "Fat", unit: "g", summaryField: "fat_g", targetField: "fat_g", decimals: 1 },
  { key: "sugars", icon: Apple, label: "Added sugar", unit: "g", summaryField: "added_sugar_g", targetField: "sugars_g", targetSuffix: " max", decimals: 1 },
];

export const nutrientStatus = (nutrient: Nutrient, value: number, target: number) =>
  nutrient.isFloor ? floorStatus(value, target) : limitStatus(value, target);

export const number = (value: number, decimals = 0) =>
  value.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });

/** Round non-negative macro shares to integers totaling exactly 100%. */
export function macroPercentages(values: number[]): number[] {
  const total = values.reduce((sum, value) => sum + value, 0);
  if (total <= 0) return values.map(() => 0);
  const exact = values.map((value) => (value * 100) / total);
  const shares = exact.map(Math.floor);
  const remaining = 100 - shares.reduce((sum, share) => sum + share, 0);
  const byRemainder = values
    .map((_, index) => index)
    .sort((left, right) => exact[right] - shares[right] - (exact[left] - shares[left]) || left - right);
  for (const index of byRemainder.slice(0, remaining)) shares[index] += 1;
  return shares;
}

/** Kilocalories per gram, so the split is by energy rather than weight. */
export const ENERGY = [
  { label: "Protein", field: "protein_g", color: "#4ade80", kcalPerGram: 4 },
  { label: "Carbs", field: "carbs_g", color: "#60a5fa", kcalPerGram: 4 },
  { label: "Fat", field: "fat_g", color: "#fbbf24", kcalPerGram: 9 },
] as const;

/**
 * Protein, carbs and fat as shares of their combined energy. Sugars are part of
 * carbs already, so counting them again would inflate the carb share.
 */
export function energySplit(totals: Record<string, number>) {
  const grams = ENERGY.map(({ field }) => Number(totals[field] ?? 0));
  const shares = macroPercentages(ENERGY.map(({ kcalPerGram }, index) => grams[index] * kcalPerGram));
  return ENERGY.map(({ label, color }, index) => ({ label, color, grams: grams[index], share: shares[index] }));
}

/** A nutrient's state in words; a goal reads "to go" and a limit reads "left". */
export function standing(nutrient: Nutrient, value: number, target: number, averaged = false) {
  const status = nutrientStatus(nutrient, value, target);
  const gap = `${number(Math.abs(target - value), nutrient.decimals)} ${nutrient.unit}`;
  if (status === "success") return { status, text: averaged ? "Goal met on average" : "Goal reached" };
  if (status === "danger") return { status, text: `${gap} over` };
  if (averaged) return { status, text: `${gap} ${nutrient.isFloor ? "short" : "under"}` };
  return { status, text: `${gap} ${nutrient.isFloor ? "to go" : "left"}` };
}
