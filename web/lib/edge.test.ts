import { describe, expect, it } from "vitest";
import { americanToDecimal, devigTwoWay, evUnder } from "./devig";
import {
  FAIR_EV_FLOOR,
  breakEvenPrice,
  contextScore,
  edgeScore,
  roundHalfUp,
  type EdgeInput,
} from "./edge";
import { evVerdictFor } from "./lineCheck";

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
  it("is the worst 5-cent American price that keeps EV >= FAIR_EV_FLOOR (-0.05)", () => {
    expect(FAIR_EV_FLOOR).toBe(-0.05);
    const p = breakEvenPrice(0.52);
    expect(p).toBe(-120); // -120 is -4.7%; -125 is -6.4%
    expect(evUnder(0.52, p!)).toBeGreaterThanOrEqual(FAIR_EV_FLOOR);
    expect(evUnder(0.52, p! - 5)).toBeLessThan(FAIR_EV_FLOOR);
    // A balanced market tolerates standard juice and nothing more.
    expect(breakEvenPrice(0.5)).toBe(-110); // -110 is -4.5%; -115 is -6.5%
    expect(breakEvenPrice(0.55)).toBe(-135); // -135 is -4.3%; -140 is -5.7%
  });
  it("never returns -100 (that is +100)", () => {
    // fair 0.48: +100 is -4.0% (inside), -105 is -6.3% (outside) — the step
    // between them must be +100, not the non-price -100.
    expect(breakEvenPrice(0.48)).toBe(100);
    expect(evUnder(0.48, 100)).toBeGreaterThanOrEqual(FAIR_EV_FLOOR);
    expect(evUnder(0.48, -105)).toBeLessThan(FAIR_EV_FLOOR);
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
    expect(e.score).toBe(82); // 50 + 27 + round(1.2)
    expect(e.tier).toBe("BET");
    expect(e.blocker).toBeNull();
    expect(e.action).toBe(
      "Bet one unit: first-half under 24.5 at -105 on Hard Rock.",
    );
    expect(e.verdict.verdict).toBe("BET");
    expect(e.kill.line).toBe(24);
    expect(e.kill.price).toBe(-120); // fair 0.52: -120 is -4.7%, -125 is -6.4%
    expect(e.kill.text).toBe(
      "No longer a bet below u24.0, or at a worse price than -120.",
    );
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
    expect(e.score).toBe(81);
    expect(e.tier).toBe("EDGE");
    expect(e.blocker).toBe("no_hr_line");
    expect(e.action).toBe(
      "Not yet — Hard Rock has no first-half line. It becomes a bet at under 24.0 or higher.",
    );
    expect(e.kill.price).toBeNull();
    expect(e.kill.text).toBe("No longer a bet below u24.0.");
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
    expect(e.score).toBe(73);
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
    expect(e.score).toBe(65);
    expect(e.tier).toBe("EDGE");
    expect(e.blocker).toBe("off_market");
    expect(e.verdict.verdict).toBe("WATCH");
    expect(e.action).toBe(
      "Not yet — Hard Rock’s 24.0 is 2.0 below the market line of 26.0. You would be giving up points, and Hard Rock can void a bet that far off the market. Bet it if Hard Rock moves to 25.5 or higher.",
    );
  });
  it("Hard Rock within half a point of the market is not off-market", () => {
    const e = edgeScore({ ...base, liveLine: 25, marketLine: 25, gap: 3.2 });
    expect(e.tier).toBe("BET");
    expect(e.score).toBe(82);
  });
  it("price too high → EDGE / price with a computed break-even", () => {
    const ev = evUnder(0.52, -125); // ≈ -0.064, below the -0.05 floor
    expect(ev).toBeLessThan(FAIR_EV_FLOOR);
    const e = edgeScore({
      ...base,
      hrUnderPrice: -125,
      ev,
      evVerdict: evVerdictFor(ev),
    });
    expect(e.score).toBe(75); // 77 + clamp(round(-6.4)) = 77 - 6
    expect(e.tier).toBe("EDGE");
    expect(e.blocker).toBe("price");
    expect(e.verdict.verdict).toBe("WATCH");
    expect(e.action).toBe(
      "Not yet — Hard Rock’s price is -125; needs -120 or better.",
    );
    expect(e.kill.price).toBe(-120);
  });
  it("price too high with no market fair price asks for a fair price", () => {
    const e = edgeScore({
      ...base,
      hrUnderPrice: -125,
      ev: -0.064,
      evVerdict: "neg",
      marketFairUnder: null,
    });
    expect(e.blocker).toBe("price");
    expect(e.action).toBe(
      "Not yet — Hard Rock’s price is -125; needs -110 or better.",
    );
    expect(e.kill.price).toBeNull();
  });
  it("price bonus is clamped to ±8", () => {
    const hi = edgeScore({ ...base, ev: 0.2, evVerdict: "pos" });
    expect(hi.score).toBe(89); // 77 + 8
    const lo = edgeScore({ ...base, ev: -0.2, evVerdict: "neg" });
    expect(lo.score).toBe(73); // 77 - 8
  });
  it("no comparable price (ev null) → EDGE / no_fair_price, paper-only action", () => {
    // Hard Rock alone at its number: gap 2.7 clears, nothing prices 24.5.
    const e = edgeScore({
      ...base,
      ev: null,
      evVerdict: "na",
      marketFairUnder: null,
    });
    expect(e.score).toBe(81); // no price bonus without an ev
    expect(e.tier).toBe("EDGE");
    expect(e.blocker).toBe("no_fair_price");
    expect(e.verdict.verdict).toBe("WATCH");
    expect(e.action).toBe(
      "Not yet — no other book is at 24.5, so -105 cannot be compared. Paper only until one is.",
    );
    expect(e.kill.price).toBeNull();
    // unpriced Hard Rock line: same gate, "hasn't priced" wording (not a false
    // "no other book is priced" claim)
    const u = edgeScore({
      ...base,
      hrUnderPrice: null,
      ev: null,
      evVerdict: "na",
      marketFairUnder: null,
    });
    expect(u.blocker).toBe("no_fair_price");
    expect(u.action).toContain(
      "Hard Rock has not priced its 24.5 under. Paper only until it does.",
    );
    // Gate order: no_fair_price is named before qb_out (transient news) ...
    const both = edgeScore({
      ...base,
      ev: null,
      evVerdict: "na",
      marketFairUnder: null,
      qbOut: true,
    });
    expect(both.blocker).toBe("no_fair_price");
    // ... and after off_market (a market read on Hard Rock's number).
    const off = edgeScore({
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
    expect(off.blocker).toBe("off_market");
  });
  it("QB out → EDGE / qb_out (−5) when the gap is short of the bar", () => {
    // A judgeable fair price (ev 0) so the QB gate, not no_fair_price, is named.
    const e = edgeScore({
      ...base,
      hrLine: 23.3,
      liveLine: 23.3,
      marketLine: 23.3,
      bestLine: 23.3,
      gap: 1.5,
      ev: 0,
      evVerdict: "fair",
      qbOut: true,
      qbOutDetail: "QB1 (knee) out",
    });
    expect(e.score).toBe(62); // 50 + 15 - 5
    expect(e.tier).toBe("EDGE");
    expect(e.blocker).toBe("qb_out");
    expect(e.action).toBe(
      "Starting QB out — recheck. Our number does not know about it.",
    );
  });
  it("QB out on a would-be BET → EDGE / qb_out (verdict WATCH) and costs 5 points", () => {
    // Everything else clears: in-band Hard Rock gap, on-market number, good
    // price. The QB news alone turns the BET into a WATCH the site renders as
    // EDGE with the qb_out blocker (gate order: no_hr_line → off_market →
    // price → qb_out → gap; the first three pass here).
    const e = edgeScore({
      ...base,
      qbOut: true,
      qbOutDetail: "QB1 (knee) out",
    });
    expect(e.tier).toBe("EDGE");
    expect(e.blocker).toBe("qb_out");
    expect(e.score).toBe(77); // 78 - 5
    expect(e.verdict.verdict).toBe("WATCH");
    expect(e.verdict.headline).toBe(
      "Our number clears the bar, but a starting quarterback is listed out and the model does not know it — re-check the number after the news settles.",
    );
    expect(e.verdict.strength).toBe(58 + 2.7 * 10);
    expect(e.action).toBe(
      "Starting QB out — recheck. Our number does not know about it.",
    );
    expect(e.verdict.flags[0]).toMatch(/QB OUT/);
    expect(e.verdict.flags[0]).toContain("QB1 (knee) out");
    // Without the QB news the same row is a BET.
    expect(edgeScore(base).tier).toBe("BET");
  });
  it("-110 at a balanced market passes the price gate; -115 does not", () => {
    // Other books -110/-110 → fair under 0.5. Standard juice is -4.5% (inside
    // the -0.05 floor); a nickel more is -6.5% (outside).
    const fair = devigTwoWay(-110, -110).fairUnder;
    expect(fair).toBeCloseTo(0.5);
    const ev110 = evUnder(fair, -110);
    expect(ev110).toBeCloseTo(-0.0455, 3);
    expect(evVerdictFor(ev110)).toBe("fair");
    const at110 = edgeScore({
      ...base,
      hrUnderPrice: -110,
      ev: ev110,
      evVerdict: evVerdictFor(ev110),
      marketFairUnder: fair,
    });
    expect(at110.tier).toBe("BET");
    expect(at110.blocker).toBeNull();
    expect(at110.kill.price).toBe(-110);
    expect(at110.action).toBe(
      "Bet one unit: first-half under 24.5 at -110 on Hard Rock.",
    );

    const ev115 = evUnder(fair, -115);
    expect(ev115).toBeCloseTo(-0.0652, 3);
    expect(evVerdictFor(ev115)).toBe("neg");
    const at115 = edgeScore({
      ...base,
      hrUnderPrice: -115,
      ev: ev115,
      evVerdict: evVerdictFor(ev115),
      marketFairUnder: fair,
    });
    expect(at115.tier).toBe("EDGE");
    expect(at115.blocker).toBe("price");
    expect(at115.verdict.verdict).toBe("WATCH");
    expect(at115.kill.price).toBe(-110);
    expect(at115.action).toBe(
      "Not yet — Hard Rock’s price is -115; needs -110 or better.",
    );
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
    expect(e.score).toBe(68);
    expect(e.tier).toBe("EDGE");
    expect(e.blocker).toBe("gap");
    expect(e.action).toBe(
      "Pass: the line is 1.5 above our number. It needs 24.0 or higher.",
    );
  });
  it("small gap → Watch (amber band) with blocker gap; a tiny gap → PASS", () => {
    const tiny = edgeScore({
      ...base,
      hrLine: 22.1,
      liveLine: 22.1,
      marketLine: 22.1,
      bestLine: 22.1,
      gap: 0.3,
      ev: null,
      evVerdict: "na",
      marketFairUnder: null,
    });
    expect(tiny.score).toBe(53);
    expect(tiny.tier).toBe("PASS");
    expect(tiny.blocker).toBeNull();
    const e = edgeScore({
      ...base,
      hrLine: 22.5,
      liveLine: 22.5,
      marketLine: 22.5,
      bestLine: 22.5,
      gap: 0.7,
      ev: 0,
      evVerdict: "fair",
      marketFairUnder: 0.5238,
    });
    expect(e.score).toBe(58);
    expect(e.tier).toBe("EDGE");
    expect(e.blocker).toBe("gap");
    expect(e.kill.line).toBe(24);
    expect(e.action).toBe(
      "Pass: the line is 0.7 above our number. It needs 24.0 or higher.",
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
    expect(e.score).toBe(35);
    expect(e.tier).toBe("PASS");
    expect(e.action).toBe(
      "Pass: the line is 1.3 below our number, so this leans over. We only bet unders.",
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
      "Not yet — no first-half line anywhere. It becomes a bet at under 24.0 or higher.",
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
    expect(e.score).toBe(82);
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
      "Pass: no model number yet, and Hard Rock’s price is no better than the market.",
    );
    expect(e.kill.text).toBe("No kill numbers without a model number.");
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
      "Watch: Hard Rock pays about 3.0% more than the market on this under. No model number behind it.",
    );
    expect(e.kill.line).toBeNull();
    expect(e.kill.price).toBe(-110); // fair 0.5: standard juice is the floor
    expect(e.kill.text).toBe("No longer a bet at a worse price than -110.");
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
