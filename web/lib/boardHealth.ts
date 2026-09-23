import { CRON_JOBS, GITHUB_REPO } from "@/lib/cronJobs";
import { cardBuilds, type BuildSlot } from "@/lib/nextBuild";
import { etClock12, etDay, etMinutesOfDay, etParts } from "@/lib/et";
import { Prisma } from "@prisma/client";
import { prisma } from "@/lib/prisma";

// Is anything broken? The board is the only place that can say so.
//
// Every scheduled text was retired on 2026-09-13 (they were local Mac routines
// that only fired when the laptop happened to be awake -- the Saturday card ran
// twice all season, once ten hours late). Nothing now pushes a failure to Tate,
// so the page he actually opens has to tell him itself.
//
// Two things can be wrong, and they fail independently:
//   1. RESULTS stopped landing -- grading is broken, so every record is stale.
//   2. A BUILD did not happen -- no card, and no line sweep, so the board is
//      showing last week's numbers while looking completely normal.
//
// On 2026-09-12/13 grade.yml failed four runs straight and nothing said so: the
// only failure channel is GitHub's failed-run email. Week 2 sat with finals for
// 14 of 303 games and 0 of 31 picks graded for two days while the board looked
// completely normal. The board is where Tate looks, so the board is where the
// alarm belongs.
//
// The tell is a game THE MODEL RATED that kicked off long enough ago to be over
// and still has no final score. The rated set is exactly the board: a
// game_records row is written when the week is scored, before kickoff.
//
// "A game a book priced" was the first cut and it was too loose -- books price
// FCS-vs-FCS games, ESPN's FBS feed does not cover them and nothing here reads
// them, so 15 of those sat unscored after the 2026-09-13 backfill and would
// have kept the banner lit forever. A banner that is always on is a banner
// nobody reads.

// A game is done ~4h after kickoff and grade.yml runs twice a day (6:30am and
// noon ET). 18h means at least one grading window came and went.
export const STALE_AFTER_HOURS = 18;

export type GradeHealth = {
  lastGradedAt: Date | null;
  /** Priced games that kicked off over STALE_AFTER_HOURS ago with no score. */
  unscored: number;
  /** Kickoff of the oldest of those — how far behind we actually are. */
  oldestUnscoredKick: Date | null;
};

export type Staleness =
  | { stale: false }
  | {
      stale: true;
      unscored: number;
      behindHours: number;
      lastGradedAt: Date | null;
    };

/** Pure: turn the counts into the thing the banner renders. */
export function staleness(h: GradeHealth, now: Date = new Date()): Staleness {
  if (h.unscored <= 0 || !h.oldestUnscoredKick) return { stale: false };
  const behindHours = Math.floor(
    (now.getTime() - h.oldestUnscoredKick.getTime()) / 3_600_000,
  );
  return {
    stale: true,
    unscored: h.unscored,
    behindHours,
    lastGradedAt: h.lastGradedAt,
  };
}

// These columns are `timestamp without time zone` holding UTC. Read them as
// text and append the Z ourselves, the same way lib/movement.ts::shortT does —
// handing a naive timestamp straight to a Date is how you get a 4-5h shift.
const utc = (s: string | null): Date | null => {
  if (!s) return null;
  const d = new Date(`${s}Z`);
  return Number.isNaN(d.getTime()) ? null : d;
};

export async function getGradeHealth(season: number): Promise<GradeHealth> {
  const rows = await prisma.$queryRaw<
    {
      last_graded: string | null;
      unscored: bigint;
      oldest_kick: string | null;
    }[]
  >`
    SELECT (SELECT to_char(MAX(graded_at), 'YYYY-MM-DD"T"HH24:MI:SS')
              FROM game_records) AS last_graded,
           COUNT(*) AS unscored,
           to_char(MIN(g.start_date), 'YYYY-MM-DD"T"HH24:MI:SS') AS oldest_kick
      FROM games g
     WHERE g.season = ${season}
       AND g.home_points IS NULL
       AND EXISTS (SELECT 1 FROM game_records gr WHERE gr.game_id = g.id)
       AND g.start_date < (NOW() AT TIME ZONE 'utc')
             - (${STALE_AFTER_HOURS} * INTERVAL '1 hour')`;
  const r = rows[0];
  return {
    lastGradedAt: utc(r?.last_graded ?? null),
    unscored: Number(r?.unscored ?? 0),
    oldestUnscoredKick: utc(r?.oldest_kick ?? null),
  };
}

// --- did the last scheduled build actually happen? -------------------------
//
// A card build is also the week's line sweep, so a missed one leaves the board
// quietly out of date rather than visibly broken. The check is self-adjusting:
// it asks whether a `cards` row exists since the most recent build window
// OPENED, rather than using a fixed staleness threshold -- a fixed one would
// have to tolerate the ~72h Saturday-to-Tuesday gap and would then be useless.

export type BuildHealth = {
  /** Newest cards.built_at, whatever week it belongs to. */
  lastBuiltAt: Date | null;
  /** ET label of the most recent build window that has closed, e.g. "Fri". */
  lastWindowDay: string | null;
  /** Start of that window, as an instant. */
  lastWindowOpenedAt: Date | null;
};

export type BuildStatus =
  { missed: false } | { missed: true; day: string; lastBuiltAt: Date | null };

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] as const;

/** Pure: the most recent build window to have CLOSED at or before `now`. */
export function lastClosedWindow(
  now: Date,
): { day: string; openedAt: Date } | null {
  return lastClosedSlot(cardBuilds(), now);
}

/** Pure: of these ET day/minute windows, the one that closed most recently at
 *  or before `now` (walking back at most a week), with the instant it opened. */
export function lastClosedSlot(
  slots: readonly BuildSlot[],
  now: Date,
): { day: string; openedAt: Date } | null {
  if (slots.length === 0) return null;
  const nowMin = etMinutesOfDay(now);
  const nowDow = DAYS.indexOf(etParts(now).weekday as (typeof DAYS)[number]);
  if (nowDow < 0) return null;

  let best: { day: string; openedAt: Date; agoMin: number } | null = null;
  for (const s of slots) {
    const dow = DAYS.indexOf(s.day as (typeof DAYS)[number]);
    if (dow < 0) continue;
    // Minutes since that window closed, walking back at most a week.
    let ago = (nowDow - dow) * 1440 + (nowMin - s.closeMin);
    if (ago < 0) ago += 7 * 1440;
    const openedAt = new Date(
      now.getTime() - (ago + (s.closeMin - s.openMin)) * 60_000,
    );
    if (best === null || ago < best.agoMin) {
      best = { day: s.day, openedAt, agoMin: ago };
    }
  }
  return best ? { day: best.day, openedAt: best.openedAt } : null;
}

/** Pure: did the most recently closed window produce a card? */
export function buildStatus(h: BuildHealth): BuildStatus {
  if (!h.lastWindowOpenedAt || !h.lastWindowDay) return { missed: false };
  if (h.lastBuiltAt && h.lastBuiltAt >= h.lastWindowOpenedAt) {
    return { missed: false };
  }
  return { missed: true, day: h.lastWindowDay, lastBuiltAt: h.lastBuiltAt };
}

export async function getBuildHealth(
  now: Date = new Date(),
): Promise<BuildHealth> {
  const rows = await prisma.$queryRaw<{ built: string | null }[]>`
    SELECT to_char(MAX(built_at), 'YYYY-MM-DD"T"HH24:MI:SS') AS built FROM cards`;
  const win = lastClosedWindow(now);
  return {
    lastBuiltAt: utc(rows[0]?.built ?? null),
    lastWindowDay: win?.day ?? null,
    lastWindowOpenedAt: win?.openedAt ?? null,
  };
}

// --------------------------------------------------------------------------
// Operational gauges (beatvegas/ops.py) -- the numbers whose silence produced
// eleven of the fourteen failures of 2026-08/09: an API budget nobody read
// until it hit zero, a close poll that stopped firing, a grading run that
// exited green having graded nothing. Each is one `app_settings` row written
// where it is learned; this reads them and turns them into a banner.

export const BASE_GAUGE_KEYS = [
  "cfbd_calls_remaining",
  "odds_credits_remaining",
  "last_close_capture_at",
  "last_close_capture_events",
  "last_grade_completed_at",
] as const;

// One more per cron job, written by app/api/cron/[job]/route.ts rather than by
// Python: the last time a Vercel tick ACTED inside that job's window (dispatched
// a build, or found one already there). GitHub's crons are the backup and a
// manual run looks identical in the runs API, so without this row the primary
// trigger can die and every build still "happen" (beatvegas/ops.py::
// last_dispatch_key). Derived from CRON_JOBS so a renamed job cannot leave a
// gauge nobody writes.
export const DISPATCH_GAUGE_PREFIX = "last_dispatch_";
export const DISPATCH_JOB_IDS: readonly string[] = Object.keys(CRON_JOBS);

// One more per scheduled Neon-writing job, written by scripts/health_check.py as
// that job's LAST step (beatvegas/health.py, docs/HEALTH.md): value = the
// verdict, note = `run=<id> event=<trigger> slot=<slot> miss=<check>(<detail>);...
// info=k=v`. The gauges above say whether the system can keep running; this one
// says whether the run that just finished left behind what it was for. Prefix
// and job ids mirror beatvegas/ops.py HEALTH_PREFIX / HEALTH_JOBS
// (tests/test_ops_gauges.py reads them out of this file).
export const HEALTH_GAUGE_PREFIX = "last_health_";
export const HEALTH_JOB_IDS = [
  "card",
  "grade",
  "sunday",
  "lines_watch",
] as const;
export type HealthJobId = (typeof HEALTH_JOB_IDS)[number];

export const GAUGE_KEYS: readonly string[] = [
  ...BASE_GAUGE_KEYS,
  ...DISPATCH_JOB_IDS.map((id) => `${DISPATCH_GAUGE_PREFIX}${id}`),
  ...HEALTH_JOB_IDS.map((id) => `${HEALTH_GAUGE_PREFIX}${id}`),
];

export type GaugeRow = {
  key: string;
  value: string;
  updated_at: string | null;
  note: string | null;
};

export type HealthVerdict = "ok" | "degraded" | "failed";
const HEALTH_VERDICTS: readonly HealthVerdict[] = ["ok", "degraded", "failed"];

export type HealthGauge = {
  /** null when no row exists or the value is not a verdict this build knows. */
  verdict: HealthVerdict | null;
  note: string | null;
  /** When the verdict was written (naive UTC in the DB). */
  at: Date | null;
};

export type Gauges = {
  cfbdCallsRemaining: number | null;
  oddsCreditsRemaining: number | null;
  lastCloseCaptureAt: Date | null;
  lastCloseCaptureEvents: number | null;
  lastGradeCompletedAt: Date | null;
  /** Per cron job id: the last in-window Vercel tick, or null if never seen. */
  lastDispatch: Record<string, Date | null>;
  /** Per scheduled job: the last health-contract verdict (docs/HEALTH.md). */
  health: Record<HealthJobId, HealthGauge>;
  /** When each gauge was last written (naive UTC in the DB). */
  updatedAt: Partial<Record<string, Date | null>>;
};

/** CFBD Academic tier is 3,000 calls a month; under this it is days, not weeks. */
export const CFBD_LOW_CALLS = 300;
/** A week of card builds + closes is ~600 Odds credits; under this the month is at risk. */
export const ODDS_LOW_CREDITS = 2000;
/** Longest gap between pre-kickoff close captures during the season (Sat to Sat plus slack). */
export const CLOSE_CAPTURE_MAX_AGE_H = 8 * 24;

const numOrNull = (v: string | undefined): number | null => {
  if (v === undefined) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};

/** A gauge VALUE that is a timestamp: naive UTC like the rest, but tolerate a
 *  trailing Z or offset so a writer that used toISOString() is not read as
 *  invalid. */
const utcValue = (s: string | undefined): Date | null => {
  if (!s) return null;
  if (/(Z|[+-]\d{2}:?\d{2})$/.test(s)) {
    const d = new Date(s);
    return Number.isNaN(d.getTime()) ? null : d;
  }
  return utc(s);
};

/** Pure: rows -> gauges. */
export function gaugesFrom(rows: GaugeRow[]): Gauges {
  const by = new Map(rows.map((r) => [r.key, r]));
  const at = (k: string): Date | null => utc(by.get(k)?.updated_at ?? null);
  const updatedAt: Gauges["updatedAt"] = {};
  for (const k of GAUGE_KEYS) updatedAt[k] = at(k);
  const lastDispatch: Record<string, Date | null> = {};
  for (const id of DISPATCH_JOB_IDS) {
    lastDispatch[id] = utcValue(by.get(`${DISPATCH_GAUGE_PREFIX}${id}`)?.value);
  }
  const health = {} as Record<HealthJobId, HealthGauge>;
  for (const id of HEALTH_JOB_IDS) {
    const row = by.get(`${HEALTH_GAUGE_PREFIX}${id}`);
    const v = row?.value;
    health[id] = {
      // A value this build does not know is unknown, never a warning.
      verdict: HEALTH_VERDICTS.includes(v as HealthVerdict)
        ? (v as HealthVerdict)
        : null,
      note: row?.note ?? null,
      at: utc(row?.updated_at ?? null),
    };
  }
  return {
    cfbdCallsRemaining: numOrNull(by.get("cfbd_calls_remaining")?.value),
    oddsCreditsRemaining: numOrNull(by.get("odds_credits_remaining")?.value),
    lastCloseCaptureAt: utc(by.get("last_close_capture_at")?.value ?? null),
    lastCloseCaptureEvents: numOrNull(
      by.get("last_close_capture_events")?.value,
    ),
    lastGradeCompletedAt: utc(by.get("last_grade_completed_at")?.value ?? null),
    lastDispatch,
    health,
    updatedAt,
  };
}

export type HealthNote = {
  /** GITHUB_RUN_ID, for the link to the Actions run. */
  run: string | null;
  /** GITHUB_EVENT_NAME: schedule (GitHub's backup cron) or workflow_dispatch. */
  event: string | null;
  slot: string | null;
  misses: { id: string; detail: string }[];
};

/** Pure: the note scripts/health_check.py writes -> its parts. The format is
 *  `run=<id> event=<name> [slot=<slot>] [market=<m>] [miss=<id>(<detail>);...]
 *  [info=k=v ...]`; a detail never carries `;` (health.py strips it), so the
 *  miss list splits on it. */
export function parseHealthNote(note: string | null): HealthNote {
  const out: HealthNote = { run: null, event: null, slot: null, misses: [] };
  if (!note) return out;
  const field = (name: string): string | null => {
    const m = note.match(new RegExp(`(?:^|\\s)${name}=(\\S+)`));
    return m ? m[1] : null;
  };
  out.run = field("run");
  out.event = field("event");
  out.slot = field("slot");
  const m = note.match(/(?:^|\s)miss=(.*?)(?=\s+info=|$)/);
  if (m) {
    for (const seg of m[1].split(";")) {
      const item = seg.match(/^([A-Za-z0-9_.]+)\((.*)\)$/);
      if (item) out.misses.push({ id: item[1], detail: item[2] });
      else if (seg.trim()) out.misses.push({ id: seg.trim(), detail: "" });
    }
  }
  return out;
}

/** The Actions run a health note points at, or null without a run id. */
export function healthRunUrl(note: HealthNote): string | null {
  return note.run && /^\d+$/.test(note.run)
    ? `https://github.com/${GITHUB_REPO}/actions/runs/${note.run}`
    : null;
}

export async function getGauges(): Promise<Gauges> {
  try {
    const rows = await prisma.$queryRaw<GaugeRow[]>`
      SELECT key, value, note,
             to_char(updated_at, 'YYYY-MM-DD"T"HH24:MI:SS') AS updated_at
        FROM app_settings
       WHERE key IN (${Prisma.join([...GAUGE_KEYS])})`;
    return gaugesFrom(rows);
  } catch (e) {
    console.error(
      "[boardHealth] gauges unreadable:",
      String((e as Error)?.message ?? e),
    );
    return gaugesFrom([]);
  }
}

export type OpsWarning = { key: string; text: string };

/** Pure: which gauges are in a state Tate would act on. `inSeason` keeps the
 *  close-capture check quiet in the off-season, when no close is expected. */
export function opsWarnings(
  g: Gauges,
  now: Date = new Date(),
  inSeason: boolean = true,
): OpsWarning[] {
  const out: OpsWarning[] = [];
  if (g.cfbdCallsRemaining !== null && g.cfbdCallsRemaining < CFBD_LOW_CALLS) {
    out.push({
      key: "cfbd",
      text: `CFBD budget low: ${g.cfbdCallsRemaining} calls left this month. At zero, grading and the weekly frame stop (it happened 2026-09-12).`,
    });
  }
  if (
    g.oddsCreditsRemaining !== null &&
    g.oddsCreditsRemaining < ODDS_LOW_CREDITS
  ) {
    out.push({
      key: "odds",
      text: `Odds API credits low: ${g.oddsCreditsRemaining} left this cycle. Each card build spends ~80; the close polls stop first.`,
    });
  }
  if (inSeason && g.lastCloseCaptureAt !== null) {
    const ageH = (now.getTime() - g.lastCloseCaptureAt.getTime()) / 3_600_000;
    if (ageH > CLOSE_CAPTURE_MAX_AGE_H) {
      out.push({
        key: "close",
        text: `No pre-kickoff close captured for ${Math.floor(ageH / 24)} days. Every line-value number since then is graded against a sweep quote, not a close.`,
      });
    }
  }
  // The primary trigger. A job whose most recent window has CLOSED without an
  // in-window Vercel tick is running on the backup (GitHub's cron, or a hand
  // dispatch) -- which is invisible everywhere else, because the build itself
  // looks the same. A job never seen is unknown, not wrong: the row appears the
  // first time a tick acts, so it cannot alarm on a fresh deploy. A window that
  // is still open never warns (the tick may be minutes away).
  for (const id of DISPATCH_JOB_IDS) {
    const last = g.lastDispatch[id] ?? null;
    if (last === null) continue;
    const job = CRON_JOBS[id];
    const days = job.days ?? DAYS;
    const win = lastClosedSlot(
      days.map((day) => ({
        day,
        openMin: job.dispatchOpenMin,
        closeMin: job.dispatchCloseMin,
      })),
      now,
    );
    if (win !== null && last.getTime() < win.openedAt.getTime()) {
      out.push({
        key: `dispatch:${id}`,
        text: `Vercel did not trigger ${id} in its ${win.day} window (last in-window tick ${last.toISOString().slice(0, 10)}). Whatever ran came from GitHub's backup cron or a hand dispatch; if it repeats, check the Vercel cron list, CRON_SECRET and GITHUB_DISPATCH_TOKEN (docs/OPS_ACCOUNTS.md).`,
      });
    }
  }
  // The health contracts (docs/HEALTH.md): the last verdict each scheduled job
  // wrote about its own run. `ok` is silent, a job never seen is unknown, a
  // value this build does not know is unknown too. `failed` (the run did not
  // do its job) sorts before `degraded` (it did, with something missing).
  const health: OpsWarning[] = [];
  for (const id of HEALTH_JOB_IDS) {
    const h = g.health[id];
    if (h.verdict !== "failed" && h.verdict !== "degraded") continue;
    health.push({ key: `health:${id}`, text: healthWarningText(id, h) });
  }
  const rank = (w: OpsWarning) =>
    g.health[w.key.slice("health:".length) as HealthJobId].verdict === "failed"
      ? 0
      : 1;
  health.sort((a, b) => rank(a) - rank(b));
  return [...out, ...health];
}

/** Pure: one banner line for a degraded/failed health verdict. */
export function healthWarningText(id: string, h: HealthGauge): string {
  const note = parseHealthNote(h.note);
  const when = h.at ? `${etDay(h.at)} ${etClock12(h.at)} ET` : "unknown time";
  const what =
    h.verdict === "failed"
      ? "did not do its job"
      : "ran with something missing";
  const misses =
    note.misses.length > 0
      ? note.misses
          .map((m) => (m.detail ? `${m.id} (${m.detail})` : m.id))
          .join("; ")
      : "no check named";
  const run = healthRunUrl(note);
  return (
    `${id} ${what} (${h.verdict?.toUpperCase()} at ${when}): ${misses}. ` +
    `Runbook: docs/HEALTH.md#${id}.` +
    (run ? ` Run: ${run}` : "")
  );
}
