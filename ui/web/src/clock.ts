/** Dates and times in the app's zone (Asia/Kolkata), as the backend resolves them. */

export type Zone = { time_zone: string; utc_offset: string };

const HAS_OFFSET = /(Z|[+-]\d{2}:?\d{2})$/;

export type Moment = { day: string; hour: number; minute: number };

/** A timestamp's calendar day and clock in ``zone``; null when it cannot be read. */
export function moment(value: unknown, zone: Zone): Moment | null {
  if (typeof value !== "string" || !value) return null;
  if (!HAS_OFFSET.test(value)) {
    const naive = /^(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}):(\d{2}))?/.exec(value);
    return naive && { day: naive[1], hour: Number(naive[2] ?? 0), minute: Number(naive[3] ?? 0) };
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", {
      timeZone: zone.time_zone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    })
      .formatToParts(parsed)
      .map(({ type, value: part }) => [type, part]),
  );
  return { day: `${parts.year}-${parts.month}-${parts.day}`, hour: Number(parts.hour), minute: Number(parts.minute) };
}

export const today = (zone: Zone) => moment(new Date().toISOString(), zone)!.day;

export function currentClock(zone: Zone): string {
  const now = moment(new Date().toISOString(), zone)!;
  return `${String(now.hour).padStart(2, "0")}:${String(now.minute).padStart(2, "0")}`;
}

export const combine = (day: string, clock: string, zone: Zone) => `${day}T${clock}:00${zone.utc_offset}`;

const dayValue = (day: string) => Date.parse(`${day}T00:00:00Z`);

export const dayLabel = (day: string) =>
  new Date(dayValue(day)).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });

export function addDays(day: string, offset: number): string {
  return new Date(dayValue(day) + offset * 86_400_000).toISOString().slice(0, 10);
}

export function daysBetween(start: string, end: string): string[] {
  const days: string[] = [];
  for (let day = start; day <= end; day = addDays(day, 1)) days.push(day);
  return days;
}
