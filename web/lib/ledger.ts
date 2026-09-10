import { cache } from "react";
import { prisma } from "@/lib/prisma";
import { MARKET_LEDGER_1H, MARKET_LEDGER_FG, MODEL_VERSION } from "@/lib/model";
import {
  isPaperFirstHalf,
  isRealFirstHalf,
  loadPicks,
  type PickFull,
} from "@/lib/picks";
import { recordFrom, type Record3 } from "@/lib/record";

export type { Record3 } from "@/lib/record";

// The 3-way Ledger (market vs model vs you), season-scoped.
//   Market 1H   = results.model_version='market'    (under vs the real closing 1H line)
//   Market full = results.model_version='market_fg'
//   Model 1H    = results.model_version=MODEL_VERSION
//   You         = graded manual_picks: real-money first-half only; paper apart.

export type Ledger = {
  market: Record3 | null;
  marketFull: Record3 | null;
  model: Record3 | null;
  you: Record3 | null; // real-money 1H picks only
  paper: Record3 | null; // paper 1H picks — never merged into "you"
  picks: PickFull[];
};

export type ResRow = {
  model_version: string | null;
  under_hit: number | boolean | null;
  units: number | null;
  clv: number | null;
  week: number | bigint | null;
  actual_first_half_total: number | null;
  line_used: number | null;
};

const truthy = (v: unknown) => v === true || Number(v) === 1;

// results store under_hit as a bool, so a push looks like a loss there —
// recover it from actual == line so pushes don't deflate the under%. under_hit
// NULL means the row was never graded — it must not count as a loss.
export function recordFromResults(rows: ResRow[]): Record3 | null {
  const isPush = (r: ResRow) =>
    r.actual_first_half_total !== null &&
    r.line_used !== null &&
    Number(r.actual_first_half_total) === Number(r.line_used);
  const usable = rows.filter((r) => r.under_hit !== null || isPush(r));
  return recordFrom(
    usable.map((r) => ({
      result: isPush(r) ? "push" : truthy(r.under_hit) ? "under" : "over",
      units: r.units,
      clv: r.clv,
    })),
  );
}

/**
 * The season's graded results, ONCE per request — getLedger and
 * getWeeklyReview both want them and /results renders both. Same reasoning as
 * loadPicks in picks.ts.
 */
export const loadResults = cache(async function loadResults(
  season: number,
): Promise<ResRow[]> {
  return prisma.$queryRaw<ResRow[]>`
    SELECT r.model_version, r.under_hit, r.units, r.clv, g.week,
           r.actual_first_half_total, r.line_used
    FROM results r JOIN games g ON g.id = r.game_id
    WHERE g.season = ${season}
  `;
});

export async function getLedger(season: number): Promise<Ledger> {
  const [res, picks] = await Promise.all([
    loadResults(season),
    loadPicks(season),
  ]);
  const graded = picks.filter((p) => p.graded);
  return {
    market: recordFromResults(
      res.filter((r) => r.model_version === MARKET_LEDGER_1H),
    ),
    marketFull: recordFromResults(
      res.filter((r) => r.model_version === MARKET_LEDGER_FG),
    ),
    model: recordFromResults(
      res.filter((r) => r.model_version === MODEL_VERSION),
    ),
    you: recordFrom(graded.filter(isRealFirstHalf)),
    paper: recordFrom(graded.filter(isPaperFirstHalf)),
    picks,
  };
}
