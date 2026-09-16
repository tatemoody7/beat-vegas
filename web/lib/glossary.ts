import { SCORE_BET_MIN, SCORE_WATCH_MIN } from "@/lib/grade";
import { usd } from "@/lib/format";
import { proxyShareText } from "@/lib/proxy";
import {
  BET_GAP_PTS,
  EV_FLOOR_PCT,
  STRONG_GAP_PTS,
  WEEKLY_BET_CAP,
} from "@/lib/verdict";

// Every word and number the site uses, in one line each. Static TS (Vercel's
// root is web/, so we cannot read ../docs at runtime). One line per term is
// the rule since 2026-09-16: the glossary is where a definition lives ONCE, so
// the pages can stop carrying captions.
//
// Copy rule (spec §26): NO NUMBER IS TYPED HERE. Every threshold is read from
// the constant that enforces it, so the copy cannot drift from the rules —
// which is exactly how the old entry came to claim "2% of vig" when the price
// floor was 5%. lib/glossary.test.ts enforces that rule.

export type GlossaryTerm = { term: string; body: string };

export function glossaryTerms(unitUsd: number): GlossaryTerm[] {
  return [
    {
      term: "Rank",
      body: "Where a game sits on this week’s board, best to worst, over every game at once; a kicked-off game has no rank.",
    },
    {
      term: "Score",
      body: `The 0–100 number the rank is built from, from the gap alone: 50 at no gap, ${SCORE_BET_MIN} at a gap of ${BET_GAP_PTS}. ${SCORE_BET_MIN}+ is green, ${SCORE_WATCH_MIN}–${SCORE_BET_MIN - 1} amber, under ${SCORE_WATCH_MIN} red.`,
    },
    {
      term: "Gap",
      body: `The line minus our number, in points; positive leans under. ${BET_GAP_PTS}+ is the band we bet, ${STRONG_GAP_PTS}+ is as large as gaps get.`,
    },
    {
      term: "Our number",
      body: "Our own first-half estimate from pace, efficiency, weather and era. It never sees the sportsbook line.",
    },
    {
      term: "Line basis",
      body: "Which line the gap is measured against: Hard Rock’s, the market’s, or our reference line. Only Hard Rock’s can make a bet.",
    },
    {
      term: "Hard Rock line",
      body: "Hard Rock’s posted first-half total and under price — the only book bettable from Florida.",
    },
    {
      term: "Market line",
      body: "The middle of the other books’ first-half totals, used to judge whether Hard Rock’s line and price are reasonable.",
    },
    {
      term: "Reference line",
      body: `A first-half number worked out from the full-game total (${proxyShareText()}), used before any book posts one. Never a bet.`,
    },
    {
      term: "Price and fair price",
      body: `The odds you are paid, like -110. Strip the vig from every book’s two-way prices and you get the fair price; Hard Rock may be up to ${EV_FLOOR_PCT}% worse than it.`,
    },
    {
      term: "Line value",
      body: "Points the line moved toward us after the bet. For an under the total dropping is good, so +1.0 means the market came a point our way.",
    },
    {
      term: "Unit",
      body: `One bet, always ${usd(unitUsd)}. Results read in units so they compare whatever the dollars are; ROI is units won over units risked.`,
    },
    {
      term: "Paper pick",
      body: "A pick with no money on it, graded exactly like a real bet but kept in its own record so it can never flatter the real one.",
    },
    {
      term: "Weekly cap",
      body: `At most ${WEEKLY_BET_CAP} real-money bets a week, taken in order of gap; anything past it is paper. A ceiling, not a target.`,
    },
    {
      term: "Kill line and kill price",
      body: `Where a bet stops being the bet we rated: our number plus ${BET_GAP_PTS} rounded up to the half point, and the worst odds within ${EV_FLOOR_PCT}% of fair.`,
    },
    {
      term: "Early season",
      body: "A team has played one game or none, so our number rests on very little. The score is real; the evidence behind it is thin.",
    },
    {
      term: "Graded and pending",
      body: "A pick is pending until its game settles, then graded the next morning. Pending bets count as bets but move nothing.",
    },
  ];
}
