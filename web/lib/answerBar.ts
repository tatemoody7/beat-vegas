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
  /** A real-money ticket is already logged on this game (HomeGame.picked):
   *  rendered muted and sorted below the open bets, because it is done. */
  picked: boolean;
};

export type AnswerNear = {
  gameId: number;
  matchup: string;
  numbers: string;
  /** What would have to change, trimmed to the clause that says it. */
  needs: string;
};

export type Answer = {
  /** Open (unplaced) bets first by rank, then the placed ones. */
  bets: AnswerBet[];
  /** How many of `bets` are still open, i.e. decisions left to make. */
  open: number;
  /** The best games that are not bets yet, best first. */
  closest: AnswerNear[];
  used: number;
  cap: number;
};

/** How many near-misses the bar lists. Three is what fits without the block
 *  turning into a second board. */
export const NEAR_COUNT = 3;

/**
 * Pure: the "needs …" clause of an action line, or the whole line when it does
 * not have one. `edge.action` reads "Not yet — Hard Rock's price is -125; needs
 * -120 or better." and the bar already prints the price beside it, so the first
 * half would be said twice.
 */
export function shortNeed(action: string): string {
  const i = action.toLowerCase().lastIndexOf("needs ");
  if (i < 0) return action;
  return action.slice(i).replace(/\.\s*$/, "");
}

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

/** Open bets before placed ones, each group by rank. */
function openFirst(a: HomeGame, b: HomeGame): number {
  return Number(a.picked) - Number(b.picked) || byRank(a, b);
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
    .sort(openFirst)
    .map((g) => ({
      gameId: g.row.gameId,
      matchup: matchupOf(g),
      numbers: numbersOf(g),
      picked: g.picked,
    }));
  const open = bets.filter((b) => !b.picked).length;

  const closest = live
    .filter((g) => g.edge.tier !== "BET")
    .sort(byRank)
    .slice(0, NEAR_COUNT)
    .map((g) => ({
      gameId: g.row.gameId,
      matchup: matchupOf(g),
      numbers: numbersOf(g),
      needs: shortNeed(g.edge.action),
    }));

  return { bets, open, closest, used, cap };
}
