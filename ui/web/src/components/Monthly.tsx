import { CalendarRange, Check, Dumbbell, Flame, Apple, Droplet, PersonStanding, Scale, ThumbsDown, ThumbsUp, Wheat, X, type LucideIcon } from "lucide-react";
import { useEffect, useState } from "react";

import { useAct, useAnalysis, useBodyComposition, useRecommendations, useWorkouts, vita, type Analysis, type AnalysisFood, type DayTotals, type Settings, type WorkoutRecord } from "../api";
import { PERIODS, average, byDay, fatRange, readings, weightRange, type Reading } from "../body";
import { dayLabel, daysBetween, today } from "../clock";
import { messageOf } from "../lib";
import { MACROS, NUTRIENTS, number, type Nutrient } from "../nutrition";
import { MAX_ICONS, WORKOUT_TYPES, calendarSpan, cellLabel, monthLabel, monthWeeks, monthsBetween, statusOf } from "../workouts";
import { FoodPhoto } from "./FoodPhoto";
import { NutrientCards, SectionHeading, cardClasses, targetsOf } from "./shared";

const SLOT = 10; // viewBox units per day
const HEIGHT = 60;
const OVERRIDE_LABEL = "Your rating";
const VERDICT_LABELS: Record<string, string> = { prefer: "Prefer", avoid: "Avoid", neutral: "" };
const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function DailyTrend({ nutrient, days, value, target }: { nutrient: Nutrient; days: DayTotals[]; value: number; target: number }) {
  const logged = days.filter((day) => day.logged).map((day) => Number(day[nutrient.summaryField] ?? 0));
  const scaleMax = Math.max(target, ...logged, 1) * 1.08;
  const y = (amount: number) => HEIGHT - (amount / scaleMax) * HEIGHT;
  const width = SLOT * days.length;
  const barWidth = 7;
  const middle = days[Math.floor(days.length / 2)].date;
  return (
    <div className={`nutrition-card nutrient-trend ${cardClasses(nutrient, value, target)}`}>
      <div className="nutrient-trend-head">
        <span>Per day</span>
        <span>
          <i className="nutrient-trend-key" />
          Target {number(target)} {nutrient.unit}
        </span>
      </div>
      <svg className="nutrient-trend-plot" viewBox={`0 0 ${width} ${HEIGHT}`} preserveAspectRatio="none" role="img" aria-label={`${nutrient.label} per day`}>
        <line className="nutrient-trend-base" x1="0" x2={width} y1={HEIGHT} y2={HEIGHT} />
        {days.map((day, index) => {
          const x = index * SLOT;
          const amount = Number(day[nutrient.summaryField] ?? 0);
          return (
            <g className="nutrient-trend-day" key={day.date}>
              <title>{`${dayLabel(day.date)} · ${day.logged ? `${number(amount, nutrient.decimals)} ${nutrient.unit}` : "not logged"}`}</title>
              <rect className="nutrient-trend-hit" x={x} y="0" width={SLOT} height={HEIGHT} />
              {day.logged && <rect className="nutrient-trend-bar" x={x + (SLOT - barWidth) / 2} y={y(amount)} width={barWidth} height={HEIGHT - y(amount)} />}
            </g>
          );
        })}
        <line className="nutrient-trend-target" x1="0" x2={width} y1={y(target)} y2={y(target)} />
      </svg>
      <div className="nutrient-trend-axis">
        <span>{dayLabel(days[0].date)}</span>
        <span>{dayLabel(middle)}</span>
        <span>{dayLabel(days[days.length - 1].date)}</span>
      </div>
    </div>
  );
}

type Metric = { label: string; unit: string; decimals: number; icon: LucideIcon };
const WEIGHT: Metric = { label: "Weight", unit: "kg", decimals: 2, icon: Scale };
const BODY_FAT: Metric = { label: "Body fat", unit: "%", decimals: 1, icon: PersonStanding };
const amountOf = (metric: Metric, value: number) => `${value.toFixed(metric.decimals)}${metric.unit === "%" ? "" : " "}${metric.unit}`;

function BodyPlot({ metric, series, days, low, high, target }: { metric: Metric; series: Reading[]; days: string[]; low: number; high: number; target?: number }) {
  const y = (value: number) => HEIGHT - ((value - low) / (high - low)) * HEIGHT;
  const grouped = byDay(series);
  const width = SLOT * days.length;
  const [barWidth, barGap] = [3.6, 0.8];
  const inset = (SLOT - 2 * barWidth - barGap) / 2;
  return (
    <svg className="nutrient-trend-plot body-trend-plot" viewBox={`0 0 ${width} ${HEIGHT}`} preserveAspectRatio="none" role="img" aria-label={`${metric.label} per day`}>
      <line className="nutrient-trend-base" x1="0" x2={width} y1={HEIGHT} y2={HEIGHT} />
      {days.map((day, index) => {
        const periods = grouped.get(day) ?? {};
        const shown = PERIODS.flatMap((period, slot) => (periods[period] ? [{ period, slot, reading: periods[period]! }] : []));
        const tips = [
          dayLabel(day),
          ...shown.map(({ period, reading }) => `${period} ${amountOf(metric, reading.value)}${reading.estimated ? " (est.)" : ""}`),
          ...(shown.length ? [] : ["not recorded"]),
        ];
        return (
          <g className="nutrient-trend-day" key={day}>
            <title>{tips.join(" · ")}</title>
            <rect className="nutrient-trend-hit" x={index * SLOT} y="0" width={SLOT} height={HEIGHT} />
            {shown.map(({ period, slot, reading }) => (
              <rect
                className={`body-trend-bar ${period.toLowerCase()}`}
                key={period}
                x={index * SLOT + inset + slot * (barWidth + barGap)}
                y={y(reading.value)}
                width={barWidth}
                height={HEIGHT - y(reading.value)}
              />
            ))}
          </g>
        );
      })}
      {target !== undefined && <line className="nutrient-trend-target" x1="0" x2={width} y1={y(target)} y2={y(target)} />}
    </svg>
  );
}

function BodyHead({ metric, latest, children }: { metric: Metric; latest: Reading; children: React.ReactNode }) {
  const Icon = metric.icon;
  return (
    <div className="body-trend-head">
      <span className="nutrition-card-label">
        <span className="nutrition-card-icon">
          <Icon size={16} />
        </span>
        {metric.label}
      </span>
      <strong>
        {amountOf(metric, latest.value)}
        {latest.estimated ? " (est.)" : ""}
      </strong>
      <span className="body-trend-note">{children}</span>
    </div>
  );
}

function AverageCard({ metric, series, target }: { metric: Metric; series: Reading[]; target?: number }) {
  const value = average(series);
  if (value === null) return null;
  const Icon = metric.icon;
  return (
    <div className={target !== undefined && value > target ? "body-average-card danger" : "body-average-card"}>
      <span className="nutrition-card-label">
        <span className="nutrition-card-icon">
          <Icon size={16} />
        </span>
        Average {metric.label.toLowerCase()}
      </span>
      <strong>{amountOf(metric, value)}</strong>
      <small>
        {series.length} reading{series.length === 1 ? "" : "s"}
      </small>
    </div>
  );
}

function BodyCard({ start, end, settings }: { start: string; end: string; settings: Settings }) {
  const { data } = useBodyComposition(start, end);
  if (!data) return null;
  const weight = readings(data.weight, settings);
  const fat = readings(data.body_fat, settings);
  if (!weight.length && !fat.length) return null;
  const target = Number(data.body_fat_target_percent);
  const days = daysBetween(start, end);
  const [weightLow, weightHigh] = weight.length ? weightRange(weight) : [0, 1];
  const [fatLow, fatHigh] = fat.length ? fatRange(fat, target) : [0, 1];
  return (
    <div className="nutrition-card body-trend-card">
      {weight.length > 0 && (
        <div className="body-trend-section">
          <BodyHead metric={WEIGHT} latest={weight[weight.length - 1]}>
            {PERIODS.map((period) => (
              <span key={period}>
                <i className={`body-trend-key ${period.toLowerCase()}`} />
                {period}
              </span>
            ))}
            <span>Bars from {weightLow.toFixed(0)} kg</span>
          </BodyHead>
          <BodyPlot metric={WEIGHT} series={weight} days={days} low={weightLow} high={weightHigh} />
        </div>
      )}
      {fat.length > 0 && (
        <div className="body-trend-section">
          <BodyHead metric={BODY_FAT} latest={fat[fat.length - 1]}>
            <i className="nutrient-trend-key" />
            Target {amountOf(BODY_FAT, target)}
            <span>Bars from {fatLow.toFixed(0)}%</span>
          </BodyHead>
          <BodyPlot metric={BODY_FAT} series={fat} days={days} low={fatLow} high={fatHigh} target={target} />
        </div>
      )}
      <div className="nutrient-trend-axis">
        <span>{dayLabel(start)}</span>
        <span>{dayLabel(days[Math.floor(days.length / 2)])}</span>
        <span>{dayLabel(end)}</span>
      </div>
      <div className="body-trend-averages">
        <AverageCard metric={WEIGHT} series={weight} />
        <AverageCard metric={BODY_FAT} series={fat} target={target} />
      </div>
    </div>
  );
}

function WorkoutTypeIcon({ kind }: { kind: string }) {
  const { label, body } = WORKOUT_TYPES[kind];
  // The bodies are this app's own constants, in workouts.ts.
  return (
    <svg className="workout-type-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" role="img" aria-label={label} dangerouslySetInnerHTML={{ __html: body }} />
  );
}

function WorkoutCalendar({ start, end, selected, settings }: { start: string; end: string; selected: string; settings: Settings }) {
  const [first, last] = calendarSpan(start, end, selected);
  const { data } = useWorkouts(first, last);
  const now = today(settings);
  const records = new Map((data ?? []).filter((row) => row.workout_date >= first && row.workout_date <= last).map((row): [string, WorkoutRecord] => [row.workout_date, row]));
  const done = [...records.values()].filter((row) => row.done).length;
  const skipped = records.size - done;

  return (
    <div className="workout-calendar">
      <div className="workout-calendar-head">
        <strong>Workouts</strong>
        <span className="workout-legend">
          <span>
            <i className="workout-key done" />
            {done} done
          </span>
          <span>
            <i className="workout-key skipped" />
            {skipped} skipped
          </span>
        </span>
      </div>
      <div className="workout-months">
        {monthsBetween(first, last).map((month) => (
          <div className="workout-month" key={month}>
            <div className="workout-month-label">{monthLabel(month)}</div>
            <div className="workout-grid">
              {WEEKDAYS.map((name) => (
                <div className="workout-weekday" key={name}>
                  {name}
                </div>
              ))}
              {monthWeeks(month).flat().map((cell, index) => {
                if (!cell) return <div className="workout-day outside" key={`${month}-${index}`} />;
                const record = records.get(cell);
                const status = statusOf(record);
                const kinds = record?.done ? (record.types ?? []).filter((kind) => kind in WORKOUT_TYPES) : [];
                const label = { done: "Workout done", skipped: "Workout skipped", none: "Not recorded" }[status];
                const classes = ["workout-day", status, cell === selected && "selected", cell === now && "today"].filter(Boolean).join(" ");
                return (
                  <div className={classes} key={cell} title={`${cellLabel(cell)} · ${label}${kinds.length ? `: ${kinds.map((kind) => WORKOUT_TYPES[kind].label).join(", ")}` : ""}`}>
                    <span className="workout-date">{Number(cell.slice(8))}</span>
                    {kinds.length > 0 ? (
                      <span className="workout-types">
                        {kinds.slice(0, MAX_ICONS).map((kind) => (
                          <WorkoutTypeIcon kind={kind} key={kind} />
                        ))}
                        {kinds.length > MAX_ICONS && <span className="workout-type-more">+{kinds.length - MAX_ICONS}</span>}
                      </span>
                    ) : status === "done" ? (
                      <span className="workout-marker">
                        <Check size={14} />
                      </span>
                    ) : status === "skipped" ? (
                      <span className="workout-marker">
                        <X size={14} />
                      </span>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

const CHIPS = [
  ["protein_g", "Protein"],
  ["carbs_g", "Carbs"],
  ["fat_g", "Fat"],
  ["added_sugar_g", "Sugar"],
] as const;

function FoodTile({ food }: { food: AnalysisFood }) {
  const { totals, verdict } = food;
  const label = VERDICT_LABELS[verdict.kind];
  const shownVerdict = verdict.source === "override" ? (label ? `${label} (${OVERRIDE_LABEL.toLowerCase()})` : OVERRIDE_LABEL) : label;
  const days = `${food.days} day${food.days === 1 ? "" : "s"}`;
  return (
    <figure
      className={`food-tile ${verdict.kind}`}
      title={`${food.name}: ${food.count}× over ${days}, ${number(totals.calories)} kcal, ${Math.round(food.protein_share * 100)}% of calories from protein`}
    >
      <div className="food-tile-media">
        <FoodPhoto source={food.image_url} alt={food.name} className="vt-tile-photo" emptyClass="food-tile-empty" />
        <span className="food-tile-count">{food.count}×</span>
        {shownVerdict && <span className="food-tile-verdict">{shownVerdict}</span>}
      </div>
      <figcaption>
        <strong>{food.name}</strong>
        <span className="food-tile-meta">
          {days} · {number(totals.calories)} kcal
        </span>
        <div className="food-chips">
          {CHIPS.map(([field, chip]) => {
            const macro = MACROS.find((item) => item.field === field)!;
            return (
              <span className="food-chip" style={{ "--chip": macro.color } as React.CSSProperties} title={`${macro.label}: ${number(totals[field], 1)} g`} key={field}>
                <i />
                {chip}
                <b>{number(totals[field])} g</b>
              </span>
            );
          })}
        </div>
      </figcaption>
    </figure>
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
    <>
      <SectionHeading title="Top contributors" description={`Which foods supplied the most of each nutrient, as a share of the ${period}'s total.`} />
      <section className="analysis-contributors">
        {CONTRIBUTORS.map(([field, label, unit, Icon]) => (
          <div className="analysis-panel" key={field}>
            <h3>
              <span className="analysis-icon">
                <Icon size={16} />
              </span>
              {label}
            </h3>
            <div className="analysis-panel-total">
              {amountIn(analysis.totals[field], unit)} {span}
            </div>
            {analysis.top_contributors[field].length ? (
              analysis.top_contributors[field].map((item) => (
                <div className="analysis-bar-row" key={item.name} title={`${item.name}: ${amountIn(item.amount, unit)} (${Math.round(item.share * 100)}% of the ${period})`}>
                  <div className="analysis-bar-name">{item.name}</div>
                  <div className="analysis-bar-line">
                    <div className="analysis-bar-track">
                      <div className="analysis-bar-fill" style={{ width: `${(item.share * 100).toFixed(1)}%` }} />
                    </div>
                    <strong>{Math.round(item.share * 100)}%</strong>
                  </div>
                </div>
              ))
            ) : (
              <p className="analysis-empty">None logged {span}.</p>
            )}
          </div>
        ))}
      </section>
    </>
  );
}

function Suggestions({ kind, icon: Icon, title, description, foods, empty }: { kind: string; icon: LucideIcon; title: string; description: string; foods: AnalysisFood[]; empty: string }) {
  return (
    <div className={`analysis-suggestions ${kind}`}>
      <h3>
        <span className="analysis-icon">
          <Icon size={16} />
        </span>
        {title}
      </h3>
      <p>{description}</p>
      {foods.length ? (
        <ul>
          {foods.map((food) => (
            <li key={food.name}>
              <span className="analysis-food">
                {food.name}
                {food.verdict.source === "override" && <span className="analysis-badge">{OVERRIDE_LABEL}</span>}
              </span>
              <span className="analysis-meta">
                {food.count}× · {number(food.totals.calories)} kcal
              </span>
              <span className="analysis-reason">{food.verdict.reason}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="analysis-empty">{empty}</p>
      )}
    </div>
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
    <>
      <div className="vt-range">
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
    </>
  );
}

export function Monthly({ day, settings }: { day: string; settings: Settings }) {
  const { data: analysis, error } = useAnalysis(day);
  const recommendations = useRecommendations();

  if (error && !analysis) return <p className="lv-alert lv-alert-error">{messageOf(error, "The Luna Vita service is unavailable.")}</p>;
  if (!analysis) return null;

  const { window: range } = analysis;
  const custom = analysis.range_source === "saved";
  const period = custom ? "range" : "month";
  const span = custom ? "in this range" : "this month";
  const picker = <RangePicker analysis={analysis} custom={custom} />;
  const body = <BodyCard start={range.start} end={range.end} settings={settings} />;
  const calendar = <WorkoutCalendar start={range.start} end={range.end} selected={day} settings={settings} />;

  if (!analysis.foods.length) {
    return (
      <>
        {picker}
        <SectionHeading title="Overview" description={range.label} />
        {body}
        {calendar}
        <p className="lv-alert">No food entries {span} yet.</p>
      </>
    );
  }

  const values = Object.fromEntries(NUTRIENTS.map((nutrient) => [nutrient.key, Number(analysis.daily_averages[nutrient.summaryField])]));
  const targets = recommendations.data ? targetsOf(recommendations.data) : null;
  const { rules } = analysis;
  const share = (value: number) => `${Math.round(value * 100)}%`;

  return (
    <>
      {picker}
      <SectionHeading
        title="Overview"
        description={`${range.label}${custom ? " · custom range" : ""} · ${analysis.entries} entries · ${analysis.foods.length} different foods · ${analysis.days_logged} of ${range.days} days logged`}
      />
      {targets ? (
        <>
          <div className="analysis-caption">Daily average across logged days, not counting today, with each day below</div>
          <div className="overview-grid">
            <NutrientCards
              values={values}
              targets={targets}
              footers={Object.fromEntries(
                NUTRIENTS.map((nutrient) => [
                  nutrient.key,
                  <DailyTrend nutrient={nutrient} days={analysis.daily_totals} value={values[nutrient.key]} target={targets[nutrient.key]} key={nutrient.key} />,
                ]),
              )}
            />
            {body}
          </div>
        </>
      ) : (
        body
      )}
      {calendar}
      <SectionHeading title="What you had" description={`Each food logged ${span}, most frequent first, with its total macros.`} />
      <div className="food-gallery">
        {analysis.foods.map((food) => (
          <FoodTile food={food} key={food.name} />
        ))}
      </div>
      <Contributors analysis={analysis} span={span} period={period} />
      <SectionHeading title="Food choices" description={`Rated on macros: protein share of calories, carbs, and added sugar. "${OVERRIDE_LABEL}" marks ratings set through the assistant.`} />
      <section className="analysis-choices">
        <Suggestions
          kind="prefer"
          icon={ThumbsUp}
          title="Prefer"
          description={`At least ${share(rules.prefer_min_protein_share)} of calories from protein, at most ${share(rules.prefer_max_carb_share)} from carbs, little added sugar.`}
          foods={analysis.prefer}
          empty={`Nothing ${span} met the high-protein, low-carb bar.`}
        />
        <Suggestions
          kind="avoid"
          icon={ThumbsDown}
          title="Avoid"
          description={`${share(rules.avoid_min_added_sugar_share)}+ of calories from added sugar, or under ${share(rules.avoid_max_protein_share)} from protein. Biggest calorie impact first.`}
          foods={analysis.avoid}
          empty={`Nothing ${span} was sugar-heavy or protein-poor.`}
        />
      </section>
    </>
  );
}
