import { describe, expect, it } from "vitest";
import {
  BET_GAP_PTS,
  STRONG_GAP_PTS,
  verdictFor,
  type VerdictInput,
} from "./verdict";
import type { BoardFactor } from "./score";

// Real 2025 shape: sigma ~11.7, so z is always tiny. Gates are in points.
const base: VerdictInput = {
  away: "Ohio State",
  home: "Michigan",
  derived: false,
  underScore: 56,
  bvLine: 21.8,
  liveLine: 24.5,
  fallbackLine: 24.5,
  gap: 2.7,
  z: 0.23,
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
  it("BET when the gap is in the validated top-20% range, a live line exists and the price is not negative", () => {
    const v = verdictFor(base);
    expect(v.verdict).toBe("BET");
    expect(v.confidence).toBe("medium");
    expect(v.priceEdgeOnly).toBe(false);
    expect(v.why[0]).toContain("top ~20%");
    expect(v.why[0]).toContain("coin flip");
    expect(v.why[1]).toContain("good price");
  });

  it("high confidence needs a top-10% gap AND the classifier agreeing", () => {
    const v = verdictFor({
      ...base,
      gap: STRONG_GAP_PTS + 0.5,
      underScore: 58,
    });
    expect(v.verdict).toBe("BET");
    expect(v.confidence).toBe("high");
    expect(v.why[0]).toContain("top ~10%");
    const weak = verdictFor({
      ...base,
      gap: STRONG_GAP_PTS + 0.5,
      underScore: 50,
    });
    expect(weak.confidence).toBe("medium");
  });

  it("never BETs a gap below the validated cutoff", () => {
    const v = verdictFor({
      ...base,
      gap: BET_GAP_PTS - 0.5,
      evVerdict: "fair",
      ev: 0,
    });
    expect(v.verdict).toBe("WATCH");
    expect(v.headline).toContain("Small model lean");
  });

  it("downgrades a bettable gap to WATCH when Hard Rock's price is negative EV", () => {
    const v = verdictFor({ ...base, evVerdict: "neg", ev: -0.03 });
    expect(v.verdict).toBe("WATCH");
    expect(v.headline).toContain("price is worse");
  });

  it("requires a LIVE line to BET — a scoring-time estimate only reaches WATCH", () => {
    const v = verdictFor({ ...base, liveLine: null });
    expect(v.verdict).toBe("WATCH");
    expect(v.headline).toContain("ESTIMATED");
  });

  it("PASSes an over-leaning gap (we only bet unders)", () => {
    const v = verdictFor({
      ...base,
      gap: -2.0,
      z: -0.17,
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
