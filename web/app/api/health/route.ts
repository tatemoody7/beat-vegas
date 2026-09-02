import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

export const dynamic = "force-dynamic";

// GET /api/health — capture-freshness metadata for the Sunday ops routine
// (cfb-sunday-ops checks lastFullGameCapture over HTTPS; Neon:5432 is blocked on campus).
// Exposes only aggregate timestamps/counts — no lines, picks, or edges — so
// it is exempt from the password gate in middleware.ts.
export async function GET() {
  try {
    const rows = await prisma.$queryRaw<
      { last_fg_capture: Date | null; fg_last_24h: bigint }[]
    >`
      SELECT MAX(captured_at) AS last_fg_capture,
             COUNT(*) FILTER (WHERE captured_at > NOW() - INTERVAL '24 hours')
               AS fg_last_24h
      FROM odds_snapshots
      WHERE market = 'full_game_total'`;
    const r = rows[0];
    return NextResponse.json({
      ok: true,
      lastFullGameCapture: r?.last_fg_capture?.toISOString() ?? null,
      fullGameSnapshotsLast24h: Number(r?.fg_last_24h ?? 0),
    });
  } catch {
    return NextResponse.json({ ok: false }, { status: 500 });
  }
}
