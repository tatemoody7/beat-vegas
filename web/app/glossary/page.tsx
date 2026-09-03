import Link from "next/link";
import { proxyShareText } from "@/lib/proxy";

// In-app glossary: the plain-English version of docs/GLOSSARY.md. Static TSX
// (Vercel's root is web/, so we don't read ../docs at runtime) — keep the two
// in step when a term changes. The estimated-line share is read from the
// fitted step (lib/proxy.ts) so this page can never drift from the model.

const TERMS: { term: string; body: string }[] = [
  {
    term: "First-half (1H) under",
    body: "A bet that the two teams’ combined points in the first half stay under the sportsbook’s first-half total. The only market we bet real money on.",
  },
  {
    term: "Break-even (52.4%)",
    body: "At the standard −110 price you must win more than 52.4% of your bets to make money. Every win rate on the site is measured against this.",
  },
  {
    term: "Our number (BV line)",
    body: "The model’s own predicted first-half total, built from pace, efficiency, weather and era. By rule it never looks at the Vegas line, so comparing the two means something.",
  },
  {
    term: "Gap",
    body: "The Vegas first-half line minus our number. Positive = Vegas is above us = the game leans under. A very big gap can also mean the model is missing something.",
  },
  {
    term: "Bettable band (1.75+ points)",
    body: "The top ~20% of a season’s gaps — the ranking rule the backtest validated for picking games out. It is not a proven win rate: against a fair estimated line the backtest shows no confirmed edge, and only closing-line value against real lines can prove one. 3.0+ points is the top ~10%. The gap that matters is Hard Rock’s own number minus ours.",
  },
  {
    term: "Margin of error (σ ≈ 12 points)",
    body: "How much any single first half can miss our number by. It is the noise of one game, not a test for an edge — which is why every card says a single game is still close to a coin flip.",
  },
  {
    term: "BET / EDGE / PASS",
    body: "The tier badge on each board card. BET = every rule passes: a model read, Hard Rock’s own posted first-half line 1.75+ points above our number, a live line, and a Hard Rock price no worse than the market. EDGE = something is there but a rule fails. PASS = nothing to act on.",
  },
  {
    term: "Edge score (0–100)",
    body: "The one number the board sorts on. With a model read it starts at 50 and moves 10 points for every point of gap between the line you can bet and our number, then adjusts for Hard Rock’s price (up to 8 points either way), takes 10 off an off-market Hard Rock number and 5 off a starting QB being out. With no model read it is a context-only score — it starts at 40, moves on pace, wind, dome, spread and last season’s first halves, and cannot pass 49 (55 when Hard Rock’s price alone beats the market). It ranks the board; it never overrides the BET rules.",
  },
  {
    term: "EDGE (tier)",
    body: "Not a bet, but worth watching: the card scores 60 or better and still fails one rule — or, in weeks 1–2, Hard Rock’s price beats the market with no model behind it. The card names the rule that is blocking it: no Hard Rock line, an off-market Hard Rock number, a price worse than fair, a starting QB out, or a gap short of 1.75 points.",
  },
  {
    term: "Action line",
    body: "The plain sentence at the bottom of every collapsed card saying what to do right now — bet it at this number and price, wait for a specific number, or pass and why. It is written from the same rules that set the tier, so the two can never disagree.",
  },
  {
    term: "Kill number",
    body: "Where the edge is gone. The line half of it is our number plus the 1.75-point bar, rounded up to the next half point — below that total the bet is no longer in the band. The price half is the worst payout that still clears the market’s fair under price by more than the unavoidable 2% of vig. A card that clears one and not the other is not a bet.",
  },
  {
    term: "Under score (0–100)",
    body: "A second, older model’s lean. 50 = coin flip after the vig; higher = stronger under. It is context on the card, not the ranking.",
  },
  {
    term: "Live line vs estimated line",
    body: `A live line is a first-half total a sportsbook has actually posted. An estimated line is our reference number worked out from the full-game total (about half of it: ${proxyShareText()}) used before books post. We never call BET on an estimate.`,
  },
  {
    term: "Price / fair price / +EV",
    body: "The odds you are paid (e.g. −110). Taking every book’s two-way prices and removing the vig gives the market’s fair price. If Hard Rock pays better than that, the price is +EV (good); worse means you are paying extra vig.",
  },
  {
    term: "Prediction market / exchange",
    body: "Apps like Kalshi, Polymarket and FanDuel Predicts where you trade contracts against other people instead of a bookmaker, so prices carry almost no vig. Legal in Florida, but they don’t offer first-half totals — so we never bet there. Their full-game prices feed the market fair price that Hard Rock is judged against.",
  },
  {
    term: "Line value (CLV)",
    body: "Closing-line value: did the line move your way after you bet? For an under, the total going down after you bet is good. Positive line value over many bets is the earliest sign of a real edge — it shows up long before win rate does.",
  },
  {
    term: "Unit",
    body: "One standard bet. This season 1 unit = $10, flat, on every bet. Profit and loss are shown in units so results read the same regardless of dollars. ROI = units won ÷ units staked.",
  },
  {
    term: "Paper pick",
    body: "A pick logged with nothing at risk (one notional unit, so its record reads in units). It is graded for record and line value like a real bet but kept in a separate record, so it can never flatter your real numbers.",
  },
  {
    term: "Pick reason (model gap / price edge / your call)",
    body: "Why a pick was logged, frozen at the moment you logged it. Model gap = the model had a read and Hard Rock’s number was 1.75+ above ours. Price edge = no model read, only a Hard Rock price better than the market’s fair price. Your call = anything else. Results groups your record by reason so you can see which kind of bet is actually paying.",
  },
  {
    term: "Derived / reference line",
    body: "Before books post first-half totals, we show a reference first-half number worked out from the full-game total. It is not a prediction and not a pick.",
  },
  {
    term: "Factor board (green / red)",
    body: "The story behind a rating: pace, weather, offense and defense levels. Green helps the under, red hurts it, amber means the factor is unproven on real lines. It explains the rating; it never changes it.",
  },
  {
    term: "QB out flag",
    body: "A starting quarterback listed out on Rotowire’s unofficial college injury report. Shown as a warning because the model’s number does not know about it.",
  },
  {
    term: "Proxy-graded backtest",
    body: `Free data has no historical first-half lines, so past seasons were graded against an estimated line (a step share: ${proxyShareText()}; FBS-only). Against that fair estimate the top-20% gap band shows no confirmed edge, so the backtest validates the ranking rule, not a profit. Real lines collected this season are the true test.`,
  },
];

export default function GlossaryPage() {
  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="bv-page-title">Glossary</h1>
      <p className="bv-page-sub mb-5">
        Every term the site uses, in plain English. If a number on a page
        doesn’t make sense, the answer should be here.
      </p>
      <dl className="flex flex-col gap-3">
        {TERMS.map((t) => (
          <div key={t.term} className="bv-card p-4">
            <dt className="text-sm font-semibold text-[var(--text)]">
              {t.term}
            </dt>
            <dd className="mt-1 text-sm text-[var(--text-muted)]">{t.body}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-6 text-xs text-[var(--text-dim)]">
        {`The betting rules themselves live on the `}
        <Link href="/" className="bv-nav-link">
          board
        </Link>
        {` — bankroll strip at the top.`}
      </p>
    </div>
  );
}
