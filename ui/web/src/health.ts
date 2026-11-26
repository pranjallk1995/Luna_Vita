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
  /** What the test measures, as Luna Lexia explains it; null until it is explained. */
  about?: string | null;
  /** Set on a snapshot row whose latest value comes from an older report than the one chosen. */
  from_report?: { document_id: string; date?: string | null } | null;
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

/** The trend windows offered: the last few reports, every report, or a range of collection dates. */
export const TREND_WINDOWS = ["3", "5", "10", "all", "range"] as const;
export type TrendWindow = (typeof TREND_WINDOWS)[number];
export const DEFAULT_TREND_WINDOW: TrendWindow = "5";

/** Collection dates from and to, as ISO days; either end may be open. */
export type DateRange = { from?: string | null; to?: string | null };

/** Whether an ISO day lies in the range; an undated report lies in no range. */
export const within = (day: string | null | undefined, range: DateRange): boolean =>
  !!day && (!range.from || day >= range.from) && (!range.to || day <= range.to);

/** The values of a series that fit the window: the last few, or those dated in the range. */
export const windowed = (points: HistoryPoint[], window: TrendWindow, range: DateRange = {}): HistoryPoint[] =>
  window === "all" ? points : window === "range" ? points.filter((point) => within(point.date, range)) : points.slice(-Number(window));

/** The reports the view covers: those collected in the range, or all of them. */
export const reportsIn = (reports: HealthReport[], window: TrendWindow, range: DateRange): HealthReport[] =>
  window === "range" ? reports.filter((report) => within(report.date, range)) : reports;

/** A test name without case, spacing, punctuation, or a plural "s"; matches Luna Vita's and Lexia's own merging. */
export const testKey = (name?: string | null): string => (name ?? "").toLowerCase().replace(/[^0-9a-z]+/g, "").replace(/s$/, "");

/** The day a report stands for: its sample collection, else its report date. */
export const reportDate = (report: HealthReport): string | null | undefined => report.collection_date || report.date;

/**
 * Every test detected up to the chosen report, each at its latest value as of then.
 *
 * The chosen report's own results come first, in its order; a test it does not have
 * follows with its value from the newest older report that has it, marked with that
 * report. Reports dated after the chosen one are left out, so trends end at it.
 */
export function snapshot(reports: HealthReport[], chosen: HealthReport): LabResult[] {
  const day = chosen.date ?? "";
  const older = reports
    .filter((report) => report !== chosen && (report.date ?? "") <= day)
    .sort((a, b) => (b.date ?? "").localeCompare(a.date ?? ""));
  const rows = [...chosen.results];
  const seen = new Set(rows.map((result) => testKey(result.test_name)));
  for (const report of older) {
    for (const result of report.results) {
      const key = testKey(result.test_name);
      if (seen.has(key)) continue;
      seen.add(key);
      rows.push({ ...result, from_report: { document_id: report.document_id, date: report.date } });
    }
  }
  return rows;
}

/** A result's series as of the chosen report: its value on its own report's day, within the window. */
export const trendOf = (result: LabResult, chosen: HealthReport, window: TrendWindow, range: DateRange = {}): HistoryPoint[] =>
  windowed(seriesOf(result, result.from_report ? result.from_report.date : chosen.date), window, range);

/** How many results of each status a list holds. */
export function countsOf(results: LabResult[]): HealthReport["counts"] {
  const counts = { tests: results.length, low: 0, high: 0, abnormal: 0, normal: 0, unknown: 0, out_of_range: 0 };
  for (const result of results) {
    counts[result.status] += 1;
    if (isOutOfRange(result.status)) counts.out_of_range += 1;
  }
  return counts;
}

/** "18 Apr 2026" from an ISO day. */
export function reportDay(day?: string | null): string {
  if (!day) return "Undated";
  const [year, month, date] = day.split("-").map(Number);
  if (!year || !month || !date) return day;
  return new Date(Date.UTC(year, month - 1, date)).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}
