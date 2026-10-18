import { describe, expect, it } from "vitest";
import {
  hrQuoteText,
  basisPhrase,
  BLOCKER_SHORT,
  blockerTag,
  CARD_INPUT_TEXT,
  GATE_TEXT,
  labelOf,
  PROXY_TEXT,
  PROVENANCE_TEXT,
  REASON_TEXT,
  RULE_TEXT,
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
      PROVENANCE_TEXT,
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

describe("hrQuoteText", () => {
  it("shows a live Hard Rock number plainly", () => {
    expect(
      hrQuoteText({
        hrLine: 27.5,
        hrUnderPrice: -105,
        hrLive: true,
        hrAsOf: "2026-09-24 20:07:23",
      }),
    ).toBe("u27.5 -105");
  });
  it("dates a held-over main line in ET (naive UTC in, Eastern out)", () => {
    // 20:07 UTC on Thu 2026-09-24 is 4:07pm EDT.
    expect(
      hrQuoteText({
        hrLine: 27.5,
        hrUnderPrice: -105,
        hrLive: false,
        hrAsOf: "2026-09-24 20:07:23.5",
      }),
    ).toBe("u27.5 -105 · as of Thu 4:07pm");
  });
  it("says so when there is no line", () => {
    expect(hrQuoteText(null)).toBe("no line yet");
    expect(hrQuoteText({ hrLine: null, hrUnderPrice: null })).toBe(
      "no line yet",
    );
  });
});
