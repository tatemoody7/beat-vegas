import { describe, expect, it } from "vitest";
import { isPaperFirstHalf, isRealFirstHalf, type PickFull } from "./picks";
import { recordFrom } from "./record";

const pick = (o: Partial<PickFull>): PickFull => ({
  id: 1,
  gameId: 1,
  week: 3,
  away: "A",
  home: "B",
  market: "1H",
  line: 24.5,
  stake: 1,
  price: -110,
  note: null,
  modelScore: null,
  modelLine: null,
  result: "under",
  units: 0.91,
  clv: null,
  graded: true,
  isPaper: false,
  isBonus: false,
  verdictAtPick: null,
  reason: null,
  gapAtPick: null,
  evAtPick: null,
  hrLineAtPick: null,
  blocker: null,
  ...o,
});

describe("the real record counts first-half real-money picks only", () => {
  const picks = [
    pick({ id: 1 }), // real 1H win
    pick({ id: 2, market: "full", isPaper: true, units: -1 }), // paper full: out of both
    pick({ id: 3, isPaper: true, units: 0.91 }), // paper 1H
    pick({ id: 4, market: "full", units: 0.91 }), // legacy real full: excluded
  ];
  it("filters", () => {
    expect(picks.filter(isRealFirstHalf).map((p) => p.id)).toEqual([1]);
    expect(picks.filter(isPaperFirstHalf).map((p) => p.id)).toEqual([3]);
  });
  it("records", () => {
    expect(recordFrom(picks.filter(isRealFirstHalf))).toMatchObject({
      record: "1-0",
      units: "+0.91",
      roi: "+91.0%",
    });
    expect(recordFrom(picks.filter(isPaperFirstHalf))).toMatchObject({
      record: "1-0",
      units: "+0.91",
    });
  });
});
