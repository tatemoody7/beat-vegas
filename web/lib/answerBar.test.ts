import { describe, expect, it } from "vitest";
import { shortNeed } from "@/lib/answerBar";

// The answer bar prints the price beside the game, so repeating the first half
// of edge.action ("Hard Rock's price is -125") would say it twice.

describe("shortNeed", () => {
  it("keeps only the needs clause", () => {
    expect(
      shortNeed("Not yet — Hard Rock’s price is -125; needs -120 or better."),
    ).toBe("needs -120 or better");
  });

  it("handles a plus price", () => {
    expect(
      shortNeed("Not yet — Hard Rock’s price is -105; needs +100 or better."),
    ).toBe("needs +100 or better");
  });

  it("falls back to the whole line when there is no needs clause", () => {
    const s =
      "Not yet — Hard Rock has no first-half line. It becomes a bet at under 26.0 or higher.";
    expect(shortNeed(s)).toBe(s);
  });

  it("leaves a pass sentence alone", () => {
    const s = "Pass: the line is 0.8 below our number, so this leans over.";
    expect(shortNeed(s)).toBe(s);
  });
});
