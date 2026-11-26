/** Health reports read from Luna Lexia: results grouped by panel, statuses, and trends. */

export type ResultStatus = "low" | "high" | "abnormal" | "normal" | "unknown";

export type HistoryPoint = { date: string; value: number; unit?: string | null; document_id?: string | null; status?: ResultStatus | null };

export type LabResult = {
  panel?: string | null;
  test_name: string;
  value?: number | null;
  value_text?: string | null;
  unit?: string | null;
  reference_range?: string | null;
  reference_low?: number | null;
  reference_high?: number | null;
  method?: string | null;
  status: ResultStatus;
  history: HistoryPoint[];
};

export type HealthReport = {
  document_id: string;
  name: string;
  title?: string | null;
  summary?: string | null;
  date?: string | null;
  lab_name?: string | null;
  patient_name?: string | null;
  patient_age?: string | null;
  patient_gender?: string | null;
  package_name?: string | null;
  collection_date?: string | null;
  report_date?: string | null;
  report_status?: string | null;
  pending_tests: string[];
  review_flags: string[];
  results: LabResult[];
  counts: Record<ResultStatus | "tests" | "out_of_range", number>;
};

export type HealthReports = { reports: HealthReport[]; count: number };

export const STATUS_LABELS: Record<ResultStatus, string> = {
  low: "Low",
  high: "High",
  abnormal: "Abnormal",
  normal: "In range",
  unknown: "No range",
};

export const isOutOfRange = (status: ResultStatus) => status === "low" || status === "high" || status === "abnormal";

/** The result as the report prints it: a number with its unit, or its text. */
export function resultText(result: Pick<LabResult, "value" | "value_text" | "unit">): string {
  const value = result.value ?? null;
  const shown = value !== null ? String(Number(value.toFixed(3))) : (result.value_text ?? "—");
  return result.unit && value !== null ? `${shown} ${result.unit}` : shown;
}

/** The reference interval as printed, else built from its limits. */
export function rangeText(result: Pick<LabResult, "reference_range" | "reference_low" | "reference_high">): string {
  if (result.reference_range) return result.reference_range;
  const { reference_low: low, reference_high: high } = result;
  if (low != null && high != null) return `${low} – ${high}`;
  if (high != null) return `≤ ${high}`;
  if (low != null) return `≥ ${low}`;
  return "—";
}

/** Results by the panel they are printed under, in the report's order; out-of-range first when asked. */
export function byPanel(results: LabResult[], outOfRangeFirst = false): [string, LabResult[]][] {
  const panels = new Map<string, LabResult[]>();
  for (const result of results) {
    const panel = result.panel?.trim() || "Other tests";
    panels.set(panel, [...(panels.get(panel) ?? []), result]);
  }
  const groups = [...panels.entries()];
  if (!outOfRangeFirst) return groups;
  const flagged = (group: LabResult[]) => group.filter((result) => isOutOfRange(result.status)).length;
  return groups.sort(([, a], [, b]) => flagged(b) - flagged(a));
}

/** Keep the results whose name or panel holds every word of the search. */
export function matching(results: LabResult[], query: string, onlyOutOfRange: boolean): LabResult[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  return results.filter((result) => {
    if (onlyOutOfRange && !isOutOfRange(result.status)) return false;
    const text = `${result.test_name} ${result.panel ?? ""}`.toLowerCase();
    return words.every((word) => text.includes(word));
  });
}

/** How a result moved since its last earlier value: the change and its direction. */
export function change(result: LabResult): { previous: HistoryPoint; delta: number; direction: "up" | "down" | "same" } | null {
  const previous = result.history.at(-1);
  if (!previous || result.value == null) return null;
  const delta = Number((result.value - previous.value).toFixed(3));
  return { previous, delta, direction: delta > 0 ? "up" : delta < 0 ? "down" : "same" };
}

/** Every dated value of a result, its own report's last, for a small trend line. */
export const seriesOf = (result: LabResult, date?: string | null): HistoryPoint[] =>
  result.value != null && date ? [...result.history, { date, value: result.value, unit: result.unit, status: result.status }] : result.history;

/** "18 Apr 2026" from an ISO day. */
export function reportDay(day?: string | null): string {
  if (!day) return "Undated";
  const [year, month, date] = day.split("-").map(Number);
  if (!year || !month || !date) return day;
  return new Date(Date.UTC(year, month - 1, date)).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}
