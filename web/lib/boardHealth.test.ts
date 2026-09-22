import { describe, expect, it } from "vitest";
import { staleness, type GradeHealth } from "@/lib/boardHealth";

const NOW = new Date("2026-09-13T15:00:00Z");

const healthy: GradeHealth = {
  lastGradedAt: new Date("2026-09-13T11:00:00Z"),
  unscored: 0,
  oldestUnscoredKick: null,
};

describe("staleness", () => {
  it("says nothing when every played game has a score", () => {
    expect(staleness(healthy, NOW)).toEqual({ stale: false });
  });

  it("reports how far behind we are, not just that we are", () => {
    // The real 2026-09-12 failure: the noon-ET Saturday slate never landed.
    const s = staleness(
      {
        lastGradedAt: new Date("2026-09-12T10:56:00Z"),
        unscored: 56,
        oldestUnscoredKick: new Date("2026-09-12T16:00:00Z"),
      },
      NOW,
    );
    expect(s).toEqual({
      stale: true,
      unscored: 56,
      behindHours: 23,
      lastGradedAt: new Date("2026-09-12T10:56:00Z"),
    });
  });

  it("stays quiet when the count is zero even if a kickoff came back", () => {
    expect(
      staleness(
        { ...healthy, oldestUnscoredKick: new Date("2026-09-12T16:00:00Z") },
        NOW,
      ),
    ).toEqual({ stale: false });
  });

  it("survives a never-graded season", () => {
    const s = staleness(
      {
        lastGradedAt: null,
        unscored: 3,
        oldestUnscoredKick: new Date("2026-09-12T16:00:00Z"),
      },
      NOW,
    );
    expect(s.stale).toBe(true);
    expect(s.stale && s.lastGradedAt).toBeNull();
  });
});

import {
  buildStatus,
  lastClosedWindow,
  type BuildHealth,
} from "@/lib/boardHealth";

// A missed build is the OTHER way the board can be silently wrong: no card and
// no line sweep, while the page looks completely normal. Since 2026-09-13 there
// is no text to notice it, so the board has to say so itself.

describe("lastClosedWindow", () => {
  it("finds Friday's window from Saturday morning", () => {
    // Sat 2026-09-12 08:00 ET. Friday's card window closed 5:15pm the day before.
    const w = lastClosedWindow(new Date("2026-09-12T12:00:00Z"));
    expect(w?.day).toBe("Fri");
  });

  it("finds Saturday's window from Sunday, not the older Friday one", () => {
    const w = lastClosedWindow(new Date("2026-09-13T18:00:00Z"));
    expect(w?.day).toBe("Sat");
  });

  it("wraps back a week rather than returning nothing on a Monday", () => {
    // Mon 2026-09-14: the most recent close is Saturday's, two days back.
    const w = lastClosedWindow(new Date("2026-09-14T18:00:00Z"));
    expect(w?.day).toBe("Sat");
  });
});

describe("buildStatus", () => {
  const win = new Date("2026-09-12T11:00:00Z"); // Saturday's window opened 7am ET
  const base: BuildHealth = {
    lastBuiltAt: null,
    lastWindowDay: "Sat",
    lastWindowOpenedAt: win,
  };

  it("is quiet when a card was built inside the window", () => {
    // The real sat_am card: built 2026-09-12 12:00Z.
    expect(
      buildStatus({ ...base, lastBuiltAt: new Date("2026-09-12T12:00:00Z") }),
    ).toEqual({ missed: false });
  });

  it("flags a window that produced nothing", () => {
    const s = buildStatus({
      ...base,
      lastBuiltAt: new Date("2026-09-11T20:18:00Z"), // Friday's card, not Saturday's
    });
    expect(s).toEqual({
      missed: true,
      day: "Sat",
      lastBuiltAt: new Date("2026-09-11T20:18:00Z"),
    });
  });

  it("survives a database with no cards at all", () => {
    expect(buildStatus(base)).toMatchObject({
      missed: true,
      lastBuiltAt: null,
    });
  });

  it("says nothing when no window has closed yet", () => {
    expect(
      buildStatus({ ...base, lastWindowDay: null, lastWindowOpenedAt: null }),
    ).toEqual({ missed: false });
  });
});

import {
  CFBD_LOW_CALLS,
  CLOSE_CAPTURE_MAX_AGE_H,
  gaugesFrom,
  ODDS_LOW_CREDITS,
  opsWarnings,
} from "@/lib/boardHealth";

describe("operational gauges (beatvegas/ops.py -> the board)", () => {
  const now = new Date("2026-09-22T18:00:00Z");
  const rows = [
    {
      key: "cfbd_calls_remaining",
      value: "1974",
      updated_at: "2026-09-22T10:52:00",
    },
    {
      key: "odds_credits_remaining",
      value: "53946",
      updated_at: "2026-09-22T10:52:00",
    },
    {
      key: "last_close_capture_at",
      value: "2026-09-19T23:30:00",
      updated_at: "2026-09-19T23:30:00",
    },
    {
      key: "last_close_capture_events",
      value: "3",
      updated_at: "2026-09-19T23:30:00",
    },
    {
      key: "last_grade_completed_at",
      value: "2026-09-22T10:58:00",
      updated_at: "2026-09-22T10:58:00",
    },
  ];
  it("parses the rows and is quiet when everything is healthy", () => {
    const g = gaugesFrom(rows);
    expect(g.cfbdCallsRemaining).toBe(1974);
    expect(g.oddsCreditsRemaining).toBe(53946);
    expect(g.lastCloseCaptureAt?.toISOString()).toBe(
      "2026-09-19T23:30:00.000Z",
    );
    expect(g.lastGradeCompletedAt?.toISOString()).toBe(
      "2026-09-22T10:58:00.000Z",
    );
    expect(opsWarnings(g, now)).toEqual([]);
  });
  it("warns on a low CFBD budget, low Odds credits, and a stale close", () => {
    const g = gaugesFrom([
      {
        key: "cfbd_calls_remaining",
        value: String(CFBD_LOW_CALLS - 1),
        updated_at: null,
      },
      {
        key: "odds_credits_remaining",
        value: String(ODDS_LOW_CREDITS - 1),
        updated_at: null,
      },
      {
        key: "last_close_capture_at",
        value: "2026-09-01T00:00:00",
        updated_at: null,
      },
    ]);
    const keys = opsWarnings(g, now).map((w) => w.key);
    expect(keys).toEqual(["cfbd", "odds", "close"]);
    expect(CLOSE_CAPTURE_MAX_AGE_H).toBe(192);
  });
  it("says nothing it does not know: missing gauges never warn, and the close check sleeps off-season", () => {
    expect(opsWarnings(gaugesFrom([]), now)).toEqual([]);
    const g = gaugesFrom([
      {
        key: "last_close_capture_at",
        value: "2026-01-10T00:00:00",
        updated_at: null,
      },
    ]);
    expect(opsWarnings(g, now, false)).toEqual([]);
    expect(opsWarnings(g, now, true).map((w) => w.key)).toEqual(["close"]);
  });
  it("a non-numeric value reads as unknown, not as zero", () => {
    const g = gaugesFrom([
      { key: "cfbd_calls_remaining", value: "n/a", updated_at: null },
    ]);
    expect(g.cfbdCallsRemaining).toBeNull();
    expect(opsWarnings(g, now)).toEqual([]);
  });
});

import {
  DISPATCH_GAUGE_PREFIX,
  DISPATCH_JOB_IDS,
  GAUGE_KEYS,
  lastClosedSlot,
} from "@/lib/boardHealth";
import { CRON_JOBS } from "@/lib/cronJobs";

describe("the trigger gauge (app/api/cron/[job] -> last_dispatch_<job>)", () => {
  // Tuesday 2026-09-22, 2:00pm ET: no card window is open (tue_pm opens 3:45pm).
  const tue2pm = new Date("2026-09-22T18:00:00Z");
  const row = (id: string, value: string) => ({
    key: `${DISPATCH_GAUGE_PREFIX}${id}`,
    value,
    updated_at: value,
  });

  it("reads one gauge per cron job, derived from CRON_JOBS", () => {
    expect([...DISPATCH_JOB_IDS].sort()).toEqual(Object.keys(CRON_JOBS).sort());
    for (const id of DISPATCH_JOB_IDS) {
      expect(GAUGE_KEYS).toContain(`last_dispatch_${id}`);
      // app_settings.key is String(32) in beatvegas/db/models.py.
      expect(`last_dispatch_${id}`.length).toBeLessThanOrEqual(32);
    }
  });

  it("parses the value as naive UTC, and tolerates a trailing Z", () => {
    const g = gaugesFrom([
      row("card-sat-am", "2026-09-19T11:05:00"),
      row("grade", "2026-09-22T10:20:00.000Z"),
    ]);
    expect(g.lastDispatch["card-sat-am"]?.toISOString()).toBe(
      "2026-09-19T11:05:00.000Z",
    );
    expect(g.lastDispatch["grade"]?.toISOString()).toBe(
      "2026-09-22T10:20:00.000Z",
    );
    expect(g.lastDispatch["card-tue-pm"]).toBeNull();
  });

  it("is quiet when every job's last closed window saw a tick", () => {
    const g = gaugesFrom([
      row("card-tue-pm", "2026-09-15T20:10:00"), // last Tue, in window
      row("card-thu-pm", "2026-09-17T20:05:00"),
      row("card-fri-pm", "2026-09-18T20:11:00"),
      row("card-sat-am", "2026-09-19T11:05:00"), // Sat 7:05am ET
      row("sunday", "2026-09-20T18:30:00"),
      row("grade", "2026-09-22T10:20:00"), // this morning
    ]);
    expect(opsWarnings(g, tue2pm)).toEqual([]);
  });

  it("warns for the job whose window closed without a tick, naming the day", () => {
    const g = gaugesFrom([
      row("card-sat-am", "2026-09-12T11:05:00"), // the Saturday BEFORE last
      row("card-fri-pm", "2026-09-18T20:11:00"),
    ]);
    const w = opsWarnings(g, tue2pm);
    expect(w.map((x) => x.key)).toEqual(["dispatch:card-sat-am"]);
    expect(w[0].text).toContain("Sat window");
    expect(w[0].text).toContain("2026-09-12");
  });

  it("never warns while the job's window is still open", () => {
    // Tuesday 4:00pm ET: tue_pm's window (3:45-5:15) is open, no tick yet.
    const tue4pm = new Date("2026-09-22T20:00:00Z");
    const g = gaugesFrom([row("card-tue-pm", "2026-09-15T20:10:00")]);
    expect(opsWarnings(g, tue4pm)).toEqual([]);
    // ...and does warn once it has closed with no tick (Tuesday 6:00pm ET).
    const tue6pm = new Date("2026-09-22T22:00:00Z");
    expect(opsWarnings(g, tue6pm).map((x) => x.key)).toEqual([
      "dispatch:card-tue-pm",
    ]);
  });

  it("a daily job (grade) is judged against yesterday's window", () => {
    const g = gaugesFrom([row("grade", "2026-09-20T10:20:00")]);
    expect(opsWarnings(g, tue2pm).map((x) => x.key)).toEqual([
      "dispatch:grade",
    ]);
    const ok = gaugesFrom([row("grade", "2026-09-21T10:20:00")]);
    expect(opsWarnings(ok, tue2pm)).toEqual([]);
  });

  it("a job never seen is unknown, not wrong", () => {
    expect(opsWarnings(gaugesFrom([]), tue2pm)).toEqual([]);
  });

  it("lastClosedSlot walks back at most a week and reports the opening instant", () => {
    const win = lastClosedSlot(
      [{ day: "Sat", openMin: 7 * 60, closeMin: 8 * 60 + 15 }],
      tue2pm,
    );
    // Sat 2026-09-19 7:00am EDT = 11:00Z
    expect(win?.day).toBe("Sat");
    expect(win?.openedAt.toISOString()).toBe("2026-09-19T11:00:00.000Z");
  });
});
