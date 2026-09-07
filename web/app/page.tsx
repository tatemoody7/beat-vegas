import { getSeasons } from "@/lib/board";
import { buildBetSlip } from "@/lib/betSlip";
import { getLatestCard } from "@/lib/card";
import {
  getHomeBoard,
  matchesFilters,
  parseFilters,
  tierCounts,
} from "@/lib/homeBoard";
import { resolveSeason } from "@/lib/season";
import { BET_GAP_PTS, MIN_GAMES_FOR_MODEL } from "@/lib/verdict";
import BankrollStrip from "@/app/components/BankrollStrip";
import BetSlip from "@/app/components/BetSlip";
import BoardFilters from "@/app/components/BoardFilters";
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
  const slip = buildBetSlip(card, board.weekPicks, board.bankroll.cap);

  const filters = parseFilters(sp);
  const games = board.games.filter((g) => matchesFilters(g, filters));
  const counts = tierCounts(games);
  const filtered = games.length !== board.games.length;

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="bv-page-title">
            {board.week !== null ? `Board · Week ${board.week}` : "Board"}
          </h1>
          <p className="bv-page-sub mt-1">
            {`Every game with a Hard Rock total, best spot first. The score is 0–100 — it ranks the board and nothing else. BET only appears when every rule passes: a model read, Hard Rock’s own first-half number ${BET_GAP_PTS}+ points above ours, a live line, and a price no worse than the market.`}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {board.weeks.length > 0 && board.week !== null && (
            <WeekSelect weeks={board.weeks} current={board.week} />
          )}
          {seasons.length > 0 && (
            <SeasonSelect seasons={seasons} current={season} />
          )}
        </div>
      </div>

      <SeasonFallbackNotice fallbackFrom={fallbackFrom} season={season} />

      <BankrollStrip b={board.bankroll} />

      {card !== null && <BetSlip slip={slip} week={board.week} />}

      <CardPanel card={card} />

      <div className="mb-4">
        <BoardFilters current={filters} />
      </div>

      {board.noModel && (
        <div className="bv-card mb-4 border-l-2 border-[#e0a44a] p-4 text-sm text-[var(--text-muted)]">
          <p className="font-medium text-[var(--text)]">
            No model read this week.
          </p>
          <p className="mt-1">
            {`The model needs both teams to have played ${MIN_GAMES_FOR_MODEL} games this season, so it sits out weeks 1–2 by design. Until then the cards compare our reference first-half number to the market and score the context (pace, weather, spread, last season’s first halves). Anything you bet this week is a price bet, not a model bet.`}
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
