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

/** Two-digit zero-padded field ("07"). */
export const pad2 = (n: number): string => String(n).padStart(2, "0");

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

/**
 * Weekday + 12-hour ET clock: "Fri 6:07pm" with the default suffixes, or
 * "Sat 7:30p" with ["a", "p"]. Midnight and noon read 12, never 0.
 */
export function etClock12(
  d: Date,
  suffix: readonly [am: string, pm: string] = ["am", "pm"],
): string {
  const p = etParts(d);
  const hour12 = p.hour % 12 === 0 ? 12 : p.hour % 12;
  return `${p.weekday} ${hour12}:${pad2(p.minute)}${p.hour >= 12 ? suffix[1] : suffix[0]}`;
}

/** The ET wall clock of an instant as a `datetime-local` value, "2026-09-25T16:10"
 *  (minute precision): the log form's default "Placed at". */
export function etLocalValue(d: Date): string {
  const p = etParts(d);
  return `${p.year}-${pad2(p.month)}-${pad2(p.day)}T${pad2(p.hour)}:${pad2(p.minute)}`;
}

/**
 * An ET wall-clock string "YYYY-MM-DDTHH:MM" (what a `datetime-local` input
 * gives) to the instant it names, DST included; null when malformed. Solved by
 * one fixed-point step on the offset: guess the instant as if the wall clock
 * were UTC, read the ET parts of that guess, correct by the difference, and
 * check. Mirrors beatvegas/picks.py bet_at_from_et.
 */
export function etLocalToUtc(local: string): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(local.trim());
  if (!m) return null;
  const [y, mo, d, h, mi] = m.slice(1).map(Number);
  const wall = Date.UTC(y, mo - 1, d, h, mi);
  const asWall = (t: Date) => {
    const p = etParts(t);
    return Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute);
  };
  let guess = new Date(wall);
  for (let i = 0; i < 3; i++) {
    const diff = asWall(guess) - wall;
    if (diff === 0) return guess;
    guess = new Date(guess.getTime() - diff);
  }
  return Number.isNaN(guess.getTime()) ? null : guess;
}

/** Weekday, calendar day and 12-hour clock in ET: "Fri 9/18 4:12pm". The
 *  ledger's "posted" stamp, where the day matters as much as the hour. */
export function etStamp(d: Date): string {
  const p = etParts(d);
  const hour12 = p.hour % 12 === 0 ? 12 : p.hour % 12;
  return `${p.weekday} ${p.month}/${p.day} ${hour12}:${pad2(p.minute)}${p.hour >= 12 ? "pm" : "am"}`;
}
