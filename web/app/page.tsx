import { getSeasons } from "@/lib/board";
import { buildAnswer } from "@/lib/answerBar";
import { etClock12 } from "@/lib/et";
import { getGradeHealth, staleness } from "@/lib/gradeHealth";
import {
  getHomeBoard,
  groupByDay,
  matchesFilters,
  parseFilters,
  tierCounts,
} from "@/lib/homeBoard";
import { nextBuild } from "@/lib/nextBuild";
import { resolveSeason } from "@/lib/season";
import { WEEKLY_BET_CAP } from "@/lib/verdict";
import AnswerBar from "@/app/components/AnswerBar";
import BoardFilters from "@/app/components/BoardFilters";
import GameRow from "@/app/components/GameRow";
import SeasonFallbackNotice from "@/app/components/SeasonFallbackNotice";
import SeasonSelect from "@/app/components/SeasonSelect";
import WeekSelect from "@/app/components/WeekSelect";

export const dynamic = "force-dynamic"; // always read live DB

// The board IS the home page: one rolling week, grouped by day, every game
// ranked best to worst with one line saying what to do. Each row is a LINK to
// /game/[id] — nothing expands in place any more, which is what took a week
// from 11,600px down to a list you can scan.
//
// The answer bar is the only thing above the games: it replaced the bankroll
// strip, the slip header and the card panel headline, all three of which said
// "no bets this week" in three different ways before the first game appeared.
// Nothing follows the last game row — the slip, the card and the bankroll all
// live on /slip now, because Tate never scrolls past the board (2026-09-10).
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
  const board = await getHomeBoard(season, weekArg);
  const results = staleness(await getGradeHealth(season));

  const filters = parseFilters(sp);
  const games = board.games.filter((g) => matchesFilters(g, filters));
  const counts = tierCounts(games);
  const filtered = games.length !== board.games.length;
  // A game that has kicked off is not a decision: it drops out of the ranked
  // list into its own group at the end, instead of sitting among the week's
  // bets with no rank.
  const upcoming = games.filter((g) => !g.kickedOff);
  const played = games.filter((g) => g.kickedOff);
  const days = groupByDay(upcoming);
  const answer = buildAnswer(
    board.games,
    board.bankroll.weekBets,
    board.bankroll.cap,
  );
  const build = nextBuild(new Date());

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
        {`Every game this week, ranked best to worst. #1 is the strongest game on the board; the bets are the ones lit up green. Open a game for the numbers behind it.`}
      </p>

      <SeasonFallbackNotice fallbackFrom={fallbackFrom} season={season} />

      <AnswerBar answer={answer} nextBuild={build?.label ?? null} />

      <div className="mb-3">
        <BoardFilters current={filters} />
      </div>

      {results.stale && (
        <div className="bv-card mb-4 border-l-2 border-[var(--bad)] p-4 text-sm text-[var(--text-muted)]">
          <p className="font-medium text-[var(--text)]">
            {`Results are ${results.behindHours} hours behind.`}
          </p>
          <p className="mt-1">
            {`${results.unscored} ${results.unscored === 1 ? "game has" : "games have"} finished without a score landing, so nothing since then is graded`}
            {results.lastGradedAt
              ? ` — the last one was ${etClock12(results.lastGradedAt)}.`
              : `.`}
            {` Anything on this page that depends on results is out of date until the grading job runs clean.`}
          </p>
        </div>
      )}

      {board.noModel && (
        <div className="bv-card mb-4 border-l-2 border-[var(--warn)] p-4 text-sm text-[var(--text-muted)]">
          <p className="font-medium text-[var(--text)]">
            No model number this week.
          </p>
          <p className="mt-1">
            {`The week has not been scored yet. Until it is, the ranking comes from pace, weather, the spread and last season’s first halves. Anything you bet this week is a price bet, not a model bet.`}
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
          {`Nothing on the board for ${season} yet. The week’s lines are swept on Tuesday, Thursday and Friday afternoons and Saturday morning, and the model scores the full week on Sunday.`}
        </p>
      ) : (
        <>
          <p className="mb-3 text-sm text-[var(--text-dim)]">
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
                  {`Nothing clears the bar this week. No bets, nothing to watch. Zero bets is a normal week — the ${WEEKLY_BET_CAP}-bet cap is a ceiling, not a target.`}
                </p>
              )}
              {days.map((grp) => (
                <section key={grp.label} aria-label={grp.label}>
                  <h2 className="bv-day-head">{grp.label}</h2>
                  <div className="flex flex-col gap-3">
                    {grp.games.map((g) => (
                      <GameRow key={g.row.gameId} g={g} />
                    ))}
                  </div>
                </section>
              ))}

              {played.length > 0 && (
                <section aria-label="Played">
                  <h2 className="bv-day-head">{`Played · ${played.length}`}</h2>
                  <div className="flex flex-col gap-3">
                    {played.map((g) => (
                      <GameRow key={g.row.gameId} g={g} />
                    ))}
                  </div>
                </section>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
