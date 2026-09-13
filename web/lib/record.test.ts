import { describe, expect, it } from "vitest";
import { recordFrom, recordFromCounts } from "./record";

describe("recordFrom", () => {
  it("returns null with nothing graded", () => {
    expect(recordFrom([])).toBeNull();
  });

  it("counts wins, losses and pushes, sums units, averages CLV, and reports ROI on units staked", () => {
    const rec = recordFrom([
      { result: "under", units: 0.91, clv: 1.0, stake: 1 },
      { result: "over", units: -1, clv: -0.5, stake: 1 },
      { result: "push", units: 0, clv: null, stake: 1 },
    ]);
    expect(rec).toMatchObject({
      n: 3,
      record: "1-1-1P",
      hit: "50.0%",
      units: "-0.09",
      roi: "-3.0%",
      clv: "-0.25", // stored +1.0 and -0.5 mean the line rose on balance: bad for an under
    });
  });

  it("results-ledger rows (no stake field) are flat 1-unit bets for ROI", () => {
    const rec = recordFrom([
      { result: "under", units: 0.91, clv: null },
      { result: "under", units: 0.91, clv: null },
    ]);
    expect(rec?.roi).toBe("+91.0%");
  });

  it("unpriced rows (units null) count in W-L and hit rate but not in units or staked", () => {
    const rec = recordFrom([
      { result: "under", units: 0.91, clv: 1.0, stake: 1 },
      { result: "under", units: null, clv: 0.5, stake: 1 }, // no Hard Rock close captured
      { result: "over", units: -1, clv: null, stake: 1 },
    ]);
    expect(rec).toMatchObject({
      n: 3,
      record: "2-1",
      hit: "66.7%",
      units: "-0.09",
      roi: "-4.5%", // -0.09 over the 2 units actually staked
      clv: "-0.75", // stored +1.0 / +0.5: the market moved away from the under
    });
  });

  it("legacy paper picks (stake 0) show no ROI but still count wins and CLV", () => {
    const rec = recordFrom([
      { result: "under", units: 0, clv: 1.5, stake: 0 },
      { result: "under", units: 0, clv: 0.5, stake: 0 },
    ]);
    expect(rec).toMatchObject({
      record: "2-0",
      hit: "100.0%",
      units: "+0.00",
      roi: "—",
      // Stored +1.5 / +0.5: the total ROSE after both bets, which is the wrong
      // way for an under, so the displayed line value is negative.
      clv: "-1.00",
    });
  });
});

describe("recordFromCounts", () => {
  it("builds the same shape from aggregate counts (pushes staked, no CLV)", () => {
    const rec = recordFromCounts(89, 72, 5, 8.9);
    expect(rec).toMatchObject({
      n: 166,
      record: "89-72-5P",
      hit: "55.3%",
      units: "+8.90",
      roi: "+5.4%",
      clv: "—",
    });
    expect(rec?.roiNum).toBeCloseTo(5.36, 1);
  });

  it("is null with nothing graded", () => {
    expect(recordFromCounts(0, 0, 0, 0)).toBeNull();
  });
});

describe("recordFrom line value", () => {
  it("counts points the market came TOWARD the under", () => {
    // Stored clv is closing - bet. Bet u28.5 and it closes 27.5 -> clv -1.0,
    // and we hold the better ticket, so the card must read +0.75 here.
    // Reported backwards until 2026-09-13; see lib/clvDirection.test.ts.
    const r = recordFrom([
      { result: "under", units: 0.87, clv: -1.0, stake: 1 },
      { result: "over", units: -1, clv: -0.5, stake: 1 },
    ]);
    expect(r!.clv).toBe("+0.75");
  });
});
