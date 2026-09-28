import { usd } from "@/lib/format";
import {
  BET_GAP_PTS,
  EV_FLOOR_PCT,
  STRONG_GAP_PTS,
  WEEKLY_BET_CAP,
} from "@/lib/verdict";

// Every word the site uses on a visitor, in one line each. Static TS (Vercel's
// root is web/, so we cannot read ../docs at runtime). One line per term is
// the rule since 2026-09-16: the glossary is where a definition lives ONCE, so
// the pages can stop carrying captions. Trimmed 16 → 9 on 2026-09-28: Rank,
// Score, Line basis, Reference line, Kill line, Early season and Graded and
// pending named things no visitor-facing page shows; Plausibly was added
// because it sits under every big number and was defined nowhere.
//
// Copy rule (spec §26): NO NUMBER IS TYPED HERE. Every threshold is read from
// the constant that enforces it, so the copy cannot drift from the rules —
// which is exactly how the old entry came to claim "2% of vig" when the price
// floor was 5%. lib/glossary.test.ts enforces that rule.

export type GlossaryTerm = { term: string; body: string };

export function glossaryTerms(unitUsd: number): GlossaryTerm[] {
  return [
    {
      term: "Gap",
      body: `The line minus our number, in points; positive leans under. ${BET_GAP_PTS}+ is the band we bet, ${STRONG_GAP_PTS}+ is as large as gaps get.`,
    },
    {
      term: "Our number",
      body: "Our own first-half estimate from pace, efficiency, weather and era. It never sees the sportsbook line.",
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
      term: "Plausibly",
      body: "The range the true win rate could sit in, given how few bets there are. It narrows as bets add up.",
    },
  ];
}
