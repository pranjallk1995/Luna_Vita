import { Droplet, Plus, Target, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";

import { useAct, useWater, vita, type Settings, type WaterEntry } from "../api";
import { combine, currentClock, today } from "../clock";
import { GOAL_LIMITS_ML, MAX_DRINK_ML, QUICK_ADD_ML, drinkAmount, drinkTime, formatMl, goalAmount, progressOf } from "../water";
import { Dialog } from "./Dialog";
import { useToast } from "./Toasts";

function GoalDialog({ goal, onClose }: { goal: number; onClose: () => void }) {
  const act = useAct();
  const toast = useToast();
  const [error, setError] = useState("");

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const goalMl = goalAmount(String(new FormData(event.currentTarget).get("goal") ?? ""));
    if (typeof goalMl === "string") return setError(goalMl);
    if (await act(() => vita.setWaterGoal(goalMl), "The goal could not be saved.")) {
      toast(`Daily water goal set to ${formatMl(goalMl, true)}`);
      onClose();
    }
  };

  return (
    <Dialog title="Daily water goal" onClose={onClose}>
      <form className="lv-form" onSubmit={submit}>
        <label className="lv-field">
          Goal (ml)
          <input className="lv-input" name="goal" type="number" min={GOAL_LIMITS_ML[0]} max={GOAL_LIMITS_ML[1]} step="50" defaultValue={goal} autoFocus />
        </label>
        {error && <p className="lv-alert lv-alert-error">{error}</p>}
        <button className="lv-button lv-button-primary" type="submit">
          <Target size={17} />
          Save goal
        </button>
      </form>
    </Dialog>
  );
}

export function Water({ day, settings }: { day: string; settings: Settings }) {
  const { data } = useWater(day);
  const act = useAct();
  const toast = useToast();
  const [custom, setCustom] = useState("");
  const [error, setError] = useState("");
  const [editingGoal, setEditingGoal] = useState(false);
  const goal = data?.goal_ml ?? 0;
  const total = data?.total_ml ?? 0;
  const { width, reached } = progressOf(total, goal);

  /** Today's drinks are timed now; a past day's are kept on that day without a time. */
  const add = async (amount_ml: number) => {
    const drank_at = day === today(settings) ? combine(day, currentClock(settings), settings) : null;
    if (await act(() => vita.addWater({ amount_ml, drank_on: day, drank_at }), "The water could not be saved.")) {
      toast(`${formatMl(amount_ml)} of water added`);
      return true;
    }
    return false;
  };

  const addCustom = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const amount = drinkAmount(custom);
    if (typeof amount === "string") return setError(amount);
    setError("");
    if (await add(amount)) setCustom("");
  };

  const remove = async (entry: WaterEntry) => {
    const removed = await act(() => vita.deleteWater(entry.id), "That drink could not be deleted.");
    const restore = { amount_ml: entry.amount_ml, drank_on: entry.drank_on, drank_at: entry.drank_at, notes: entry.notes };
    if (removed) toast(`${formatMl(entry.amount_ml)} deleted`, { label: "Undo", run: () => act(() => vita.addWater(restore), "That drink could not be restored.") });
  };

  return (
    <section className="vt-card" aria-labelledby="water-title">
      <h3 id="water-title">
        <Droplet size={16} />
        Water
      </h3>
      <div className="vt-water-head">
        <strong>
          {formatMl(total, true)} <small>of {formatMl(goal, true)}</small>
        </strong>
        <button className="vt-link-button" type="button" aria-label="Change the daily water goal" onClick={() => setEditingGoal(true)}>
          {reached ? "Goal reached" : `${formatMl(Math.max(goal - total, 0), true)} left`}
        </button>
      </div>
      <div
        className={reached ? "vt-water-bar vt-water-reached" : "vt-water-bar"}
        role="progressbar"
        aria-label="Water against the daily goal"
        aria-valuemin={0}
        aria-valuemax={goal}
        aria-valuenow={total}
      >
        <i style={{ width: `${width}%` }} />
      </div>
      <div className="vt-pills" role="group" aria-label="Add water">
        {QUICK_ADD_ML.map((ml) => (
          <button className="vt-pill" type="button" key={ml} onClick={() => add(ml)}>
            +{ml} ml
          </button>
        ))}
      </div>
      <form className="vt-water-custom" onSubmit={addCustom}>
        <input
          className="lv-input"
          type="number"
          inputMode="numeric"
          min="1"
          max={MAX_DRINK_ML}
          step="1"
          placeholder="Other amount (ml)"
          aria-label="Other amount in ml"
          value={custom}
          onChange={(event) => setCustom(event.target.value)}
        />
        <button className="lv-button" type="submit" aria-label="Add this amount of water" title="Add">
          <Plus size={16} />
        </button>
      </form>
      {error && <p className="lv-alert lv-alert-error">{error}</p>}
      {data && data.entries.length > 0 && (
        <ul className="vt-exercises vt-water-drinks" aria-label="Drinks">
          {data.entries.map((entry) => (
            <li key={entry.id}>
              <div>
                <strong>{formatMl(entry.amount_ml)}</strong>
                {(drinkTime(entry.drank_at, settings) || entry.notes) && (
                  <span>{[drinkTime(entry.drank_at, settings), entry.notes].filter(Boolean).join(" · ")}</span>
                )}
              </div>
              <button className="lv-icon-button" type="button" aria-label={`Delete ${formatMl(entry.amount_ml)}`} title="Delete" onClick={() => remove(entry)}>
                <Trash2 size={15} />
              </button>
            </li>
          ))}
        </ul>
      )}
      {editingGoal && <GoalDialog goal={goal} onClose={() => setEditingGoal(false)} />}
    </section>
  );
}
