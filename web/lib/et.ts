// Eastern-time clock helpers. Every "what time is it for the bettor" question
// on the site (card health, kickoff labels, day grouping, line-move timestamps)
// goes through ONE Intl formatter so DST is handled in one place and the
// pieces (weekday, calendar day, hour, minute) come back as numbers, never as
// re-parsed strings. Mirrors beatvegas/ci.py ET for the Python side.

export const ET_ZONE = "America/New_York";

export type EtParts = {
  /** "Mon" … "Sun" */
  weekday: string;
  year: number;
  month: number;
  day: number;
  /** 0-23 (h23: midnight is 0, never 24) */
  hour: number;
  minute: number;
};

const ET_PARTS_FMT = new Intl.DateTimeFormat("en-US", {
  timeZone: ET_ZONE,
  weekday: "short",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

/** The ET wall-clock pieces of an instant. */
export function etParts(d: Date): EtParts {
  const parts = ET_PARTS_FMT.formatToParts(d);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  return {
    weekday: get("weekday").slice(0, 3),
    year: Number(get("year")),
    month: Number(get("month")),
    day: Number(get("day")),
    // Some engines still print "24" for midnight under h23; fold it to 0.
    hour: Number(get("hour")) % 24,
    minute: Number(get("minute")),
  };
}

const pad2 = (n: number) => String(n).padStart(2, "0");

/** Calendar day in ET, "2026-09-12". */
export function etDay(d: Date): string {
  const p = etParts(d);
  return `${p.year}-${pad2(p.month)}-${pad2(p.day)}`;
}

/** Minutes since ET midnight, 0-1439. */
export function etMinutesOfDay(d: Date): number {
  const p = etParts(d);
  return p.hour * 60 + p.minute;
}
