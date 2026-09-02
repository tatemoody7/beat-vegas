import { describe, expect, it } from "vitest";
import {
  PROXY_BASE_SHARE,
  PROXY_BLOWOUT_CUT,
  PROXY_BLOWOUT_SHARE,
  fhShare,
  isFbsGame,
  proxyShareText,
  proxyTotal,
} from "./proxy";

describe("proxy first-half share (mirrors etl/proxy_line.py)", () => {
  it("reads the fitted step from data/multiplier.json", () => {
    expect(PROXY_BASE_SHARE).toBeCloseTo(0.4975, 6);
    expect(PROXY_BLOWOUT_SHARE).toBeCloseTo(0.5375, 6);
    expect(PROXY_BLOWOUT_CUT).toBe(21);
  });
  it("base share below the cut, blowout share at/above it, base with no spread", () => {
    expect(fhShare(-7)).toBeCloseTo(0.4975, 6);
    expect(fhShare(20.5)).toBeCloseTo(0.4975, 6);
    expect(fhShare(21)).toBeCloseTo(0.5375, 6);
    expect(fhShare(-28)).toBeCloseTo(0.5375, 6);
    expect(fhShare(null)).toBeCloseTo(0.4975, 6);
  });
  it("proxyTotal rounds to the half point", () => {
    expect(proxyTotal(50, -3)).toBe(25); // 24.875 → 25.0
    expect(proxyTotal(50, 24)).toBe(27); // 26.875 → 27.0
    expect(proxyTotal(47, -3)).toBe(23.5); // 23.38 → 23.5
  });
  it("prose says the real share, not 52%", () => {
    expect(proxyShareText()).toBe(
      "49.8% of the full-game total (53.8% when the spread is 21+ points)",
    );
  });
});

describe("FBS filter (mirrors etl/fbs.py)", () => {
  it("keeps FBS-vs-FBS only and never guesses an unknown season", () => {
    expect(isFbsGame(2015, "Alabama", "Auburn")).toBe(true);
    expect(isFbsGame(2015, "Alabama", "Mercer")).toBe(false);
    expect(isFbsGame(1999, "Alabama", "Auburn")).toBe(false);
    expect(isFbsGame(2015, null, "Auburn")).toBe(false);
  });
});
