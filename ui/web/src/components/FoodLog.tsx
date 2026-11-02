import { Download, Save } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";

import { fittedPhoto, useAct, useFood, vita, type FoodEntry, type Settings } from "../api";
import { currentClock, combine } from "../clock";
import { NOT_RECORDED, byTime, draftOf, foodErrors, payloadOf, type FoodDraft } from "../food";
import { messageOf } from "../lib";
import { MACROS, macroPercentages, number } from "../nutrition";
import { Dialog } from "./Dialog";
import { FoodPhoto } from "./FoodPhoto";
import { SectionHeading, SectionWithAdd } from "./shared";
import { useToast } from "./Toasts";

function MacroChart({ rows }: { rows: FoodEntry[] }) {
  const calories = rows.reduce((sum, row) => sum + Number(row.calories), 0);
  const grams = MACROS.map(({ field }) => rows.reduce((sum, row) => sum + Number(row[field as keyof FoodEntry] ?? 0), 0));
  const shares = macroPercentages(grams);
  let offset = 0;
  return (
    <>
      <SectionHeading title="Macro distribution" />
      <section className="macro-content">
        <div className="macro-legend">
          {MACROS.map(({ label, color }, index) => (
            <div className="macro-row" key={label}>
              <span className="macro-dot" style={{ "--dot": color } as React.CSSProperties} />
              <span>{label}</span>
              <strong>{shares[index]}%</strong>
            </div>
          ))}
        </div>
        <div className="macro-donut">
          <svg viewBox="0 0 120 120" role="img" aria-label="Macro distribution">
            <circle className="macro-track" cx="60" cy="60" r="48" />
            {MACROS.map(({ label, color }, index) => {
              const segment = (
                <g className="macro-slice" key={label}>
                  <circle
                    className="macro-segment"
                    cx="60"
                    cy="60"
                    r="48"
                    pathLength={100}
                    stroke={color}
                    color={color}
                    strokeDasharray={`${shares[index]} ${100 - shares[index]}`}
                    strokeDashoffset={-offset}
                    transform="rotate(-90 60 60)"
                  />
                  <text className="macro-tooltip" x="60" y="56" textAnchor="middle">
                    <tspan x="60">
                      {label} {shares[index]}%
                    </tspan>
                    <tspan className="macro-tooltip-value" x="60" dy="10">
                      {number(grams[index], 1)} g
                    </tspan>
                  </text>
                </g>
              );
              offset += shares[index];
              return segment;
            })}
          </svg>
          <div className="macro-center">
            {number(calories)}
            <small>kcal</small>
          </div>
        </div>
      </section>
    </>
  );
}

const NUTRITION_INPUTS = [
  ["calories", "Calories kcal", "1"],
  ["protein_g", "Protein g", "0.5"],
  ["carbs_g", "Carbs g", "0.5"],
  ["fat_g", "Fat g", "0.5"],
  ["natural_sugar_g", "Natural sugar", "0.5"],
  ["added_sugar_g", "Added sugar", "0.5"],
] as const;

function FoodDialog({ day, settings, onClose }: { day: string; settings: Settings; onClose: () => void }) {
  const act = useAct();
  const toast = useToast();
  const [includeTime, setIncludeTime] = useState(true);
  const [error, setError] = useState("");

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    const text = (name: string) => String(fields.get(name) ?? "").trim();
    if (!text("name") || !text("quantity")) return setError("Food name and quantity are required.");
    setError("");
    const photo = fields.get("photo");
    let imageUrl: string | null = null;
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
        toast("Food saved to database");
        onClose();
      } catch (failure) {
        setError(messageOf(failure, "The food could not be saved."));
      }
    });
  };

  return (
    <Dialog title="Add food or supplement" size="large" onClose={onClose}>
      <form className="lv-form" onSubmit={submit}>
        <div className="vt-form-2-1">
          <label className="lv-field">
            Food / supplement
            <input className="lv-input" name="name" maxLength={200} autoFocus />
          </label>
          <label className="lv-field">
            Quantity
            <input className="lv-input" name="quantity" maxLength={300} placeholder="30 g, 1 serving..." />
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
          Food photo (optional)
          <input className="lv-input" name="photo" type="file" accept={settings.photo_upload_types.map((type) => `.${type}`).join(",")} />
        </label>
        <div className="vt-form-grid-6">
          {NUTRITION_INPUTS.map(([name, label, step]) => (
            <label className="lv-field" key={name}>
              {label}
              <input className="lv-input" name={name} type="number" min="0" step={step} defaultValue="0" />
            </label>
          ))}
        </div>
        <label className="lv-field">
          Notes
          <input className="lv-input" name="notes" maxLength={2000} />
        </label>
        {error && <p className="lv-alert lv-alert-error">{error}</p>}
        <button className="lv-button lv-button-primary" type="submit">
          Record food
        </button>
      </form>
    </Dialog>
  );
}

const NUMBER_COLUMNS = [
  ["calories", "♨ Calories", "1"],
  ["protein_g", "≋ Protein", "any"],
  ["carbs_g", "≋ Carbs", "any"],
  ["fat_g", "◉ Fat", "any"],
  ["natural_sugar_g", "◇ Natural sugar", "any"],
  ["added_sugar_g", "◇ Added sugar", "any"],
] as const;

function FoodTable({ rows, drafts, setDrafts }: { rows: FoodEntry[]; drafts: FoodDraft[]; setDrafts: (next: FoodDraft[]) => void }) {
  const change = (id: number, field: keyof FoodDraft, value: string | boolean) =>
    setDrafts(drafts.map((draft) => (draft.id === id ? { ...draft, [field]: value } : draft)));
  const byId = new Map(rows.map((row) => [row.id, row]));
  return (
    <div className="lv-panel lv-table-scroll">
      <table className="lv-table">
        <thead>
          <tr>
            <th>Time</th>
            <th>Image</th>
            <th>Food / supplement</th>
            <th>↪ Quantity</th>
            {NUMBER_COLUMNS.map(([, label]) => (
              <th key={label}>{label}</th>
            ))}
            <th>Notes</th>
            <th>Delete</th>
          </tr>
        </thead>
        <tbody>
          {drafts.map((draft, index) => {
            const row = byId.get(draft.id);
            const at = `Row ${index + 1}`;
            return (
              <tr key={draft.id}>
                <td>
                  <input aria-label={`${at} time`} value={draft.time} onChange={(event) => change(draft.id, "time", event.target.value)} />
                </td>
                <td>
                  <FoodPhoto source={row?.image_url} alt="" className="vt-photo" emptyClass="vt-photo-empty" />
                </td>
                <td>
                  <input className="vt-wide" aria-label={`${at} food`} value={draft.food_name} onChange={(event) => change(draft.id, "food_name", event.target.value)} />
                </td>
                <td>
                  <input aria-label={`${at} quantity`} value={draft.quantity} onChange={(event) => change(draft.id, "quantity", event.target.value)} />
                </td>
                {NUMBER_COLUMNS.map(([field, label, step]) => (
                  <td key={field}>
                    <input type="number" min="0" step={step} aria-label={`${at} ${label}`} value={draft[field]} onChange={(event) => change(draft.id, field, event.target.value)} />
                  </td>
                ))}
                <td>
                  <input className="vt-wide" aria-label={`${at} notes`} value={draft.notes} onChange={(event) => change(draft.id, "notes", event.target.value)} />
                </td>
                <td>
                  <input type="checkbox" aria-label={`${at} delete`} checked={draft.remove} onChange={(event) => change(draft.id, "remove", event.target.checked)} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function FoodLog({ day, settings }: { day: string; settings: Settings }) {
  const { data, error } = useFood(day, settings.max_food_rows);
  const act = useAct();
  const toast = useToast();
  const [adding, setAdding] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const rows = useMemo(() => byTime(data ?? [], settings), [data, settings]);
  const [drafts, setDrafts] = useState<FoodDraft[]>([]);
  const table = useRef<HTMLDivElement>(null);

  // New data replaces the drafts, unless someone is typing in the table.
  useEffect(() => {
    if (!table.current?.contains(window.document.activeElement)) setDrafts(rows.map((row) => draftOf(row, settings)));
  }, [rows, settings]);

  const save = async () => {
    const problems = foodErrors(drafts);
    setErrors(problems);
    if (problems.length) return;
    const originals = new Map(rows.map((row) => [row.id, row]));
    const saved = await act(async () => {
      for (const draft of drafts) {
        const original = originals.get(draft.id);
        if (!original) continue;
        if (draft.remove) await vita.deleteFood(draft.id);
        // A row left as it was is not sent, so a table of many rows saves as fast as one.
        else if (JSON.stringify({ ...draft }) !== JSON.stringify(draftOf(original, settings))) {
          await vita.updateFood(draft.id, payloadOf(draft, original, settings));
        }
      }
    }, "The daily log could not be saved.");
    if (saved) toast("Daily log saved");
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

  return (
    <>
      <SectionWithAdd title="Food and nutrition" description="Log your meals, snacks and supplements for the day." onAdd={() => setAdding(true)} />
      {error && <p className="lv-alert lv-alert-error">{messageOf(error, "The food log is unavailable.")}</p>}
      {data && !rows.length && <p className="lv-alert">No food entries for this day yet.</p>}
      {rows.length > 0 && (
        <div ref={table}>
          <FoodTable rows={rows} drafts={drafts} setDrafts={setDrafts} />
        </div>
      )}
      {errors.length > 0 && (
        <div className="vt-errors" role="alert">
          Please correct the daily log before saving:
          <ul>
            {errors.map((problem) => (
              <li key={problem}>{problem}</li>
            ))}
          </ul>
        </div>
      )}
      <div className="vt-actions">
        <button className="lv-button lv-button-primary" type="button" disabled={!rows.length} onClick={save}>
          <Save size={17} />
          Save daily log
        </button>
        <button className="lv-button" type="button" onClick={downloadReport}>
          <Download size={17} />
          Download daily PDF
        </button>
      </div>
      <MacroChart rows={data ?? []} />
      {adding && <FoodDialog day={day} settings={settings} onClose={() => setAdding(false)} />}
    </>
  );
}
