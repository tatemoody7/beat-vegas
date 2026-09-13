import { describe, expect, it } from "vitest";
import { staleness, type GradeHealth } from "@/lib/gradeHealth";

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
