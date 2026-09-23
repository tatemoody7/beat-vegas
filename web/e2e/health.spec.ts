import { expect, test } from "@playwright/test";
import { buildWeek } from "./fixture/week.mjs";
import { CRON_JOBS, HEALTH_JOBS } from "./fixture/expected.mjs";

// /api/health is the one endpoint a machine reads (the board's own probes, the
// bv-card-check skill). On the clean fixture every gauge is healthy, so the
// payload must say so and carry exactly the keys app/api/health/route.ts writes
// -- a renamed key would break every reader silently.

const HEALTH_KEYS = [
  "ok",
  "rulePaused",
  "rulePauseReadable",
  "lastFullGameCapture",
  "resultsStale",
  "buildMissed",
  "resultsBehindHours",
  "unscoredPlayedGames",
  "fullGameSnapshotsLast24h",
  "fullGameGamesLast24h",
  "gauges",
  "warnings",
].sort();

const GAUGE_KEYS = [
  "cfbdCallsRemaining",
  "oddsCreditsRemaining",
  "lastCloseCaptureAt",
  "lastCloseCaptureEvents",
  "lastGradeCompletedAt",
  "lastDispatch",
  "health",
].sort();

test.describe("GET /api/health", () => {
  test("answers 200 with exactly the documented keys", async ({ request }) => {
    const res = await request.get("/api/health");
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(Object.keys(body).sort()).toEqual(HEALTH_KEYS);
    expect(Object.keys(body.gauges).sort()).toEqual(GAUGE_KEYS);
  });

  test("reports the clean fixture as healthy", async ({ request }) => {
    const body = await (await request.get("/api/health")).json();
    expect(body.ok).toBe(true);
    expect(body.rulePaused).toBe(false);
    expect(body.rulePauseReadable).toBe(true);
    expect(body.resultsStale).toBe(false);
    expect(body.buildMissed).toBe(false);
    expect(body.resultsBehindHours).toBe(0);
    expect(body.unscoredPlayedGames).toBe(0);
    expect(body.warnings).toEqual([]);
    expect(body.gauges.cfbdCallsRemaining).toBe(2500);
    expect(body.gauges.oddsCreditsRemaining).toBe(15000);
    expect(body.gauges.lastCloseCaptureEvents).toBe(40);
    // The seed wrote every timestamp as naive UTC; the route appends the Z.
    expect(body.gauges.lastCloseCaptureAt).toMatch(/Z$/);
    expect(body.gauges.lastGradeCompletedAt).toMatch(/Z$/);
    expect(body.lastFullGameCapture).toMatch(/Z$/);
    expect(typeof body.fullGameSnapshotsLast24h).toBe("number");
    expect(typeof body.fullGameGamesLast24h).toBe("number");
  });

  test("carries one dispatch gauge per cron job, each inside its last window", async ({
    request,
  }) => {
    const body = await (await request.get("/api/health")).json();
    const jobs = Object.keys(CRON_JOBS).sort();
    expect(Object.keys(body.gauges.lastDispatch).sort()).toEqual(jobs);
    for (const id of jobs) {
      const at = body.gauges.lastDispatch[id];
      expect(at, id).toMatch(/Z$/);
      expect(new Date(at).getTime(), id).toBeLessThan(Date.now());
    }
  });

  test("carries one health verdict per scheduled job, each ok with its run note", async ({
    request,
  }) => {
    const body = await (await request.get("/api/health")).json();
    const jobs = [...(HEALTH_JOBS as string[])].sort();
    expect(Object.keys(body.gauges.health).sort()).toEqual(jobs);
    for (const id of jobs) {
      const h = body.gauges.health[id];
      expect(Object.keys(h).sort(), id).toEqual(["at", "note", "verdict"]);
      expect(h.verdict, id).toBe("ok");
      expect(h.at, id).toMatch(/Z$/);
      expect(h.note, id).toMatch(/^run=\d+ event=schedule/);
    }
  });

  test("sends the security headers next.config.ts declares", async ({
    request,
  }) => {
    const res = await request.get("/api/health");
    const h = res.headers();
    expect(h["x-frame-options"]).toBe("DENY");
    expect(h["content-security-policy"]).toBe("frame-ancestors 'none'");
    expect(h["referrer-policy"]).toBe("strict-origin-when-cross-origin");
    expect(h["x-content-type-options"]).toBe("nosniff");
    expect(h["permissions-policy"]).toBe(
      "camera=(), microphone=(), geolocation=(), interest-cohort=()",
    );
  });
});

test.describe("GET /api/records", () => {
  test("streams the season as CSV with the documented columns", async ({
    request,
  }) => {
    const { season, games } = buildWeek(new Date());
    const res = await request.get(`/api/records?season=${season}`);
    expect(res.status()).toBe(200);
    expect(res.headers()["content-type"]).toContain("text/csv");
    expect(res.headers()["content-disposition"]).toContain(
      `beatvegas-records-${season}.csv`,
    );
    const csv = await res.text();
    const lines = csv.trim().split("\n");
    expect(lines[0]).toBe(
      "season,week,away,home,full_game_total,spread,line_1h,bv_line,bv_gap,bv_gap_z,under_score,rank,first_half_total_actual,outcome,scored_after_kickoff",
    );
    // One row per fixture game, every one scored before kickoff.
    expect(lines.length - 1).toBe(games.length);
    for (const line of lines.slice(1))
      expect(line.endsWith(",false")).toBe(true);
  });

  test("refuses a missing or malformed season", async ({ request }) => {
    expect((await request.get("/api/records")).status()).toBe(400);
    expect((await request.get("/api/records?season=abc")).status()).toBe(400);
    expect((await request.get("/api/records?season=1999")).status()).toBe(400);
  });
});
