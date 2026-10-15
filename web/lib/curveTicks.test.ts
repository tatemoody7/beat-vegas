import { describe, expect, it } from "vitest";
import { curveTicks } from "./curveTicks";

describe("curveTicks", () => {
  it("labels every whole unit and always includes zero", () => {
    // The live season: about +2.8u at week 4, -1.43u at week 6.
    expect(curveTicks(-2.1, 3.5)).toEqual([-3, -2, -1, 0, 1, 2, 3, 4]);
    expect(curveTicks(0, 0.6)).toEqual([0, 1]);
  });

  it("steps by two beyond eight units of range", () => {
    expect(curveTicks(-6.2, 5.4)).toEqual([-8, -6, -4, -2, 0, 2, 4, 6]);
  });
});
