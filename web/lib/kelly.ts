// Fractional-Kelly stake suggestion for an UNDER bet (research-only, advisory).
// The edge is the same one /line-check surfaces: the market's no-vig fair-under
// vs the price you'd take. We work in UNITS (1 unit = 1% of bankroll by default),
// so the suggestion is bankroll-relative and needs no bankroll input.

import { americanToDecimal } from "@/lib/devig";

// Full-Kelly fraction of bankroll for taking the under at `offeredPrice` given a
// fair win probability. 0 when there is no edge (never bet a -EV number).
export function kellyFraction(
  fairUnderProb: number,
  offeredPrice: number,
): number {
  const b = americanToDecimal(offeredPrice) - 1; // net decimal payout
  if (b <= 0) return 0;
  const p = fairUnderProb;
  const f = (b * p - (1 - p)) / b;
  return f > 0 ? f : 0;
}

export type KellyOpts = {
  fraction?: number; // fraction of full Kelly (default quarter-Kelly)
  unitPctOfBankroll?: number; // what 1 unit means (default 1% of bankroll)
  capUnits?: number; // hard ceiling, since edge estimates are uncertain
};

// Suggested stake in UNITS. Quarter-Kelly by default, capped — overbetting a
// misestimated edge is ruinous (Doc 2). Returns 0 when there is no edge.
export function suggestedUnits(
  fairUnderProb: number,
  offeredPrice: number,
  opts: KellyOpts = {},
): number {
  const { fraction = 0.25, unitPctOfBankroll = 0.01, capUnits = 3 } = opts;
  const f = kellyFraction(fairUnderProb, offeredPrice) * fraction;
  if (f <= 0) return 0;
  return Math.min(f / unitPctOfBankroll, capUnits);
}
