import { describe, expect, it } from "vitest";
import { FACTOR_NOTE, scoringWords } from "./score";

// Q5, 2026-10-15: factors speak of scoring, never of the bet.
describe("scoringWords", () => {
  it("rewrites the old bet words stored in earlier weeks", () => {
    expect(
      scoringWords("Wind 12 mph — helps the under (passing & kicking)."),
    ).toBe("Wind 12 mph — points to less scoring (passing & kicking).");
    expect(scoringWords("Combined pace 25.4s/play — hurts the under.")).toBe(
      "Combined pace 25.4s/play — points to more scoring.",
    );
    expect(scoringWords("0.00in precip — is neutral for the under.")).toBe(
      "0.00in precip — small effect, if any.",
    );
    expect(
      scoringWords("Visitors travel ~1087 miles — unproven for the under."),
    ).toBe("Visitors travel ~1087 miles.");
    expect(
      scoringWords(
        "A 21-point favourite — blowouts score early, works against the under.",
      ),
    ).toBe(
      "A 21-point favourite — blowouts score early, points to more scoring.",
    );
  });

  it("leaves new sentences alone and never mentions the under", () => {
    const s = "Wind 12 mph — points to less scoring (passing & kicking).";
    expect(scoringWords(s)).toBe(s);
    expect(FACTOR_NOTE).toContain("64 factors tested");
    expect(FACTOR_NOTE).not.toMatch(/helps|edge/);
  });
});
