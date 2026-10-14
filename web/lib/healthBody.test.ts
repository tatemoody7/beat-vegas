import { describe, expect, it } from "vitest";
import { publicBody, type HealthBody } from "./healthBody";

const full: HealthBody = {
  ok: true,
  rulePaused: false,
  rulePauseReadable: true,
  lastFullGameCapture: "2026-10-13T23:38:38.000Z",
  resultsStale: false,
  buildMissed: false,
  resultsBehindHours: 0,
  unscoredPlayedGames: 0,
  fullGameSnapshotsLast24h: 1291,
  fullGameGamesLast24h: 61,
  gauges: {
    cfbdCallsRemaining: 73707,
    oddsCreditsRemaining: 19270,
    lastCloseCaptureAt: "2026-10-13T23:38:08.000Z",
    lastCloseCaptureEvents: 1,
    lastGradeCompletedAt: "2026-10-14T10:59:34.000Z",
    closeCoveragePct: 1,
    closeCoverage: "sat=2026-10-10 games=45 covered=45",
    lastDispatch: { grade: "2026-10-14T10:52:54.000Z" },
    health: {
      grade: {
        verdict: "degraded",
        at: "2026-10-14T11:00:40.000Z",
        note: "run=38552655444 event=workflow_dispatch miss=grade.records_graded(1 ...)",
      },
    },
  },
  warnings: [
    "grade ran with something missing (DEGRADED at 2026-10-14 Wed 7:00am ET): grade.records_graded (1 game_records with a first-half total still ungraded). Runbook: docs/HEALTH.md#grade. Run: https://github.com/tatemoody7/beat-vegas/actions/runs/38552655444",
    "Odds API credits low: 1,900 left.",
  ],
};

describe("publicBody", () => {
  it("removes the pause switch, the budgets and the run notes; keys go, never nulled", () => {
    const pub = publicBody(full) as Record<string, unknown>;
    expect(pub).not.toHaveProperty("rulePaused");
    expect(pub).not.toHaveProperty("rulePauseReadable");
    const gauges = pub.gauges as Record<string, unknown>;
    expect(gauges).not.toHaveProperty("cfbdCallsRemaining");
    expect(gauges).not.toHaveProperty("oddsCreditsRemaining");
    const health = gauges.health as Record<string, Record<string, unknown>>;
    expect(Object.keys(health.grade).sort()).toEqual(["at", "verdict"]);
    expect(health.grade.verdict).toBe("degraded");
  });
  it("keeps what a visitor and the smoke check read, and cuts the run link off each warning", () => {
    const pub = publicBody(full) as Record<string, unknown>;
    expect(pub.ok).toBe(true);
    expect(pub.resultsStale).toBe(false);
    expect(pub.buildMissed).toBe(false);
    expect((pub.gauges as Record<string, unknown>).closeCoveragePct).toBe(1);
    expect((pub.gauges as Record<string, unknown>).lastDispatch).toEqual({
      grade: "2026-10-14T10:52:54.000Z",
    });
    expect(pub.warnings).toEqual([
      "grade ran with something missing (DEGRADED at 2026-10-14 Wed 7:00am ET): grade.records_graded (1 game_records with a first-half total still ungraded). Runbook: docs/HEALTH.md#grade.",
      "Odds API credits low: 1,900 left.",
    ]);
  });
});
