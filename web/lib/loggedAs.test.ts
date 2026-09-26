import { describe, expect, it } from "vitest";
import { loggedAs } from "./loggedAs";

describe("loggedAs", () => {
  it("names the verdict, the reason and the gap", () => {
    expect(
      loggedAs({
        verdictAtPick: "BET",
        reason: "model_gap",
        gapAtPick: 3.45,
        isPaper: false,
        blocker: null,
      }),
    ).toBe("Bet · model gap · +3.5 vs our number");
  });

  it("flags real money on a Watch and a paper pick's blocker", () => {
    expect(
      loggedAs({
        verdictAtPick: "WATCH",
        reason: "model_gap",
        gapAtPick: 2.0,
        isPaper: false,
        blocker: null,
      }),
    ).toBe("Watch · model gap · +2.0 vs our number · real money on a Watch");
    expect(
      loggedAs({
        verdictAtPick: "WATCH",
        reason: "model_gap",
        gapAtPick: 3.5,
        isPaper: true,
        blocker: "price",
      }),
    ).toBe(
      "Watch · model gap · +3.5 vs our number · blocked by price too short",
    );
  });

  it("a legacy pick with no snapshot is a dash", () => {
    expect(
      loggedAs({
        verdictAtPick: null,
        reason: null,
        gapAtPick: null,
        isPaper: false,
        blocker: null,
      }),
    ).toBe("—");
  });
});
