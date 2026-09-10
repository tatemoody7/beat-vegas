import { CRON_JOBS } from "@/lib/cronJobs";
import { etParts, pad2 } from "@/lib/et";

// When the next decision build lands, for the answer bar at the top of the
// board. Derived from CRON_JOBS rather than retyped, so renaming or moving a
// slot cannot leave the board advertising a build that no longer happens.
//
// It states a WINDOW, not a time. Vercel's Hobby cron fires within the hour
// after its scheduled minute (lib/cronJobs.ts), so "Thu 4:05pm" would be a
// precision the scheduler does not have. The window is the dispatch window the
// route itself enforces.

const DAY_ORDER = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] as const;

export type BuildSlot = { day: string; openMin: number; closeMin: number };

/** The card builds only — grading is daily and is not a decision build. */
export function cardBuilds(): BuildSlot[] {
  return Object.values(CRON_JOBS)
    .filter((j) => j.workflow === "card.yml" && j.days !== null)
    .map((j) => ({
      day: (j.days as readonly string[])[0],
      openMin: j.dispatchOpenMin,
      closeMin: j.dispatchCloseMin,
    }));
}

function clock12(min: number): { h: number; m: number; pm: boolean } {
  const h24 = Math.floor(min / 60);
  return { h: h24 % 12 === 0 ? 12 : h24 % 12, m: min % 60, pm: h24 >= 12 };
}

/** "3:45–5:15pm", or "7:00–8:15am" — one suffix when both sides share it. */
function windowLabel(openMin: number, closeMin: number): string {
  const a = clock12(openMin);
  const b = clock12(closeMin);
  const suf = (pm: boolean) => (pm ? "pm" : "am");
  const left = `${a.h}:${pad2(a.m)}${a.pm === b.pm ? "" : suf(a.pm)}`;
  return `${left}–${b.h}:${pad2(b.m)}${suf(b.pm)}`;
}

/**
 * Pure: the next card build at or after `now`, in ET. A build already inside
 * its window counts as next — it has not happened yet from the board's point of
 * view, and saying "next build Saturday" while Saturday's window is open would
 * be wrong.
 */
export function nextBuild(now: Date): { label: string } | null {
  const slots = cardBuilds();
  if (slots.length === 0) return null;
  const p = etParts(now);
  const today = DAY_ORDER.indexOf(p.weekday as (typeof DAY_ORDER)[number]);
  if (today < 0) return null;
  const nowMin = p.hour * 60 + p.minute;

  let best: { at: number; slot: BuildSlot } | null = null;
  for (const slot of slots) {
    const idx = DAY_ORDER.indexOf(slot.day as (typeof DAY_ORDER)[number]);
    if (idx < 0) continue;
    let days = (idx - today + 7) % 7;
    // Past its close today: it is next week's. Still inside the window: today.
    if (days === 0 && nowMin > slot.closeMin) days = 7;
    const at = days * 1440 + slot.openMin;
    if (best === null || at < best.at) best = { at, slot };
  }
  if (best === null) return null;
  return {
    label: `${best.slot.day} ${windowLabel(best.slot.openMin, best.slot.closeMin)} ET`,
  };
}
