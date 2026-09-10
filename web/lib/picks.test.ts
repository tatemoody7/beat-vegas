import { describe, expect, it } from "vitest";
import {
  isDuplicatePick,
  isPaperFirstHalf,
  isRealFirstHalf,
  type PickFull,
} from "./picks";
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

// The uq_manual_pick_per_ledger backstop only reaches the user as a 409 if this
// classifier recognises the driver's message. Get it wrong and a double-click
// becomes a bare 500 on the one screen where money is logged -- so pin the
// exact strings Postgres and the SQLite dev/test path actually produce.
describe("a unique-constraint violation is read as a duplicate, not a crash", () => {
  it("recognises Postgres", () => {
    expect(
      isDuplicatePick(
        new Error(
          'duplicate key value violates unique constraint "uq_manual_pick_per_ledger"',
        ),
      ),
    ).toBe(true);
  });

  it("recognises SQLite (local dev and the sim DB)", () => {
    expect(
      isDuplicatePick(
        new Error(
          "UNIQUE constraint failed: index 'uq_manual_pick_per_ledger'",
        ),
      ),
    ).toBe(true);
  });

  it("does not swallow an unrelated failure as a duplicate", () => {
    // These must reach the 503 branch, not be reported as "already logged".
    expect(isDuplicatePick(new Error("connection terminated"))).toBe(false);
    expect(isDuplicatePick(new Error('column "is_bonus" does not exist'))).toBe(
      false,
    );
    expect(isDuplicatePick(undefined)).toBe(false);
  });
});
