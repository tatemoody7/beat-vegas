import { etMinutesOfDay, etParts } from "@/lib/et";

/**
 * The trigger table for /api/cron/[job].
 *
 * GitHub Actions cron is unreliable, not merely late: it fired 0 of 5 scheduled
 * card builds on time on 2026-09-09 (the 12:05Z tick ran at 16:33Z), and the
 * cards that existed that week were dispatched by hand. So a Vercel cron hits
 * this site and the site dispatches the workflow. GitHub's own crons stay as
 * the backup, and beatvegas/ci.py's built-today probe stops the two from both
 * building.
 *
 * Everything schedule-shaped lives here, so renaming a slot touches one line.
 *
 * WINDOWS. Vercel's Hobby plan fires within the hour AFTER the scheduled
 * minute, so an entry lands anywhere in a 60-minute band, and the band shifts
 * an hour at the DST change. Two consequences, both load-bearing:
 *
 *  1. A window must be at least 60 minutes wide plus the entry's lead-in, or
 *     an entry is refused systematically rather than occasionally.
 *  2. One UTC hour cannot serve both regimes, so each job carries several and
 *     the window here decides which of them is allowed to act.
 *
 * EVERY DISPATCH WINDOW SITS INSIDE ITS BUILD GATE (2026-10-17). Since #379
 * (2026-10-14) a named slot dispatched outside beatvegas/ci.py's ET gate skips,
 * and the skipped run still concludes "success" -- which suppressedBy counts as
 * the window's build, standing every later tick down. Saturday's window used to
 * open at 7:00 against a 7:45 gate, so the first Hobby tick (anywhere in its
 * hour) skipped about three times in four and took the card with it. The
 * window is now 7:45-9:00: the 12Z entry (EDT) and the 13Z entry (EST) land
 * wholly inside it, and 9:00 leaves 15 minutes for the neon-writers queue
 * before the 9:15 gate closes. cronJobs.test.ts pins both properties.
 */

export type CronJob = {
  /** Workflow FILE name — the dispatch identifier GitHub expects. */
  workflow: string;
  /** workflow_dispatch inputs. Empty means send NO `inputs` key at all. */
  inputs: Readonly<Record<string, string>>;
  /** ET weekday short names this job may run on; null = any day. */
  days: readonly string[] | null;
  /** ET minutes-of-day, inclusive, in which a tick may dispatch. */
  dispatchOpenMin: number;
  dispatchCloseMin: number;
  /**
   * The ET window inside which a SCHEDULED GitHub run actually builds
   * (beatvegas/ci.py SLOT_GATE_ET). Not the dispatch window: it is how we tell
   * a real backup build from a tick that gate-skipped and built nothing.
   * null = the workflow has no gate, so any run of it counts.
   */
  gateOpenMin: number | null;
  gateCloseMin: number | null;
  /**
   * Dispatch on EVERY in-window tick instead of once per window. For a job
   * whose runs are cheap and idempotent and whose value is in repetition (the
   * Saturday close poll: each run covers only the games kicking off in the next
   * two hours), "already ran this window" is the wrong question. Default false.
   */
  everyTick?: boolean;
};

export const GITHUB_REPO = "tatemoody7/beat-vegas";
export const GITHUB_REF = "main";

/** 3:45pm and 5:15pm ET — beatvegas/ci.py SLOT_GATE_ET for the afternoon slots. */
const PM_GATE_OPEN = 15 * 60 + 45;
const PM_GATE_CLOSE = 17 * 60 + 15;

/** The afternoon dispatch window, 90 minutes wide so the 20Z EDT tick always fits. */
const PM_DISPATCH_OPEN = 15 * 60 + 45;
const PM_DISPATCH_CLOSE = 17 * 60 + 15;

const afternoon = (slot: string, day: string): CronJob => ({
  workflow: "card.yml",
  inputs: { slot },
  days: [day],
  dispatchOpenMin: PM_DISPATCH_OPEN,
  dispatchCloseMin: PM_DISPATCH_CLOSE,
  gateOpenMin: PM_GATE_OPEN,
  gateCloseMin: PM_GATE_CLOSE,
});

export const CRON_JOBS: Readonly<Record<string, CronJob>> = {
  "card-tue-pm": afternoon("tue_pm", "Tue"),
  "card-thu-pm": afternoon("thu_pm", "Thu"),
  "card-fri-pm": afternoon("fri_pm", "Fri"),
  "card-sat-am": {
    workflow: "card.yml",
    inputs: { slot: "sat_am" },
    days: ["Sat"],
    // 7:45–9:00am, inside ci.py's 7:45–9:15 gate (see the header): an early
    // tick would gate-skip, conclude "success" and suppress the real build.
    // One UTC entry per regime lands wholly inside (12Z EDT, 13Z EST); the
    // 15 minutes before the gate closes are for the neon-writers queue.
    dispatchOpenMin: 7 * 60 + 45,
    dispatchCloseMin: 9 * 60,
    gateOpenMin: 7 * 60 + 45,
    gateCloseMin: 9 * 60 + 15,
  },
  sunday: {
    workflow: "sunday.yml",
    // sunday.yml declares ONE optional input (`force`), so an empty object is
    // accepted -- like grade.yml's optional `hist`; neither is sent from here.
    inputs: {},
    days: ["Sun"],
    // The last workflow whose only trigger was GitHub's best-effort cron, which
    // dropped 17 of 19 scheduled runs over 2026-08-28/30. It is not a small one
    // to lose: the Sunday capture is the ONLY full-game opener poll, and the
    // same run refreshes pace, weather, scoring and the derived 1H lines that
    // the board falls back to before Hard Rock posts. Its previous watchdog was
    // a Mac routine that ran once ever, three days late.
    //
    // Wide window because nothing downstream has a deadline: capture is gated
    // to one per ET day inside the workflow (sunday.yml), so several ticks
    // landing in the same afternoon cannot double-spend the 6 credits.
    // The catch-up (2026-10-13, roadmap v2.2): the window runs to 8pm ET so a
    // fourth entry at 23Z (7pm EDT / 6pm EST) is in-window. suppressedBy lets it
    // dispatch only when no run since 1pm succeeded -- one automatic retry for
    // an afternoon whose three ticks all failed or never fired.
    dispatchOpenMin: 13 * 60,
    dispatchCloseMin: 20 * 60,
    gateOpenMin: null,
    gateCloseMin: null,
  },
  "lines-close": {
    workflow: "lines_watch.yml",
    // lines_watch.yml's resolve step maps an EMPTY schedule to the `market`
    // input, so a dispatch carrying market=1h_close runs the per-game close
    // poll exactly as the scheduled slot does (2026-09-28).
    inputs: { market: "1h_close" },
    days: ["Sat"],
    // Measured 2026-09-28: GitHub's 30-minute Saturday close crons fired 3 of
    // 18 slots in week 4 and 5 in week 3, so only ~a third of Hard-Rock-priced
    // games ever had a 1H snapshot inside the registered 2-hour close window
    // (wk2 25/72, wk3 27/72, wk4 18/57) -- and H-STOP-2's line-value clock
    // takes only those. This is the backup: one Hobby entry per UTC hour from
    // 14Z Saturday to 04Z Sunday, each firing once within its hour, every tick
    // dispatching (everyTick); 15 entries. Since 2026-10-11 a Saturday tick
    // polls every Hard Rock-priced game kicking off in the next 6 hours
    // (CLOSE_LOOKAHEAD_MIN_SAT=360 in the workflow; the capture design note), so
    // a game is read about six times in its last six hours; weeknight ticks keep
    // 120. The 14Z entry (added 2026-09-29) is 10:00-10:59 EDT: the noon
    // slate's guaranteed look. Without it the first tick (15Z) could land at
    // 11:59 and, after runner start-up, capture the noon games at 12:0x --
    // outside their 2-hour window -- leaving them to GitHub's own cron.
    // Window: 10:00am ET to midnight ET Saturday. The 14Z entry is 9am EST
    // from November, refused as before_window at no cost; the 04Z Sunday entry
    // is 11pm EST Saturday (in window from November) and 00:00 EDT Sunday in
    // summer, when this route refuses it as wrong_day at no cost.
    dispatchOpenMin: 10 * 60,
    dispatchCloseMin: 24 * 60 - 1,
    gateOpenMin: null,
    gateCloseMin: null,
    everyTick: true,
  },
  "close-weeknight": {
    workflow: "lines_watch.yml",
    // The weeknight twin of `lines-close` (2026-10-06, Tate's call: Tue-Fri,
    // hourly 6-10pm ET, first-half + full-game closes). GitHub's weeknight close
    // crons fired after kickoff or overnight for two weeks running (0 captures),
    // so Thursday/Friday games -- and November's Tuesday/Wednesday MACtion --
    // never had a close inside H-STOP-2's 2-hour window or a full-game close
    // inside 3 h. Same dispatch as Saturday's: market=1h_close, every tick; the
    // workflow's free /events pre-check skips a tick with no Hard Rock game
    // kicking off in the next 120 minutes (0 credits, ~1 Actions minute).
    // Entries 22Z-03Z cover 6pm-10pm ET in both DST regimes (22Z is 5pm EST,
    // refused before_window; 03Z is 11pm EDT, allowed). GitHub's crons stay as
    // the backup (Tate, 2026-10-06).
    inputs: { market: "1h_close" },
    days: ["Tue", "Wed", "Thu", "Fri"],
    dispatchOpenMin: 18 * 60,
    dispatchCloseMin: 24 * 60 - 1,
    gateOpenMin: null,
    gateCloseMin: null,
    everyTick: true,
  },
  "pricing-monday": {
    // The Monday pricing report (H-PRICE-HR, docs/PRICING_RESEARCH.md; Tate's
    // approval 2026-10-12). Read-only: the workflow writes a report, no table, so
    // a second run cannot double-count. Two entries, 12Z and 15Z (8am/11am EDT,
    // 7am/10am EST), both inside a 6am-noon ET window: the later tick is the
    // retry -- suppressedBy re-dispatches when the first run failed and stays
    // quiet when it succeeded. No GitHub cron (a scheduled Neon job needs a
    // health contract); `gh workflow run pricing_monday.yml` is the fallback.
    // The catch-up (2026-10-13, roadmap v2.2): the window runs to 3pm ET and a
    // third entry at 18Z (2pm EDT / 1pm EST) retries once more if neither
    // morning tick produced a successful run.
    workflow: "pricing_monday.yml",
    inputs: {},
    days: ["Mon"],
    dispatchOpenMin: 6 * 60,
    dispatchCloseMin: 15 * 60,
    gateOpenMin: null,
    gateCloseMin: null,
  },
  "weekly-report": {
    // The Sunday report (final-2026 plan D4, 2026-10-20): after the 10Z grading,
    // one page committed to docs/reads/ and a GitHub issue (emailed to Tate).
    // Two entries, 15Z (11am EDT) and 16Z (11am EST), inside a 10:30am-12:59pm
    // ET window; the 16:30Z GitHub cron is the backup and stands down when a
    // report landed in the last 20 hours.
    workflow: "weekly_report.yml",
    inputs: {},
    days: ["Sun"],
    dispatchOpenMin: 10 * 60 + 30,
    dispatchCloseMin: 12 * 60 + 59,
    gateOpenMin: null,
    gateCloseMin: null,
  },
  archive: {
    // The archive queue (final-2026 plan PR-C10, 2026-10-20): daily `auto`, which
    // spends only inside the last 4 days before the credit reset (Nov 1-4, then
    // Nov 30 - Dec 4) and does nothing otherwise. One 07Z entry (3am EDT / 2am
    // EST, inside a 1:30-4:59am ET window); the 07:00Z GitHub cron runs too, and
    // a second run the same day reads the live balance, so it never overspends.
    workflow: "archive.yml",
    inputs: { item: "auto" },
    days: null,
    dispatchOpenMin: 1 * 60 + 30,
    dispatchCloseMin: 4 * 60 + 59,
    gateOpenMin: null,
    gateCloseMin: null,
  },
  digest: {
    // The daily digest (final-2026 plan D4, 2026-10-20): silent when healthy, a
    // failed run (GitHub's email) when a job went quiet, a verdict failed, a
    // gauge went stale or the budget heads for the floor. Read-only apart from
    // its own verdict, so a second run in the window is harmless. Two entries,
    // 13Z and 14Z (9am EDT / 9am EST), inside an 8:00-10:59am ET window; the
    // 13:30Z GitHub cron is the backup.
    workflow: "digest.yml",
    inputs: {},
    days: null,
    dispatchOpenMin: 8 * 60,
    dispatchCloseMin: 10 * 60 + 59,
    gateOpenMin: null,
    gateCloseMin: null,
  },
  grade: {
    workflow: "grade.yml",
    // grade.yml declares one OPTIONAL input (`hist`, the 2023-25 post-mortem
    // regrade); the daily dispatch sends none, so the history pass stays a
    // Monday-only job. GitHub answers 422 to any input a workflow does NOT
    // declare, so never add a key here without adding it to the workflow.
    inputs: {},
    days: null,
    // No window: grading is idempotent, spends no Odds credits and has no
    // deadline, so the hour it drifts across the DST change does not matter.
    // The catch-up (2026-10-13, roadmap v2.2): a second entry at 20Z dispatches
    // only when no grade run since midnight ET succeeded (suppressedBy).
    dispatchOpenMin: 0,
    dispatchCloseMin: 24 * 60 - 1,
    gateOpenMin: null,
    gateCloseMin: null,
  },
};

export function cronJobFor(id: string): CronJob | null {
  return Object.prototype.hasOwnProperty.call(CRON_JOBS, id)
    ? CRON_JOBS[id]
    : null;
}

export type DispatchDecision = { allowed: boolean; reason: string };

/** May this tick dispatch? ET wall clock only — never the cron string. */
export function dispatchDecision(job: CronJob, now: Date): DispatchDecision {
  const p = etParts(now);
  if (job.days !== null && !job.days.includes(p.weekday)) {
    return { allowed: false, reason: `wrong_day ${p.weekday}` };
  }
  const mins = etMinutesOfDay(now);
  const clock = `${String(p.hour).padStart(2, "0")}:${String(p.minute).padStart(2, "0")}`;
  if (mins < job.dispatchOpenMin) {
    return { allowed: false, reason: `before_window ${clock} ET` };
  }
  if (mins > job.dispatchCloseMin) {
    return { allowed: false, reason: `after_window ${clock} ET` };
  }
  return { allowed: true, reason: "in_window" };
}

/** The dispatch POST body. Omits `inputs` entirely when the workflow has none. */
export function dispatchBody(job: CronJob): {
  ref: string;
  inputs?: Record<string, string>;
} {
  const body: { ref: string; inputs?: Record<string, string> } = {
    ref: GITHUB_REF,
  };
  if (Object.keys(job.inputs).length > 0) body.inputs = { ...job.inputs };
  return body;
}

/**
 * The instant today's dispatch window opened, by subtracting elapsed ET minutes
 * from `now`. Arithmetic on the instant, so there is no ET-to-instant reverse
 * conversion to get wrong at a DST boundary.
 */
export function windowOpenInstant(job: CronJob, now: Date): Date {
  const elapsed = etMinutesOfDay(now) - job.dispatchOpenMin;
  return new Date(now.getTime() - elapsed * 60_000);
}

export type RunSummary = {
  id: number;
  event: string;
  created_at: string;
  conclusion: string | null;
};

const DEAD_CONCLUSIONS = new Set([
  "failure",
  "cancelled",
  "timed_out",
  "startup_failure",
]);

/**
 * Non-null when a build for this window already happened, so we must not
 * dispatch a second one. The string says which run.
 *
 * The subtle rule is the scheduled one. A GitHub cron tick that fired outside
 * beatvegas/ci.py's ET gate resolves to slot=skip and builds NOTHING, so
 * counting it would suppress the real build — exactly the bug ci.py's header
 * documents, and in EST GitHub's own 12:05Z/12:35Z Saturday ticks land inside
 * our dispatch window and outside that gate. A dispatched run always counts:
 * something deliberately asked for a build.
 */
export function suppressedBy(
  runs: readonly RunSummary[],
  job: CronJob,
  now: Date,
): string | null {
  const since = windowOpenInstant(job, now).getTime();
  for (const run of runs) {
    const created = new Date(run.created_at);
    if (Number.isNaN(created.getTime()) || created.getTime() < since) continue;
    if (run.conclusion !== null && DEAD_CONCLUSIONS.has(run.conclusion)) {
      continue; // a failed build is exactly what a retry is for
    }
    if (run.event === "workflow_dispatch") {
      return `workflow_dispatch run ${run.id}`;
    }
    if (run.event === "schedule") {
      if (job.gateOpenMin === null || job.gateCloseMin === null) {
        return `schedule run ${run.id}`;
      }
      const mins = etMinutesOfDay(created);
      if (mins >= job.gateOpenMin && mins <= job.gateCloseMin) {
        return `schedule run ${run.id}`;
      }
      // Outside the gate: that run skipped and built nothing.
    }
  }
  return null;
}
