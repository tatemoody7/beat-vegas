import Link from "next/link";
import { BREAKEVEN_PCT } from "@/lib/lineStudy";

export const metadata = { title: "How much to trust this — Beat Vegas" };

// The honesty caveat, said once. Every other page links here instead of
// repeating it. Static: no database read.

const SIGMA_PTS = 12; // typical miss of our number on one first half, in points

export default function TrustPage() {
  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="bv-page-title">How much to trust this</h1>
      <div className="mt-4 space-y-4 text-sm leading-6 text-[var(--text-muted)]">
        <p>Beat Vegas rates one market: the first-half under.</p>
        <p>
          Our number is a model estimate of first-half points. It never sees the
          sportsbook line, so comparing the two is a real comparison. The gap
          between them is how we rank games.
        </p>
        <p>
          {`We cannot prove the gap makes money. Free historical data has no first-half lines, so past seasons were graded against an estimated line. Against that estimate, the biggest gaps did not clear the break-even rate you need at -110 (${BREAKEVEN_PCT}%). The backtest supports the ordering of games, not a profit.`}
        </p>
        <p>
          {`One first half is close to a coin flip. Our number misses a typical game by about ${SIGMA_PTS} points, far more than any gap. A score only means something across hundreds of bets.`}
        </p>
        <p>
          So the real test is the live record: Hard Rock’s actual lines, the
          bets you log, and line value. It is on{" "}
          <Link
            href="/results"
            className="text-[var(--accent)] hover:underline"
          >
            Results
          </Link>
          . Until that record is large, read every score as an opinion with a
          number on it.
        </p>
      </div>
    </div>
  );
}
