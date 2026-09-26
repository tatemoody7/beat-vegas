import { displayLineValue } from "@/lib/clvDirection";
import { csvCell } from "@/lib/format";
import { recordFrom, type Record3 } from "@/lib/record";
import type { PickReason, Verdict } from "@/lib/verdict";

// Every bet we have placed, for the Track record page: the real-money ledger
// and the paper ledger, one row per pick, with everything a reader needs to
// check the row against the book and the score -- when it was posted, the
// kickoff it was posted before, the price, the closing line and both teams'
// first-half points. This module is PURE (the loader is lib/betLedgerDb) so
// the client component can import the grouping and the CSV shape without
// dragging prisma into the browser bundle. Dates are UTC ISO strings for the
// same reason: they cross the server/client boundary as props.

export type LedgerRow = {
  id: number;
  gameId: number | null;
  week: number | null;
  away: string | null;
  home: string | null;
  market: "1H" | "full";
  line: number | null;
  price: number | null;
  stake: number | null;
  note: string | null;
  book: string | null;
  /** UTC ISO; null on a legacy row with no placed_at. */
  placedAt: string | null;
  /** UTC ISO kickoff from `games`; null when the game row is missing. */
  kickoff: string | null;
  isPaper: boolean;
  isBonus: boolean;
  graded: boolean;
  /** under / over / push, or "pending" until graded. */
  result: string;
  units: number | null;
  awayFh: number | null;
  homeFh: number | null;
  actualTotal: number | null;
  modelLine: number | null;
  modelScore: number | null;
  closingLine: number | null;
  closingPrice: number | null;
  closingCapturedAt: string | null;
  priceProvenance: string | null;
  /** Stored `closing - bet`: NEGATIVE is the good direction for an under. */
  clv: number | null;
  clvProb: number | null;
  verdictAtPick: Verdict | null;
  reason: PickReason | null;
  gapAtPick: number | null;
  hrLineAtPick: number | null;
  blocker: string | null;
};

/** Newest first: week, then when it was posted, then id. */
export function sortNewestFirst(rows: LedgerRow[]): LedgerRow[] {
  return [...rows].sort(
    (a, b) =>
      (b.week ?? -1) - (a.week ?? -1) ||
      (b.placedAt ?? "").localeCompare(a.placedAt ?? "") ||
      b.id - a.id,
  );
}

export type LedgerView = "real" | "paper" | "all";

export function rowsFor(rows: LedgerRow[], view: LedgerView): LedgerRow[] {
  if (view === "all") return rows;
  return rows.filter((r) => (view === "paper" ? r.isPaper : !r.isPaper));
}

export type RunningRow = LedgerRow & {
  /** Cumulative units through this bet, oldest first; null until it grades. */
  runningUnits: number | null;
};

/**
 * Stamp each row with the ledger's cumulative units after it, walking oldest
 * to newest so the last graded row carries the ledger's total. A pending row
 * carries null (nothing has been added yet). Bonus rows count like any other:
 * their units are the profit they paid, floored at 0 on a loss upstream.
 * Returns the rows newest first, the order the page shows them.
 */
export function withRunningUnits(rows: LedgerRow[]): RunningRow[] {
  const oldestFirst = sortNewestFirst(rows).reverse();
  let total = 0;
  const stamped = oldestFirst.map((r) => {
    if (!r.graded || r.units === null) return { ...r, runningUnits: null };
    total = Math.round((total + r.units) * 100) / 100;
    return { ...r, runningUnits: total };
  });
  return stamped.reverse();
}

export type WeekGroup = {
  week: number | null;
  rows: RunningRow[];
  /** recordFrom over the week's graded rows; null when nothing has graded. */
  record: Record3 | null;
  pending: number;
};

/** Rows grouped by week, newest week first, each with its own record. */
export function groupByWeek(rows: RunningRow[]): WeekGroup[] {
  const groups = new Map<number | null, RunningRow[]>();
  for (const r of rows) {
    const list = groups.get(r.week) ?? [];
    list.push(r);
    groups.set(r.week, list);
  }
  return [...groups.entries()]
    .sort(([a], [b]) => (b ?? -1) - (a ?? -1))
    .map(([week, list]) => ({
      week,
      rows: list,
      record: recordFrom(list.filter((r) => r.graded)),
      pending: list.filter((r) => !r.graded).length,
    }));
}

export type LedgerSummary = {
  record: Record3 | null;
  /** Bets logged, pending or graded. */
  bets: number;
  /** Graded rows with a close, and how many of those the line moved toward us. */
  closes: number;
  movedOurWay: number;
};

/** The strip above the list: the same recordFrom the scoreboard uses. */
export function ledgerSummary(rows: LedgerRow[]): LedgerSummary {
  const graded = rows.filter((r) => r.graded);
  const withClose = graded.filter((r) => r.clv !== null);
  return {
    record: recordFrom(graded),
    bets: rows.length,
    closes: withClose.length,
    movedOurWay: withClose.filter((r) => (displayLineValue(r.clv) ?? 0) > 0)
      .length,
  };
}

/** Whole hours from posting to kickoff; null when either is unknown, and
 *  negative when the pick was logged after kickoff (which the API refuses,
 *  so a negative number is itself a finding). */
export function hoursBeforeKickoff(r: LedgerRow): number | null {
  if (!r.placedAt || !r.kickoff) return null;
  const ms = Date.parse(r.kickoff) - Date.parse(r.placedAt);
  return Number.isNaN(ms) ? null : Math.round(ms / 3_600_000) || 0;
}

// --- CSV --------------------------------------------------------------------

export const BETS_CSV_HEADER = [
  "season",
  "week",
  "placed_at_utc",
  "kickoff_utc",
  "ledger",
  "away",
  "home",
  "market",
  "bet",
  "line",
  "price",
  "stake",
  "bonus",
  "book",
  "price_provenance",
  "verdict_at_pick",
  "reason",
  "gap_at_pick",
  "model_line_at_pick",
  "away_1h",
  "home_1h",
  "first_half_total",
  "result",
  "units",
  "closing_line",
  "closing_price",
  "clv_points_stored",
  "line_value_displayed",
  "clv_prob",
  "note",
].join(",");

/** One line per pick, newest first, with the stored clv AND its displayed
 *  negation side by side so nobody has to remember the sign convention. */
export function betsToCsv(season: number, rows: LedgerRow[]): string {
  const body = sortNewestFirst(rows).map((r) =>
    [
      season,
      r.week,
      r.placedAt,
      r.kickoff,
      r.isPaper ? "paper" : "real",
      r.away,
      r.home,
      r.market,
      "under",
      r.line,
      r.price,
      r.stake,
      r.isBonus,
      r.book,
      r.priceProvenance,
      r.verdictAtPick,
      r.reason,
      r.gapAtPick,
      r.modelLine,
      r.awayFh,
      r.homeFh,
      r.actualTotal,
      r.graded ? r.result : "pending",
      r.units,
      r.closingLine,
      r.closingPrice,
      r.clv,
      displayLineValue(r.clv),
      r.clvProb,
      r.note,
    ]
      .map(csvCell)
      .join(","),
  );
  return [BETS_CSV_HEADER, ...body].join("\n") + "\n";
}
