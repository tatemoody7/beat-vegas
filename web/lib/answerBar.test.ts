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

import { buildAnswer } from "@/lib/answerBar";
import type { HomeGame } from "@/lib/homeBoard";

// Enough of a HomeGame for buildAnswer: it reads kickedOff, edge.tier,
// edge.action, boardRank, picked, row.away/home/gameId and check.hrLine/price.
function game(o: {
  id: number;
  tier: "BET" | "EDGE" | "PASS";
  rank: number | null;
  picked?: boolean;
  kickedOff?: boolean;
  action?: string;
}): HomeGame {
  return {
    row: { gameId: o.id, away: `A${o.id}`, home: `H${o.id}` },
    check: { hrLine: 24.5, hrUnderPrice: -110 },
    edge: {
      tier: o.tier,
      action: o.action ?? "Not yet — needs -110 or better.",
    },
    boardRank: o.rank,
    picked: o.picked ?? false,
    kickedOff: o.kickedOff ?? false,
  } as unknown as HomeGame;
}

describe("buildAnswer — placed bets are marked and sorted below open ones", () => {
  it("puts open bets first by rank, placed ones after, and counts only the open", () => {
    const a = buildAnswer(
      [
        game({ id: 1, tier: "BET", rank: 1, picked: true }),
        game({ id: 2, tier: "BET", rank: 3 }),
        game({ id: 3, tier: "BET", rank: 2 }),
        game({ id: 4, tier: "EDGE", rank: 4 }),
      ],
      1,
      5,
    );
    expect(a.bets.map((b) => b.gameId)).toEqual([3, 2, 1]);
    expect(a.bets.map((b) => b.picked)).toEqual([false, false, true]);
    expect(a.open).toBe(2);
    expect(a.closest.map((c) => c.gameId)).toEqual([4]);
  });
  it("a week with every bet placed has zero open and keeps the placed list", () => {
    const a = buildAnswer(
      [game({ id: 1, tier: "BET", rank: 1, picked: true })],
      1,
      5,
    );
    expect(a.open).toBe(0);
    expect(a.bets).toHaveLength(1);
  });
  it("a kicked-off game is neither a bet nor the closest", () => {
    const a = buildAnswer(
      [game({ id: 1, tier: "BET", rank: null, kickedOff: true })],
      0,
      5,
    );
    expect(a.bets).toEqual([]);
    expect(a.open).toBe(0);
  });
});
