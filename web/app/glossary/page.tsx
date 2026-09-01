import Link from "next/link";

// In-app glossary: the plain-English version of docs/GLOSSARY.md. Static TSX
// (Vercel's root is web/, so we don't read ../docs at runtime) — keep the two
// in step when a term changes.

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
    body: "The top ~20% of a season’s gaps. In the backtest that group went under about 54% of the time — a small edge over the 52.4% break-even. 3.0+ points is the top ~10%.",
  },
  {
    term: "Margin of error (σ ≈ 12 points)",
    body: "How much any single first half can miss our number by. It is the noise of one game, not a test for an edge — which is why every card says a single game is still close to a coin flip.",
  },
  {
    term: "BET / WATCH / PASS",
    body: "The This Week verdict. BET = bettable gap, a real (live) first-half line, and a Hard Rock price no worse than the market. WATCH = a smaller lean, a good price on its own, or a bettable gap against an estimated line. PASS = nothing to act on.",
  },
  {
    term: "Under score (0–100)",
    body: "A second, older model’s lean. 50 = coin flip after the vig; higher = stronger under. It is context on the card, not the ranking.",
  },
  {
    term: "Live line vs estimated line",
    body: "A live line is a first-half total a sportsbook has actually posted. An estimated line is our reference number (about 52% of the full-game total) used before books post. We never call BET on an estimate.",
  },
  {
    term: "Price / fair price / +EV",
    body: "The odds you are paid (e.g. −110). Taking every book’s two-way prices and removing the vig gives the market’s fair price. If Hard Rock pays better than that, the price is +EV (good); worse means you are paying extra vig.",
  },
  {
    term: "Line value (CLV)",
    body: "Closing-line value: did the line move your way after you bet? For an under, the total going down after you bet is good. Positive line value over many bets is the earliest sign of a real edge — it shows up long before win rate does.",
  },
  {
    term: "Unit",
    body: "One standard bet. This season 1 unit = $10, flat, on every bet. Profit and loss are shown in units so results read the same regardless of dollars.",
  },
  {
    term: "Paper pick",
    body: "A pick logged with nothing at risk. It is graded for record and line value like a real bet but kept in a separate record, so it can never flatter your real numbers.",
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
    body: "A starting quarterback listed out on ESPN’s unofficial injury feed. Shown as a warning because the model’s number does not know about it.",
  },
  {
    term: "Proxy-graded backtest",
    body: "Free data has no historical first-half lines, so past seasons were graded against an estimated line (52% of the full-game total). That makes the backtest directional, not proof. Real lines collected this season are the true test.",
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
        The betting rules themselves live in{" "}
        <Link href="/" className="bv-nav-link">
          This Week
        </Link>
        {" — bankroll strip at the top."}
      </p>
    </div>
  );
}
