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

export const MACROS = [
  { label: "Protein", field: "protein_g", color: "#4ade80" },
  { label: "Carbs", field: "carbs_g", color: "#60a5fa" },
  { label: "Fat", field: "fat_g", color: "#fbbf24" },
  { label: "Natural sugar", field: "natural_sugar_g", color: "#c084fc" },
  { label: "Added sugar", field: "added_sugar_g", color: "#fb7185" },
];

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
