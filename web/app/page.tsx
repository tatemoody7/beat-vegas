import { getSeasons } from "@/lib/board";
import { buildBetSlip, liveLinesFrom } from "@/lib/betSlip";
import { getLatestCard } from "@/lib/card";
import { SCORE_BET_MIN, SCORE_WATCH_MIN } from "@/lib/grade";
import {
  getHomeBoard,
  groupByDay,
  matchesFilters,
  parseFilters,
  tierCounts,
} from "@/lib/homeBoard";
import { resolveSeason } from "@/lib/season";
import { WEEKLY_BET_CAP } from "@/lib/verdict";
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

// The board IS the home page: one rolling week, grouped by day, every game
// with a coloured 0–100 score and one line saying what to do. Open a card for
// the lines, our number, what is behind it, and the news.
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
  // ?week= is only a request when it is a real week number (empty or 0 = absent).
  const reqWeek = Number(sp.week);
  const weekArg =
    Number.isInteger(reqWeek) && reqWeek > 0 ? reqWeek : undefined;
  // The board settles the week first; the card is then read FOR that week, so
  // a stale card never sits above a different week's games.
  const board = await getHomeBoard(season, weekArg);
  const card = await getLatestCard(season, board.week ?? undefined);
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
  const slipOpen = slip.rows.some(
    (r) => r.kickMinutes === null || r.kickMinutes > 0,
  );

  const filters = parseFilters(sp);
  const games = board.games.filter((g) => matchesFilters(g, filters));
  const counts = tierCounts(games);
  const filtered = games.length !== board.games.length;
  const days = groupByDay(games);

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

      <p className="bv-page-sub mb-4 mt-1">
        {`Every game this week, highest score first. ${SCORE_BET_MIN}+ is a bet, ${SCORE_WATCH_MIN}–${SCORE_BET_MIN - 1} is worth watching, under ${SCORE_WATCH_MIN} is a pass.`}
      </p>

      <SeasonFallbackNotice fallbackFrom={fallbackFrom} season={season} />

      {/* Phone: the graded game list comes first (that is what the site is
          for); the slip and bankroll follow, with a sticky jump to the slip
          when a bet is live. md+: bankroll, slip, card, then the board. */}
      <div className="flex flex-col">
        <div className="order-3 md:order-1">
          <BankrollStrip b={board.bankroll} />
        </div>
        <div className="order-2 md:order-2">
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
        <div className="order-4 md:order-3">
          <CardPanel card={card} />
        </div>

        <div className="order-1 md:order-4">
          <div className="mb-3">
            <BoardFilters current={filters} />
          </div>

          {board.noModel && (
            <div className="bv-card mb-4 border-l-2 border-[var(--warn)] p-4 text-sm text-[var(--text-muted)]">
              <p className="font-medium text-[var(--text)]">
                No model number this week.
              </p>
              <p className="mt-1">
                {`The week has not been scored yet. Until it is, each score comes from pace, weather, the spread and last season’s first halves. Anything you bet this week is a price bet, not a model bet.`}
              </p>
            </div>
          )}

          {board.noHrLine && board.games.length > 0 && (
            <div className="bv-card mb-4 border-l-2 border-[var(--accent)] p-4 text-sm text-[var(--text-muted)]">
              <p className="font-medium text-[var(--text)]">
                Hard Rock has not posted first-half lines yet.
              </p>
              <p className="mt-1">
                {`First-half totals usually post later in the week. Each game says the line and price that would make it a bet.`}
              </p>
            </div>
          )}

          {board.games.length === 0 ? (
            <p className="bv-card p-6 text-sm text-[var(--text-muted)]">
              {`Nothing on the board for ${season} yet. The week’s lines are swept every morning from Tuesday, and the model scores the full week on Sunday.`}
            </p>
          ) : (
            <>
              <p className="mb-1 text-sm text-[var(--text-dim)]">
                <span className="font-mono font-semibold text-[var(--good)]">
                  {counts.bet}
                </span>
                {` bet · `}
                <span className="font-mono font-semibold text-[var(--warn)]">
                  {counts.edge}
                </span>
                {` watch · `}
                <span className="font-mono font-semibold text-[var(--bad)]">
                  {counts.pass}
                </span>
                {` pass`}
                {filtered
                  ? ` · ${board.games.length} games before filters`
                  : ""}
              </p>
              <p className="mb-3 text-xs text-[var(--text-dim)]">
                {`Bet = score ${SCORE_BET_MIN}+. Watch = ${SCORE_WATCH_MIN}–${SCORE_BET_MIN - 1}. Pass = under ${SCORE_WATCH_MIN}.`}
              </p>

              {games.length === 0 ? (
                <p className="bv-card p-5 text-sm text-[var(--text-muted)]">
                  {`No games match those filters. Clear a filter to see the rest of the week.`}
                </p>
              ) : (
                <>
                  {counts.bet === 0 && counts.edge === 0 && (
                    <p className="bv-card mb-4 p-5 text-sm text-[var(--text-muted)]">
                      {`Nothing clears the bar this week. No bets, nothing to watch. Zero bets is a normal week — the ${WEEKLY_BET_CAP}-bet cap is a ceiling, not a target.`}
                    </p>
                  )}
                  {days.map((grp) => (
                    <section key={grp.label} aria-label={grp.label}>
                      <h2 className="bv-day-head">{grp.label}</h2>
                      <div className="flex flex-col gap-3">
                        {grp.games.map((g) => (
                          <GameCard
                            key={g.row.gameId}
                            g={g}
                            unitUsd={board.bankroll.unitUsd}
                          />
                        ))}
                      </div>
                    </section>
                  ))}
                </>
              )}
            </>
          )}
        </div>
      </div>

      {/* Phone only: a sticky jump to the slip while a bet on it is still live. */}
      {card !== null && slipOpen && (
        <a
          href="#bet-slip"
          className="fixed inset-x-0 bottom-0 z-20 flex items-center justify-between border-t border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-sm md:hidden"
        >
          <span className="font-semibold text-[var(--text)]">Bet slip</span>
          <span className="font-mono text-[var(--text-muted)]">
            {`${slip.used} of ${slip.cap} used ↓`}
          </span>
        </a>
      )}
    </div>
  );
}
