import { getSeasons } from "@/lib/board";
import { buildBetSlip, liveLinesFrom } from "@/lib/betSlip";
import { getLatestCard } from "@/lib/card";
import {
  getHomeBoard,
  matchesFilters,
  parseFilters,
  tierCounts,
} from "@/lib/homeBoard";
import { resolveSeason } from "@/lib/season";
import { BET_GAP_PTS } from "@/lib/verdict";
import BankrollStrip from "@/app/components/BankrollStrip";
import BetSlip from "@/app/components/BetSlip";
import BoardFilters from "@/app/components/BoardFilters";
import CardStatusBanner from "@/app/components/CardStatusBanner";
import CardPanel from "@/app/components/CardPanel";
import GameCard from "@/app/components/GameCard";
import SeasonFallbackNotice from "@/app/components/SeasonFallbackNotice";
import SeasonSelect from "@/app/components/SeasonSelect";
import WeekSelect from "@/app/components/WeekSelect";

export const dynamic = "force-dynamic"; // always read live DB

// The board IS the home page: every game on the week in one ranked list, best
// spot first, each with an edge score 0–100, a tier, and one line saying what
// to do. Open a card for the lines, the model, the reasons and the news.
export default async function BoardPage({
  searchParams,
}: {
  searchParams: Promise<{
    season?: string;
    week?: string;
    days?: string;
    mine?: string;
    hr?: string;
  }>;
}) {
  const seasons = await getSeasons();
  const sp = await searchParams;
  const { season, fallbackFrom } = resolveSeason(seasons, sp.season);
  const reqWeek = Number(sp.week);
  const weekArg = Number.isFinite(reqWeek) ? reqWeek : undefined;
  // The card read runs alongside the board read. With no ?week= it fetches the
  // season's latest card and keeps it only if it is for the week the board
  // settled on, so a stale card never sits above a different week's games.
  const [board, latestCard] = await Promise.all([
    getHomeBoard(season, weekArg),
    getLatestCard(season, weekArg),
  ]);
  const card =
    latestCard !== null && latestCard.week === board.week ? latestCard : null;
  // The slip reconciles the frozen card against the live Hard Rock numbers
  // this same render loaded, so a moved line or a kill breach shows before
  // the tap, not after the server says no.
  const live = liveLinesFrom(board.games);
  const slip = buildBetSlip(
    card,
    board.weekPicks,
    board.bankroll.cap,
    new Date(),
    live,
  );

  const filters = parseFilters(sp);
  const games = board.games.filter((g) => matchesFilters(g, filters));
  const counts = tierCounts(games);
  const filtered = games.length !== board.games.length;
  // Kept as one string so the phone-collapsed <details> copy and the sm+
  // always-visible copy stay byte-for-byte identical.
  const introCopy = `Every game with a Hard Rock total, best spot first. The score is 0–100 — it ranks the board and nothing else. BET only appears when every rule passes: a model read, Hard Rock’s own first-half number ${BET_GAP_PTS}+ points above ours, a live line, and a price no worse than the market.`;

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-1 flex flex-wrap items-start justify-between gap-3 sm:items-end sm:gap-4">
        <h1 className="bv-page-title">
          {board.week !== null ? `Board · Week ${board.week}` : "Board"}
        </h1>
        <div className="flex flex-wrap items-center gap-3">
          {board.weeks.length > 0 && board.week !== null && (
            <WeekSelect weeks={board.weeks} current={board.week} />
          )}
          {seasons.length > 0 && (
            <SeasonSelect seasons={seasons} current={season} />
          )}
        </div>
      </div>

      {/* Phone: the intro is what pushed the bet slip below the fold, so it
          collapses behind a tap. sm+: always visible, no disclosure control. */}
      <div className="mb-4">
        <p className="bv-page-sub mt-1 hidden sm:block">{introCopy}</p>
        <details className="sm:hidden">
          <summary className="flex min-h-11 cursor-pointer items-center gap-2 text-sm text-[var(--text-muted)]">
            <span>How this works</span>
            <span aria-hidden="true" className="text-xs text-[var(--text-dim)]">
              ▾
            </span>
          </summary>
          <p className="bv-page-sub mt-1">{introCopy}</p>
        </details>
      </div>

      <SeasonFallbackNotice fallbackFrom={fallbackFrom} season={season} />

      {/* Phone: the slip first (it is what Saturday morning is for), bankroll
          under it. md+: bankroll first, then the slip. */}
      <div className="flex flex-col">
        <div className="order-1 md:order-2">
          {card !== null && (
            <>
              <CardStatusBanner card={card} />
              <BetSlip
                slip={slip}
                week={board.week}
                unitUsd={board.bankroll.unitUsd}
              />
            </>
          )}
        </div>
        <div className="order-2 md:order-1">
          <BankrollStrip b={board.bankroll} />
        </div>
      </div>

      <CardPanel card={card} />

      <div className="mb-4">
        <BoardFilters current={filters} />
      </div>

      {board.noModel && (
        <div className="bv-card mb-4 border-l-2 border-[var(--warn)] p-4 text-sm text-[var(--text-muted)]">
          <p className="font-medium text-[var(--text)]">
            No model read this week.
          </p>
          <p className="mt-1">
            {`The week has not been scored yet. Until it is, the cards compare our reference first-half number to the market and score the context (pace, weather, spread, last season’s first halves). Anything you bet this week is a price bet, not a model bet.`}
          </p>
        </div>
      )}

      {board.noHrLine && board.games.length > 0 && (
        <div className="bv-card mb-4 border-l-2 border-[var(--accent)] p-4 text-sm text-[var(--text-muted)]">
          <p className="font-medium text-[var(--text)]">
            Hard Rock has not posted first-half lines yet.
          </p>
          <p className="mt-1">
            {`First-half totals usually post later in the week. Each card says the number and price that would make it a bet, so you know what to watch for.`}
          </p>
        </div>
      )}

      {board.games.length === 0 ? (
        <p className="bv-card p-6 text-sm text-[var(--text-muted)]">
          {`Nothing on the board for ${season} yet. It fills in automatically on Sunday afternoon once the week’s opening lines post.`}
        </p>
      ) : (
        <>
          <p className="mb-3 text-sm text-[var(--text-dim)]">
            <span className="font-mono font-semibold text-[var(--accent)]">
              {counts.bet}
            </span>
            {` bet · `}
            <span className="font-mono font-semibold text-[var(--text)]">
              {counts.edge}
            </span>
            {` edge · `}
            <span className="font-mono font-semibold text-[var(--text-muted)]">
              {counts.pass}
            </span>
            {` pass`}
            {filtered ? ` · ${board.games.length} games before filters` : ""}
          </p>

          {games.length === 0 ? (
            <p className="bv-card p-5 text-sm text-[var(--text-muted)]">
              {`No games match those filters. Clear a filter to see the rest of the week.`}
            </p>
          ) : (
            <>
              {counts.bet === 0 && counts.edge === 0 && (
                <p className="bv-card mb-4 p-5 text-sm text-[var(--text-muted)]">
                  {`Nothing clears the bar this week — no bets, no edges worth watching. That is a result, not a failure: passing costs nothing, and the weekly cap is a ceiling, not a target.`}
                </p>
              )}
              <div className="flex flex-col gap-3">
                {games.map((g) => (
                  <GameCard key={g.row.gameId} g={g} />
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
