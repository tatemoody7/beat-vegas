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
 * The Saturday window opens at 7:00 and closes at 8:15. That was originally so
 * the card landed before an 8:50am Mac routine texted it; that routine was
 * retired 2026-09-13 (every scheduled text was), so the window could now widen
 * to ci.py's 9:15 gate and let more entries act. Left as-is deliberately: it
 * works, and a wider window is a behaviour change worth making on purpose
 * rather than as a side effect. The cost is that Saturday's card may build as
 * early as 7:00am; minute-accurate timing needs Vercel's paid tier.
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
    // 7:00–8:15am: wide enough that the EDT entry always lands inside it, and
    // closed before the 9:15 ET gate so a late Hobby tick cannot dispatch a
    // build the gate would then refuse. (It once also had to beat an 8:50am
    // text; that routine was retired 2026-09-13 and the window kept.)
    dispatchOpenMin: 7 * 60,
    dispatchCloseMin: 8 * 60 + 15,
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
    dispatchOpenMin: 13 * 60,
    dispatchCloseMin: 17 * 60,
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
