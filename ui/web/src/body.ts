/** Pure shaping of body measurements and weight / body fat series. */

import type { Measurement, RawReading } from "./api";
import { moment, type Zone } from "./clock";

export const PERIODS = ["Morning", "Night"] as const;
export type Period = (typeof PERIODS)[number];

export const METRICS: Record<string, { label: string; unit: string }> = {
  weight: { label: "Weight", unit: "kg" },
  bmr: { label: "BMR", unit: "kcal/day" },
  health_score: { label: "Health score", unit: "/100" },
  body_age: { label: "Body age", unit: "years" },
  bmi: { label: "BMI", unit: "index" },
  water_ratio: { label: "Water ratio", unit: "%" },
};

/** Morning or Night, from the label or else the local hour. */
export function periodOf(label: string | null | undefined, hour: number): Period {
  const text = (label ?? "").toLowerCase();
  if (text.includes("morning") || text.includes("am")) return "Morning";
  if (text.includes("night") || text.includes("evening") || text.includes("pm")) return "Night";
  return hour < 12 ? "Morning" : "Night";
}

/** ``value`` without trailing zeros, like Python's ``%g``. */
export const compact = (value: number) => String(Number(value.toPrecision(6)));

export function formatMetric(metric: string, value: number, unit: string): string {
  if (metric === "health_score") return `${compact(value)}/100`;
  if (metric === "bmi") return compact(value);
  return `${compact(value)} ${unit}`;
}

export type DayMeasurement = Measurement & { period: Period; at: number };

/** The selected day's known measurements, each with its period. */
export function measurementsOn(rows: Measurement[], day: string, zone: Zone): DayMeasurement[] {
  return rows.flatMap((row) => {
    const at = moment(row.measured_at, zone);
    if (!(row.metric in METRICS) || !at || at.day !== day) return [];
    return [{ ...row, period: periodOf(row.time_label, at.hour), at: Date.parse(row.measured_at) }];
  });
}

/** One row per metric: its latest Morning and Night value, Morning always first. */
export function measurementTable(rows: DayMeasurement[]) {
  return Object.entries(METRICS).map(([metric, { label }]) => {
    const cell = (period: Period) => {
      const latest = rows.filter((row) => row.metric === metric && row.period === period).sort((a, b) => a.at - b.at).pop();
      return latest ? formatMetric(metric, Number(latest.value), latest.unit) : "Not recorded";
    };
    return { label, Morning: cell("Morning"), Night: cell("Night") };
  });
}

/** One payload per entered metric; blank metrics are skipped. */
export function measurementPayloads(values: Record<string, string>, measuredAt: string, period: Period, notes: string) {
  return Object.entries(METRICS).flatMap(([metric, { unit }]) =>
    values[metric]?.trim()
      ? [{ metric, value: Number(values[metric]), unit, measured_at: measuredAt, time_label: period, notes: notes.trim() || null }]
      : [],
  );
}

// Trend

export type Reading = { day: string; period: Period; value: number; estimated: boolean; at: number };

export function readings(raw: RawReading[], zone: Zone): Reading[] {
  return raw.flatMap((item) => {
    const at = moment(item.measured_at, zone);
    if (!at) return [];
    return [
      {
        day: at.day,
        period: periodOf(item.time_label, at.hour),
        value: Number(item.value),
        estimated: Boolean(item.estimated),
        at: Date.parse(item.measured_at),
      },
    ];
  });
}

/** The latest Morning and Night reading of each local day. */
export function byDay(series: Reading[]): Map<string, Partial<Record<Period, Reading>>> {
  const grouped = new Map<string, Partial<Record<Period, Reading>>>();
  for (const reading of [...series].sort((a, b) => a.at - b.at)) {
    grouped.set(reading.day, { ...grouped.get(reading.day), [reading.period]: reading });
  }
  return grouped;
}

export const WEIGHT_STEP = 1;
export const FAT_FLOOR = 15;
export const FAT_STEP = 3;

/** Weight bars rise from a whole-kg floor below the lowest reading. */
export function weightRange(series: Reading[]): [number, number] {
  const values = series.map(({ value }) => value);
  const floor = Math.floor(Math.min(...values) - 0.5);
  return [floor, Math.max(Math.ceil(Math.max(...values) + 0.5), floor + WEIGHT_STEP)];
}

/** Body fat bars rise from 15%, or a lower 3% step when a reading or the target dips below. */
export function fatRange(series: Reading[], target: number): [number, number] {
  const values = [target, ...series.map(({ value }) => value)];
  const [lowest, highest] = [Math.min(...values), Math.max(...values)];
  const floor = Math.min(FAT_FLOOR, Math.floor((lowest - 1) / FAT_STEP) * FAT_STEP);
  return [floor, highest + Math.max(1, (highest - floor) * 0.1)];
}

export const average = (series: Reading[]) =>
  series.length ? series.reduce((sum, { value }) => sum + value, 0) / series.length : null;
