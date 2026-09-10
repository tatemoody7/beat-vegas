import { american, fmt } from "@/lib/format";
import type { HomeGame } from "@/lib/homeBoard";

// What the board says before you scroll. It replaces three panels that all
// stated the same fact three different ways (the bankroll strip's "2 / 5 bets",
// the slip's "No bets this week · 2 of 5 used" and the card panel's "This
// week's bets — No bets this week").
//
// Most weeks there is nothing to bet, so the empty state has to be useful
// rather than just empty: it names the best game on the board and what would
// have to change for it to become a bet.

export type AnswerBet = {
  gameId: number;
  matchup: string;
  /** "u30.5 -110", or "no line yet" when Hard Rock has not posted. */
  numbers: string;
};

export type Answer = {
  bets: AnswerBet[];
  /** The best game that is not a bet, and what it needs. Null when none. */
  closest: { gameId: number; matchup: string; action: string } | null;
  used: number;
  cap: number;
};

function matchupOf(g: HomeGame): string {
  return `${g.row.away} @ ${g.row.home}`;
}

function numbersOf(g: HomeGame): string {
  const line = g.check?.hrLine ?? null;
  if (line === null) return "no line yet";
  const price = g.check?.hrUnderPrice ?? null;
  return `u${fmt(line)}${price === null ? "" : ` ${american(price)}`}`;
}

/** Rank ascending, with unranked (kicked off) last. */
function byRank(a: HomeGame, b: HomeGame): number {
  return (
    (a.boardRank ?? Number.POSITIVE_INFINITY) -
    (b.boardRank ?? Number.POSITIVE_INFINITY)
  );
}

/**
 * Pure: the week's answer. A kicked-off game is never a bet and never the
 * closest — it is not a decision any more.
 */
export function buildAnswer(
  games: HomeGame[],
  used: number,
  cap: number,
): Answer {
  const live = games.filter((g) => !g.kickedOff);
  const bets = live
    .filter((g) => g.edge.tier === "BET")
    .sort(byRank)
    .map((g) => ({
      gameId: g.row.gameId,
      matchup: matchupOf(g),
      numbers: numbersOf(g),
    }));

  const next = live.filter((g) => g.edge.tier !== "BET").sort(byRank)[0];
  return {
    bets,
    closest:
      next === undefined
        ? null
        : {
            gameId: next.row.gameId,
            matchup: matchupOf(next),
            action: next.edge.action,
          },
    used,
    cap,
  };
}
