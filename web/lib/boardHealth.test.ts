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
