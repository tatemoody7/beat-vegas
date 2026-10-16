import { describe, expect, it } from "vitest";
import {
  gradeColor,
  gradeOf,
  gradeWord,
  SCORE_BET_MIN,
  SCORE_WATCH_MIN,
  settledOf,
} from "./grade";
import { badgeColor, badgeWord, tierColor, TIER_WORD } from "./grade";

describe("gradeOf", () => {
  it("bands 70+ bet, 55–69 watch, under 55 pass, with exact boundaries", () => {
    expect(SCORE_BET_MIN).toBe(70);
    expect(SCORE_WATCH_MIN).toBe(55);
    expect(gradeOf(100)).toBe("bet");
    expect(gradeOf(70)).toBe("bet");
    expect(gradeOf(69)).toBe("watch");
    expect(gradeOf(55)).toBe("watch");
    expect(gradeOf(54)).toBe("pass");
    expect(gradeOf(0)).toBe("pass");
  });

  it("is null without a score", () => {
    expect(gradeOf(null)).toBeNull();
    expect(gradeOf(Number.NaN)).toBeNull();
  });
});

describe("settledOf", () => {
  it("grades the first-half under at the line", () => {
    expect(settledOf(17, 24.5)).toBe("won");
    expect(settledOf(31, 24.5)).toBe("lost");
    expect(settledOf(24, 24)).toBe("push");
  });

  it("is null until both the actual and the line are known", () => {
    expect(settledOf(null, 24.5)).toBeNull();
    expect(settledOf(17, null)).toBeNull();
  });
});

describe("gradeColor / gradeWord", () => {
  it("colours by grade before kickoff", () => {
    expect(gradeColor(74)).toBe("good");
    expect(gradeColor(60)).toBe("warn");
    expect(gradeColor(40)).toBe("bad");
    expect(gradeColor(null)).toBe("push");
    expect(gradeWord(74)).toBe("bet");
    expect(gradeWord(null)).toBe("no score");
  });

  it("colours by the result once settled, whatever the score was", () => {
    expect(gradeColor(74, "lost")).toBe("bad");
    expect(gradeColor(40, "won")).toBe("good");
    expect(gradeColor(74, "push")).toBe("push");
    expect(gradeWord(74, "lost")).toBe("lost");
  });
});

// Q3, 2026-10-15: the badge is coloured by the verdict, and its words never
// claim more than the rule (adjustment 4).
describe("tierColor", () => {
  it("is green for a game meeting the rule, amber for not yet, red for pass", () => {
    expect(tierColor("BET")).toBe("good");
    expect(tierColor("EDGE")).toBe("warn");
    expect(tierColor("PASS")).toBe("bad");
  });

  it("never words green as an edge", () => {
    expect(TIER_WORD.BET).toBe("meets this week's rule");
    for (const w of Object.values(TIER_WORD))
      expect(w).not.toMatch(/edge|value/);
  });
});

// Tate 2026-10-16: the Board's #1-#10 read green; past #10 the verdict colours
// the badge; a game meeting the rule (a lit row) is green wherever it ranks.
describe("badgeColor", () => {
  it("is green for ranks 1-10 whatever the verdict", () => {
    expect(badgeColor("PASS", 1)).toBe("good");
    expect(badgeColor("EDGE", 10)).toBe("good");
  });
  it("past #10 is amber for not yet and red for a pass", () => {
    expect(badgeColor("EDGE", 11)).toBe("warn");
    expect(badgeColor("PASS", 41)).toBe("bad");
    expect(badgeColor("EDGE", null)).toBe("warn");
  });
  it("keeps a game meeting the rule green wherever it ranks", () => {
    expect(badgeColor("BET", 14)).toBe("good");
  });
  it("tells a screen reader why a top-10 badge is green", () => {
    expect(badgeWord("EDGE", 3)).toBe("Board top 10, not yet");
    expect(badgeWord("EDGE", 12)).toBe("not yet");
    expect(badgeWord("BET", 2)).toBe("meets this week's rule");
  });
});
