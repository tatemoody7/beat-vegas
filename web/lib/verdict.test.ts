import { describe, expect, it } from "vitest";
import { verdictFor, type VerdictInput } from "./verdict";
import type { BoardFactor } from "./score";

const base: VerdictInput = {
  away: "Ohio State",
  home: "Michigan",
  derived: false,
  underScore: 56,
  bvLine: 21.8,
  liveLine: 24.5,
  fallbackLine: 24.5,
  gap: 2.7,
  z: 1.3,
  hrLine: 24.5,
  hrUnderPrice: -105,
  ev: 0.012,
  evVerdict: "pos",
  qbOut: false,
  qbOutDetail: null,
  bvAdjust: null,
  bvAdjustReason: null,
  factorBoard: null,
};

const factor = (over: Partial<BoardFactor>): BoardFactor => ({
  key: "wx_wind",
  label: "Wind",
  family: "weather",
  tier: 1,
  direction: 1,
  hypothesis: false,
  binary: false,
  value: 18,
  color: "green",
  intensity: 0.8,
  lean: 1.6,
  sentence: "Wind 18 mph at kickoff",
  live: null,
  ...over,
});

describe("verdictFor — model rows", () => {
  it("BET when the gap clears noise, a live line exists and the price is not negative", () => {
    const v = verdictFor(base);
    expect(v.verdict).toBe("BET");
    expect(v.priceEdgeOnly).toBe(false);
    expect(v.why[0]).toContain("clear signal");
    expect(v.why[1]).toContain("good price");
  });

  it("never BETs a gap inside the noise band (z < 1)", () => {
    const v = verdictFor({ ...base, z: 0.7, evVerdict: "fair", ev: 0 });
    expect(v.verdict).toBe("WATCH");
    expect(v.why[0]).toContain("inside the noise");
  });

  it("downgrades a clear edge to WATCH when Hard Rock's price is negative EV", () => {
    const v = verdictFor({ ...base, evVerdict: "neg", ev: -0.03 });
    expect(v.verdict).toBe("WATCH");
    expect(v.headline).toContain("price is worse");
  });

  it("requires a LIVE line to BET — a scoring-time fallback is not bettable", () => {
    const v = verdictFor({ ...base, liveLine: null });
    expect(v.verdict).not.toBe("BET");
  });

  it("PASSes an over-leaning gap (we only bet unders)", () => {
    const v = verdictFor({
      ...base,
      gap: -2.0,
      z: -1.2,
      evVerdict: "fair",
      ev: 0,
    });
    expect(v.verdict).toBe("PASS");
    expect(v.headline).toContain("leans over");
  });

  it("names the strongest real drivers, skipping hypotheses and tier 3", () => {
    const v = verdictFor({
      ...base,
      factorBoard: [
        factor({}),
        factor({
          key: "mm_havoc",
          hypothesis: true,
          lean: 5,
          sentence: "Havoc",
        }),
        factor({ key: "spec", tier: 3, lean: 4, sentence: "Speculative" }),
        factor({
          key: "pace",
          lean: -0.4,
          color: "red",
          sentence: "Both offenses play fast.",
        }),
      ],
    });
    expect(v.why).toHaveLength(4);
    expect(v.why[2]).toBe("Wind 18 mph at kickoff — helps the under.");
    expect(v.why[3]).toBe("Both offenses play fast — works against the under.");
  });

  it("surfaces QB-out and manual adjustments as flags, not silently", () => {
    const v = verdictFor({
      ...base,
      qbOut: true,
      qbOutDetail: "QB J. Smith — Out",
      bvAdjust: -1.5,
      bvAdjustReason: "backup QB",
    });
    expect(v.flags).toHaveLength(2);
    expect(v.flags[0]).toContain("does not know this");
  });
});

describe("verdictFor — no model (weeks 1–2 / derived lines)", () => {
  const derived: VerdictInput = {
    ...base,
    derived: true,
    underScore: null,
    bvLine: null,
    gap: null,
    z: null,
  };

  it("can only reach WATCH, and only on a positive Hard Rock price", () => {
    const v = verdictFor(derived);
    expect(v.verdict).toBe("WATCH");
    expect(v.priceEdgeOnly).toBe(true);
    expect(v.confidence).toBe("low");
    expect(v.why[0]).toContain("No model read yet");
  });

  it("PASSes without a price edge", () => {
    const v = verdictFor({ ...derived, evVerdict: "fair", ev: 0 });
    expect(v.verdict).toBe("PASS");
    expect(v.confidence).toBe("none");
  });

  it("says so when Hard Rock has not posted", () => {
    const v = verdictFor({
      ...derived,
      hrLine: null,
      hrUnderPrice: null,
      ev: null,
      evVerdict: "na",
    });
    expect(v.verdict).toBe("PASS");
    expect(v.why[1]).toContain("hasn’t posted");
  });
});
