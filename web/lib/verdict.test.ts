import { describe, expect, it } from "vitest";
import {
  BET_GAP_PTS,
  STRONG_GAP_PTS,
  deriveReason,
  verdictFor,
  type VerdictInput,
} from "./verdict";
import type { BoardFactor } from "./score";

// Real 2025 shape: sigma ~11.7, so a z-score would always be tiny. Gates are
// in points, and the gap that matters is Hard Rock's own number minus ours.
const base: VerdictInput = {
  away: "Ohio State",
  home: "Michigan",
  derived: false,
  underScore: 56,
  bvLine: 21.8,
  liveLine: 24.5,
  fallbackLine: 24.5,
  gap: 2.7,
  hrLine: 24.5,
  hrUnderPrice: -105,
  ev: 0.012,
  evVerdict: "pos",
  fhShare: null,
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

describe("verdictFor — model rows, gated on Hard Rock's number", () => {
  it("WATCH, never BET, when Hard Rock's total sits more than half a point below the market", () => {
    // Our 21.8 vs HR 24.0 clears 1.75, but the market is at 26.0: HR is 2 pts
    // off-market — giving up points, and a void risk under HR house rules.
    const v = verdictFor({
      ...base,
      liveLine: 26.0,
      gap: 4.2,
      hrLine: 24.0,
      ev: null,
      evVerdict: "na",
    });
    expect(v.verdict).toBe("WATCH");
    expect(v.headline).toContain("2.0 points below the market");
    expect(v.hrGap).toBe(2.2);
  });
  it("BET still allowed when Hard Rock is within half a point of the market", () => {
    const v = verdictFor({ ...base, liveLine: 25.0, gap: 3.2, hrLine: 24.5 });
    expect(v.verdict).toBe("BET");
  });
  it("BET when Hard Rock's gap is in the validated top-20% band at a fair-or-better price", () => {
    const v = verdictFor(base);
    expect(v.verdict).toBe("BET");
    expect(v.confidence).toBe("medium");
    expect(v.priceEdgeOnly).toBe(false);
    expect(v.hrGap).toBe(2.7);
    expect(v.reason).toBe("model_gap");
    expect(v.why[0]).toContain("top ~20%");
    expect(v.why[0]).toContain("coin flip");
    expect(v.why[0]).not.toMatch(/54/);
    expect(v.why[1]).toContain("good price");
  });

  it("BET at a FAIR Hard Rock price too (only a negative price blocks)", () => {
    const v = verdictFor({ ...base, evVerdict: "fair", ev: 0 });
    expect(v.verdict).toBe("BET");
    expect(v.headline).toContain("fair price");
  });

  it("no BET when Hard Rock has not posted, however big the consensus gap", () => {
    const v = verdictFor({
      ...base,
      gap: 3.5,
      liveLine: 25.3,
      hrLine: null,
      hrUnderPrice: null,
      ev: null,
      evVerdict: "na",
    });
    expect(v.verdict).toBe("WATCH");
    expect(v.hrGap).toBeNull();
    expect(v.headline).toContain(
      "Hard Rock has not posted a first-half line yet",
    );
  });

  it("WATCH when the market clears the bar but Hard Rock's number is 2 points lower", () => {
    // consensus 24.5 vs ours 21.8 = 2.7 (clears); HR 22.5 → 0.7 (does not).
    const v = verdictFor({ ...base, hrLine: 22.5, evVerdict: "fair", ev: 0 });
    expect(v.verdict).toBe("WATCH");
    expect(v.hrGap).toBe(0.7);
    expect(v.headline).toBe(
      "The market’s number clears our bar but Hard Rock’s is 2.0 points lower — no edge at Hard Rock’s line.",
    );
    expect(v.reason).toBe("manual");
  });

  it("WATCH when Hard Rock's gap clears the bar but its price is worse than the market", () => {
    // -0.065 ≈ -115 into a balanced market: below the -0.05 floor.
    const v = verdictFor({ ...base, evVerdict: "neg", ev: -0.065 });
    expect(v.verdict).toBe("WATCH");
    expect(v.headline).toContain("price is worse");
  });

  it("uses Hard Rock's gap, not the consensus, for the bar — HR above consensus can BET", () => {
    // consensus 23.0 (gap 1.2, below the bar) but HR hangs 24.0 (gap 2.2).
    const v = verdictFor({
      ...base,
      liveLine: 23.0,
      gap: 1.2,
      hrLine: 24.0,
      evVerdict: "fair",
      ev: 0,
    });
    expect(v.verdict).toBe("BET");
    expect(v.hrGap).toBe(2.2);
  });

  it("high confidence needs only a top-10% Hard Rock gap; the classifier score does not gate it", () => {
    // 2026-09-06 post-mortem: under_score bands hit the same rate (48.6–49.0%)
    // against a fair line, so the score is a display chip, not a confidence input.
    const v = verdictFor({
      ...base,
      hrLine: 21.8 + STRONG_GAP_PTS + 0.5,
      underScore: 58,
    });
    expect(v.verdict).toBe("BET");
    expect(v.confidence).toBe("high");
    expect(v.why[0]).toContain("top ~10%");
    const lowScore = verdictFor({
      ...base,
      hrLine: 21.8 + STRONG_GAP_PTS + 0.5,
      underScore: 40,
    });
    expect(lowScore.confidence).toBe("high");
    const smallerGap = verdictFor({
      ...base,
      hrLine: 21.8 + STRONG_GAP_PTS - 0.5,
      underScore: 90,
    });
    expect(smallerGap.confidence).toBe("medium");
  });

  it("never BETs a Hard Rock gap below the validated cutoff", () => {
    const v = verdictFor({
      ...base,
      liveLine: 21.8 + BET_GAP_PTS - 0.5,
      gap: BET_GAP_PTS - 0.5,
      hrLine: 21.8 + BET_GAP_PTS - 0.5,
      evVerdict: "fair",
      ev: 0,
    });
    expect(v.verdict).toBe("WATCH");
    expect(v.headline).toContain("Small model lean");
  });

  it("a scoring-time estimate with no book at all only reaches WATCH", () => {
    const v = verdictFor({
      ...base,
      liveLine: null,
      hrLine: null,
      hrUnderPrice: null,
      ev: null,
      evVerdict: "na",
    });
    expect(v.verdict).toBe("WATCH");
    expect(v.headline).toContain("ESTIMATED");
  });

  it("PASSes an over-leaning gap (we only bet unders)", () => {
    const v = verdictFor({
      ...base,
      liveLine: 19.8,
      gap: -2.0,
      hrLine: 19.8,
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

  it("does not double the '— helps the under' tail the board already words", () => {
    const v = verdictFor({
      ...base,
      factorBoard: [
        factor({ sentence: "Combined PPA allowed 0.15 — helps the under." }),
        factor({
          key: "pace",
          lean: -0.9,
          color: "red",
          sentence: "Both 1H offenses average 30.8 pts — hurts the under.",
        }),
      ],
    });
    expect(v.why[2]).toBe("Combined PPA allowed 0.15 — helps the under.");
    expect(v.why[3]).toBe(
      "Both 1H offenses average 30.8 pts — works against the under.",
    );
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
    expect(v.flags[0]).toContain("QB J. Smith — Out");
    expect(v.flags[1]).toContain("-1.5");
  });

  it("WATCH, never BET, when a starting QB is listed out — even with the gap and price clearing", () => {
    // base is a BET (gap 2.7 at a good price); the QB news alone blocks it.
    expect(verdictFor(base).verdict).toBe("BET");
    const v = verdictFor({
      ...base,
      qbOut: true,
      qbOutDetail: "QB1 (knee) out",
    });
    expect(v.verdict).toBe("WATCH");
    expect(v.confidence).toBe("medium");
    expect(v.headline).toBe(
      "Our number clears the bar, but a starting quarterback is listed out and the model does not know it — re-check the number after the news settles.",
    );
    expect(v.hrGap).toBe(2.7);
    expect(v.strength).toBe(58 + 2.7 * 10);
    expect(v.priceEdgeOnly).toBe(false);
    expect(v.flags[0]).toMatch(/^QB OUT/);
    // The gate sits after the off-market check: an off-market number still
    // reads as off-market first.
    const off = verdictFor({
      ...base,
      qbOut: true,
      liveLine: 26.0,
      gap: 4.2,
      hrLine: 24.0,
      ev: null,
      evVerdict: "na",
    });
    expect(off.verdict).toBe("WATCH");
    expect(off.headline).toContain("below the market");
    // Below the bar (Hard Rock and the market both at 23.0: gap 1.2) the QB
    // flag is just a flag; the verdict is the usual small lean.
    const short = verdictFor({
      ...base,
      qbOut: true,
      hrLine: 23.0,
      liveLine: 23.0,
      gap: 1.2,
      ev: 0,
      evVerdict: "fair",
    });
    expect(short.verdict).toBe("WATCH");
    expect(short.headline).toContain("Small model lean");
  });
});

describe("verdictFor — no model (weeks 1–2 / derived lines)", () => {
  const derived: VerdictInput = {
    ...base,
    derived: true,
    underScore: null,
    bvLine: null,
    gap: null,
  };

  it("can only reach WATCH, and only on a positive Hard Rock price", () => {
    const v = verdictFor(derived);
    expect(v.verdict).toBe("WATCH");
    expect(v.priceEdgeOnly).toBe(true);
    expect(v.reason).toBe("price_edge");
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

  it("describes the reference line with the real first-half share when stored", () => {
    const v = verdictFor({ ...derived, fhShare: 0.5375 });
    expect(v.why[0]).toContain("53.8% of it");
    const noShare = verdictFor({ ...derived, fhShare: null });
    expect(noShare.why[0]).toContain("about half of it");
    expect(noShare.why[0]).not.toContain("52%");
  });
});

describe("deriveReason", () => {
  it("model_gap when the model reads and Hard Rock's gap clears the bar", () => {
    expect(deriveReason(true, 1.75, false)).toBe("model_gap");
    expect(deriveReason(true, 3.2, true)).toBe("model_gap");
  });
  it("price_edge when the only edge is Hard Rock's price", () => {
    expect(deriveReason(false, null, true)).toBe("price_edge");
  });
  it("manual otherwise", () => {
    expect(deriveReason(true, 1.0, false)).toBe("manual");
    expect(deriveReason(false, null, false)).toBe("manual");
  });
});
