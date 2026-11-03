import { CopyPlus, Download, Ellipsis, Pencil, Plus, Trash2, Utensils } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";

import { fittedPhoto, useAct, useFood, useFoodBetween, useSummary, vita, type FoodEntry, type Settings } from "../api";
import { addDays, combine, currentClock, today } from "../clock";
import { NOT_RECORDED, byTime, copyOf, displayTime, draftOf, entryErrors, payloadOf, recentFoods, type FoodDraft } from "../food";
import { messageOf } from "../lib";
import { energySplit, number } from "../nutrition";
import { Dialog } from "./Dialog";
import { FoodPhoto } from "./FoodPhoto";
import { SectionHead } from "./shared";
import { useToast } from "./Toasts";

const NUTRITION_INPUTS = [
  ["calories", "Calories kcal", "1"],
  ["protein_g", "Protein g", "0.5"],
  ["carbs_g", "Carbs g", "0.5"],
  ["fat_g", "Fat g", "0.5"],
  ["natural_sugar_g", "Natural sugar g", "0.5"],
  ["added_sugar_g", "Added sugar g", "0.5"],
] as const;

/** How far back the Add dialog looks for foods to offer again. */
const RECENT_DAYS = 28;
const RECENT_LIMIT = 8;

function FoodDialog({ day, settings, onClose }: { day: string; settings: Settings; onClose: () => void }) {
  const act = useAct();
  const toast = useToast();
  const [includeTime, setIncludeTime] = useState(true);
  const [error, setError] = useState("");
  const [preset, setPreset] = useState<FoodEntry | null>(null);
  const history = useFoodBetween(addDays(day, -RECENT_DAYS), day, settings.max_food_rows);
  const recents = useMemo(() => recentFoods(history.data ?? [], RECENT_LIMIT), [history.data]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    const text = (name: string) => String(fields.get(name) ?? "").trim();
    if (!text("name") || !text("quantity")) return setError("Food name and quantity are required.");
    setError("");
    const photo = fields.get("photo");
    // A recent food brings its photo along unless a new one is chosen.
    let imageUrl: string | null = preset?.image_url ?? null;
    if (photo instanceof File && photo.size) {
      try {
        imageUrl = await fittedPhoto(photo, settings.food_photo_size, settings.food_photo_quality);
      } catch (failure) {
        return setError(messageOf(failure, "Choose a valid food photo."));
      }
    }
    const consumedDate = text("date");
    const clock = includeTime ? text("time") : "";
    const payload = {
      food_name: text("name"),
      quantity: text("quantity"),
      meal_type: "other",
      calories: Math.trunc(Number(fields.get("calories") || 0)),
      protein_g: Number(fields.get("protein_g") || 0),
      carbs_g: Number(fields.get("carbs_g") || 0),
      fat_g: Number(fields.get("fat_g") || 0),
      natural_sugar_g: Number(fields.get("natural_sugar_g") || 0),
      added_sugar_g: Number(fields.get("added_sugar_g") || 0),
      image_url: imageUrl,
      consumed_at: combine(consumedDate, clock || "00:00", settings),
      consumed_date: consumedDate,
      // An omitted time is stored as midnight plus a label.
      time_label: text("label") || (clock ? null : NOT_RECORDED),
      notes: text("notes") || null,
    };
    await act(async () => {
      try {
        await vita.createFood(payload);
        toast(`${payload.food_name} added`);
        onClose();
      } catch (failure) {
        setError(messageOf(failure, "The food could not be saved."));
      }
    });
  };

  return (
    <Dialog title="Add food or supplement" size="large" onClose={onClose}>
      {/* Choosing a recent food refills the form, so it remounts with that food's values. */}
      <form className="lv-form" onSubmit={submit} key={preset?.id ?? "blank"}>
        {recents.length > 0 && (
          <div className="vt-recents">
            <span className="vt-recents-label">Recent foods</span>
            <div className="vt-pills" role="group" aria-label="Recent foods">
              {recents.map((food) => (
                <button className={preset?.id === food.id ? "vt-pill vt-pill-active" : "vt-pill"} type="button" key={food.id} aria-pressed={preset?.id === food.id} onClick={() => setPreset(food)}>
                  {food.food_name}
                </button>
              ))}
            </div>
          </div>
        )}
        <div className="vt-form-2-1">
          <label className="lv-field">
            Food / supplement
            <input className="lv-input" name="name" maxLength={200} defaultValue={preset?.food_name} autoFocus />
          </label>
          <label className="lv-field">
            Quantity
            <input className="lv-input" name="quantity" maxLength={300} placeholder="30 g, 1 serving..." defaultValue={preset?.quantity} />
          </label>
        </div>
        <div className="vt-form-when">
          <label className="lv-field">
            Consumed date
            <input className="lv-input" name="date" type="date" defaultValue={day} required />
          </label>
          <label className="vt-toggle">
            <input type="checkbox" checked={includeTime} onChange={(event) => setIncludeTime(event.target.checked)} />
            Include consumed time
          </label>
          <label className="lv-field">
            Consumed time
            {includeTime ? (
              <input className="lv-input" name="time" type="time" defaultValue={currentClock(settings)} required />
            ) : (
              <input className="lv-input" value={NOT_RECORDED} disabled readOnly />
            )}
          </label>
        </div>
        <label className="lv-field">
          Time label
          <input className="lv-input" name="label" maxLength={100} placeholder="Morning, ~4:30 PM..." />
        </label>
        <label className="lv-field">
          {preset?.image_url ? `Food photo (optional; keeps ${preset.food_name}'s photo if left empty)` : "Food photo (optional)"}
          <input className="lv-input" name="photo" type="file" accept={settings.photo_upload_types.map((type) => `.${type}`).join(",")} />
        </label>
        <div className="vt-form-grid-6">
          {NUTRITION_INPUTS.map(([name, label, step]) => (
            <label className="lv-field" key={name}>
              {label}
              <input className="lv-input" name={name} type="number" min="0" step={step} defaultValue={preset ? String(preset[name]) : "0"} />
            </label>
          ))}
        </div>
        <label className="lv-field">
          Notes
          <input className="lv-input" name="notes" maxLength={2000} />
        </label>
        {error && <p className="lv-alert lv-alert-error">{error}</p>}
        <button className="lv-button lv-button-primary" type="submit">
          Add food
        </button>
      </form>
    </Dialog>
  );
}

/** One food's editor. It keeps its own draft, so fresh server data never overwrites typing. */
function FoodEditor({ entry, settings, onDone, onDirty }: { entry: FoodEntry; settings: Settings; onDone: () => void; onDirty: (dirty: boolean) => void }) {
  const act = useAct();
  const toast = useToast();
  const original = useMemo(() => draftOf(entry, settings), [entry, settings]);
  const [draft, setDraft] = useState<FoodDraft>(original);
  const [errors, setErrors] = useState<string[]>([]);
  const dirty = JSON.stringify(draft) !== JSON.stringify(original);

  useEffect(() => {
    onDirty(dirty);
  }, [dirty, onDirty]);
  useEffect(() => () => onDirty(false), [onDirty]);

  const change = (field: keyof FoodDraft) => (event: React.ChangeEvent<HTMLInputElement>) => setDraft({ ...draft, [field]: event.target.value });

  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const problems = entryErrors(draft);
    setErrors(problems);
    if (problems.length) return;
    if (!dirty) return onDone();
    const saved = await act(() => vita.updateFood(entry.id, payloadOf(draft, entry, settings)), `${entry.food_name} could not be saved.`);
    if (saved) {
      toast(`${draft.food_name.trim()} saved`);
      onDone();
    }
  };

  return (
    <form className="vt-food-edit" onSubmit={save} aria-label={`Edit ${entry.food_name}`}>
      <div className="vt-edit-top">
        <label className="lv-field">
          Food / supplement
          <input className="lv-input" value={draft.food_name} onChange={change("food_name")} autoFocus />
        </label>
        <label className="lv-field">
          Quantity
          <input className="lv-input" value={draft.quantity} onChange={change("quantity")} />
        </label>
        <label className="lv-field">
          Time
          <input className="lv-input" value={draft.time} onChange={change("time")} placeholder="7:30 PM, Morning..." />
        </label>
      </div>
      <div className="vt-form-grid-6">
        {NUTRITION_INPUTS.map(([field, label, step]) => (
          <label className="lv-field" key={field}>
            {label}
            <input className="lv-input" type="number" min="0" step={step} value={draft[field]} onChange={change(field)} />
          </label>
        ))}
      </div>
      <label className="lv-field">
        Notes
        <input className="lv-input" value={draft.notes} onChange={change("notes")} maxLength={2000} />
      </label>
      {errors.length > 0 && (
        <div className="vt-errors" role="alert">
          <ul>
            {errors.map((problem) => (
              <li key={problem}>{problem}</li>
            ))}
          </ul>
        </div>
      )}
      <div className="vt-form-actions">
        <button className="lv-button" type="button" onClick={onDone}>
          Cancel
        </button>
        <button className="lv-button lv-button-primary" type="submit">
          Save
        </button>
      </div>
    </form>
  );
}

function Numbers({ calories, protein, carbs, fat }: { calories: number; protein: number; carbs: number; fat: number }) {
  return (
    <div className="vt-food-nums">
      {(
        [
          ["kcal", number(calories)],
          ["P", number(protein, 1)],
          ["C", number(carbs, 1)],
          ["F", number(fat, 1)],
        ] as const
      ).map(([label, value]) => (
        <div className="vt-num" key={label}>
          <span className="vt-num-label">{label}</span>
          {value}
        </div>
      ))}
    </div>
  );
}

export function FoodLog({ day, settings, onDirtyChange }: { day: string; settings: Settings; onDirtyChange: (dirty: boolean) => void }) {
  const { data, error } = useFood(day, settings.max_food_rows);
  const act = useAct();
  const toast = useToast();
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<number | null>(null);
  // Phones keep a food's actions behind its ⋯ button; wider screens always show them.
  const [menu, setMenu] = useState<number | null>(null);
  const rows = useMemo(() => byTime(data ?? [], settings), [data, settings]);

  // A different day closes the editor; App has already asked before discarding changes.
  useEffect(() => {
    setEditing(null);
    setMenu(null);
  }, [day]);

  const total = rows.reduce(
    (sum, row) => ({
      calories: sum.calories + Number(row.calories),
      protein: sum.protein + Number(row.protein_g),
      carbs: sum.carbs + Number(row.carbs_g),
      fat: sum.fat + Number(row.fat_g),
    }),
    { calories: 0, protein: 0, carbs: 0, fat: 0 },
  );

  const remove = async (entry: FoodEntry) => {
    if (editing === entry.id) setEditing(null);
    const removed = await act(() => vita.deleteFood(entry.id), `${entry.food_name} could not be deleted.`);
    // Undo logs it again; the backend gives the restored entry a new id.
    if (removed) toast(`${entry.food_name} deleted`, { label: "Undo", run: () => act(() => vita.createFood(copyOf(entry)), `${entry.food_name} could not be restored.`) });
  };

  const logAgain = async (entry: FoodEntry) => {
    // Today's repeat is logged now; a repeat on a past day keeps the original's time.
    const now = day === today(settings) ? { consumed_at: combine(day, currentClock(settings), settings), consumed_date: day, time_label: null } : undefined;
    const result: { created?: FoodEntry } = {};
    const logged = await act(async () => {
      result.created = await vita.createFood(copyOf(entry, now));
    }, `${entry.food_name} could not be logged again.`);
    if (logged && result.created) {
      const { id } = result.created;
      toast(`${entry.food_name} logged again`, { label: "Undo", run: () => act(() => vita.deleteFood(id), "The repeat could not be removed.") });
    }
  };

  const downloadReport = async () => {
    try {
      const response = await fetch(`/api/reports/daily/${day}`);
      if (!response.ok) throw new Error();
      const link = window.document.createElement("a");
      link.href = URL.createObjectURL(await response.blob());
      link.download = `lunavita-${day}.pdf`;
      link.click();
      URL.revokeObjectURL(link.href);
    } catch {
      toast("Daily PDF is temporarily unavailable.");
    }
  };

  const isToday = day === today(settings);

  return (
    <section aria-labelledby="food-log-title">
      <SectionHead title="Food log" id="food-log-title">
        <div className="vt-section-actions">
          <button className="lv-icon-button" type="button" aria-label="Download daily PDF" title="Download daily PDF" onClick={downloadReport}>
            <Download size={17} />
          </button>
          <button className="lv-button lv-button-primary" type="button" onClick={() => setAdding(true)}>
            <Plus size={17} />
            Add food
          </button>
        </div>
      </SectionHead>
      {error && <p className="lv-alert lv-alert-error">{messageOf(error, "The food log is unavailable.")}</p>}
      <div className="vt-food vt-food-log">
        {data && !rows.length && (
          <div className="vt-empty">
            <Utensils size={22} />
            <strong>Nothing logged for {isToday ? "today" : new Date(`${day}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "long", timeZone: "UTC" })}</strong>
            <p>Add food here, or ask Claude to log it for you.</p>
            <button className="lv-button lv-button-primary" type="button" onClick={() => setAdding(true)}>
              <Plus size={17} />
              Add food
            </button>
          </div>
        )}
        {rows.length > 0 && (
          <>
            <div className="vt-food-row vt-food-labels" aria-hidden="true">
              <span>Time</span>
              <span />
              <span>Food</span>
              <span className="vt-num">kcal</span>
              <span className="vt-num">Protein</span>
              <span className="vt-num">Carbs</span>
              <span className="vt-num">Fat</span>
              <span />
            </div>
            {rows.map((row) => {
              const time = displayTime(row, settings);
              return (
                <div key={row.id}>
                  <div className="vt-food-row">
                    <span className="vt-food-time">{time}</span>
                    <FoodPhoto source={row.image_url} name={row.food_name} className="vt-food-photo" emptyClass="vt-food-photo vt-food-photo-empty" />
                    <div className="vt-food-name">
                      <strong title={row.food_name}>{row.food_name}</strong>
                      <span title={row.quantity}>
                        <span className="vt-mobile-only">{time} · </span>
                        {row.quantity}
                        {row.notes && <span className="vt-food-notes"> · {row.notes}</span>}
                      </span>
                    </div>
                    <Numbers calories={row.calories} protein={row.protein_g} carbs={row.carbs_g} fat={row.fat_g} />
                    <button
                      className="lv-icon-button vt-food-more"
                      type="button"
                      aria-label={`Actions for ${row.food_name}`}
                      aria-expanded={menu === row.id}
                      onClick={() => setMenu(menu === row.id ? null : row.id)}
                    >
                      <Ellipsis size={18} />
                    </button>
                    <div className={menu === row.id ? "vt-food-actions vt-food-actions-open" : "vt-food-actions"}>
                      <button className="lv-icon-button" type="button" aria-label={`Log ${row.food_name} again`} title="Log again" onClick={() => logAgain(row)}>
                        <CopyPlus size={16} />
                        <span className="vt-mobile-only">Log again</span>
                      </button>
                      <button
                        className="lv-icon-button"
                        type="button"
                        aria-label={`Edit ${row.food_name}`}
                        aria-expanded={editing === row.id}
                        title="Edit"
                        onClick={() => {
                          setEditing(editing === row.id ? null : row.id);
                          setMenu(null);
                        }}
                      >
                        <Pencil size={16} />
                        <span className="vt-mobile-only">Edit</span>
                      </button>
                      <button className="lv-icon-button" type="button" aria-label={`Delete ${row.food_name}`} title="Delete" onClick={() => remove(row)}>
                        <Trash2 size={16} />
                        <span className="vt-mobile-only">Delete</span>
                      </button>
                    </div>
                  </div>
                  {editing === row.id && <FoodEditor entry={row} settings={settings} onDone={() => setEditing(null)} onDirty={onDirtyChange} />}
                </div>
              );
            })}
            <div className="vt-food-row vt-food-total">
              <span className="vt-food-time" />
              <span className="vt-food-photo vt-hidden" />
              <div className="vt-food-name">
                <strong>Total</strong>
              </div>
              <Numbers {...total} />
              <span className="vt-food-actions" />
            </div>
          </>
        )}
      </div>
      {adding && <FoodDialog day={day} settings={settings} onClose={() => setAdding(false)} />}
    </section>
  );
}

/** Protein, carbs and fat by energy; the bar sits level with Add food, the legend with the log. */
export function EnergySplit({ day }: { day: string }) {
  const { data } = useSummary(day);
  const parts = energySplit(data ?? {});
  const logged = parts.some((part) => part.grams > 0);
  const label = logged ? `Energy split: ${parts.map((part) => `${part.label} ${part.share}%`).join(", ")}` : "No food logged";
  return (
    <>
      <SectionHead title="Energy split">
        <div className="vt-split" role="img" aria-label={label}>
          {parts.map((part) => (
            <i key={part.label} style={{ width: `${part.share}%`, background: part.color }} />
          ))}
        </div>
      </SectionHead>
      <section className="vt-card" aria-label="Energy split by macro">
        {parts.map((part) => (
          <div className="vt-split-row" key={part.label}>
            <i style={{ background: part.color }} />
            <span>{part.label}</span>
            <strong>{part.share}%</strong>
            <span>{number(part.grams, 1)} g</span>
          </div>
        ))}
        <p className="vt-caption">
          Natural and added sugar are part of carbs.
        </p>
      </section>
    </>
  );
}
