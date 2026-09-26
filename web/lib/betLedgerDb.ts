import { cache } from "react";
import { prisma } from "@/lib/prisma";
import { sortNewestFirst, type LedgerRow } from "@/lib/betLedger";
import type { PickReason, Verdict } from "@/lib/verdict";

// The loader behind lib/betLedger: ONE query over manual_picks joined to
// games for the kickoff and both teams' first-half points (a pick stores only
// the total). Kept apart from the pure module so a client component can use
// the grouping without pulling prisma into the browser (lib/prisma.test.ts
// lists this file as database-backed).

type Raw = {
  id: number | bigint;
  game_id: number | bigint | null;
  week: number | bigint | null;
  away_team: string | null;
  home_team: string | null;
  market: string | null;
  line: number | null;
  price: number | bigint | null;
  stake: number | null;
  note: string | null;
  book: string | null;
  placed_at: string | null;
  kickoff: string | null;
  is_paper: number | boolean | null;
  is_bonus?: number | boolean | null;
  graded: number | boolean | null;
  result: string | null;
  units: number | null;
  away_fh: number | bigint | null;
  home_fh: number | bigint | null;
  actual_first_half_total: number | bigint | null;
  model_line_at_pick: number | null;
  model_score_at_pick: number | bigint | null;
  closing_line: number | null;
  closing_price?: number | bigint | null;
  closing_captured_at?: string | null;
  price_provenance?: string | null;
  clv: number | null;
  clv_prob?: number | null;
  verdict_at_pick?: string | null;
  reason?: string | null;
  gap_at_pick?: number | null;
  hr_line_at_pick?: number | null;
  blocker?: string | null;
};

const truthy = (v: unknown) => v === true || Number(v) === 1;
const num = (v: number | bigint | null | undefined): number | null =>
  v === null || v === undefined ? null : Number(v);
const asVerdict = (v: string | null | undefined): Verdict | null =>
  v === "BET" || v === "WATCH" || v === "PASS" ? v : null;
const asReason = (v: string | null | undefined): PickReason | null =>
  v === "model_gap" || v === "price_edge" || v === "manual" ? v : null;
const isMissingColumn = (e: unknown): boolean =>
  /column .* does not exist|no such column/i.test(
    String((e as Error)?.message ?? e),
  );

/** A `timestamp without time zone` read as text ("2026-09-18 20:12:04.5")
 *  holds UTC: append the Z ourselves. Handing the bare value to a Date is how
 *  you get a 4-5 h shift (lib/boardHealth.ts makes the same move). */
export function isoFromNaive(s: string | null | undefined): string | null {
  if (!s) return null;
  const t = s.trim();
  const d = new Date(
    /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(t)
      ? `${t.replace(" ", "T")}Z`
      : t,
  );
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

async function selectRows(season: number): Promise<Raw[]> {
  try {
    return await prisma.$queryRaw<Raw[]>`
      SELECT mp.id, mp.game_id, mp.week, mp.away_team, mp.home_team, mp.market,
             mp.line, mp.price, mp.stake, mp.note, mp.book,
             mp.placed_at::text AS placed_at, g.start_date::text AS kickoff,
             mp.is_paper, mp.is_bonus, mp.graded, mp.result, mp.units,
             g.away_first_half_points AS away_fh, g.home_first_half_points AS home_fh,
             mp.actual_first_half_total, mp.model_line_at_pick, mp.model_score_at_pick,
             mp.closing_line, mp.closing_price,
             mp.closing_captured_at::text AS closing_captured_at,
             mp.price_provenance, mp.clv, mp.clv_prob,
             mp.verdict_at_pick, mp.reason, mp.gap_at_pick, mp.hr_line_at_pick, mp.blocker
      FROM manual_picks mp
      LEFT JOIN games g ON g.id = mp.game_id
      WHERE mp.season = ${season}
    `;
  } catch (e) {
    if (!isMissingColumn(e)) throw e;
  }
  // Before the 2026-09 money-path migrations: no closing price or provenance,
  // no closing_captured_at, no clv_prob. The ledger still renders.
  console.warn("manual_picks money-path columns missing — run the migration");
  return prisma.$queryRaw<Raw[]>`
    SELECT mp.id, mp.game_id, mp.week, mp.away_team, mp.home_team, mp.market,
           mp.line, mp.price, mp.stake, mp.note, mp.book,
           mp.placed_at::text AS placed_at, g.start_date::text AS kickoff,
           mp.is_paper, mp.graded, mp.result, mp.units,
           g.away_first_half_points AS away_fh, g.home_first_half_points AS home_fh,
           mp.actual_first_half_total, mp.model_line_at_pick, mp.model_score_at_pick,
           mp.closing_line, mp.clv
    FROM manual_picks mp
    LEFT JOIN games g ON g.id = mp.game_id
    WHERE mp.season = ${season}
  `;
}

async function getBetLedgerUncached(season: number): Promise<LedgerRow[]> {
  const raw = await selectRows(season);
  return sortNewestFirst(
    raw.map((r) => ({
      id: Number(r.id),
      gameId: num(r.game_id),
      week: num(r.week),
      away: r.away_team,
      home: r.home_team,
      market: r.market === "full" ? "full" : "1H",
      line: r.line,
      price: num(r.price),
      stake: r.stake,
      note: r.note,
      book: r.book,
      placedAt: isoFromNaive(r.placed_at),
      kickoff: isoFromNaive(r.kickoff),
      isPaper: truthy(r.is_paper),
      isBonus: truthy(r.is_bonus),
      graded: truthy(r.graded),
      result: truthy(r.graded) ? (r.result ?? "pending") : "pending",
      units: r.units,
      awayFh: num(r.away_fh),
      homeFh: num(r.home_fh),
      actualTotal: num(r.actual_first_half_total),
      modelLine: r.model_line_at_pick,
      modelScore: num(r.model_score_at_pick),
      closingLine: r.closing_line,
      closingPrice: num(r.closing_price),
      closingCapturedAt: isoFromNaive(r.closing_captured_at),
      priceProvenance: r.price_provenance ?? null,
      clv: r.clv,
      clvProb: r.clv_prob ?? null,
      verdictAtPick: asVerdict(r.verdict_at_pick),
      reason: asReason(r.reason),
      gapAtPick: r.gap_at_pick ?? null,
      hrLineAtPick: r.hr_line_at_pick ?? null,
      blocker: r.blocker ?? null,
    })),
  );
}

/** The season's rows, once per request (React cache, like loadPicks). */
export const getBetLedger = cache(getBetLedgerUncached);

/** Seasons with at least one pick, newest first. */
export async function getBetSeasons(): Promise<number[]> {
  const rows = await prisma.$queryRaw<{ season: number | bigint | null }[]>`
    SELECT DISTINCT season FROM manual_picks
    WHERE season IS NOT NULL ORDER BY season DESC
  `;
  return rows.map((r) => Number(r.season)).filter((s) => Number.isFinite(s));
}
