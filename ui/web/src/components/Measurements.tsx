import { Save, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";

import { useAct, useMeasurements, vita, type Settings } from "../api";
import { PERIODS, measurementPayloads, measurementTable, measurementsOn, type Period } from "../body";
import { combine, currentClock } from "../clock";
import { messageOf } from "../lib";
import { Dialog } from "./Dialog";
import { SectionWithAdd } from "./shared";
import { useToast } from "./Toasts";

const METRIC_INPUTS = [
  ["bmr", "BMR (kcal/day)", { min: 0, step: 1 }],
  ["health_score", "Health score (/100)", { min: 0, max: 100, step: 1 }],
  ["body_age", "Body age (years)", { min: 0, step: 1 }],
  ["bmi", "BMI", { min: 0, step: 0.1 }],
  ["water_ratio", "Water ratio (%)", { min: 0, max: 100, step: 0.1 }],
] as const;

function MeasurementDialog({ day, settings, onClose }: { day: string; settings: Settings; onClose: () => void }) {
  const act = useAct();
  const toast = useToast();
  const [includeTime, setIncludeTime] = useState(true);
  const [error, setError] = useState("");

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    const text = (name: string) => String(fields.get(name) ?? "");
    if (!text("weight").trim()) return setError("Weight is required.");
    setError("");
    const values = Object.fromEntries(["weight", ...METRIC_INPUTS.map(([name]) => name)].map((name) => [name, text(name)]));
    const measuredAt = combine(text("date"), includeTime ? text("time") : "00:00", settings);
    await act(async () => {
      try {
        await vita.createMeasurements(measurementPayloads(values, measuredAt, text("period") as Period, text("notes")));
        toast("Body measurements saved to database");
        onClose();
      } catch (failure) {
        setError(messageOf(failure, "The measurements could not be saved."));
      }
    });
  };

  return (
    <Dialog title="Add body measurements" size="large" onClose={onClose}>
      <form className="lv-form" onSubmit={submit}>
        <label className="lv-field">
          Weight (kg)
          <input className="lv-input" name="weight" type="number" min="0" step="0.1" autoFocus />
        </label>
        <div className="lv-form-row">
          <label className="lv-field">
            Measured date
            <input className="lv-input" name="date" type="date" defaultValue={day} required />
          </label>
          <label className="lv-field">
            Morning / night
            <select className="lv-select" name="period" defaultValue="Morning">
              {PERIODS.map((period) => (
                <option key={period}>{period}</option>
              ))}
            </select>
          </label>
          <label className="vt-toggle">
            <input type="checkbox" checked={includeTime} onChange={(event) => setIncludeTime(event.target.checked)} />
            Include measured time
          </label>
          {includeTime && (
            <label className="lv-field">
              Measured time
              <input className="lv-input" name="time" type="time" defaultValue={currentClock(settings)} required />
            </label>
          )}
        </div>
        <div className="lv-form-row">
          {METRIC_INPUTS.map(([name, label, limits]) => (
            <label className="lv-field" key={name}>
              {label}
              <input className="lv-input" name={name} type="number" {...limits} />
            </label>
          ))}
        </div>
        <label className="lv-field">
          Notes
          <input className="lv-input" name="notes" maxLength={2000} />
        </label>
        {error && <p className="lv-alert lv-alert-error">{error}</p>}
        <button className="lv-button lv-button-primary" type="submit">
          <Save size={17} />
          Save body measurements
        </button>
      </form>
    </Dialog>
  );
}

export function Measurements({ day, settings }: { day: string; settings: Settings }) {
  const { data, error } = useMeasurements(settings.max_measurement_rows);
  const act = useAct();
  const toast = useToast();
  const [adding, setAdding] = useState(false);
  const rows = measurementsOn(data ?? [], day, settings);

  const deletePeriod = async (period: Period) => {
    const done = await act(async () => {
      for (const row of rows) if (row.period === period) await vita.deleteMeasurement(row.id);
    }, `The ${period.toLowerCase()} weigh-in could not be deleted.`);
    if (done) toast(`${period} weigh-in deleted`);
  };

  return (
    <>
      <SectionWithAdd
        title="Body measurements"
        description="Track morning and night weight, BMR, health score, body age, BMI, and water ratio."
        onAdd={() => setAdding(true)}
      />
      {error && <p className="lv-alert lv-alert-error">{messageOf(error, "Measurements are unavailable.")}</p>}
      <div className="lv-panel lv-table-scroll">
        <table className="lv-table">
          <thead>
            <tr>
              <th>Measurement</th>
              {PERIODS.map((period) => (
                <th key={period}>{period}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {measurementTable(rows).map((row) => (
              <tr key={row.label}>
                <td>{row.label}</td>
                <td>{row.Morning}</td>
                <td>{row.Night}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="vt-delete-row">
        {PERIODS.map((period) => (
          <button className="lv-button" type="button" key={period} disabled={!rows.some((row) => row.period === period)} onClick={() => deletePeriod(period)}>
            <Trash2 size={16} />
            Delete {period.toLowerCase()} weigh-in
          </button>
        ))}
      </div>
      {adding && <MeasurementDialog day={day} settings={settings} onClose={() => setAdding(false)} />}
    </>
  );
}
