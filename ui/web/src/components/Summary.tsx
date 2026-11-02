import { useRecommendations, useSummary } from "../api";
import { messageOf } from "../lib";
import { NUTRIENTS } from "../nutrition";
import { SummaryTiles, targetsOf } from "./shared";

/** "Today", or the chosen date, with a way back to today. */
export function DayHeading({ day, today, onToday }: { day: string; today: string; onToday: () => void }) {
  const isToday = day === today;
  const long = new Date(`${day}T00:00:00Z`).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" });
  return (
    <div className="vt-day-head">
      <h2>{isToday ? "Today" : long}</h2>
      {isToday ? (
        <p>{long}</p>
      ) : (
        <button className="vt-link-button" type="button" onClick={onToday}>
          Back to today
        </button>
      )}
    </div>
  );
}

export function Summary({ day }: { day: string }) {
  const summary = useSummary(day);
  const recommendations = useRecommendations();

  if (summary.error) return <p className="lv-alert lv-alert-error">{messageOf(summary.error, "The Luna Vita service is unavailable.")}</p>;
  if (recommendations.data === null) return <p className="lv-alert">Daily nutrition recommendations have not been configured.</p>;

  const totals = summary.data;
  const values = totals ? Object.fromEntries(NUTRIENTS.map((nutrient) => [nutrient.key, Number(totals[nutrient.summaryField])])) : null;
  const targets = recommendations.data ? targetsOf(recommendations.data) : null;
  return <SummaryTiles values={values} targets={targets} />;
}
