import { cache } from "react";
import { prisma } from "@/lib/prisma";
import { recordFrom, type Record3 } from "@/lib/record";
import type { PickReason, Verdict } from "@/lib/verdict";

// The manual_picks READ layer: every logged pick with the model + verdict
// snapshot frozen at log time, and the running records. ONE picks query
// (loadPicks) feeds the season comparison and the arms' forward picks so they
// can never disagree. The write half (createPick, updatePick, deletePick, the
// slate check and the duplicate backstop) left on 2026-10-18 (final-2026 plan,
// D2): the site writes nothing; `beatvegas/picks.py::add_pick` is the one
// writer left, and tests/test_pick_columns_parity.py refuses any INSERT here.

export type PickFull = {
  id: number;
  gameId: number | null;
  week: number | null;
  away: string | null;
  home: string | null;
  market: "1H" | "full";
  line: number | null;
  stake: number | null;
  price: number | null;
  note: string | null;
  modelLine: number | null;
  result: string | null; // under/over/push or "pending"
  units: number | null;
  clv: number | null;
  graded: boolean;
  isPaper: boolean; // tracked with nothing at risk
  /** Bonus/free bet: the book funded the stake, so a loss books 0 units and a
   *  win books the profit only. A real ticket, but it risks no bankroll, so it
   *  does not use one of the week's five cap slots. */
  isBonus: boolean;
  // Decision snapshot (null on picks logged before the tracking columns existed).
  verdictAtPick: Verdict | null;
  reason: PickReason | null;
  gapAtPick: number | null;
  evAtPick: number | null;
  hrLineAtPick: number | null;
  /** Paper ledger: the gate that blocked a real bet (none | price | off_market | qb_out | cap); null on real picks. */
  blocker: string | null;
  /** 'logged' when the price was recorded at the bet (audit 2026-10-17). */
  priceProvenance: string | null;
  /** Why the pick is left out of every record ('alt_line'); null when it counts. */
  excludedReason: string | null;
};

const truthy = (v: unknown) => v === true || Number(v) === 1;
const num = (v: number | bigint | null | undefined): number | null =>
  v === null || v === undefined ? null : Number(v);

type RawPick = {
  id: number | bigint;
  game_id: number | bigint | null;
  week: number | bigint | null;
  away_team: string | null;
  home_team: string | null;
  market: string | null;
  line: number | null;
  stake: number | null;
  price: number | bigint | null;
  note: string | null;
  model_line_at_pick: number | null;
  result: string | null;
  units: number | null;
  clv: number | null;
  graded: number | boolean | null;
  is_paper: number | boolean | null;
  is_bonus?: number | boolean | null;
  verdict_at_pick?: string | null;
  reason?: string | null;
  gap_at_pick?: number | null;
  ev_at_pick?: number | null;
  hr_line_at_pick?: number | null;
  blocker?: string | null;
  price_provenance?: string | null;
  excluded_reason?: string | null;
};

const isMissingColumn = (e: unknown): boolean =>
  /column .* does not exist|no such column/i.test(
    String((e as Error)?.message ?? e),
  );

// The tracking columns arrive with the Python lane's migration; until it has
// run on a database, fall back to the legacy column list (snapshot fields null)
// and say so in the server log rather than 500 the whole Results page.
async function selectPicks(season: number): Promise<RawPick[]> {
  try {
    return await prisma.$queryRaw<RawPick[]>`
      SELECT id, game_id, week, away_team, home_team, market, line, stake, price,
             note, model_line_at_pick, result, units, clv,
             graded, is_paper, is_bonus, verdict_at_pick, reason, gap_at_pick,
             ev_at_pick, hr_line_at_pick, blocker, price_provenance, excluded_reason
      FROM manual_picks WHERE season = ${season}
    `;
  } catch (e) {
    if (!isMissingColumn(e)) throw e;
  }
  // `blocker` (2026-09-07) arrives with the Python lane's migration; keep the
  // rest of the snapshot when only it is missing.
  try {
    return await prisma.$queryRaw<RawPick[]>`
      SELECT id, game_id, week, away_team, home_team, market, line, stake, price,
             note, model_line_at_pick, result, units, clv,
             graded, is_paper, verdict_at_pick, reason, gap_at_pick, ev_at_pick,
             hr_line_at_pick
      FROM manual_picks WHERE season = ${season}
    `;
  } catch (e) {
    if (!isMissingColumn(e)) throw e;
    console.warn("manual_picks tracking columns missing — run the migration");
    return prisma.$queryRaw<RawPick[]>`
      SELECT id, game_id, week, away_team, home_team, market, line, stake, price,
             note, model_line_at_pick, result, units, clv,
             graded, is_paper
      FROM manual_picks WHERE season = ${season}
    `;
  }
}

const asVerdict = (v: string | null | undefined): Verdict | null =>
  v === "BET" || v === "WATCH" || v === "PASS" ? v : null;
const asReason = (v: string | null | undefined): PickReason | null =>
  v === "model_gap" || v === "price_edge" || v === "manual" ? v : null;

/** Every pick for the season, pending first then newest first. */
async function loadPicksUncached(season: number): Promise<PickFull[]> {
  const rows = await selectPicks(season);
  const picks: PickFull[] = rows.map((r) => ({
    id: Number(r.id),
    gameId: num(r.game_id),
    week: num(r.week),
    away: r.away_team,
    home: r.home_team,
    market: r.market === "full" ? "full" : "1H", // null (legacy) -> 1H
    line: r.line,
    stake: r.stake,
    price: num(r.price),
    note: r.note,
    modelLine: r.model_line_at_pick,
    result: truthy(r.graded) ? r.result : "pending",
    units: r.units,
    clv: r.clv,
    graded: truthy(r.graded),
    isPaper: truthy(r.is_paper),
    isBonus: truthy(r.is_bonus),
    verdictAtPick: asVerdict(r.verdict_at_pick),
    reason: asReason(r.reason),
    gapAtPick: r.gap_at_pick ?? null,
    evAtPick: r.ev_at_pick ?? null,
    hrLineAtPick: r.hr_line_at_pick ?? null,
    blocker: r.blocker ?? null,
    priceProvenance: r.price_provenance ?? null,
    excludedReason: r.excluded_reason ?? null,
  }));
  picks.sort((a, b) => Number(a.graded) - Number(b.graded) || b.id - a.id);
  return picks;
}

/** The frozen real-money tickets (first half, the only market that was bet). */
export const isRealFirstHalf = (p: PickFull): boolean =>
  !p.isPaper && p.market === "1H";
export const isPaperFirstHalf = (p: PickFull): boolean =>
  p.isPaper && p.market === "1H";

export type PickRecords = {
  picks: PickFull[];
  /** Real-money first-half picks only. */
  record: Record3 | null;
  /** Paper first-half picks, kept apart so they never flatter the real ledger. */
  paperRecord: Record3 | null;
};

/**
 * The season's picks, ONCE per request.
 *
 * picks.ts already said "ONE picks query feeds the ledger, the weekly review
 * and the board" — but /results had drifted to four independent callers, each
 * running the full manual_picks season scan, on a force-dynamic page with no
 * caching. React's cache() dedupes within a single render pass, so the
 * comment becomes true again without any caller having to know about the others
 * or thread a value through.
 *
 * Per-request, NOT across requests: a freshly logged pick still shows up on the
 * next render.
 */
export const loadPicks = cache(loadPicksUncached);

export async function getPicks(season: number): Promise<PickRecords> {
  const picks = await loadPicks(season);
  const graded = picks.filter((p) => p.graded);
  return {
    picks,
    record: recordFrom(graded.filter(isRealFirstHalf)),
    paperRecord: recordFrom(graded.filter(isPaperFirstHalf)),
  };
}
