import { describe, expect, it } from "vitest";
import { american, capitalize, fmt, median, pct, signed } from "./format";

describe("format helpers", () => {
  it("signed adds + only to positives", () => {
    expect(signed(1.5)).toBe("+1.50");
    expect(signed(-0.5, 1)).toBe("-0.5");
    expect(signed(0)).toBe("+0.00");
  });
  it("fmt/pct fall back to an em dash", () => {
    expect(fmt(null)).toBe("—");
    expect(fmt(24.5)).toBe("24.5");
    expect(pct(54)).toBe("54.0%");
    expect(pct(undefined)).toBe("—");
  });
  it("american odds", () => {
    expect(american(105)).toBe("+105");
    expect(american(-110)).toBe("-110");
  });
  it("capitalize upper-cases only the first letter", () => {
    expect(capitalize("won")).toBe("Won");
    expect(capitalize("no score")).toBe("No score");
    expect(capitalize("")).toBe("");
  });
  it("median handles odd/even/empty", () => {
    expect(median([])).toBeNull();
    expect(median([3, 1, 2])).toBe(2);
    expect(median([1, 2, 3, 4])).toBe(2.5);
  });
});
