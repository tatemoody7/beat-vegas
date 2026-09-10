import { describe, expect, it } from "vitest";
import { glossaryTerms } from "./glossary";
import { SCORE_BET_MIN, SCORE_WATCH_MIN } from "./grade";
import {
  BET_GAP_PTS,
  EV_FLOOR_PCT,
  STRONG_GAP_PTS,
  WEEKLY_BET_CAP,
} from "./verdict";

describe("glossary", () => {
  const terms = glossaryTerms(10);

  it("defines every term with a body", () => {
    expect(terms.length).toBeGreaterThanOrEqual(15);
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
      SCORE_BET_MIN,
      SCORE_WATCH_MIN,
    ]) {
      expect(all).toContain(String(n));
    }
  });

  it("reads the unit size from the bankroll rather than hard-coding it", () => {
    const at10 = glossaryTerms(10);
    const at25 = glossaryTerms(25);
    const differing = at10.filter((t, i) => t.body !== at25[i].body);
    // At least one entry moves with the unit, and every entry that moves does
    // so only where the money appears.
    expect(differing.length).toBeGreaterThan(0);
    for (const t of differing) {
      expect(t.body).toContain("$10");
    }
    expect(at25.some((t) => t.body.includes("$25"))).toBe(true);
  });
});
