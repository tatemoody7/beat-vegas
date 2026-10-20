import { describe, expect, it } from "vitest";
import {
  hrQuoteText,
  hrSeenText,
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
      "Not a paper signal yet: Hard Rock's under price is -125; the rule needs -115 or better",
    );
    expect(blockerTag("no_hr_line")).toBe(
      "Not a paper signal yet: Hard Rock has no first-half line",
    );
    expect(blockerTag("off_market", { hrLine: 23.5, marketLine: 24.5 })).toBe(
      "Not a paper signal yet: Hard Rock's line is 1.0 below the market line",
    );
    expect(blockerTag("gap", { killLine: 24.5 })).toBe(
      "Not a paper signal yet: the line needs to reach 24.5",
    );
    expect(blockerTag("qb_out")).toBe("Starting QB out");
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
  it("keeps the number plain on a held-over main line; the time is separate", () => {
    expect(
      hrQuoteText({
        hrLine: 27.5,
        hrUnderPrice: -105,
        hrLive: false,
        hrAsOf: "2026-09-24 20:07:23.5",
      }),
    ).toBe("u27.5 -105");
  });
  it("says so when there is no line", () => {
    expect(hrQuoteText(null)).toBe("no line yet");
    expect(hrQuoteText({ hrLine: null, hrUnderPrice: null })).toBe(
      "no line yet",
    );
  });
});

describe("hrSeenText", () => {
  it("reads naive UTC as ET, with the zone named", () => {
    // 20:44 UTC on Tue 2026-10-20 is 4:44 PM EDT.
    expect(
      hrSeenText({
        hrLine: 27.5,
        hrUnderPrice: -105,
        hrAsOf: "2026-10-20 20:44:09.5",
      }),
    ).toBe("Tue 4:44 PM ET");
  });
  it("prefers the newest confirmation over the capture", () => {
    expect(
      hrSeenText({
        hrLine: 27.5,
        hrUnderPrice: -105,
        hrAsOf: "2026-10-20 20:44:09",
        hrSeenAt: "2026-10-21 14:05:00",
      }),
    ).toBe("Wed 10:05 AM ET");
  });
  it("shows nothing without a timestamp or a line", () => {
    expect(hrSeenText({ hrLine: 27.5, hrUnderPrice: -105 })).toBeNull();
    expect(
      hrSeenText({ hrLine: 27.5, hrUnderPrice: null, hrAsOf: "garbage" }),
    ).toBeNull();
    expect(
      hrSeenText({
        hrLine: null,
        hrUnderPrice: null,
        hrAsOf: "2026-10-20 20:44:09",
      }),
    ).toBeNull();
    expect(hrSeenText(null)).toBeNull();
  });
});
