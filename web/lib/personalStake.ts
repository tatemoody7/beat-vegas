import { recordFrom, type Gradable, type Record3 } from "@/lib/record";
import type { Verdict } from "@/lib/verdict";

// The personal stake read honestly (fact-check audit 2026-10-17, Tate's calls):
// the record counts every graded cash ticket; units, ROI, line move and value
// vs the close count only tickets whose price was LOGGED at the time
// (`price_provenance = 'logged'`), never a reconstructed or market price; bonus
// bets sit on their own line so a promotion's payout never reads as skill; and
// the tickets that followed the Board's rule (BET at the log) get a sub-line.
// Pure: the client ledger and the server comparison table both call it.

export type StakeRow = Gradable & {
  isPaper: boolean;
  isBonus: boolean;
  graded: boolean;
  priceProvenance: string | null;
  verdictAtPick: Verdict | null;
};

/** A price recorded at the time of the bet; nothing else counts as verified. */
export const isPriceVerified = (r: { priceProvenance: string | null }) =>
  r.priceProvenance === "logged";

export type StakeSplit = {
  /** Every graded cash ticket: the record and the hit rate. */
  cash: Record3 | null;
  /** Graded cash tickets with a verified price: units, ROI, line move. */
  money: Record3 | null;
  /** Graded cash tickets left out of `money`. */
  unverified: number;
  /** Graded bonus tickets and what they actually paid. */
  bonus: { n: number; units: number };
  /** Graded cash tickets logged on a BET verdict. */
  boardRule: Record3 | null;
};

export function personalStake<R extends StakeRow>(rows: R[]): StakeSplit {
  const graded = rows.filter((r) => !r.isPaper && r.graded);
  const cash = graded.filter((r) => !r.isBonus);
  const verified = cash.filter(isPriceVerified);
  const bonus = graded.filter((r) => r.isBonus);
  return {
    cash: recordFrom(cash),
    money: recordFrom(verified),
    unverified: cash.length - verified.length,
    bonus: {
      n: bonus.length,
      units: bonus.reduce((a, r) => a + (r.units ?? 0), 0),
    },
    boardRule: recordFrom(cash.filter((r) => r.verdictAtPick === "BET")),
  };
}

/**
 * One row for the season comparison table: the record and its interval from
 * every cash ticket, the money columns (units, ROI, line value) from the
 * price-verified ones only.
 */
export function stakeRecord(s: StakeSplit): Record3 | null {
  if (s.cash === null) return null;
  const m = s.money;
  return {
    ...s.cash,
    units: m?.units ?? "—",
    roi: m?.roi ?? "—",
    clv: m?.clv ?? "—",
    unitsNum: m?.unitsNum ?? 0,
    roiNum: m?.roiNum ?? null,
  };
}
