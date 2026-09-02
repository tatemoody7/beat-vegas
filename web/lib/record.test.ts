import { describe, expect, it } from "vitest";
import { recordFrom } from "./record";

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
      clv: "+0.25",
    });
  });

  it("results-ledger rows (no stake field) are flat 1-unit bets for ROI", () => {
    const rec = recordFrom([
      { result: "under", units: 0.91, clv: null },
      { result: "under", units: 0.91, clv: null },
    ]);
    expect(rec?.roi).toBe("+91.0%");
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
      clv: "+1.00",
    });
  });
});
