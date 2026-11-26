import { ArrowDown, ArrowRight, ArrowUp, ExternalLink, FileText, FlaskConical, Search, TriangleAlert } from "lucide-react";
import { useMemo, useState } from "react";

import { healthReportFile, useHealthReports, type Settings } from "../api";
import {
  STATUS_LABELS,
  byPanel,
  change,
  isOutOfRange,
  matching,
  rangeText,
  reportDay,
  resultText,
  seriesOf,
  type HealthReport,
  type HistoryPoint,
  type LabResult,
} from "../health";
import { ApiError } from "../http";
import { Dialog } from "./Dialog";
import { SectionHead } from "./shared";

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

function TrendDialog({ result, report, onClose }: { result: LabResult; report: HealthReport; onClose: () => void }) {
  const points = seriesOf(result, report.date);
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
        <p className="vt-lab-muted">This is the only report with this test so far; its trend appears once another report has it.</p>
      )}
      <p className="vt-caption">The shaded band is the reference interval of this report. Earlier values come from older reports in Luna Lexia, or from the trends column a report prints.</p>
    </Dialog>
  );
}

function PdfDialog({ report, onClose }: { report: HealthReport; onClose: () => void }) {
  const source = healthReportFile(report.document_id);
  return (
    <Dialog title={report.title || report.name} size="large" onClose={onClose}>
      <iframe className="vt-lab-pdf" src={source} title={`${report.title || report.name} (PDF)`} />
      <a className="lv-button vt-lab-open" href={source} target="_blank" rel="noopener">
        <ExternalLink size={15} />
        Open in a new tab
      </a>
    </Dialog>
  );
}

function ReportDetails({ report }: { report: HealthReport }) {
  const [filter, setFilter] = useState<(typeof FILTERS)[number][0]>(report.counts.out_of_range ? "flagged" : "all");
  const [query, setQuery] = useState("");
  const [trend, setTrend] = useState<LabResult | null>(null);
  const [pdf, setPdf] = useState(false);
  const shown = useMemo(() => byPanel(matching(report.results, query, filter === "flagged"), true), [report, query, filter]);
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
              ["Tests", report.counts.tests, ""],
              ["In range", report.counts.normal, "normal"],
              ["Low", report.counts.low, "low"],
              ["High", report.counts.high, "high"],
              ["Abnormal", report.counts.abnormal, "abnormal"],
              ["No range", report.counts.unknown, "unknown"],
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
                        <td className="lv-number">{resultText(result)}</td>
                        <td className="vt-lab-range">{rangeText(result)}</td>
                        <td><StatusBadge status={result.status} /></td>
                        <td><Change result={result} /></td>
                        <td><TrendLine points={seriesOf(result, report.date)} low={result.reference_low} high={result.reference_high} /></td>
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
        Read by Luna Lexia from the report's PDF. Status compares each result with the interval this report prints; it is
        not a diagnosis, so discuss results with your doctor.
      </p>
      {trend && <TrendDialog result={trend} report={report} onClose={() => setTrend(null)} />}
      {pdf && <PdfDialog report={report} onClose={() => setPdf(false)} />}
    </>
  );
}

/** The person's lab reports, stored and read by Luna Lexia, shown here against their ranges and over time. */
export function HealthReports({ settings }: { settings: Settings }) {
  const { data, error, isPending, refetch } = useHealthReports();
  const [chosen, setChosen] = useState<string | null>(null);
  const reports = data?.reports ?? [];
  const report = reports.find((candidate) => candidate.document_id === chosen) ?? reports[0];
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
      ) : reports.length === 0 ? (
        <div className="vt-empty">
          <FlaskConical size={28} />
          <strong>No health reports yet</strong>
          <p>Upload a lab report PDF to Luna Lexia. It is read as a health report, and its results appear here.</p>
        </div>
      ) : (
        <>
          {reports.length > 1 && (
            <div className="vt-chips vt-lab-picker" role="group" aria-label="Report">
              {reports.map((candidate) => (
                <button className="vt-chip" type="button" key={candidate.document_id} aria-pressed={candidate === report}
                  onClick={() => setChosen(candidate.document_id)}>
                  {reportDay(candidate.date)}
                  {candidate.lab_name ? ` · ${candidate.lab_name}` : ""}
                  {candidate.counts.out_of_range > 0 ? ` · ${candidate.counts.out_of_range} out of range` : ""}
                </button>
              ))}
            </div>
          )}
          {report && <ReportDetails key={report.document_id} report={report} />}
        </>
      )}
    </section>
  );
}
