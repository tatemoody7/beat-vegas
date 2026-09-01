import { describe, expect, it } from "vitest";
import { recordFromPicks } from "./picks";

const pick = (result: string, units: number | null, clv: number | null) => ({
  result,
  units,
  clv,
});

describe("recordFromPicks", () => {
  it("returns null with nothing graded", () => {
    expect(recordFromPicks([])).toBeNull();
  });

  it("counts wins, losses and pushes, sums units, averages CLV", () => {
    const rec = recordFromPicks([
      pick("under", 0.91, 1.0),
      pick("over", -1, -0.5),
      pick("push", 0, null),
    ]);
    expect(rec).toEqual({
      record: "1-1-1P",
      hit: "50.0%",
      units: "-0.09",
      clv: "+0.25",
    });
  });

  it("paper picks (stake 0) contribute 0 units but still count wins + CLV", () => {
    const rec = recordFromPicks([pick("under", 0, 1.5), pick("under", 0, 0.5)]);
    expect(rec).toEqual({
      record: "2-0",
      hit: "100.0%",
      units: "+0.00",
      clv: "+1.00",
    });
  });
});
