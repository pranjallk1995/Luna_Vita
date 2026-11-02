import { TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";

import type { Totals } from "../api";
import { NUTRIENTS, number, percentage, standing } from "../nutrition";

/** A section title with its controls on the right, shared by every column so their tops line up. */
export function SectionHead({ title, children, id }: { title: ReactNode; children?: ReactNode; id?: string }) {
  return (
    <div className="vt-section-head">
      <h2 id={id}>{title}</h2>
      {children}
    </div>
  );
}

export const targetsOf = (recommendations: Totals) =>
  Object.fromEntries(NUTRIENTS.map((nutrient) => [nutrient.key, Number(recommendations[nutrient.targetField])]));

/** Progress toward a target as a ring; past 100% it stays full and the tile's state colors it. */
export function Ring({ percent, label }: { percent: number; label: string }) {
  const arc = Math.min(Math.max(percent, 0), 100);
  return (
    <div className="vt-ring" role="img" aria-label={label}>
      <svg viewBox="0 0 36 36" aria-hidden="true">
        <circle className="vt-ring-track" cx="18" cy="18" r="15.9155" pathLength={100} />
        {arc > 0 && <circle className="vt-ring-fill" cx="18" cy="18" r="15.9155" pathLength={100} strokeDasharray={`${arc} 100`} />}
      </svg>
      <span aria-hidden="true">{percent}%</span>
    </div>
  );
}

type TilesProps = {
  /** Null while loading: the tiles keep their size, so the page does not jump. */
  values: Record<string, number> | null;
  targets: Record<string, number> | null;
  /** Monthly daily averages read "a day" and "on average" rather than "left". */
  averaged?: boolean;
};

/** Calories as the lead tile, then protein, carbs, fat and added sugar. */
export function SummaryTiles({ values, targets, averaged = false }: TilesProps) {
  const [calories, ...meters] = NUTRIENTS;
  const ready = values && targets;
  const kcal = ready ? values.calories : 0;
  const goal = ready ? targets.calories : 0;
  const heroStatus = ready ? standing(calories, kcal, goal, averaged).status : "";
  const percent = percentage(kcal, goal);
  const over = kcal > goal;
  const CalorieIcon = calories.icon;

  return (
    <section className="vt-summary" aria-label={averaged ? "Daily averages" : "Nutrition summary"} aria-busy={!ready}>
      <div className={`vt-tile vt-tile-hero ${heroStatus}`}>
        <div className="vt-tile-label">
          <CalorieIcon size={15} />
          {averaged ? "Calories, daily average" : "Calories"}
        </div>
        <div className="vt-tile-body">
          <div className="vt-tile-text">
            <div className="vt-tile-value">
              {ready ? number(averaged ? kcal : Math.abs(goal - kcal)) : "–"} <small>{averaged ? "kcal a day" : over ? "kcal over" : "kcal left"}</small>
            </div>
            <div className="vt-tile-foot">
              <span className="vt-tile-state">
                {heroStatus && <TriangleAlert size={13} />}
                {!ready
                  ? "Loading"
                  : averaged
                    ? `${number(Math.abs(kcal - goal))} kcal ${over ? "over" : "under"} the ${number(goal)} target`
                    : `${number(kcal)} of ${number(goal)} kcal`}
              </span>
            </div>
          </div>
          <Ring percent={percent} label={`${percent}% of the calorie target`} />
        </div>
      </div>
      <div className="vt-meters">
        {meters.map((nutrient) => {
          const value = ready ? values[nutrient.key] : 0;
          const target = ready ? targets[nutrient.key] : 0;
          const share = percentage(value, target);
          const state = ready ? standing(nutrient, value, target, averaged) : { status: "", text: "Loading" };
          const Icon = nutrient.icon;
          return (
            <div className={`vt-tile ${state.status}`} key={nutrient.key}>
              <div className="vt-tile-label">
                <Icon size={15} />
                {nutrient.label}
              </div>
              <div className="vt-tile-body">
                <div className="vt-tile-text">
                  <div className="vt-tile-value">
                    {ready ? number(value, nutrient.decimals) : "–"}{" "}
                    <small>
                      / {ready ? number(target) : "–"} {nutrient.unit}
                      {nutrient.targetSuffix}
                    </small>
                  </div>
                  <div className="vt-tile-foot">
                    <span className="vt-tile-state">
                      {(state.status === "danger" || state.status === "warning") && <TriangleAlert size={13} />}
                      {state.text}
                    </span>
                  </div>
                </div>
                <Ring percent={share} label={`${share}% of the ${nutrient.label.toLowerCase()} ${nutrient.isFloor ? "goal" : "limit"}`} />
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
