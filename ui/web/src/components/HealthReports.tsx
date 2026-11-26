import { ArrowDown, ArrowRight, ArrowUp, ExternalLink, FileText, FlaskConical, Search, TriangleAlert } from "lucide-react";
import { useMemo, useState } from "react";

import { healthReportFile, useHealthReports, type Settings } from "../api";
import {
  DEFAULT_TREND_WINDOW,
  STATUS_LABELS,
  TREND_WINDOWS,
  byPanel,
  change,
  countsOf,
  isOutOfRange,
  matching,
  rangeText,
  reportDate,
  reportDay,
  reportsIn,
  resultText,
  snapshot,
  trendOf,
  type HealthReport,
  type HistoryPoint,
  type DateRange,
  type LabResult,
  type TrendWindow,
} from "../health";
import { ApiError } from "../http";
import { remember, remembered } from "../lib";
import { Dialog } from "./Dialog";
import { PdfPages } from "./PdfPages";
import { SectionHead } from "./shared";

const TREND_WINDOW_KEY = "luna-vita.health-trend-window";
const RANGE_KEY = "luna-vita.health-date-range";
const WINDOW_LABELS: Record<TrendWindow, string> = {
  "3": "Last 3 reports", "5": "Last 5 reports", "10": "Last 10 reports", all: "All reports", range: "Date range",
};
const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;

/** The remembered date range, when it is two valid days. */
function rememberedRange(): DateRange {
  try {
    const [from, to] = (localStorage.getItem(RANGE_KEY) ?? "").split("/");
    return { from: ISO_DAY.test(from ?? "") ? from : null, to: ISO_DAY.test(to ?? "") ? to : null };
  } catch {
    return {};
  }
}

/** What the trends cover, in words, for the caption. */
function periodText(window: TrendWindow, range: DateRange): string {
  if (window !== "range") return `${WINDOW_LABELS[window].toLowerCase()} up to this one`;
  if (range.from && range.to) return `values collected ${reportDay(range.from)} to ${reportDay(range.to)}`;
  if (range.from) return `values collected from ${reportDay(range.from)}`;
  if (range.to) return `values collected up to ${reportDay(range.to)}`;
  return "every value";
}

const FILTERS = [
  ["all", "All results"],
  ["flagged", "Out of range"],
] as const;

/** A result's dated values as a line, with its reference band shaded behind. */
function TrendLine({ points, low, high, large = false }: { points: HistoryPoint[]; low?: number | null; high?: number | null; large?: boolean }) {
  if (points.length < 2) return null;
  const [width, height, pad] = large ? [560, 180, 14] : [84, 24, 3];
  const values = points.map((point) => point.value);
  const limits = [low, high].filter((limit): limit is number => limit != null);
  const top = Math.max(...values, ...limits);
  const bottom = Math.min(...values, ...limits);
  const span = top - bottom || 1;
  const x = (index: number) => pad + (index * (width - 2 * pad)) / (points.length - 1);
  const y = (value: number) => height - pad - ((value - bottom) * (height - 2 * pad)) / span;
  const bandTop = high != null ? y(high) : pad;
  const bandBottom = low != null ? y(low) : height - pad;
  return (
    <svg className={large ? "vt-lab-trend vt-lab-trend-large" : "vt-lab-trend"} viewBox={`0 0 ${width} ${height}`} role="img"
      aria-label={`Trend: ${points.map((point) => `${reportDay(point.date)} ${point.value}`).join(", ")}`}>
      {limits.length > 0 && <rect className="vt-lab-band" x={0} y={bandTop} width={width} height={Math.max(bandBottom - bandTop, 1)} />}
      <polyline className="vt-lab-line" points={points.map((point, index) => `${x(index)},${y(point.value)}`).join(" ")} />
      {points.map((point, index) => (
        <g key={`${point.date}-${index}`}>
          <circle className="vt-lab-dot" cx={x(index)} cy={y(point.value)} r={large ? 4 : 1.8} />
          {large && (
            <>
              <text className="vt-lab-label" x={x(index)} y={y(point.value) - 9} textAnchor="middle">{point.value}</text>
              <text className="vt-lab-label vt-lab-date" x={x(index)} y={height - 1} textAnchor="middle">{reportDay(point.date)}</text>
            </>
          )}
        </g>
      ))}
    </svg>
  );
}

function StatusBadge({ status }: { status: LabResult["status"] }) {
  return <span className={`vt-lab-status vt-lab-${status}`}>{STATUS_LABELS[status]}</span>;
}

function Change({ result }: { result: LabResult }) {
  const moved = change(result);
  if (!moved) return <span className="vt-lab-muted">—</span>;
  const Icon = moved.direction === "up" ? ArrowUp : moved.direction === "down" ? ArrowDown : ArrowRight;
  return (
    <span className="vt-lab-change" title={`${moved.previous.value} on ${reportDay(moved.previous.date)}`}>
      <Icon size={13} aria-hidden="true" />
      {moved.delta > 0 ? "+" : ""}
      {moved.delta}
      <small>since {reportDay(moved.previous.date)}</small>
    </span>
  );
}

function TrendDialog({ result, points, onClose }: { result: LabResult; points: HistoryPoint[]; onClose: () => void }) {
  return (
    <Dialog title={result.test_name} size="large" onClose={onClose}>
      <div className="vt-lab-trend-head">
        <strong>{resultText(result)}</strong>
        <StatusBadge status={result.status} />
        <span className="vt-lab-muted">Reference {rangeText(result)}{result.method ? ` · ${result.method}` : ""}</span>
      </div>
      {points.length > 1 ? (
        <TrendLine points={points} low={result.reference_low} high={result.reference_high} large />
      ) : (
        <p className="vt-lab-muted">Only one value of this test falls in the trend window; its trend appears once another report has it.</p>
      )}
      {result.from_report && <p className="vt-caption">The chosen report does not have this test; its latest value is from the report of {reportDay(result.from_report.date)}.</p>}
      <p className="vt-caption">The shaded band is the reference interval of the latest value's report. Earlier values come from older reports in Luna Lexia, or from the trends column a report prints.</p>
    </Dialog>
  );
}

function PdfDialog({ report, onClose }: { report: HealthReport; onClose: () => void }) {
  const source = healthReportFile(report.document_id);
  return (
    <Dialog title={report.title || report.name} size="large" onClose={onClose}>
      <PdfPages source={source} title={`${report.title || report.name} (PDF)`} />
      <a className="lv-button vt-lab-open" href={source} target="_blank" rel="noopener">
        <ExternalLink size={15} />
        Open in a new tab
      </a>
    </Dialog>
  );
}

function ReportDetails({ report, reports, window, range }: { report: HealthReport; reports: HealthReport[]; window: TrendWindow; range: DateRange }) {
  const rows = useMemo(() => snapshot(reports, report), [reports, report]);
  const counts = useMemo(() => countsOf(rows), [rows]);
  const earlier = rows.filter((result) => result.from_report).length;
  const [filter, setFilter] = useState<(typeof FILTERS)[number][0]>(counts.out_of_range ? "flagged" : "all");
  const [query, setQuery] = useState("");
  const [trend, setTrend] = useState<LabResult | null>(null);
  const [pdf, setPdf] = useState(false);
  const shown = useMemo(() => byPanel(matching(rows, query, filter === "flagged"), true), [rows, query, filter]);
  const facts = [
    report.lab_name,
    report.collection_date && `Collected ${reportDay(report.collection_date)}`,
    report.report_date && report.report_date !== report.collection_date && `Reported ${reportDay(report.report_date)}`,
    [report.patient_name, report.patient_age, report.patient_gender].filter(Boolean).join(", "),
    report.report_status && `${report.report_status[0].toUpperCase()}${report.report_status.slice(1)} report`,
  ].filter(Boolean);

  return (
    <>
      <section className="vt-card vt-lab-report" aria-label="Report">
        <div className="vt-lab-report-head">
          <div>
            <h3>
              <FlaskConical size={15} />
              {report.package_name || report.title || report.name}
            </h3>
            <p className="vt-lab-muted">{facts.join(" · ")}</p>
          </div>
          <button className="lv-button" type="button" onClick={() => setPdf(true)}>
            <FileText size={15} />
            View PDF
          </button>
        </div>
        <div className="vt-lab-counts">
          {(
            [
              ["Tests", counts.tests, ""],
              ["In range", counts.normal, "normal"],
              ["Low", counts.low, "low"],
              ["High", counts.high, "high"],
              ["Abnormal", counts.abnormal, "abnormal"],
              ["No range", counts.unknown, "unknown"],
            ] as const
          )
            .filter(([label, count]) => count > 0 || label === "Tests" || label === "In range")
            .map(([label, count, status]) => (
              <div className={`vt-lab-count ${status && `vt-lab-${status}`}`} key={label}>
                <strong>{count}</strong>
                <span>{label}</span>
              </div>
            ))}
        </div>
        {report.review_flags.length > 0 && (
          <div className="lv-alert vt-lab-flags" role="note">
            <TriangleAlert size={15} aria-hidden="true" />
            <div>
              Luna Lexia marked this reading for review; check these against the PDF:
              <ul>
                {report.review_flags.map((flag) => <li key={flag}>{flag}</li>)}
              </ul>
            </div>
          </div>
        )}
        {earlier > 0 && (
          <p className="vt-caption">
            {earlier === 1 ? "1 test is" : `${earlier} tests are`} not in this report; {earlier === 1 ? "its" : "their"} latest value from an earlier report is shown, dated beside it.
          </p>
        )}
        {report.pending_tests.length > 0 && <p className="vt-caption">Pending: {report.pending_tests.join(", ")}</p>}
      </section>

      <div className="vt-lab-tools">
        <div className="vt-chips" role="group" aria-label="Show">
          {FILTERS.map(([id, label]) => (
            <button className="vt-chip" type="button" key={id} aria-pressed={filter === id} onClick={() => setFilter(id)}>
              {label}
            </button>
          ))}
        </div>
        <label className="vt-lab-search">
          <Search size={15} aria-hidden="true" />
          <input className="lv-input" type="search" placeholder="Find a test" aria-label="Find a test" value={query} onChange={(event) => setQuery(event.target.value)} />
        </label>
      </div>

      {shown.length === 0 ? (
        <p className="vt-empty-note">{filter === "flagged" && !query ? "Every result is within its reference range." : "No test matches."}</p>
      ) : (
        <div className="vt-lab-panels">
          {shown.map(([panel, results]) => (
            <section className="vt-card vt-lab-panel" key={panel} aria-label={panel}>
              <h3>
                {panel}
                {results.some((result) => isOutOfRange(result.status)) && (
                  <span className="vt-lab-muted"> · {results.filter((result) => isOutOfRange(result.status)).length} out of range</span>
                )}
              </h3>
              <div className="lv-table-scroll">
                <table className="lv-table vt-lab-table">
                  <thead>
                    <tr>
                      <th>Test</th>
                      <th className="lv-number">Result</th>
                      <th>Reference</th>
                      <th>Status</th>
                      <th>Change</th>
                      <th>Trend</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.map((result, index) => (
                      <tr key={`${result.test_name}-${index}`} className={isOutOfRange(result.status) ? "vt-lab-flagged" : undefined}>
                        <td>
                          <button className="vt-link-button" type="button" onClick={() => setTrend(result)} title="Show its trend">
                            {result.test_name}
                          </button>
                        </td>
                        <td className="lv-number">
                          {resultText(result)}
                          {result.from_report && <small className="vt-lab-from">{reportDay(result.from_report.date)}</small>}
                        </td>
                        <td className="vt-lab-range">{rangeText(result)}</td>
                        <td><StatusBadge status={result.status} /></td>
                        <td><Change result={result} /></td>
                        <td><TrendLine points={trendOf(result, report, window, range)} low={result.reference_low} high={result.reference_high} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ))}
        </div>
      )}
      <p className="vt-caption">
        Read by Luna Lexia from the reports' PDFs. Trends show {periodText(window, range)}. Status compares each result with the interval this report prints; it is
        not a diagnosis, so discuss results with your doctor.
      </p>
      {trend && <TrendDialog result={trend} points={trendOf(trend, report, window, range)} onClose={() => setTrend(null)} />}
      {pdf && <PdfDialog report={report} onClose={() => setPdf(false)} />}
    </>
  );
}

/** The person's lab reports, stored and read by Luna Lexia, shown here against their ranges and over time. */
export function HealthReports({ settings }: { settings: Settings }) {
  const { data, error, isPending, refetch } = useHealthReports();
  const [chosen, setChosen] = useState<string | null>(null);
  const [window, setWindow] = useState<TrendWindow>(() => remembered(TREND_WINDOW_KEY, TREND_WINDOWS, DEFAULT_TREND_WINDOW));
  const [range, setRange] = useState<DateRange>(rememberedRange);
  const all = data?.reports ?? [];
  const reports = useMemo(() => reportsIn(all, window, range), [all, window, range]);
  const report = reports.find((candidate) => candidate.document_id === chosen) ?? reports[0];
  const dates = all.map((candidate) => candidate.date).filter((day): day is string => !!day).sort();
  const chooseWindow = (value: TrendWindow) => {
    setWindow(value);
    remember(TREND_WINDOW_KEY, value);
    // A first date range spans every dated report.
    if (value === "range" && !range.from && !range.to) chooseRange({ from: dates[0] ?? null, to: dates.at(-1) ?? null });
  };
  const chooseRange = (next: DateRange) => {
    setRange(next);
    remember(RANGE_KEY, `${next.from ?? ""}/${next.to ?? ""}`);
  };
  const lexia = settings.lexia_ui_url;

  return (
    <section className="vt-lab" aria-labelledby="health-reports-title">
      <SectionHead id="health-reports-title" title="Health reports">
        {lexia && (
          <a className="lv-button" href={lexia} target="_blank" rel="noopener">
            <ExternalLink size={15} />
            Add in Luna Lexia
          </a>
        )}
      </SectionHead>
      {error ? (
        <div className="lv-alert lv-alert-error vt-lab-flags" role="alert">
          <TriangleAlert size={15} aria-hidden="true" />
          <div>
            {error instanceof ApiError && error.status === 503 ? error.message : "Health reports could not be loaded."}{" "}
            <button className="vt-link-button" type="button" onClick={() => refetch()}>Try again</button>
          </div>
        </div>
      ) : isPending ? (
        <p className="vt-empty-note">Reading your reports from Luna Lexia…</p>
      ) : all.length === 0 ? (
        <div className="vt-empty">
          <FlaskConical size={28} />
          <strong>No health reports yet</strong>
          <p>Upload a lab report PDF to Luna Lexia. It is read as a health report, and its results appear here.</p>
        </div>
      ) : (
        <>
          <div className="vt-card vt-lab-period">
            <label className="vt-lab-picker">
              <span>
                {window === "range" ? `${reports.length} of ${all.length}` : reports.length} {(window === "range" ? all.length : reports.length) === 1 ? "report" : "reports"} detected
                {window === "range" ? " in this period" : ""} · collected on
              </span>
              <select className="lv-select" value={report?.document_id ?? ""} disabled={!reports.length}
                onChange={(event) => setChosen(event.target.value)} aria-label="Report, by collection date">
                {reports.length === 0 && <option value="">No report</option>}
                {reports.map((candidate) => (
                  <option key={candidate.document_id} value={candidate.document_id}>{reportDay(reportDate(candidate))}</option>
                ))}
              </select>
            </label>
            <label className="vt-lab-window">
              <span>Trend</span>
              <select className="lv-select" value={window} onChange={(event) => chooseWindow(event.target.value as TrendWindow)} aria-label="Trend period">
                {TREND_WINDOWS.map((value) => <option key={value} value={value}>{WINDOW_LABELS[value]}</option>)}
              </select>
            </label>
            {window === "range" && (
              <div className="vt-lab-range-pick" role="group" aria-label="Collection dates">
                <label>
                  <span>From</span>
                  <input className="lv-input" type="date" value={range.from ?? ""} max={range.to ?? undefined}
                    onChange={(event) => chooseRange({ ...range, from: event.target.value || null })} />
                </label>
                <label>
                  <span>To</span>
                  <input className="lv-input" type="date" value={range.to ?? ""} min={range.from ?? undefined}
                    onChange={(event) => chooseRange({ ...range, to: event.target.value || null })} />
                </label>
              </div>
            )}
          </div>
          {report ? (
            <ReportDetails key={report.document_id} report={report} reports={reports} window={window} range={range} />
          ) : (
            <p className="vt-empty-note">No report was collected in this period. Widen the dates to see its tests.</p>
          )}
        </>
      )}
    </section>
  );
}
