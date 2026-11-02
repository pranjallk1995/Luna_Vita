import { Plus } from "lucide-react";
import type { ReactNode } from "react";

import type { Totals } from "../api";
import { NUTRIENTS, number, nutrientStatus, percentage, type Nutrient } from "../nutrition";

export function SectionHeading({ title, description }: { title: string; description?: string }) {
  return (
    <div className="food-log-heading">
      <h2>{title}</h2>
      {description && <p>{description}</p>}
    </div>
  );
}

export function SectionWithAdd({ title, description, onAdd }: { title: string; description: string; onAdd: () => void }) {
  return (
    <div className="food-log-heading-row">
      <SectionHeading title={title} description={description} />
      <button className="lv-button lv-button-primary" type="button" aria-label={`Add entry to ${title}`} onClick={onAdd}>
        <Plus size={17} />
        Add entry
      </button>
    </div>
  );
}

export const targetsOf = (recommendations: Totals) =>
  Object.fromEntries(NUTRIENTS.map((nutrient) => [nutrient.key, Number(recommendations[nutrient.targetField])]));

/** The nutrient and status classes that set a card's accent color. */
export const cardClasses = (nutrient: Nutrient, value: number, target: number) => `${nutrient.key} ${nutrientStatus(nutrient, value, target)}`;

function NutrientCard({ nutrient, value, target }: { nutrient: Nutrient; value: number; target: number }) {
  const percent = percentage(value, target);
  const Icon = nutrient.icon;
  return (
    <div className={`nutrition-card ${cardClasses(nutrient, value, target)}`}>
      <div>
        <div className="nutrition-card-label">
          <span className="nutrition-card-icon">
            <Icon size={16} />
          </span>
          {nutrient.label}
        </div>
        <div className="nutrition-card-value">
          {number(value, nutrient.decimals)} {nutrient.unit}
        </div>
        <div className="nutrition-card-target">
          Target {number(target)} {nutrient.unit}
          {nutrient.targetSuffix}
        </div>
      </div>
      <div className="nutrition-ring" style={{ "--ring-value": `${Math.min(Math.max(percent, 0), 100) * 3.6}deg` } as React.CSSProperties}>
        <span>{percent}%</span>
      </div>
    </div>
  );
}

/** The card row; each footer sits under its card at the same width. */
export function NutrientCards({ values, targets, footers }: { values: Record<string, number>; targets: Record<string, number>; footers?: Record<string, ReactNode> }) {
  return (
    <div className="nutrition-cards">
      {NUTRIENTS.map((nutrient) => {
        const card = <NutrientCard nutrient={nutrient} value={values[nutrient.key]} target={targets[nutrient.key]} key={nutrient.key} />;
        return footers?.[nutrient.key] ? (
          <div className="nutrient-stack" key={nutrient.key}>
            {card}
            {footers[nutrient.key]}
          </div>
        ) : (
          card
        );
      })}
    </div>
  );
}
