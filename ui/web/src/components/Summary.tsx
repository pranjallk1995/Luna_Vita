import { useRecommendations, useSummary } from "../api";
import { messageOf } from "../lib";
import { NUTRIENTS, number, percentage } from "../nutrition";
import { NutrientCards, targetsOf } from "./shared";

export function Summary({ day }: { day: string }) {
  const summary = useSummary(day);
  const recommendations = useRecommendations();

  if (summary.error) return <p className="lv-alert lv-alert-error">{messageOf(summary.error, "The Luna Vita service is unavailable.")}</p>;
  if (!summary.data || recommendations.isPending) return null;
  if (!recommendations.data) return <p className="lv-alert">Daily nutrition recommendations have not been configured.</p>;

  const values = Object.fromEntries(NUTRIENTS.map((nutrient) => [nutrient.key, Number(summary.data[nutrient.summaryField])]));
  const targets = targetsOf(recommendations.data);
  const percent = percentage(values.calories, targets.calories);

  return (
    <section className="nutrition-panel">
      <div className="nutrition-head">
        <div className="nutrition-title">
          <h2>Today's Nutrition</h2>
          <p>Running totals from today's food log</p>
        </div>
        <div className="nutrition-overall">
          <div className="nutrition-overall-row">
            <span>
              {number(values.calories)} / {number(targets.calories)} kcal
            </span>
            <strong>{percent}%</strong>
          </div>
          <div className="nutrition-track">
            <div className="nutrition-fill" style={{ width: `${Math.min(Math.max(percent, 0), 100)}%` }} />
          </div>
        </div>
      </div>
      <NutrientCards values={values} targets={targets} />
    </section>
  );
}
