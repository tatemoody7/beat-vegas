import { signed } from "@/lib/format";

// The one W-L-P record shape used by the ledger, the weekly review, My Picks,
// the bankroll strip and the Results tables. Built by `recordFrom` — the only
// place the arithmetic lives, so "You", "Market" and "Model" can never drift.

export type Record3 = {
  /** Graded rows (wins + losses + pushes). */
  n: number;
  /** Wins (unders) and decided rows (wins + losses); pushes are neither. */
  wins: number;
  decided: number;
  /** 95% Wilson interval on the hit rate over decided rows; null when nothing is decided. */
  hitLo: number | null;
  hitHi: number | null;
  record: string; // e.g. "6-6" or "5-4-1P"
  hit: string; // "50.0%" or "—"
  units: string; // signed, "+0.91" / "-0.55"
  /** Units won ÷ units staked over graded rows, as a signed percent; "—" when nothing was staked. */
  roi: string;
  /** Mean points the line came TOWARD us, signed; "+0.58" is good. "—" when no bet has a close. */
  clv: string;
  unitsNum: number;
  roiNum: number | null;
};

export type Gradable = {
  /** under / over / push (anything else = not decided). */
  result: string | null;
  /** Null on an unpriced pick (no Hard Rock close captured): counts in W-L and
   *  hit rate, but neither its units nor its stake enter units/ROI. */
  units: number | null;
  clv: number | null;
  /** Units risked; null/0 for paper and for results-ledger rows (flat 1u). */
  stake?: number | null;
};

/**
 * Wilson score interval on a hit rate — a port of beatvegas/postmortem.py::wilson_ci,
 * pinned to its digits in lib/record.test.ts. Correct in the tails where the normal
 * approximation is not, which matters at the n this ledger has. Null at n = 0.
 */
export function wilson(
  hits: number,
  n: number,
  z = 1.96,
): { lo: number; hi: number } | null {
  if (n <= 0) return null;
  const p = hits / n;
  const denom = 1 + (z * z) / n;
  const centre = (p + (z * z) / (2 * n)) / denom;
  const half =
    (z * Math.sqrt((p * (1 - p)) / n + (z * z) / (4 * n * n))) / denom;
  return { lo: Math.max(0, centre - half), hi: Math.min(1, centre + half) };
}

/** Record over already-graded rows. Null when there is nothing graded. */
export function recordFrom(rows: Gradable[]): Record3 | null {
  if (rows.length === 0) return null;
  const wins = rows.filter((r) => r.result === "under").length;
  const pushes = rows.filter((r) => r.result === "push").length;
  const decided = rows.length - pushes;
  // Unpriced rows (units null) are excluded from BOTH sums so ROI stays
  // units won over units actually priced and staked.
  const priced = rows.filter((r) => r.units !== null);
  const unitsSum = priced.reduce((a, r) => a + (r.units as number), 0);
  // Results-ledger rows carry no stake: they are flat 1-unit bets by construction.
  const staked = priced.reduce(
    (a, r) => a + (r.stake === undefined ? 1 : (r.stake ?? 0)),
    0,
  );
  // Stored clv is closing - bet. Every bet is an UNDER, so a line that FELL
  // after the bet is the good one, and the raw mean therefore reads backwards
  // to anyone looking at a stat called "Line value". Negate it here so the
  // displayed figure is points the market came TOWARD us: +0.6 is good.
  // See web/lib/decision-quality.ts for the full note; lib/record.test.ts pins
  // the direction.
  const clvs = rows
    .filter((r) => r.clv !== null)
    .map((r) => -(r.clv as number));
  const roiNum = staked > 0 ? (100 * unitsSum) / staked : null;
  const ci = wilson(wins, decided);
  return {
    n: rows.length,
    wins,
    decided,
    hitLo: ci?.lo ?? null,
    hitHi: ci?.hi ?? null,
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
  const ci = wilson(unders, decided);
  return {
    n,
    wins: unders,
    decided,
    hitLo: ci?.lo ?? null,
    hitHi: ci?.hi ?? null,
    record: `${unders}-${overs}${pushes ? `-${pushes}P` : ""}`,
    hit: decided ? `${((100 * unders) / decided).toFixed(1)}%` : "—",
    units: signed(units),
    roi: `${signed(roiNum, 1)}%`,
    clv: "—",
    unitsNum: units,
    roiNum,
  };
}
