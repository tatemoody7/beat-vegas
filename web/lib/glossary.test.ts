import { describe, expect, it } from "vitest";
import { glossaryTerms } from "./glossary";
import { barRule } from "./glossary";
import {
  BET_GAP_PTS,
  EV_FLOOR_PCT,
  STRONG_GAP_PTS,
  WEEKLY_BET_CAP,
} from "./verdict";

describe("glossary", () => {
  const terms = glossaryTerms();

  it("defines every term with a body", () => {
    // Ten since 2026-09-28: one line per word a visitor-facing page uses.
    expect(terms.length).toBe(10);
    for (const t of terms) {
      expect(t.term.trim()).not.toBe("");
      expect(t.body.trim().length).toBeGreaterThan(20);
    }
    expect(new Set(terms.map((t) => t.term)).size).toBe(terms.length);
  });

  it("takes every threshold from the constant that enforces it", () => {
    // Spec §26: no number is TYPED in the glossary. This is the rule that
    // failed before — an entry claimed "2% of vig" while the price floor was
    // 5% — so it is checked rather than trusted.
    const all = terms.map((t) => t.body).join(" ");
    for (const n of [
      BET_GAP_PTS,
      EV_FLOOR_PCT,
      STRONG_GAP_PTS,
      WEEKLY_BET_CAP,
    ]) {
      expect(all).toContain(String(n));
    }
  });

  it("prints no dollar figure (no stake size is public since 2026-09-28)", () => {
    for (const t of terms) expect(t.body).not.toMatch(/\$\d/);
  });
});

// Adjustment 1 (2026-10-15): the bar is per-slate; 1.75 is only the fallback.
describe("barRule", () => {
  it("names the week's bar when there is one, and no number otherwise", () => {
    expect(barRule(1.6, 7)).toBe(
      "The bar is set each week at the top 20% of gaps among games Hard Rock has priced (1.6 in week 7); 1.75 applies only to a week with no priced games.",
    );
    expect(barRule()).not.toMatch(/in week/);
    expect(barRule()).not.toMatch(/band we bet/);
  });
});
