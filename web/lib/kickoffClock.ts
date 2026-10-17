// The kickoff's wall clock at the venue and the visitor's time-zone change
// (2026-10-17). Both read the venue's IANA zone (`venues.timezone`, from CFBD
// /venues), DST-aware, the same way beatvegas/etl/situational.py builds
// kickoff_local_hour and away_tz_shift. Before, both were longitude / 15 —
// solar time with no minutes and no DST: Penn State @ Michigan, 19:30Z =
// 3:30pm EDT, read "1pm local kickoff" and "0.39 hours of time change".
//
// Pure: the loader is lib/kickoffClockDb.ts. A missing zone gives null, never a
// guess.

/** What the game page needs: the kickoff instant and the two zones. */
export type KickZones = {
  /** UTC ISO kickoff, or null when unknown. */
  kickoff: string | null;
  /** The game venue's IANA zone (neutral sites included). */
  venueTz: string | null;
  /** The zone of the visitor's home venue that season (its most-used one). */
  awayHomeTz: string | null;
};

/** The zone's wall-clock hour and minute at an instant; null for a bad zone. */
function wallClock(
  at: Date,
  tz: string,
): { y: number; mo: number; d: number; h: number; mi: number } | null {
  let parts: Intl.DateTimeFormatPart[];
  try {
    parts = new Intl.DateTimeFormat("en-US", {
      timeZone: tz,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).formatToParts(at);
  } catch {
    return null; // RangeError: not an IANA zone
  }
  const get = (t: string) => Number(parts.find((p) => p.type === t)?.value);
  const h = get("hour");
  return {
    y: get("year"),
    mo: get("month"),
    d: get("day"),
    // Some engines print "24" for midnight under h23.
    h: h === 24 ? 0 : h,
    mi: get("minute"),
  };
}

function instant(kickoff: string | null): Date | null {
  if (!kickoff) return null;
  const d = new Date(kickoff);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** Local kickoff hour as hour + minutes/60 (Michigan 19:30Z in October = 15.5). */
export function localKickoffHour(
  kickoff: string | null,
  tz: string | null,
): number | null {
  const at = instant(kickoff);
  if (at === null || !tz) return null;
  const w = wallClock(at, tz);
  return w === null ? null : w.h + w.mi / 60;
}

/** 15.5 -> "3:30pm", 12 -> "12:00pm", 0.25 -> "12:15am" (situational.clock_text). */
export function clockText(hour: number | null): string | null {
  if (hour === null || !Number.isFinite(hour)) return null;
  const total = ((Math.round(hour * 60) % 1440) + 1440) % 1440;
  const h = Math.floor(total / 60);
  const m = total % 60;
  return `${h % 12 || 12}:${String(m).padStart(2, "0")}${h < 12 ? "am" : "pm"}`;
}

/** The zone's UTC offset in hours at an instant (EDT = -4, MST = -7). */
export function utcOffsetHours(
  kickoff: string | null,
  tz: string | null,
): number | null {
  const at = instant(kickoff);
  if (at === null || !tz) return null;
  const w = wallClock(at, tz);
  if (w === null) return null;
  const asUtc = Date.UTC(w.y, w.mo - 1, w.d, w.h, w.mi);
  const whole = Math.floor(at.getTime() / 60000) * 60000;
  return Math.round((asUtc - whole) / 60000) / 60;
}

/** Hours the visitor's clock moves, game zone minus home zone at kickoff
 *  (positive = travelled east); null when either zone is unknown. */
export function tzShiftHours(z: KickZones): number | null {
  const g = utcOffsetHours(z.kickoff, z.venueTz);
  const h = utcOffsetHours(z.kickoff, z.awayHomeTz);
  return g === null || h === null ? null : g - h;
}
