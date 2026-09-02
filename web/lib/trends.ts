import { prisma } from "@/lib/prisma";

// Lightweight "trend search" with guardrails. These are NOT live edges — they're
// the factor-ranking harness's top candidates from the latest run, surfaced as
// HYPOTHESES for a pre-registered holdout. A season is ~14 weeks / a few hundred
// bets, so unfiltered "trends" are a multiple-testing trap: anything here must be
// pre-registered and confirmed out-of-sample (and opponent-adjusted, since low
// scoring is often a blowout = the spread, already priced) before it's bettable.

export type TrendRow = {
  factor: string;
  family: string | null;
  underPct: number | null;
  roi: number | null;
  corr: number | null;
  n: number | null;
};

// factor_scores is written by scripts/rank_factors.py and is NOT in the Prisma
// schema — degrade to "no ranking yet" when the table is absent.
export async function getTrends(limit = 8): Promise<TrendRow[]> {
  try {
    return await getTrendsUnsafe(limit);
  } catch (e) {
    console.warn("factor_scores unavailable:", (e as Error)?.message ?? e);
    return [];
  }
}

async function getTrendsUnsafe(limit: number): Promise<TrendRow[]> {
  const rows = await prisma.$queryRaw<
    {
      factor: string | null;
      family: string | null;
      top_under_pct: number | null;
      top_roi: number | null;
      corr: number | null;
      n: number | bigint | null;
    }[]
  >`
    SELECT factor, family, top_under_pct, top_roi, corr, n
    FROM factor_scores
    WHERE kind = 'univariate'
      AND leak_free = true
      AND (market = false OR market IS NULL)
      AND run_id = (SELECT run_id FROM factor_scores ORDER BY created_at DESC LIMIT 1)
    ORDER BY rank ASC
    LIMIT ${limit}
  `;
  return rows.map((r) => ({
    factor: r.factor ?? "?",
    family: r.family,
    underPct: r.top_under_pct,
    roi: r.top_roi,
    corr: r.corr,
    n: r.n === null ? null : Number(r.n),
  }));
}
