import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import {
  buildStatus,
  getBuildHealth,
  getGauges,
  getGradeHealth,
  opsWarnings,
  staleness,
} from "@/lib/boardHealth";
import { getRulePause } from "@/lib/rulePause";
import { currentCfbSeason } from "@/lib/season";

export const dynamic = "force-dynamic";

// GET /api/health — capture-freshness metadata for the Sunday ops routine
// (cfb-sunday-ops checks lastFullGameCapture over HTTPS; Neon:5432 is blocked on campus).
// Since 2026-09-13 it also reports GRADING freshness: grade.yml died for two days
// and the only signal was a failed-run email nobody read.
// Exposes only aggregate timestamps/counts — no lines, picks, or edges — so
// it is exempt from the password gate in middleware.ts.
export async function GET() {
  try {
    const rows = await prisma.$queryRaw<
      {
        last_fg_capture: Date | null;
        fg_last_24h: bigint;
        fg_games_last_24h: bigint;
      }[]
    >`
      SELECT MAX(captured_at) AS last_fg_capture,
             COUNT(*) FILTER (WHERE captured_at > NOW() - INTERVAL '24 hours')
               AS fg_last_24h,
             COUNT(DISTINCT game_id)
               FILTER (WHERE captured_at > NOW() - INTERVAL '24 hours')
               AS fg_games_last_24h
      FROM odds_snapshots
      WHERE market = 'full_game_total'`;
    const r = rows[0];
    const grading = staleness(await getGradeHealth(currentCfbSeason()));
    const build = buildStatus(await getBuildHealth());
    const pause = await getRulePause();
    const gauges = await getGauges();
    const warnings = opsWarnings(gauges);
    return NextResponse.json({
      ok: true,
      // The real-money pause (docs/STOPPING_RULE.md): thrown, or unreadable —
      // both mean real money is refused right now.
      rulePaused: pause.paused === true,
      rulePauseReadable: pause.paused !== "unreadable",
      lastFullGameCapture: r?.last_fg_capture?.toISOString() ?? null,
      resultsStale: grading.stale,
      buildMissed: build.missed,
      lastBuiltAt: build.missed
        ? (build.lastBuiltAt?.toISOString() ?? null)
        : undefined,
      resultsBehindHours: grading.stale ? grading.behindHours : 0,
      unscoredPlayedGames: grading.stale ? grading.unscored : 0,
      lastGradedAt: grading.stale
        ? (grading.lastGradedAt?.toISOString() ?? null)
        : undefined,
      // Rows vs distinct games: many books per game inflate the row count, so
      // the games figure is the one that says "the slate was captured".
      fullGameSnapshotsLast24h: Number(r?.fg_last_24h ?? 0),
      fullGameGamesLast24h: Number(r?.fg_games_last_24h ?? 0),
      // Operational gauges (beatvegas/ops.py): the API budgets, the last
      // pre-kickoff close capture, the last completed grading run. `warnings`
      // is what the board's banner shows.
      gauges: {
        cfbdCallsRemaining: gauges.cfbdCallsRemaining,
        oddsCreditsRemaining: gauges.oddsCreditsRemaining,
        lastCloseCaptureAt: gauges.lastCloseCaptureAt?.toISOString() ?? null,
        lastCloseCaptureEvents: gauges.lastCloseCaptureEvents,
        lastGradeCompletedAt:
          gauges.lastGradeCompletedAt?.toISOString() ?? null,
        // Per cron job: the last Vercel tick that acted inside its window.
        lastDispatch: Object.fromEntries(
          Object.entries(gauges.lastDispatch).map(([id, d]) => [
            id,
            d?.toISOString() ?? null,
          ]),
        ),
        // Per scheduled job: the last health-contract verdict the job wrote
        // about its own run (docs/HEALTH.md), with the note naming the run
        // and every missed check.
        health: Object.fromEntries(
          Object.entries(gauges.health).map(([id, h]) => [
            id,
            {
              verdict: h.verdict,
              at: h.at?.toISOString() ?? null,
              note: h.note,
            },
          ]),
        ),
      },
      warnings: warnings.map((w) => w.text),
    });
  } catch {
    return NextResponse.json({ ok: false }, { status: 500 });
  }
}
