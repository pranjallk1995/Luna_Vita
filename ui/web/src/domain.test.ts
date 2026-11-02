import { describe, expect, it } from "vitest";

import { average, byDay, fatRange, formatMetric, measurementPayloads, measurementTable, measurementsOn, periodOf, readings, weightRange } from "./body";
import { addDays, combine, daysBetween, dayLabel, moment } from "./clock";
import { byTime, displayTime, foodErrors, numberError, parseClock, payloadOf, resolveTime, textError, type FoodDraft } from "./food";
import { floorStatus, limitStatus, macroPercentages, percentage } from "./nutrition";
import { calendarSpan, exerciseErrors, exercisePayload, monthWeeks, monthsBetween, statusOf } from "./workouts";

const IST = { time_zone: "Asia/Kolkata", utc_offset: "+05:30" };

describe("clock", () => {
  it("reads timestamps in the app's zone, and naive ones as written", () => {
    expect(moment("2026-01-01T20:00:00+00:00", IST)).toEqual({ day: "2026-01-02", hour: 1, minute: 30 });
    expect(moment("2026-01-01T07:05:00", IST)).toEqual({ day: "2026-01-01", hour: 7, minute: 5 });
    expect(moment("nonsense", IST)).toBeNull();
    expect(moment(null, IST)).toBeNull();
  });

  it("builds and walks days", () => {
    expect(combine("2026-01-01", "07:30", IST)).toBe("2026-01-01T07:30:00+05:30");
    expect(addDays("2026-12-31", 1)).toBe("2027-01-01");
    expect(daysBetween("2026-02-27", "2026-03-01")).toHaveLength(3);
    expect(dayLabel("2026-10-01")).toBe("1 Oct");
  });
});

describe("nutrition", () => {
  it("warns near a ceiling and flags going over", () => {
    expect(limitStatus(80, 100)).toBe("");
    expect(limitStatus(85, 100)).toBe("warning");
    expect(limitStatus(101, 100)).toBe("danger");
    expect(limitStatus(5, 0)).toBe("");
  });

  it("treats protein as a floor", () => {
    expect(floorStatus(100, 100)).toBe("success");
    expect(floorStatus(99, 100)).toBe("");
    expect(percentage(50, 200)).toBe(25);
    expect(percentage(50, 0)).toBe(0);
  });

  it("rounds macro shares to exactly 100", () => {
    expect(macroPercentages([1, 1, 1])).toEqual([34, 33, 33]);
    expect(macroPercentages([0, 0])).toEqual([0, 0]);
    expect(macroPercentages([3, 1]).reduce((sum, share) => sum + share)).toBe(100);
  });
});

describe("food time", () => {
  const timed = { consumed_at: "2026-01-01T14:05:00+05:30", time_label: null };
  const labelled = { consumed_at: "2026-01-01T00:00:00+05:30", time_label: "Morning" };

  it("prefers a recorded time and falls back to a label", () => {
    expect(displayTime(timed, IST)).toBe("2:05 PM");
    expect(displayTime(labelled, IST)).toBe("Morning");
    expect(displayTime({ consumed_at: "2026-01-01T00:00:00+05:30", time_label: "" }, IST)).toBe("12:00 AM");
  });

  it("orders timed rows and keeps label-only rows last", () => {
    const rows = [
      { id: 1, ...labelled },
      { id: 2, ...timed },
      { id: 3, consumed_at: "2026-01-01T08:00:00+05:30", time_label: null },
    ];
    expect(byTime(rows, IST).map(({ id }) => id)).toEqual([3, 2, 1]);
  });

  it("parses clocks", () => {
    expect(parseClock("7:30 PM")).toBe("19:30");
    expect(parseClock("12:15 am")).toBe("00:15");
    expect(parseClock("19:30")).toBe("19:30");
    expect(parseClock("7 pm")).toBe("19:00");
    expect(parseClock("Morning")).toBeNull();
    expect(parseClock("25:00")).toBeNull();
    expect(parseClock("7")).toBeNull();
  });

  it("resolves an edited cell onto the entry's own day", () => {
    expect(resolveTime("7:30 PM", timed.consumed_at, IST)).toEqual({ consumed_at: "2026-01-01T19:30:00+05:30", time_label: null });
    expect(resolveTime("After gym", timed.consumed_at, IST)).toEqual({ consumed_at: "2026-01-01T00:00:00+05:30", time_label: "After gym" });
    expect(resolveTime("", timed.consumed_at, IST).time_label).toBe("Not recorded");
    expect(resolveTime("not recorded", timed.consumed_at, IST).time_label).toBe("Not recorded");
  });
});

describe("food rules", () => {
  const draft: FoodDraft = { id: 1, remove: false, time: "9:00 AM", food_name: "Oats", quantity: "30 g", calories: "120", protein_g: "4", carbs_g: "20", fat_g: "2", natural_sugar_g: "1", added_sugar_g: "0", notes: "" };

  it("mirrors the backend's text and number rules", () => {
    expect(textError(" ", "Name", true, 10)).toBe("Name cannot be blank.");
    expect(textError("x".repeat(11), "Name", false, 10)).toMatch(/10 characters/);
    expect(textError("Oats 😀", "Name", false, 10)).toMatch(/emojis/);
    expect(textError("a\u0007b", "Name", false, 10)).toMatch(/control/);
    expect(numberError("", "Fat", 10, false)).toMatch(/valid number/);
    expect(numberError("-1", "Fat", 10, false)).toMatch(/negative/);
    expect(numberError("11", "Fat", 10, false)).toMatch(/exceed 10/);
    expect(numberError("1.5", "Calories", 10, true)).toMatch(/whole/);
  });

  it("checks only rows that stay, numbering them by position", () => {
    expect(foodErrors([draft])).toEqual([]);
    expect(foodErrors([{ ...draft, food_name: "" }, { ...draft, quantity: "" }])).toEqual([
      "Row 1 Food / supplement cannot be blank.",
      "Row 2 Quantity cannot be blank.",
    ]);
    expect(foodErrors([{ ...draft, food_name: "", remove: true }])).toEqual([]);
  });

  it("merges an edited row onto the stored entry", () => {
    const original = { id: 1, meal_type: "other", image_url: "x", consumed_date: "2026-01-01", consumed_at: "2026-01-01T09:00:00+05:30" } as never;
    const payload = payloadOf({ ...draft, notes: " " }, original, IST);
    expect(payload).toMatchObject({ meal_type: "other", image_url: "x", calories: 120, notes: null, consumed_date: "2026-01-01", time_label: null });
  });
});

describe("body", () => {
  it("names the period from the label, or else the hour", () => {
    expect(periodOf("Morning", 20)).toBe("Morning");
    expect(periodOf("evening", 7)).toBe("Night");
    expect(periodOf(null, 7)).toBe("Morning");
    expect(periodOf("", 13)).toBe("Night");
  });

  it("formats values without trailing zeros", () => {
    expect(formatMetric("weight", 72.5, "kg")).toBe("72.5 kg");
    expect(formatMetric("health_score", 80, "/100")).toBe("80/100");
    expect(formatMetric("bmi", 24.10, "index")).toBe("24.1");
  });

  it("keeps the selected day and the latest of each period", () => {
    const rows = [
      { id: 1, metric: "weight", value: 70, unit: "kg", measured_at: "2026-01-01T07:00:00+05:30", time_label: "Morning" },
      { id: 2, metric: "weight", value: 71, unit: "kg", measured_at: "2026-01-01T08:00:00+05:30", time_label: "Morning" },
      { id: 3, metric: "weight", value: 72, unit: "kg", measured_at: "2026-01-02T07:00:00+05:30", time_label: "Morning" },
      { id: 4, metric: "mystery", value: 1, unit: "x", measured_at: "2026-01-01T07:00:00+05:30", time_label: null },
    ];
    const day = measurementsOn(rows, "2026-01-01", IST);
    expect(day.map(({ id }) => id)).toEqual([1, 2]);
    expect(measurementTable(day)[0]).toEqual({ label: "Weight", Morning: "71 kg", Night: "Not recorded" });
  });

  it("builds one payload per entered metric", () => {
    const payloads = measurementPayloads({ weight: "70.5", bmi: "", bmr: "1600" }, "2026-01-01T07:00:00+05:30", "Morning", " ");
    expect(payloads.map(({ metric }) => metric)).toEqual(["weight", "bmr"]);
    expect(payloads[0]).toMatchObject({ value: 70.5, unit: "kg", time_label: "Morning", notes: null });
  });

  it("draws bars from sensible floors", () => {
    const series = readings(
      [
        { measured_at: "2026-01-01T07:00:00+05:30", value: 72.4, time_label: "Morning" },
        { measured_at: "2026-01-01T21:00:00+05:30", value: 73.1, time_label: "Night", estimated: true },
      ],
      IST,
    );
    expect(weightRange(series)).toEqual([71, 74]);
    expect(average(series)).toBeCloseTo(72.75);
    expect(average([])).toBeNull();
    expect(byDay(series).get("2026-01-01")?.Night?.estimated).toBe(true);
    const fat = series.map((reading) => ({ ...reading, value: 20 }));
    expect(fatRange(fat, 12)[0]).toBe(9);
    expect(fatRange(fat, 18)[0]).toBe(15);
  });
});

describe("workouts", () => {
  it("reads status", () => {
    expect(statusOf()).toBe("none");
    expect(statusOf({ done: true } as never)).toBe("done");
    expect(statusOf({ done: false } as never)).toBe("skipped");
  });

  it("covers whole months including the selected day", () => {
    expect(calendarSpan("2026-02-10", "2026-02-20", "2026-03-05")).toEqual(["2026-02-01", "2026-03-31"]);
    expect(calendarSpan("2026-02-10", "2026-02-20", "2026-01-05")).toEqual(["2026-01-01", "2026-02-28"]);
    expect(monthsBetween("2026-11-15", "2027-01-02")).toEqual(["2026-11-01", "2026-12-01", "2027-01-01"]);
  });

  it("lays a month out Monday first", () => {
    const weeks = monthWeeks("2026-02-01");
    expect(weeks[0].slice(0, 6)).toEqual([null, null, null, null, null, null]);
    expect(weeks[0][6]).toBe("2026-02-01");
    expect(weeks.flat().filter(Boolean)).toHaveLength(28);
    expect(weeks.every((week) => week.length === 7)).toBe(true);
  });

  it("turns blanks into nulls and requires a name", () => {
    expect(exercisePayload({ exercise: " Squat ", type: "", sets: "3", reps: "", weight_kg: "62.5", duration_min: "", notes: " " }, "2026-01-01")).toEqual({
      day: "2026-01-01", exercise: "Squat", type: null, notes: null, sets: 3, reps: null, weight_kg: 62.5, duration_min: null,
    });
    expect(exerciseErrors([{ id: 1, remove: false, exercise: " ", type: "", sets: "", reps: "", weight_kg: "", duration_min: "", notes: "" }])).toEqual(["Row 1: exercise name is required."]);
  });
});
