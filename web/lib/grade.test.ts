import { describe, expect, it } from "vitest";
import {
  gradeColor,
  gradeOf,
  gradeWord,
  SCORE_BET_MIN,
  SCORE_WATCH_MIN,
  settledOf,
} from "./grade";

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
