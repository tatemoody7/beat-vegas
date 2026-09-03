import { describe, expect, it } from "vitest";
import { americanToDecimal, evUnder } from "./devig";
import {
  breakEvenPrice,
  contextScore,
  edgeScore,
  roundHalfUp,
  type EdgeInput,
} from "./edge";

// Same real-2025 shape as verdict.test.ts: our 21.8 vs Hard Rock 24.5 is a
// 2.7-point gap at a slightly-better-than-fair price.
const base: EdgeInput = {
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
  marketLine: 24.5,
  bestLine: 24.5,
  marketFairUnder: 0.52,
  context: {
    combinedSecPlay: null,
    windMph: null,
    dome: null,
    spread: null,
    fhPrior: null,
  },
};

const noModel: EdgeInput = {
  ...base,
  derived: true,
  underScore: null,
  bvLine: null,
  gap: null,
  hrLine: null,
  hrUnderPrice: null,
  ev: null,
  evVerdict: "na",
  marketFairUnder: null,
};

describe("roundHalfUp", () => {
  it("rounds up to the next half point", () => {
    expect(roundHalfUp(23.55)).toBe(24);
    expect(roundHalfUp(23.1)).toBe(23.5);
    expect(roundHalfUp(23.5)).toBe(23.5);
    expect(roundHalfUp(24)).toBe(24);
  });
  it("is not fooled by float noise (21.8 + 1.75)", () => {
    expect(roundHalfUp(21.8 + 1.75)).toBe(24);
    expect(roundHalfUp(22.75 + 1.75)).toBe(24.5);
  });
});

describe("breakEvenPrice", () => {
  it("is the worst 5-cent American price that keeps EV >= -0.02", () => {
    const p = breakEvenPrice(0.52);
    expect(p).toBe(-110);
    expect(evUnder(0.52, p!)).toBeGreaterThanOrEqual(-0.02);
    expect(evUnder(0.52, p! - 5)).toBeLessThan(-0.02);
  });
  it("never returns -100 (that is +100)", () => {
    expect(breakEvenPrice(0.5)).toBe(100);
  });
  it("is monotonic: a likelier under tolerates a worse price", () => {
    const pay = (f: number) => americanToDecimal(breakEvenPrice(f)!);
    expect(pay(0.58)).toBeLessThanOrEqual(pay(0.52));
    expect(pay(0.52)).toBeLessThanOrEqual(pay(0.46));
    expect(pay(0.46)).toBeLessThanOrEqual(pay(0.4));
  });
  it("returns null when no price in range clears the bar", () => {
    expect(breakEvenPrice(0.01)).toBeNull();
  });
});

describe("edgeScore — model rows", () => {
  it("BET: score >= 60, tier BET, no blocker, bet-now action at Hard Rock's number and price", () => {
    const e = edgeScore(base);
    expect(e.score).toBe(78); // 50 + 27 + round(1.2)
    expect(e.tier).toBe("BET");
    expect(e.blocker).toBeNull();
    expect(e.action).toBe("Bet now: 1H under 24.5 at -105 on Hard Rock.");
    expect(e.verdict.verdict).toBe("BET");
    expect(e.kill.line).toBe(24);
    expect(e.kill.price).toBe(-110);
    expect(e.kill.text).toBe("Not worth it below u24.0 or worse than -110.");
  });
  it("no Hard Rock line + big market gap → EDGE / no_hr_line, action names the line to take", () => {
    const e = edgeScore({
      ...base,
      hrLine: null,
      hrUnderPrice: null,
      ev: null,
      evVerdict: "na",
      marketFairUnder: null,
    });
    expect(e.score).toBe(77);
    expect(e.tier).toBe("EDGE");
    expect(e.blocker).toBe("no_hr_line");
    expect(e.action).toBe(
      "No Hard Rock line yet. A bet at under 24.0 or higher, -110 or better.",
    );
    expect(e.kill.price).toBeNull();
    expect(e.kill.text).toBe("Not worth it below u24.0.");
  });
  it("falls back to the derived line when nothing live is posted", () => {
    const e = edgeScore({
      ...base,
      hrLine: null,
      hrUnderPrice: null,
      ev: null,
      evVerdict: "na",
      liveLine: null,
      marketLine: null,
      bestLine: null,
      marketFairUnder: null,
      fallbackLine: 23.8,
      gap: 2.0,
    });
    expect(e.score).toBe(70);
    expect(e.blocker).toBe("no_hr_line");
  });
  it("off-market Hard Rock → EDGE / off_market with the −10 penalty and a wait-for line", () => {
    const e = edgeScore({
      ...base,
      liveLine: 26,
      marketLine: 26,
      bestLine: 26,
      gap: 4.2,
      hrLine: 24,
      ev: null,
      evVerdict: "na",
      marketFairUnder: null,
    });
    // hrGap 2.2 → 72, minus 10 off-market
    expect(e.score).toBe(62);
    expect(e.tier).toBe("EDGE");
    expect(e.blocker).toBe("off_market");
    expect(e.verdict.verdict).toBe("WATCH");
    expect(e.action).toBe(
      "Wait: Hard Rock’s 24.0 is 2.0 below the market’s 26.0 — giving up points and a void risk. Bet if it moves to 25.5 or higher.",
    );
  });
  it("Hard Rock within half a point of the market is not off-market", () => {
    const e = edgeScore({ ...base, liveLine: 25, marketLine: 25, gap: 3.2 });
    expect(e.tier).toBe("BET");
    expect(e.score).toBe(78);
  });
  it("price too high → EDGE / price with a computed break-even", () => {
    const ev = evUnder(0.52, -125); // ≈ -0.064
    const e = edgeScore({
      ...base,
      hrUnderPrice: -125,
      ev,
      evVerdict: "neg",
    });
    expect(e.score).toBe(71); // 77 + clamp(round(-6.4)) = 77 - 6
    expect(e.tier).toBe("EDGE");
    expect(e.blocker).toBe("price");
    expect(e.action).toBe("Wait: Hard Rock is -125; needs -110 or better.");
    expect(e.kill.price).toBe(-110);
  });
  it("price too high with no market fair price asks for a fair price", () => {
    const e = edgeScore({
      ...base,
      hrUnderPrice: -125,
      ev: -0.05,
      evVerdict: "neg",
      marketFairUnder: null,
    });
    expect(e.blocker).toBe("price");
    expect(e.action).toBe(
      "Wait: Hard Rock is -125; needs a fair price (-110 or better).",
    );
    expect(e.kill.price).toBeNull();
  });
  it("price bonus is clamped to ±8", () => {
    const hi = edgeScore({ ...base, ev: 0.2, evVerdict: "pos" });
    expect(hi.score).toBe(85); // 77 + 8
    const lo = edgeScore({ ...base, ev: -0.2, evVerdict: "neg" });
    expect(lo.score).toBe(69); // 77 - 8
  });
  it("QB out → EDGE / qb_out (−5) when the gap is short of the bar", () => {
    const e = edgeScore({
      ...base,
      hrLine: 23.3,
      liveLine: 23.3,
      marketLine: 23.3,
      bestLine: 23.3,
      gap: 1.5,
      ev: null,
      evVerdict: "na",
      qbOut: true,
      qbOutDetail: "QB1 (knee) out",
    });
    expect(e.score).toBe(60); // 50 + 15 - 5
    expect(e.tier).toBe("EDGE");
    expect(e.blocker).toBe("qb_out");
    expect(e.action).toBe(
      "Wait: a starting QB is listed out — re-check the number after the news settles.",
    );
  });
  it("QB out on a BET keeps the BET tier (verdict rules) but costs 5 points", () => {
    const e = edgeScore({ ...base, qbOut: true });
    expect(e.tier).toBe("BET");
    expect(e.score).toBe(73);
    expect(e.verdict.flags[0]).toMatch(/QB OUT/);
  });
  it("gap just short of the bar at a good price → EDGE / gap", () => {
    const e = edgeScore({
      ...base,
      hrLine: 23.3,
      liveLine: 23.3,
      marketLine: 23.3,
      bestLine: 23.3,
      gap: 1.5,
    });
    expect(e.score).toBe(66);
    expect(e.tier).toBe("EDGE");
    expect(e.blocker).toBe("gap");
    expect(e.action).toBe(
      "Pass: the line is only 1.5 above our number; needs 24.0 or higher.",
    );
  });
  it("small gap → PASS with the kill line", () => {
    const e = edgeScore({
      ...base,
      hrLine: 22.5,
      liveLine: 22.5,
      marketLine: 22.5,
      bestLine: 22.5,
      gap: 0.7,
      ev: null,
      evVerdict: "na",
      marketFairUnder: null,
    });
    expect(e.score).toBe(57);
    expect(e.tier).toBe("PASS");
    expect(e.blocker).toBeNull();
    expect(e.kill.line).toBe(24);
    expect(e.action).toBe(
      "Pass: the line is only 0.7 above our number; needs 24.0 or higher.",
    );
  });
  it("line below our number reads as an over lean", () => {
    const e = edgeScore({
      ...base,
      hrLine: 20.5,
      liveLine: 20.5,
      marketLine: 20.5,
      bestLine: 20.5,
      gap: -1.3,
      ev: null,
      evVerdict: "na",
    });
    expect(e.score).toBe(37);
    expect(e.tier).toBe("PASS");
    expect(e.action).toBe(
      "Pass: the line is 1.3 below our number (leans over); needs 24.0 or higher.",
    );
  });
  it("model read but no line anywhere → PASS at 50, action names the line to take", () => {
    const e = edgeScore({
      ...base,
      hrLine: null,
      hrUnderPrice: null,
      ev: null,
      evVerdict: "na",
      liveLine: null,
      marketLine: null,
      bestLine: null,
      fallbackLine: null,
      gap: null,
      marketFairUnder: null,
    });
    expect(e.score).toBe(50);
    expect(e.tier).toBe("PASS");
    expect(e.action).toBe(
      "No line captured yet. A bet at under 24.0 or higher, -110 or better.",
    );
  });
  it("score clamps to 0..100", () => {
    const hi = edgeScore({
      ...base,
      hrLine: 30,
      liveLine: 30,
      marketLine: 30,
      gap: 8.2,
    });
    expect(hi.score).toBe(100);
    const lo = edgeScore({
      ...base,
      hrLine: 14.5,
      liveLine: 14.5,
      marketLine: 14.5,
      gap: -7.3,
      ev: -0.3,
      evVerdict: "neg",
      qbOut: true,
    });
    expect(lo.score).toBe(0);
  });
  it("uses Hard Rock's number as the gap basis even when the market differs", () => {
    // market 25.0 vs HR 24.5: HR gap 2.7 (not 3.2) drives the score
    const e = edgeScore({ ...base, liveLine: 25, marketLine: 25, gap: 3.2 });
    expect(e.score).toBe(78);
  });
});

describe("contextScore — no model read", () => {
  it("missing inputs contribute nothing", () => {
    expect(contextScore(noModel.context)).toBe(40);
  });
  it("slow pace + wind + close spread + low prior lean under, capped at 49", () => {
    expect(
      contextScore({
        combinedSecPlay: 29.5,
        windMph: 16,
        dome: false,
        spread: -3,
        fhPrior: 14,
      }),
    ).toBe(49); // 40 + 6 + 3 + 2 + 3 = 54 → cap
    expect(
      contextScore({
        combinedSecPlay: 28,
        windMph: 11,
        dome: false,
        spread: 10,
        fhPrior: 16.5,
      }),
    ).toBe(48); // 40 + 4 + 2 + 1 + 1
  });
  it("dome + blowout spread + high prior lean over", () => {
    expect(
      contextScore({
        combinedSecPlay: null,
        windMph: null,
        dome: true,
        spread: -28,
        fhPrior: 26,
      }),
    ).toBe(33); // 40 - 2 - 3 - 2
    expect(
      contextScore({
        combinedSecPlay: 25,
        windMph: 3,
        dome: false,
        spread: 17,
        fhPrior: 20,
      }),
    ).toBe(40);
  });
});

describe("edgeScore — no model read", () => {
  it("slow pace + wind → PASS, at most 49", () => {
    const e = edgeScore({
      ...noModel,
      context: {
        combinedSecPlay: 29.5,
        windMph: 16,
        dome: false,
        spread: -3,
        fhPrior: 14,
      },
    });
    expect(e.score).toBeLessThanOrEqual(49);
    expect(e.score).toBe(49);
    expect(e.tier).toBe("PASS");
    expect(e.blocker).toBeNull();
    expect(e.kill.line).toBeNull();
    expect(e.action).toBe(
      "Pass: no model read this week and no price edge at Hard Rock.",
    );
    expect(e.kill.text).toBe("No kill point without a model read.");
  });
  it("dome + big spread scores lower than the slow/windy game", () => {
    const windy = edgeScore({
      ...noModel,
      context: {
        combinedSecPlay: 29.5,
        windMph: 16,
        dome: false,
        spread: -3,
        fhPrior: 14,
      },
    });
    const dome = edgeScore({
      ...noModel,
      context: {
        combinedSecPlay: null,
        windMph: null,
        dome: true,
        spread: -28,
        fhPrior: 26,
      },
    });
    expect(dome.score).toBe(33);
    expect(dome.score).toBeLessThan(windy.score);
  });
  it("Hard Rock price beats fair → EDGE / gap, price-only action, at most 55", () => {
    const e = edgeScore({
      ...noModel,
      hrLine: 24.5,
      hrUnderPrice: 105,
      ev: 0.03,
      evVerdict: "pos",
      marketFairUnder: 0.5,
    });
    expect(e.score).toBe(43); // 40 + 3
    expect(e.tier).toBe("EDGE");
    expect(e.blocker).toBe("gap");
    expect(e.verdict.priceEdgeOnly).toBe(true);
    expect(e.action).toBe(
      "Price only: Hard Rock pays 3.0% better than the market on this under. No model behind it.",
    );
    expect(e.kill.line).toBeNull();
    expect(e.kill.price).toBe(100);
    expect(e.kill.text).toBe("Not worth it worse than +100.");
  });
  it("price edge on top of a strong context caps at 55", () => {
    const e = edgeScore({
      ...noModel,
      hrLine: 24.5,
      hrUnderPrice: 120,
      ev: 0.12,
      evVerdict: "pos",
      marketFairUnder: 0.5,
      context: {
        combinedSecPlay: 29.5,
        windMph: 16,
        dome: false,
        spread: -3,
        fhPrior: 14,
      },
    });
    expect(e.score).toBe(55);
    expect(e.tier).toBe("EDGE");
    expect(e.blocker).toBe("gap");
  });
});
