import { unstable_cache } from "next/cache";
import { median } from "@/lib/format";
import { MARKET_LEDGER_1H, MODEL_VERSION } from "@/lib/model";
import { prisma } from "@/lib/prisma";
import { hasFbsSeason, isFbsGame } from "@/lib/proxy";
import { STRONG_GAP_PTS } from "@/lib/verdict";
import { Prisma } from "@prisma/client";

// Port of the "Research" tab in beatvegas/dashboard/app.py — the edge question
// (realized 1H/full-game ratio) + model_runs over time.

export type EdgeStats = { games: number; mean: number; median: number } | null;

// --- Gap vs CLV: do our biggest BV-vs-Vegas gaps earn positive closing-line
// value? The verdict on the whole "make our own number" method. Gap is in the
// under direction (bet line − BV line); CLV is reused from results (positive =
// the under closed at a softer number).
// --- BV-line calibration audit: the per-segment OOF residual table emitted by
// scripts/retrain.py into the latest model_runs row (metrics_json.bv_residual).
export type BvCalibration = {
  n: number;
  overall: number | null;
  segments: { label: string; n: number; meanResidual: number | null }[];
} | null;

async function getBvCalibrationUncached(): Promise<BvCalibration> {
  const rows = await prisma.$queryRaw<{ metrics_json: string | null }[]>`
    SELECT metrics_json FROM model_runs
    WHERE metrics_json IS NOT NULL
    ORDER BY created_at DESC LIMIT 5
  `;
  for (const row of rows) {
    if (!row.metrics_json) continue;
    let bv: Record<string, unknown> | undefined;
    try {
      bv = (JSON.parse(row.metrics_json) as Record<string, unknown>)
        .bv_residual as Record<string, unknown> | undefined;
    } catch {
      continue;
    }
    if (!bv || typeof bv !== "object") continue;
    const segments: {
      label: string;
      n: number;
      meanResidual: number | null;
    }[] = [];
    const pushGroup = (group: unknown) => {
      if (!group || typeof group !== "object") return;
      for (const [k, v] of Object.entries(group as Record<string, unknown>)) {
        const seg = v as { n?: number; mean_residual?: number | null };
        if (seg && typeof seg === "object" && "mean_residual" in seg) {
          segments.push({
            label: k,
            n: Number(seg.n ?? 0),
            meanResidual:
              seg.mean_residual === null || seg.mean_residual === undefined
                ? null
                : Number(seg.mean_residual),
          });
        }
      }
    };
    pushGroup(bv.by_era);
    pushGroup(bv.by_tempo);
    pushGroup(bv.by_dome);
    return {
      n: Number(bv.n ?? 0),
      overall:
        bv.overall_mean_residual === null ||
        bv.overall_mean_residual === undefined
          ? null
          : Number(bv.overall_mean_residual),
      segments,
    };
  }
  return null;
}

export const getBvCalibration = unstable_cache(
  getBvCalibrationUncached,
  ["bv-calibration"],
  { revalidate: 3600 },
);

// Realized 1H share of the full-game total. FBS-vs-FBS only (etl/fbs.py) —
// lower-division games run a higher share and would bias the read.
async function getEdgeStatsUncached(season?: number): Promise<EdgeStats> {
  const seasonFilter =
    season === undefined ? Prisma.empty : Prisma.sql`AND season = ${season}`;
  const rows = await prisma.$queryRaw<
    {
      season: number | bigint;
      home_team: string | null;
      away_team: string | null;
      first_half_total: number | bigint;
      full_game_total: number;
    }[]
  >`
    SELECT season, home_team, away_team, first_half_total, full_game_total
    FROM games
    WHERE first_half_total IS NOT NULL AND full_game_total > 0
      ${seasonFilter}
  `;
  const ratios = rows
    .filter(
      (r) =>
        !hasFbsSeason(Number(r.season)) ||
        isFbsGame(Number(r.season), r.home_team, r.away_team),
    )
    .map((r) => Number(r.first_half_total) / r.full_game_total);
  if (ratios.length === 0) return null;
  const mean = ratios.reduce((a, b) => a + b, 0) / ratios.length;
  return { games: ratios.length, mean, median: median(ratios) ?? mean };
}

export const getEdgeStats = unstable_cache(
  getEdgeStatsUncached,
  ["edge-stats"],
  { revalidate: 3600 },
);
