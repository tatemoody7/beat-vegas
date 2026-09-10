import { SCORE_BET_MIN, SCORE_WATCH_MIN } from "@/lib/grade";
import { usd } from "@/lib/format";
import { proxyShareText } from "@/lib/proxy";
import {
  BET_GAP_PTS,
  EV_FLOOR_PCT,
  STRONG_GAP_PTS,
  WEEKLY_BET_CAP,
} from "@/lib/verdict";

// Every word and number the site uses, in plain English. Static TS (Vercel's
// root is web/, so we cannot read ../docs at runtime).
//
// Copy rule (spec §26): NO NUMBER IS TYPED HERE. Every threshold is read from
// the constant that enforces it, so the copy cannot drift from the rules —
// which is exactly how the old entry came to claim "2% of vig" when the price
// floor was 5%. lib/glossary.test.ts enforces that rule now.

export type GlossaryTerm = { term: string; body: string };

export function glossaryTerms(unitUsd: number): GlossaryTerm[] {
  return [
    {
      term: "Rank",
      body: `Where a game sits on this week’s board, best to worst. #1 is the strongest game of the week. It is ranked on the score, over every game on the board at once, so a day or team filter never changes a game’s number. A game that has kicked off has no rank — it shows Live, then its result.`,
    },
    {
      term: "Score",
      body: `The 0–100 number the rank is built from. It sits inside each card under Our number, and on the Results and Research pages. ${SCORE_BET_MIN} or higher is green and means bet. ${SCORE_WATCH_MIN} to ${SCORE_BET_MIN - 1} is amber and means watch. Under ${SCORE_WATCH_MIN} is red and means pass. The number is the gap alone: 50 at no gap, ${SCORE_BET_MIN} at a gap of ${BET_GAP_PTS}. Hard Rock’s price and anything flagged on the game decide whether it is a bet, not the number.`,
    },
    {
      term: "Gap",
      body: `The line minus our number. Positive means the line is above us, which leans under. ${BET_GAP_PTS} points or more is the band we bet; ${STRONG_GAP_PTS}+ is as large as gaps get. A very large gap can also mean our number is missing something.`,
    },
    {
      term: "Our number",
      body: "Our own estimate of first-half points, built from pace, efficiency, weather and era. It never looks at the sportsbook line, which is what makes comparing the two worth anything.",
    },
    {
      term: "Line basis",
      body: "Which line the gap is measured against, said on every game: Hard Rock’s line, the market line, or our reference line. Only a gap against Hard Rock’s line is a gap you can bet.",
    },
    {
      term: "Hard Rock line",
      body: "Hard Rock’s own posted first-half total and under price. The only book you can bet from Florida, so it is the only line that can make something a bet.",
    },
    {
      term: "Market line",
      body: "The middle of the first-half totals the other books have posted — DraftKings, FanDuel and the rest. Used to judge whether Hard Rock’s line and price are reasonable.",
    },
    {
      term: "Reference line",
      body: `A first-half number worked out from the posted full-game total (${proxyShareText()}), used before any book posts a first-half line. Not a prediction, and never a bet.`,
    },
    {
      term: "Price and fair price",
      body: `The price is the odds you are paid, like -110. Take every book’s two-way prices, strip the vig, and you get the fair price. Hard Rock is judged against that. We allow Hard Rock’s price to be up to ${EV_FLOOR_PCT}% worse than fair, which lets standard -110 juice through and rejects -125.`,
    },
    {
      term: "Line value",
      body: "Whether the line moved your way after you bet. For an under, the total going down afterwards is good. Positive line value over many bets shows up long before a win rate does.",
    },
    {
      term: "Unit",
      body: `One bet. Every bet is the same size: ${usd(unitUsd)}, always. Results are shown in units so they read the same whatever the dollars are. ROI = units won divided by units risked.`,
    },
    {
      term: "Paper pick",
      body: "A pick logged with no money on it. Graded for record and line value exactly like a real bet, but kept in its own record so it can never flatter the real one.",
    },
    {
      term: "Weekly cap",
      body: `At most ${WEEKLY_BET_CAP} real-money bets a week, taken in order of gap. Anything past that is logged as paper. The cap is a ceiling, not a target — zero bets is a normal week.`,
    },
    {
      term: "Kill line and kill price",
      body: `Where a bet stops being the bet we rated. The kill line is our number plus the ${BET_GAP_PTS}-point bar, rounded up to the next half point — below that total it is out of the band. The kill price is the worst odds that still clear the fair price by no more than ${EV_FLOOR_PCT}%. Miss either one and it is not a bet.`,
    },
    {
      term: "Early season",
      body: "A tag on games where a team has only played one game. Our number is built from very little, so read the score loosely. The model scores every game — it does not sit weeks out — so an early-season score is a real score with thin evidence behind it.",
    },
    {
      term: "Graded and pending",
      body: "A pick is pending until the game is played and settled, then graded. Games are graded the morning after they are played. Pending bets count in the bet count but do not move the bankroll or the record.",
    },
  ];
}
