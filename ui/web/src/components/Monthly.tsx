import { Apple, CalendarRange, ChevronLeft, ChevronRight, Droplet, Dumbbell, Flame, PersonStanding, Scale, ThumbsDown, ThumbsUp, Utensils, Wheat, type LucideIcon } from "lucide-react";
import { useEffect, useRef, useState, type CSSProperties } from "react";
import { createPortal } from "react-dom";

import { photoSource, useAct, useAnalysis, useBodyComposition, useRecommendations, useWorkouts, vita, type Analysis, type AnalysisFood, type DayTotals, type Settings, type WorkoutRecord } from "../api";
import { PERIODS, average, byDay, fatRange, readings, weightRange, type Reading } from "../body";
import { dayLabel, daysBetween, today } from "../clock";
import { messageOf } from "../lib";
import { NUTRIENTS, number, type Nutrient } from "../nutrition";
import { WORKOUT_TYPES, calendarSpan, cellLabel, monthLabel, monthWeeks, monthsBetween, statusOf } from "../workouts";
import { Dialog } from "./Dialog";
import { SectionHead, SummaryTiles, targetsOf } from "./shared";

const SLOT = 10; // viewBox units per day
const HEIGHT = 60;
const OVERRIDE_LABEL = "Your rating";
const WEEKDAYS = ["M", "T", "W", "T", "F", "S", "S"];
/** Prefer and Avoid show this many until expanded, so the column stays level with the food list. */
const CHOICES_SHOWN = 3;

/** A day's bars; a day with nothing logged gets a small mark so gaps read as gaps. */
type Bar = { x: number; width: number; value: number; className: string };
type Slot = { day: string; tip: string; bars: Bar[] };

function BarPlot({ slots, low, high, target, label }: { slots: Slot[]; low: number; high: number; target?: number; label: string }) {
  const y = (value: number) => HEIGHT - ((value - low) / (high - low)) * HEIGHT;
  const width = SLOT * slots.length;
  // Touch screens have no hover, so a tap shows what a title shows a mouse.
  const [picked, setPicked] = useState<string | null>(null);
  const plot = useRef<HTMLDivElement>(null);
  const at = slots.findIndex((slot) => slot.day === picked);

  useEffect(() => {
    if (picked === null) return;
    const dismiss = (event: PointerEvent) => {
      if (!plot.current?.contains(event.target as Node)) setPicked(null);
    };
    document.addEventListener("pointerdown", dismiss);
    return () => document.removeEventListener("pointerdown", dismiss);
  }, [picked]);

  return (
    <div className="vt-plot-wrap" ref={plot}>
      <svg className="vt-plot" viewBox={`0 0 ${width} ${HEIGHT}`} preserveAspectRatio="none" role="img" aria-label={label}>
        {slots.map((slot, index) => {
          const x = index * SLOT;
          return (
            <g className={`vt-plot-day${index === at ? " picked" : ""}`} key={slot.day} onClick={() => setPicked(slot.day === picked ? null : slot.day)}>
              <title>{slot.tip}</title>
              <rect className="vt-plot-hit" x={x} y="0" width={SLOT} height={HEIGHT} />
              {slot.bars.length ? (
                slot.bars.map((bar, barAt) => (
                  <rect className={`vt-plot-bar ${bar.className}`} key={barAt} x={x + bar.x} y={y(bar.value)} width={bar.width} height={Math.max(HEIGHT - y(bar.value), 0.6)} rx="1" />
                ))
              ) : (
                <rect className="vt-plot-gap" x={x + 4} y={HEIGHT - 1.2} width="2" height="1.2" />
              )}
            </g>
          );
        })}
        <line className="vt-plot-base" x1="0" x2={width} y1={HEIGHT} y2={HEIGHT} />
        {target !== undefined && <line className="vt-plot-target" x1="0" x2={width} y1={y(target)} y2={y(target)} />}
      </svg>
      {at >= 0 && (
        <div className="vt-plot-tip" style={{ "--at": (at + 0.5) / slots.length } as CSSProperties}>
          {slots[at].tip}
        </div>
      )}
    </div>
  );
}

function Axis({ days }: { days: string[] }) {
  return (
    <div className="vt-axis">
      <span>{dayLabel(days[0])}</span>
      <span>{dayLabel(days[Math.floor(days.length / 2)])}</span>
      <span>{dayLabel(days[days.length - 1])}</span>
    </div>
  );
}

/** One nutrient at a time, with each day against the target. */
function PerDay({ days, averages, targets }: { days: DayTotals[]; averages: Record<string, number>; targets: Record<string, number> }) {
  const [key, setKey] = useState("calories");
  const nutrient = NUTRIENTS.find((item) => item.key === key)!;
  const target = targets[key];
  const amount = (day: DayTotals) => Number(day[nutrient.summaryField] ?? 0);
  const logged = days.filter((day) => day.logged);
  const over = (value: number) => !nutrient.isFloor && value > target;
  const met = (value: number) => Boolean(nutrient.isFloor) && value >= target;
  const high = Math.max(target, ...logged.map(amount), 1) * 1.08;
  const count = nutrient.isFloor ? logged.filter((day) => met(amount(day))).length : logged.filter((day) => over(amount(day))).length;
  const slots: Slot[] = days.map((day) => {
    const value = amount(day);
    const shown = `${number(value, nutrient.decimals)} ${nutrient.unit}`;
    return {
      day: day.date,
      tip: `${dayLabel(day.date)} · ${day.logged ? shown : "not logged"}`,
      bars: day.logged ? [{ x: 1.5, width: 7, value, className: over(value) ? "over" : met(value) ? "met" : "" }] : [],
    };
  });

  return (
    <section className="vt-stretch-col" aria-labelledby="per-day-title">
      <SectionHead title="Per day" id="per-day-title">
        <div className="vt-chips" role="group" aria-label="Nutrient">
          {NUTRIENTS.map((item) => (
            <button className="vt-chip" type="button" key={item.key} aria-pressed={item.key === key} onClick={() => setKey(item.key)}>
              {item.label}
            </button>
          ))}
        </div>
      </SectionHead>
      <div className="vt-card vt-trend">
        <div className="vt-trend-top">
          <strong>
            {number(averages[key], nutrient.decimals)}{" "}
            <small>
              {nutrient.unit} average · target {number(target)} {nutrient.unit}
            </small>
          </strong>
          <span className="vt-legend">
            {count} of {logged.length} logged days {nutrient.isFloor ? "reached the goal" : "went over"}
          </span>
        </div>
        <div className="vt-plot-box">
          <BarPlot slots={slots} low={0} high={high} target={target} label={`${nutrient.label} per day`} />
        </div>
        <Axis days={days.map((day) => day.date)} />
        <div className="vt-legend">
          <span>
            <i className={nutrient.isFloor ? "vt-key vt-key-met" : "vt-key vt-key-over"} />
            {nutrient.isFloor ? "Goal reached" : "Over target"}
          </span>
          <span>
            <i className="vt-key vt-key-line" />
            Target
          </span>
          <span>
            <i className="vt-key vt-key-gap" />
            Not logged
          </span>
        </div>
      </div>
    </section>
  );
}

/** The selected day's month when the range holds it; otherwise the month with most of the range. */
function openingMonth(start: string, end: string, selected: string): string {
  if (selected >= start && selected <= end) return `${selected.slice(0, 7)}-01`;
  const days = daysBetween(start, end);
  const counts = new Map<string, number>();
  for (const day of days) counts.set(`${day.slice(0, 7)}-01`, (counts.get(`${day.slice(0, 7)}-01`) ?? 0) + 1);
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || b[0].localeCompare(a[0]))[0][0];
}

/** One month at a time; dots count the muscle groups trained, and a tap lists them. */
function WorkoutCalendar({ start, end, selected, settings }: { start: string; end: string; selected: string; settings: Settings }) {
  const [first, last] = calendarSpan(start, end, selected);
  const { data } = useWorkouts(first, last);
  const months = monthsBetween(first, last);
  const inside = selected >= start && selected <= end;
  const [month, setMonth] = useState(() => openingMonth(start, end, selected));
  const [picked, setPicked] = useState(inside ? selected : end);
  const now = today(settings);
  const shown = months.includes(month) ? month : months[months.length - 1];
  const at = months.indexOf(shown);

  // A new day or range reopens on the month that matters most.
  useEffect(() => {
    setMonth(openingMonth(start, end, selected));
    setPicked(selected >= start && selected <= end ? selected : end);
  }, [selected, start, end]);

  const records = new Map((data ?? []).filter((row) => row.workout_date >= first && row.workout_date <= last).map((row): [string, WorkoutRecord] => [row.workout_date, row]));
  const inRange = [...records.values()].filter((row) => row.workout_date >= start && row.workout_date <= end);
  const done = inRange.filter((row) => row.done).length;
  const pickedRecord = records.get(picked);
  const pickedKinds = (pickedRecord?.types ?? []).filter((kind) => kind in WORKOUT_TYPES).map((kind) => WORKOUT_TYPES[kind].label);
  const pickedText = pickedRecord ? (pickedRecord.done ? `Done${pickedKinds.length ? `: ${pickedKinds.join(", ")}` : ", no muscle groups recorded"}` : "Skipped") : "Not recorded";

  return (
    <aside className="vt-stretch-col" aria-labelledby="workouts-title">
      <SectionHead title="Workouts" id="workouts-title">
        <span className="vt-legend">
          <span>
            <i className="vt-key vt-key-met" />
            {done} done
          </span>
          <span>
            <i className="vt-key vt-key-over" />
            {inRange.length - done} skipped
          </span>
        </span>
      </SectionHead>
      <div className="vt-card">
        <div className="vt-cal-nav">
          <button className="lv-icon-button" type="button" aria-label="Previous month" disabled={at <= 0} onClick={() => setMonth(months[at - 1])}>
            <ChevronLeft size={16} />
          </button>
          <strong>{monthLabel(shown)}</strong>
          <button className="lv-icon-button" type="button" aria-label="Next month" disabled={at >= months.length - 1} onClick={() => setMonth(months[at + 1])}>
            <ChevronRight size={16} />
          </button>
        </div>
        <div className="vt-cal">
          {WEEKDAYS.map((name, index) => (
            <span className="vt-cal-weekday" key={index} aria-hidden="true">
              {name}
            </span>
          ))}
          {monthWeeks(shown)
            .flat()
            .map((cell, index) => {
              if (!cell) return <span className="vt-cal-day vt-cal-out" key={`${shown}-${index}`} />;
              const record = records.get(cell);
              const status = statusOf(record);
              const kinds = record?.done ? (record.types ?? []).filter((kind) => kind in WORKOUT_TYPES) : [];
              const outside = cell < start || cell > end;
              const classes = ["vt-cal-day", status, outside && "outside", cell === now && "today"].filter(Boolean).join(" ");
              return (
                <button className={classes} type="button" key={cell} aria-pressed={cell === picked} aria-label={`${cellLabel(cell)}: ${status === "none" ? "not recorded" : status}`} onClick={() => setPicked(cell)}>
                  {Number(cell.slice(8))}
                  {kinds.length > 0 && (
                    <i aria-hidden="true">
                      {kinds.slice(0, 4).map((kind) => (
                        <b key={kind} />
                      ))}
                    </i>
                  )}
                </button>
              );
            })}
        </div>
        <p className="vt-cal-detail">
          <strong>{dayLabel(picked)}</strong> · {pickedText}
        </p>
      </div>
    </aside>
  );
}

type Metric = { label: string; unit: string; decimals: number; icon: LucideIcon };
const WEIGHT: Metric = { label: "Weight", unit: "kg", decimals: 2, icon: Scale };
const BODY_FAT: Metric = { label: "Body fat", unit: "%", decimals: 1, icon: PersonStanding };
const amountOf = (metric: Metric, value: number) => `${value.toFixed(metric.decimals)}${metric.unit === "%" ? "%" : ` ${metric.unit}`}`;

function BodyCard({ metric, series, days, range, target }: { metric: Metric; series: Reading[]; days: string[]; range: [number, number]; target?: number }) {
  const grouped = byDay(series);
  const latest = series[series.length - 1];
  const mean = average(series)!;
  const values = series.map(({ value }) => value);
  const [low, high] = range;
  const Icon = metric.icon;
  const slots: Slot[] = days.map((day) => {
    const periods = grouped.get(day) ?? {};
    const shown = PERIODS.flatMap((period, slot) => (periods[period] ? [{ period, slot, reading: periods[period]! }] : []));
    return {
      day,
      tip: [dayLabel(day), ...shown.map(({ period, reading }) => `${period} ${amountOf(metric, reading.value)}${reading.estimated ? " (est.)" : ""}`), ...(shown.length ? [] : ["not recorded"])].join(" · "),
      bars: shown.map(({ period, slot, reading }) => ({ x: 1.2 + slot * 4, width: 3.4, value: reading.value, className: period.toLowerCase() })),
    };
  });
  const aboveTarget = target !== undefined && mean > target;
  return (
    <div className="vt-card">
      <div className="vt-body-top">
        <div className="vt-tile-label">
          <Icon size={15} />
          {metric.label}
        </div>
        <div className="vt-tile-value">
          {latest.value.toFixed(metric.decimals)}{" "}
          <small>
            {metric.unit}
            {latest.estimated ? " est." : ""} latest
          </small>
        </div>
        <div className="vt-body-stats">
          <span className={aboveTarget ? "danger" : ""}>
            Average
            <b>{amountOf(metric, mean)}</b>
          </span>
          {target !== undefined ? (
            <span>
              Target
              <b>{amountOf(metric, target)}</b>
            </span>
          ) : (
            <span>
              Range
              <b>
                {Math.min(...values).toFixed(1)} to {Math.max(...values).toFixed(1)}
              </b>
            </span>
          )}
        </div>
      </div>
      <BarPlot slots={slots} low={low} high={high} target={target} label={`${metric.label} per day`} />
      <Axis days={days} />
      <div className="vt-legend">
        {PERIODS.map((period) => (
          <span key={period}>
            <i className={`vt-key vt-key-${period.toLowerCase()}`} />
            {period}
          </span>
        ))}
        {target !== undefined && (
          <span>
            <i className="vt-key vt-key-line" />
            Target
          </span>
        )}
        <span>
          Bars start at {amountOf({ ...metric, decimals: 0 }, low)}
        </span>
      </div>
    </div>
  );
}

function Body({ start, end, settings }: { start: string; end: string; settings: Settings }) {
  const { data } = useBodyComposition(start, end);
  if (!data) return null;
  const weight = readings(data.weight, settings);
  const fat = readings(data.body_fat, settings);
  if (!weight.length && !fat.length) return null;
  const target = Number(data.body_fat_target_percent);
  const days = daysBetween(start, end);
  const estimated = fat.some((reading) => reading.estimated);
  return (
    <section className="vt-month-row" aria-labelledby="body-title">
      <SectionHead title="Body" id="body-title">
        {estimated && <p className="vt-head-note">Body fat is estimated from body water, within about 3 to 5 points</p>}
      </SectionHead>
      <div className="vt-body-grid">
        {weight.length > 0 && <BodyCard metric={WEIGHT} series={weight} days={days} range={weightRange(weight)} />}
        {fat.length > 0 && <BodyCard metric={BODY_FAT} series={fat} days={days} range={fatRange(fat, target)} target={target} />}
      </div>
    </section>
  );
}

const VERDICT_LABELS: Record<string, string> = { prefer: "Prefer", avoid: "Avoid" };

type TileSize = "hero" | "wide" | "small";

/** Tiles grow with how often a food was had; a food without a photo stays small. */
function tileSize(food: AnalysisFood, most: number, rank: number): TileSize {
  if (!photoSource(food.image_url)) return "small";
  const ratio = food.count / most;
  if (rank === 0 || ratio >= 0.6) return "hero";
  if (ratio >= 0.3) return "wide";
  return "small";
}

/** One food in the collage; a tap opens its photo large with what it added up to. */
function CollageTile({ food, size, span }: { food: AnalysisFood; size: TileSize; span: string }) {
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState(false);
  const url = photoSource(food.image_url, size === "hero");
  const verdict = VERDICT_LABELS[food.verdict.kind];
  const times = `${food.count}× on ${food.days} day${food.days === 1 ? "" : "s"}`;
  return (
    <>
      <button className={`vt-tile-photo ${size}${url && !failed ? "" : " empty"}`} type="button" title={`${food.name} · ${times}`} aria-label={`${food.name}, ${times}${verdict ? `, ${verdict.toLowerCase()}` : ""}`} onClick={() => setOpen(true)}>
        {url && !failed ? <img src={url} alt="" width={size === "small" ? 108 : 216} height={size === "wide" ? 108 : size === "hero" ? 216 : 108} loading="lazy" decoding="async" onError={() => setFailed(true)} /> : <Utensils size={18} aria-hidden="true" />}
        <span className="vt-tile-count">{food.count}×</span>
        {verdict && (
          <span className={`vt-tile-verdict ${food.verdict.kind}`} aria-hidden="true">
            {food.verdict.kind === "prefer" ? <ThumbsUp size={11} /> : <ThumbsDown size={11} />}
          </span>
        )}
        <span className="vt-tile-name">{food.name}</span>
      </button>
      {open &&
        createPortal(
          <Dialog title={food.name} size="large" onClose={() => setOpen(false)}>
            {url && !failed && <img className="vt-photo-large" src={photoSource(food.image_url, true)} alt={food.name} decoding="async" />}
            <p className="vt-tile-detail">
              <strong>{times}</strong> {span}
              {verdict && (
                <em className={`vt-verdict ${food.verdict.kind}`}>
                  {verdict}
                  {food.verdict.source === "override" ? ` · ${OVERRIDE_LABEL.toLowerCase()}` : ""}
                </em>
              )}
            </p>
            <div className="vt-tile-macros">
              {(
                [
                  ["Calories", `${number(food.totals.calories)} kcal`],
                  ["Protein", `${number(food.totals.protein_g, 1)} g`],
                  ["Carbs", `${number(food.totals.carbs_g, 1)} g`],
                  ["Fat", `${number(food.totals.fat_g, 1)} g`],
                ] as const
              ).map(([label, value]) => (
                <span key={label}>
                  {label}
                  <b>{value}</b>
                </span>
              ))}
            </div>
            {food.verdict.reason && <p className="vt-empty-note">{food.verdict.reason}</p>}
          </Dialog>,
          document.body,
        )}
    </>
  );
}

/** Every food in the range as a photo collage, the most frequent biggest, scrolling inside its card. */
function Foods({ foods, span }: { foods: AnalysisFood[]; span: string }) {
  const most = Math.max(...foods.map((food) => food.count), 1);
  return (
    <section className="vt-stretch-col" aria-labelledby="foods-title">
      <SectionHead title="What you had" id="foods-title">
        <span className="vt-head-note">
          {foods.length} foods {span}, bigger the more often you had them
        </span>
      </SectionHead>
      <div className="vt-scroll-box">
        <div className="vt-collage-wrap" tabIndex={0} role="region" aria-label="Foods eaten in this range">
          <div className="vt-collage">
            {foods.map((food, rank) => (
              <CollageTile key={food.name} food={food} size={tileSize(food, most, rank)} span={span} />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function Choice({ kind, icon: Icon, title, rule, foods, empty }: { kind: string; icon: LucideIcon; title: string; rule: string; foods: AnalysisFood[]; empty: string }) {
  const [all, setAll] = useState(false);
  const shown = all ? foods : foods.slice(0, CHOICES_SHOWN);
  return (
    <section className={`vt-card vt-choice ${kind}`} aria-label={title}>
      <h3>
        <Icon size={16} />
        {title}
      </h3>
      <p>{rule}</p>
      {foods.length ? (
        <ul>
          {shown.map((food) => (
            <li key={food.name}>
              <strong>
                {food.name}
                {food.verdict.source === "override" && <em className={`vt-verdict ${kind}`}>{OVERRIDE_LABEL.toLowerCase()}</em>}
              </strong>
              <span>
                {food.count}× · {number(food.totals.calories)} kcal · {food.verdict.reason}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="vt-empty-note">{empty}</p>
      )}
      {foods.length > CHOICES_SHOWN && (
        <button className="vt-link-button" type="button" onClick={() => setAll(!all)}>
          {all ? "Show fewer" : `Show all ${foods.length}`}
        </button>
      )}
    </section>
  );
}

const CONTRIBUTORS: [string, string, string, LucideIcon][] = [
  ["calories", "Calories", "kcal", Flame],
  ["protein_g", "Protein", "g", Dumbbell],
  ["carbs_g", "Carbs", "g", Wheat],
  ["fat_g", "Fat", "g", Droplet],
  ["added_sugar_g", "Added sugar", "g", Apple],
];

const amountIn = (value: number, unit: string) => (unit === "kcal" ? `${number(value)} ${unit}` : `${number(value, 1)} ${unit}`);

function Contributors({ analysis, span, period }: { analysis: Analysis; span: string; period: string }) {
  return (
    <section className="vt-month-row" aria-labelledby="contributors-title">
      <SectionHead title="Top contributors" id="contributors-title">
        <p className="vt-head-note">Share of the {period}'s total</p>
      </SectionHead>
      <div className="vt-contributors">
        {CONTRIBUTORS.map(([field, label, unit, Icon]) => (
          <section className="vt-card" key={field} aria-label={`${label} contributors`}>
            <h3>
              <Icon size={16} />
              {label}
            </h3>
            <p className="vt-contrib-total">
              {amountIn(analysis.totals[field], unit)} {span}
            </p>
            {analysis.top_contributors[field].length ? (
              analysis.top_contributors[field].map((item) => (
                <div className="vt-share" key={item.name} title={`${item.name}: ${amountIn(item.amount, unit)} (${Math.round(item.share * 100)}% of the ${period})`}>
                  <span>{item.name}</span>
                  <strong>{Math.round(item.share * 100)}%</strong>
                  <div className="vt-share-track">
                    <i style={{ width: `${(item.share * 100).toFixed(1)}%` }} />
                  </div>
                </div>
              ))
            ) : (
              <p className="vt-empty-note">None logged {span}.</p>
            )}
          </section>
        ))}
      </div>
    </section>
  );
}

function RangePicker({ analysis, custom }: { analysis: Analysis; custom: boolean }) {
  const act = useAct();
  const { start, end } = analysis.window;
  const [from, setFrom] = useState(start);
  const [to, setTo] = useState(end);
  const [error, setError] = useState("");

  // Follows ranges set elsewhere, such as by the assistant.
  useEffect(() => {
    setFrom(start);
    setTo(end);
  }, [start, end]);

  const save = async (nextFrom: string, nextTo: string) => {
    setFrom(nextFrom);
    setTo(nextTo);
    if (!nextFrom || !nextTo || (nextFrom === start && nextTo === end)) return;
    setError("");
    await act(async () => {
      try {
        await vita.setRange(nextFrom, nextTo);
      } catch (failure) {
        setFrom(start);
        setTo(end);
        setError(messageOf(failure, "Could not update the date range."));
      }
    });
  };

  const reset = () =>
    act(async () => {
      setError("");
      await vita.resetRange();
    }, "Could not update the date range.");

  return (
    <div className="vt-range-wrap">
      <div className="vt-range" role="group" aria-label="Date range">
        <label className="lv-field">
          From
          <input className="lv-input" type="date" aria-label="Range from" value={from} onChange={(event) => save(event.target.value, to)} />
        </label>
        <label className="lv-field">
          To
          <input className="lv-input" type="date" aria-label="Range to" value={to} onChange={(event) => save(from, event.target.value)} />
        </label>
        {custom && (
          <button className="lv-button" type="button" onClick={reset}>
            <CalendarRange size={16} />
            This month
          </button>
        )}
      </div>
      {error && <p className="lv-alert lv-alert-error">{error}</p>}
    </div>
  );
}

function MonthHead({ analysis, custom }: { analysis: Analysis; custom: boolean }) {
  const { window: range } = analysis;
  return (
    <div className="vt-month-head">
      <div className="vt-day-head">
        <h2>{range.label}</h2>
        <p>
          {custom ? "Custom range · " : ""}
          {analysis.entries} entries · {analysis.foods.length} foods · {analysis.days_logged} of {range.days} days logged
        </p>
      </div>
      <RangePicker analysis={analysis} custom={custom} />
    </div>
  );
}

export function Monthly({ day, settings }: { day: string; settings: Settings }) {
  const { data: analysis, error } = useAnalysis(day);
  const recommendations = useRecommendations();

  if (error && !analysis) return <p className="lv-alert lv-alert-error">{messageOf(error, "The Luna Vita service is unavailable.")}</p>;
  if (!analysis) return <SummaryTiles values={null} targets={null} averaged />;

  const { window: range } = analysis;
  const custom = analysis.range_source === "saved";
  const period = custom ? "range" : "month";
  const span = custom ? "in this range" : "this month";
  const calendar = <WorkoutCalendar start={range.start} end={range.end} selected={day} settings={settings} />;
  const body = <Body start={range.start} end={range.end} settings={settings} />;

  if (!analysis.foods.length) {
    return (
      <>
        <MonthHead analysis={analysis} custom={custom} />
        <p className="lv-alert">No food entries {span} yet.</p>
        <div className="vt-day-grid vt-month-row">
          <div />
          {calendar}
        </div>
        {body}
      </>
    );
  }

  const averages = Object.fromEntries(NUTRIENTS.map((nutrient: Nutrient) => [nutrient.key, Number(analysis.daily_averages[nutrient.summaryField])]));
  const targets = recommendations.data ? targetsOf(recommendations.data) : null;
  const { rules } = analysis;
  const share = (value: number) => `${Math.round(value * 100)}%`;

  return (
    <>
      <MonthHead analysis={analysis} custom={custom} />
      <p className="vt-caption vt-averages-note">Daily average across logged days, not counting today</p>
      <SummaryTiles values={averages} targets={targets} averaged />
      <div className="vt-day-grid vt-month-row vt-stretch">
        {targets ? <PerDay days={analysis.daily_totals} averages={averages} targets={targets} /> : <div />}
        {calendar}
      </div>
      {body}
      <div className="vt-day-grid vt-month-row vt-stretch">
        <Foods foods={analysis.foods} span={span} />
        <aside className="vt-stretch-col" aria-labelledby="choices-title">
          <SectionHead title="Food choices" id="choices-title" />
          <div className="vt-rail">
            <Choice
              kind="prefer"
              icon={ThumbsUp}
              title="Prefer"
              rule={`At least ${share(rules.prefer_min_protein_share)} of calories from protein, at most ${share(rules.prefer_max_carb_share)} from carbs, little added sugar.`}
              foods={analysis.prefer}
              empty={`Nothing ${span} met the high-protein, low-carb bar.`}
            />
            <Choice
              kind="avoid"
              icon={ThumbsDown}
              title="Avoid"
              rule={`${share(rules.avoid_min_added_sugar_share)}+ of calories from added sugar, or under ${share(rules.avoid_max_protein_share)} from protein. Biggest calorie impact first.`}
              foods={analysis.avoid}
              empty={`Nothing ${span} was sugar-heavy or protein-poor.`}
            />
          </div>
        </aside>
      </div>
      <Contributors analysis={analysis} span={span} period={period} />
    </>
  );
}
