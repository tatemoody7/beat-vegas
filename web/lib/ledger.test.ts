import { describe, expect, it } from "vitest";
import { recordFromResults, type ResRow } from "./ledger";

const row = (o: Partial<ResRow>): ResRow => ({
  model_version: "market",
  under_hit: null,
  units: null,
  clv: null,
  week: 1,
  actual_first_half_total: null,
  line_used: null,
  ...o,
});

describe("recordFromResults", () => {
  it("recovers pushes from actual == line and drops never-graded rows", () => {
    const rec = recordFromResults([
      row({ under_hit: true, units: 0.91, clv: 0.5 }),
      row({ under_hit: false, units: -1, clv: -0.5 }),
      row({
        under_hit: false,
        units: 0,
        actual_first_half_total: 24,
        line_used: 24,
      }),
      row({ under_hit: null }), // never graded
    ]);
    expect(rec).toMatchObject({
      n: 3,
      record: "1-1-1P",
      hit: "50.0%",
      units: "-0.09",
      clv: "+0.00",
    });
    expect(rec?.roi).toBe("-3.0%"); // flat 1u per results row
  });
  it("is null with nothing graded", () => {
    expect(recordFromResults([row({})])).toBeNull();
  });
});
