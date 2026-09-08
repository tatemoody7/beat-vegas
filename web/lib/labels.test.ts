import { describe, expect, it } from "vitest";
import {
  basisPhrase,
  BLOCKER_SHORT,
  blockerTag,
  CARD_INPUT_TEXT,
  GATE_TEXT,
  labelOf,
  PROXY_TEXT,
  REASON_TEXT,
  RULE_TEXT,
  slipBlockText,
  TIER_TEXT,
} from "./labels";

describe("labelOf", () => {
  it("never echoes an unknown key to the screen", () => {
    expect(labelOf(TIER_TEXT, "EDGE", "?")).toBe("Watch");
    expect(labelOf(TIER_TEXT, "vibes", "?")).toBe("?");
    expect(labelOf(TIER_TEXT, null, "?")).toBe("?");
  });
});

describe("every enum member has text", () => {
  it("blockers, gates, reasons, inputs, rules, proxies", () => {
    for (const m of [
      BLOCKER_SHORT,
      GATE_TEXT,
      CARD_INPUT_TEXT,
      RULE_TEXT,
      PROXY_TEXT,
    ]) {
      for (const [k, v] of Object.entries(m)) {
        expect(v, k).toMatch(/\S/);
        expect(v, k).not.toBe(k);
      }
    }
    for (const [k, v] of Object.entries(REASON_TEXT)) {
      expect(v.long, k).toMatch(/\S/);
      expect(v.short, k).toMatch(/\S/);
    }
  });

  it("EDGE renders as Watch, never as EDGE", () => {
    expect(TIER_TEXT.EDGE).toBe("Watch");
    expect(Object.values(TIER_TEXT)).not.toContain("EDGE");
  });
});

describe("blockerTag", () => {
  it("puts the numbers in the tag, not a tooltip", () => {
    expect(blockerTag("price", { hrPrice: -125, killPrice: -115 })).toBe(
      "Not yet — Hard Rock's price is -125; needs -115 or better",
    );
    expect(blockerTag("no_hr_line")).toBe(
      "Not yet — Hard Rock has no first-half line",
    );
    expect(blockerTag("off_market", { hrLine: 23.5, marketLine: 24.5 })).toBe(
      "Not yet — Hard Rock's line is 1.0 below the market line",
    );
    expect(blockerTag("gap", { killLine: 24.5 })).toBe(
      "Not yet — the line needs to reach 24.5",
    );
    expect(blockerTag("qb_out")).toBe("Starting QB out — recheck");
    expect(blockerTag(null)).toBeNull();
  });
});

describe("slipBlockText", () => {
  it("reads differently for a typed value and a live line", () => {
    expect(
      slipBlockText("kill_line", false, { line: 24, killLine: 24.5 }),
    ).toBe("u24.0 is below the kill line of u24.5 — not the bet we rated.");
    expect(
      slipBlockText("kill_line", true, { liveLine: 24, killLine: 24.5 }),
    ).toBe("Hard Rock is now at u24.0, below the kill line of u24.5.");
    expect(
      slipBlockText("kill_price", false, { price: -125, killPrice: -115 }),
    ).toBe("-125 is worse than the kill price of -115 — not the bet we rated.");
    expect(slipBlockText("cap", false)).toMatch(/already logged this week/);
    expect(slipBlockText("degraded", true)).toMatch(/paper only/);
  });
});

describe("basisPhrase", () => {
  it("names the line the gap is measured against, with the books when it is the market", () => {
    expect(basisPhrase("hardrock")).toBe("vs Hard Rock's line");
    expect(basisPhrase("market", ["DraftKings", "FanDuel"])).toBe(
      "vs the market line (DraftKings, FanDuel)",
    );
    expect(basisPhrase("market")).toBe("vs the market line");
    expect(basisPhrase("reference")).toBe(
      "vs our reference line (from the full-game total)",
    );
    expect(basisPhrase(null)).toBe("");
  });
});
