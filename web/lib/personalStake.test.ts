import { describe, expect, it } from "vitest";
import { personalStake, stakeRecord, type StakeRow } from "@/lib/personalStake";

const t = (o: Partial<StakeRow>): StakeRow => ({
  result: "under",
  units: 0.91,
  clv: -1,
  stake: 1,
  isPaper: false,
  isBonus: false,
  graded: true,
  priceProvenance: "logged",
  verdictAtPick: "BET",
  ...o,
});

// Audit 2026-10-17 (Tate): record over every cash ticket; money columns over
// price-verified cash only; bonus on its own line; Board-rule sub-line.
describe("personalStake", () => {
  const rows = [
    t({}), // verified BET win
    t({ result: "over", units: -1, clv: 1 }), // verified BET loss
    t({ priceProvenance: "unknown", units: 0.95 }), // unverified win
    t({ priceProvenance: null, result: "over", units: -1 }), // unverified loss
    t({ isBonus: true, units: 1.54, stake: 2, priceProvenance: "unknown" }), // bonus win
    t({ verdictAtPick: "WATCH", result: "over", units: -1 }), // off-rule loss
    t({ isPaper: true }), // paper never counts
    t({ graded: false, result: "pending", units: null }), // pending never counts
  ];
  const s = personalStake(rows);

  it("counts every graded cash ticket in the record, never bonus or paper", () => {
    expect(s.cash?.record).toBe("2-3");
  });
  it("counts money only from price-verified cash tickets", () => {
    expect(s.money?.record).toBe("1-2");
    expect(s.money?.units).toBe("-1.09");
    expect(s.unverified).toBe(2);
  });
  it("puts bonus bets on their own line with what they paid", () => {
    expect(s.bonus).toEqual({ n: 1, units: 1.54 });
  });
  it("reads the Board-rule tickets on their own", () => {
    expect(s.boardRule?.record).toBe("2-2");
  });
  it("builds one comparison row: cash record, verified money", () => {
    const r = stakeRecord(s)!;
    expect(r.record).toBe("2-3");
    expect(r.units).toBe("-1.09");
    expect(r.roi).toBe(s.money!.roi);
    expect(r.clv).toBe(s.money!.clv);
  });
  it("is empty with nothing graded", () => {
    expect(stakeRecord(personalStake([t({ graded: false })]))).toBeNull();
  });
});
