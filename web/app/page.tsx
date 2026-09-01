import Link from "next/link";
import { getSeasons } from "@/lib/board";
import { resolveSeason } from "@/lib/season";
import { getThisWeek } from "@/lib/thisWeek";
import { MIN_GAMES_FOR_MODEL } from "@/lib/verdict";
import BankrollStrip from "@/app/components/BankrollStrip";
import SeasonFallbackNotice from "@/app/components/SeasonFallbackNotice";
import SeasonSelect from "@/app/components/SeasonSelect";
import VerdictCard from "@/app/components/VerdictCard";

export const dynamic = "force-dynamic"; // always read live DB

// Landing page: one plain-English verdict per game (BET / WATCH / PASS), how
// sure we are, why, and the bankroll/discipline strip. The full research
// board lives at /board.
export default async function ThisWeekPage({
  searchParams,
}: {
  searchParams: Promise<{ season?: string }>;
}) {
  const seasons = await getSeasons();
  const sp = await searchParams;
  const { season, fallbackFrom } = resolveSeason(seasons, sp.season);
  const tw = await getThisWeek(season);

  const actionable = tw.games.filter((g) => g.verdict.verdict !== "PASS");
  const passes = tw.games.filter((g) => g.verdict.verdict === "PASS");

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="bv-page-title">
            {tw.week !== null ? `This Week · Week ${tw.week}` : "This Week"}
          </h1>
          <p className="bv-page-sub mt-1">
            {`One verdict per game. BET = clear model edge at a fair-or-better Hard Rock price. WATCH = something is there but not enough. PASS = nothing to act on.`}
          </p>
        </div>
        {seasons.length > 0 && (
          <SeasonSelect seasons={seasons} current={season} />
        )}
      </div>

      <SeasonFallbackNotice fallbackFrom={fallbackFrom} season={season} />

      <BankrollStrip b={tw.bankroll} />

      {tw.noModel && (
        <div className="bv-card mb-5 border-l-2 border-[#e0a44a] p-4 text-sm text-[var(--text-muted)]">
          <p className="font-medium text-[var(--text)]">
            No model picks yet this week.
          </p>
          <p className="mt-1">
            {`The model needs both teams to have played ${MIN_GAMES_FOR_MODEL} games this season before it will rate a game, so it sits out weeks 1–2 by design. Until then the only thing worth acting on is a Hard Rock price that beats the rest of the market — those show as WATCH with "price edge only". Anything you bet this week is a price bet, not a model bet.`}
          </p>
        </div>
      )}

      {tw.games.length === 0 ? (
        <p className="bv-card p-6 text-sm text-[var(--text-muted)]">
          {`Nothing on the board for ${season} yet. Lines and verdicts land automatically on Sunday afternoon once the week’s openers post.`}
        </p>
      ) : (
        <>
          <p className="mb-3 text-sm text-[var(--text-dim)]">
            <span className="font-mono font-semibold text-[var(--accent)]">
              {tw.counts.bet}
            </span>
            {` to bet · `}
            <span className="font-mono font-semibold text-[#e0a44a]">
              {tw.counts.watch}
            </span>
            {` to watch · `}
            <span className="font-mono font-semibold text-[var(--text-muted)]">
              {tw.counts.pass}
            </span>
            {` pass · `}
            <Link href="/board" className="bv-nav-link">
              full research board →
            </Link>
          </p>

          {actionable.length === 0 ? (
            <p className="bv-card mb-5 p-5 text-sm text-[var(--text-muted)]">
              {`Nothing clears the bar this week. That is a result, not a failure — passing costs nothing, and the cap is a ceiling, not a target.`}
            </p>
          ) : (
            <div className="mb-6 flex flex-col gap-3.5">
              {actionable.map((g) => (
                <VerdictCard key={g.row.gameId} g={g} />
              ))}
            </div>
          )}

          {passes.length > 0 && (
            <details className="bv-card p-4">
              <summary className="cursor-pointer text-sm font-semibold text-[var(--text)]">
                {`${passes.length} games we pass on`}
                <span className="ml-2 text-xs font-normal text-[var(--text-dim)]">
                  click to see why, one line each
                </span>
              </summary>
              <div className="bv-table-wrap mt-3">
                <table className="bv-table">
                  <thead>
                    <tr>
                      <th>Matchup</th>
                      <th title="The market’s first-half total, or our reference number when none is posted.">
                        1H line
                      </th>
                      <th title="Hard Rock’s first-half total and under price.">
                        Hard Rock
                      </th>
                      <th>Why pass</th>
                    </tr>
                  </thead>
                  <tbody>
                    {passes.map((g) => {
                      const line = g.row.curLine ?? g.row.factors.line ?? null;
                      return (
                        <tr key={g.row.gameId}>
                          <td className="text-[var(--text)]">
                            {`${g.row.away} @ ${g.row.home}`}
                          </td>
                          <td className="font-mono text-[var(--text-muted)]">
                            {line !== null ? line.toFixed(1) : "—"}
                          </td>
                          <td className="font-mono text-[var(--text-muted)]">
                            {g.check?.hrLine != null
                              ? `u${g.check.hrLine.toFixed(1)}${g.check.hrUnderPrice != null ? ` ${g.check.hrUnderPrice > 0 ? "+" : ""}${g.check.hrUnderPrice}` : ""}`
                              : "—"}
                          </td>
                          <td className="text-[var(--text-dim)]">
                            {g.verdict.headline}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </details>
          )}
        </>
      )}
    </div>
  );
}
