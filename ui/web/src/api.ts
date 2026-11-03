/** The backend routes the gateway forwards, and the hooks over them. */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";

import { useToast } from "./components/Toasts";
import { post, put, remove, request } from "./http";
import { messageOf } from "./lib";

export type Settings = {
  time_zone: string;
  utc_offset: string;
  food_photo_size: [number, number];
  food_photo_quality: number;
  photo_upload_types: string[];
  max_food_rows: number;
  max_measurement_rows: number;
};

export type FoodEntry = {
  id: number;
  consumed_date: string;
  consumed_at: string;
  time_label?: string | null;
  food_name: string;
  quantity: string;
  meal_type?: string;
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  natural_sugar_g: number;
  added_sugar_g: number;
  image_url?: string | null;
  notes?: string | null;
};

export type Measurement = {
  id: number;
  metric: string;
  value: number;
  unit: string;
  measured_at: string;
  time_label?: string | null;
};

export type RawReading = { measured_at: string; value: number; time_label?: string | null; estimated?: boolean };

export type BodyComposition = { weight: RawReading[]; body_fat: RawReading[]; body_fat_target_percent: number };

export type WorkoutRecord = { workout_date: string; done: boolean; notes?: string | null; types?: string[] | null };

export type Exercise = {
  id: number;
  exercise: string;
  type?: string | null;
  sets?: number | null;
  reps?: number | null;
  weight_kg?: number | null;
  duration_min?: number | null;
  notes?: string | null;
};

export type Totals = Record<string, number>;

export type AnalysisFood = {
  name: string;
  count: number;
  days: number;
  image_url?: string | null;
  totals: Totals;
  protein_share: number;
  verdict: { kind: "prefer" | "avoid" | "neutral"; source: string; reason: string };
};

export type Contributor = { name: string; amount: number; share: number };
export type DayTotals = { date: string; logged: boolean } & Totals;

export type Analysis = {
  window: { label: string; start: string; end: string; days: number };
  range_source: string;
  entries: number;
  days_logged: number;
  foods: AnalysisFood[];
  daily_averages: Totals;
  daily_totals: DayTotals[];
  totals: Totals;
  top_contributors: Record<string, Contributor[]>;
  prefer: AnalysisFood[];
  avoid: AnalysisFood[];
  rules: Record<string, number>;
};

const range = (start: string, end: string) => `start=${start}&end=${end}`;

export const useSummary = (day: string) =>
  useQuery({ queryKey: ["summary", day], queryFn: () => request<Totals>(`/api/summary/${day}`) });

export const useRecommendations = () =>
  useQuery({ queryKey: ["recommendations"], queryFn: () => request<Totals | null>("/api/recommendations") });

export const useFood = (day: string, limit: number) =>
  useQuery({ queryKey: ["food", day], queryFn: () => request<FoodEntry[]>(`/api/food?${range(day, day)}&limit=${limit}`) });

/** Every entry between two days, newest first; feeds the recent foods in the Add dialog. */
export const useFoodBetween = (start: string, end: string, limit: number) =>
  useQuery({ queryKey: ["food-range", start, end], queryFn: () => request<FoodEntry[]>(`/api/food?${range(start, end)}&limit=${limit}`) });

export const useMeasurements = (limit: number) =>
  useQuery({ queryKey: ["measurements"], queryFn: () => request<Measurement[]>(`/api/measurements?limit=${limit}`) });

export const useAnalysis = (day: string) =>
  useQuery({
    queryKey: ["analysis", day],
    queryFn: () => request<Analysis>(`/api/analysis/displayed?day=${day}`),
    placeholderData: (previous) => previous,
  });

export const useBodyComposition = (start: string, end: string) =>
  useQuery({ queryKey: ["body", start, end], queryFn: () => request<BodyComposition>(`/api/body-composition?${range(start, end)}`) });

export const useWorkouts = (start: string, end: string) =>
  useQuery({ queryKey: ["workouts", start, end], queryFn: () => request<WorkoutRecord[]>(`/api/workouts?${range(start, end)}`) });

export const useExercises = (day: string) =>
  useQuery({ queryKey: ["exercises", day], queryFn: () => request<Exercise[]>(`/api/workouts/exercises?${range(day, day)}`) });

export const vita = {
  createFood: (payload: unknown) => post<FoodEntry>("/api/food", payload),
  updateFood: (id: number, payload: unknown) => put(`/api/food/${id}`, payload),
  deleteFood: (id: number) => remove(`/api/food/${id}`),
  createMeasurements: (measurements: unknown[]) => post("/api/measurements/batch", { measurements }),
  deleteMeasurement: (id: number) => remove(`/api/measurements/${id}`),
  setRange: (start: string, end: string) => put("/api/analysis/range", { start_date: start, end_date: end }),
  resetRange: () => remove("/api/analysis/range"),
  recordWorkout: (day: string, done: boolean, notes: string | null | undefined, types: string[]) =>
    put(`/api/workouts/${day}`, { done, notes: notes ?? null, types }),
  deleteWorkout: (day: string) => remove(`/api/workouts/${day}`),
  addExercises: (exercises: unknown[]) => post("/api/workouts/exercises", { exercises }),
  updateExercise: (id: number, payload: unknown) => put(`/api/workouts/exercises/${id}`, payload),
  deleteExercise: (id: number) => remove(`/api/workouts/exercises/${id}`),
};

/** Run a change, then refresh everything it may affect; a refusal becomes a toast, and the result says which. */
export function useAct() {
  const client = useQueryClient();
  const toast = useToast();
  return useCallback(
    async (action: () => Promise<unknown>, fallback = "That could not be saved. Please try again.") => {
      try {
        await action();
        return true;
      } catch (failure) {
        toast(messageOf(failure, fallback));
        return false;
      } finally {
        client.invalidateQueries({ predicate: ({ queryKey }) => queryKey[0] !== "session" && queryKey[0] !== "recommendations" });
      }
    },
    [client, toast],
  );
}

const VISIA_IMAGE = /\/api\/public\/images\/[0-9a-fA-F-]{36}\/?$/;

/** Where the browser loads a food photo: fitted by the gateway when it lives in Luna Visia, whole when large. */
export function photoSource(source?: string | null, large = false): string {
  if (!source) return "";
  return VISIA_IMAGE.test(source) ? `/app/food-photos?url=${encodeURIComponent(source)}${large ? "&size=large" : ""}` : source;
}

/** Fit a chosen photo to the table's 3:2 format, as a compact data URL for the database. */
export async function fittedPhoto(file: File, [width, height]: [number, number], quality: number): Promise<string> {
  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    throw new Error("Choose a valid JPG, PNG, or WebP food photo.");
  }
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d")!;
  context.fillStyle = "#111111";
  context.fillRect(0, 0, width, height);
  const scale = Math.max(width / bitmap.width, height / bitmap.height);
  const [drawnWidth, drawnHeight] = [bitmap.width * scale, bitmap.height * scale];
  context.drawImage(bitmap, (width - drawnWidth) / 2, (height - drawnHeight) / 2, drawnWidth, drawnHeight);
  bitmap.close();
  return canvas.toDataURL("image/jpeg", quality);
}
