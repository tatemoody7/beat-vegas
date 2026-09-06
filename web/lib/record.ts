import { signed } from "@/lib/format";

// The one W-L-P record shape used by the ledger, the weekly review, My Picks,
// the bankroll strip and the Results tables. Built by `recordFrom` — the only
// place the arithmetic lives, so "You", "Market" and "Model" can never drift.

export type Record3 = {
  /** Graded rows (wins + losses + pushes). */
  n: number;
  record: string; // e.g. "6-6" or "5-4-1P"
  hit: string; // "50.0%" or "—"
  units: string; // signed, "+0.91" / "-0.55"
  /** Units won ÷ units staked over graded rows, as a signed percent; "—" when nothing was staked. */
  roi: string;
  clv: string; // signed mean CLV, or "—"
  unitsNum: number;
  roiNum: number | null;
};

export type Gradable = {
  /** under / over / push (anything else = not decided). */
  result: string | null;
  units: number | null;
  clv: number | null;
  /** Units risked; null/0 for paper and for results-ledger rows (flat 1u). */
  stake?: number | null;
};

/** Record over already-graded rows. Null when there is nothing graded. */
export function recordFrom(rows: Gradable[]): Record3 | null {
  if (rows.length === 0) return null;
  const wins = rows.filter((r) => r.result === "under").length;
  const pushes = rows.filter((r) => r.result === "push").length;
  const decided = rows.length - pushes;
  const unitsSum = rows.reduce((a, r) => a + (r.units ?? 0), 0);
  // Results-ledger rows carry no stake: they are flat 1-unit bets by construction.
  const staked = rows.reduce(
    (a, r) => a + (r.stake === undefined ? 1 : (r.stake ?? 0)),
    0,
  );
  const clvs = rows.filter((r) => r.clv !== null).map((r) => r.clv as number);
  const roiNum = staked > 0 ? (100 * unitsSum) / staked : null;
  return {
    n: rows.length,
    record: `${wins}-${decided - wins}${pushes ? `-${pushes}P` : ""}`,
    hit: decided ? `${((100 * wins) / decided).toFixed(1)}%` : "—",
    units: signed(unitsSum),
    roi: roiNum === null ? "—" : `${signed(roiNum, 1)}%`,
    clv: clvs.length
      ? signed(clvs.reduce((a, b) => a + b, 0) / clvs.length)
      : "—",
    unitsNum: unitsSum,
    roiNum,
  };
}

/**
 * The same record shape from aggregate counts (the post-mortem buckets store
 * W-L-P and units, not rows). Pushes count as staked; no CLV at bucket level.
 */
export function recordFromCounts(
  unders: number,
  overs: number,
  pushes: number,
  units: number,
): Record3 | null {
  const n = unders + overs + pushes;
  if (n === 0) return null;
  const decided = unders + overs;
  const roiNum = (100 * units) / n;
  return {
    n,
    record: `${unders}-${overs}${pushes ? `-${pushes}P` : ""}`,
    hit: decided ? `${((100 * unders) / decided).toFixed(1)}%` : "—",
    units: signed(units),
    roi: `${signed(roiNum, 1)}%`,
    clv: "—",
    unitsNum: units,
    roiNum,
  };
}
