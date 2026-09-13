import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { getGradeHealth, staleness } from "@/lib/gradeHealth";
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
    return NextResponse.json({
      ok: true,
      lastFullGameCapture: r?.last_fg_capture?.toISOString() ?? null,
      resultsStale: grading.stale,
      resultsBehindHours: grading.stale ? grading.behindHours : 0,
      unscoredPlayedGames: grading.stale ? grading.unscored : 0,
      lastGradedAt: grading.stale
        ? (grading.lastGradedAt?.toISOString() ?? null)
        : undefined,
      // Rows vs distinct games: many books per game inflate the row count, so
      // the games figure is the one that says "the slate was captured".
      fullGameSnapshotsLast24h: Number(r?.fg_last_24h ?? 0),
      fullGameGamesLast24h: Number(r?.fg_games_last_24h ?? 0),
    });
  } catch {
    return NextResponse.json({ ok: false }, { status: 500 });
  }
}
