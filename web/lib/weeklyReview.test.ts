import { describe, expect, it } from "vitest";
import type { PickFull } from "./picks";
import { reasonRows, weekRows } from "./weeklyReview";

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
  clv: 0.5,
  graded: true,
  isPaper: false,
  verdictAtPick: "BET",
  reason: "model_gap",
  gapAtPick: 2.1,
  evAtPick: 0.01,
  hrLineAtPick: 24.5,
  ...o,
});

const picks: PickFull[] = [
  pick({ id: 1, week: 3 }),
  pick({ id: 2, week: 3, result: "over", units: -1, clv: -0.5 }),
  pick({ id: 3, week: 3, isPaper: true, reason: "price_edge" }),
  pick({
    id: 4,
    week: 4,
    graded: false,
    result: "pending",
    units: null,
    clv: null,
  }),
  pick({ id: 5, week: 4, reason: null, isPaper: true }), // logged before tracking
  pick({ id: 6, week: 4, reason: null, market: "full", isPaper: true }), // full game: context only
];

describe("weekRows", () => {
  it("one row per week with real vs paper 1H records, pending counted as a bet", () => {
    const rows = weekRows(picks);
    expect(rows.map((r) => r.week)).toEqual([3, 4]);
    expect(rows[0].real).toMatchObject({
      record: "1-1",
      units: "-0.09",
      roi: "-4.5%",
      clv: "+0.00",
    });
    expect(rows[0].paper).toMatchObject({ record: "1-0" });
    expect(rows[0].realBets).toBe(2);
    expect(rows[1]).toMatchObject({ real: null, realBets: 1, paperBets: 1 });
    expect(rows[1].paper).toMatchObject({ record: "1-0" });
  });
});

describe("reasonRows", () => {
  it("groups by stored reason, with untagged picks in their own row", () => {
    const rows = reasonRows(picks);
    expect(rows.map((r) => r.reason)).toEqual([
      "model_gap",
      "price_edge",
      "untagged",
    ]);
    expect(rows[0].realBets).toBe(3);
    expect(rows[0].real).toMatchObject({ record: "1-1" });
    expect(rows[1].paperBets).toBe(1);
    // untagged: one 1H paper pick counts; the full-game paper pick is context only
    expect(rows[2]).toMatchObject({ realBets: 0, paperBets: 1, real: null });
    expect(rows[2].paper).toMatchObject({ record: "1-0" });
  });
});
