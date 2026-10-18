import { getSeasons } from "@/lib/board";
import { etClock12 } from "@/lib/et";
import {
  buildStatus,
  getBuildHealth,
  getGradeHealth,
  staleness,
} from "@/lib/boardHealth";
import { getHomeBoard, matchesFilters, parseFilters } from "@/lib/homeBoard";
import { getLatestCard } from "@/lib/card";
import { getArmPositions } from "@/lib/armPositions";
import { cardsFor } from "@/lib/research";
import ResearchStrip from "@/app/components/ResearchStrip";
import { resolveSeason } from "@/lib/season";
import { PASS_HEAD } from "@/lib/boardKey";
import { Fragment } from "react";
import CardStatusBanner from "@/app/components/CardStatusBanner";
import OpsBanner from "@/app/components/OpsBanner";
import BoardFilters from "@/app/components/BoardFilters";
import GameRow from "@/app/components/GameRow";
import SeasonFallbackNotice from "@/app/components/SeasonFallbackNotice";
import SeasonSelect from "@/app/components/SeasonSelect";
import WeekSelect from "@/app/components/WeekSelect";
import { BOARD_HONESTY_TEXT } from "@/lib/labels";

export const dynamic = "force-dynamic"; // always read live DB

// The board IS the home page: one rolling week, every game ranked best to
// worst in one list with one line saying what to do. Each row is a LINK to
// /game/[id] — nothing expands in place any more, which is what took a week
// from 11,600px down to a list you can scan.
//
// The answer bar is the only thing above the games: it replaced the bankroll
// strip, the slip header and the card panel headline, all three of which said
// "no bets this week" in three different ways before the first game appeared.
// Nothing follows the last game row, because Tate never scrolls past the board
// (2026-09-10). Since 2026-10-18 (final-2026 plan, D2/D17) nothing is logged
// anywhere: the board is a read-only record, every warning renders for everyone,
// and every rating reads in paper wording.
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
  const all = board.games;
  const results = staleness(await getGradeHealth(season));
  const buildHealth = buildStatus(await getBuildHealth());
  // The card's own health — "paper only, some inputs are missing", "built by
  // hand", "an earlier build". It used to head /results; it belongs here, with
  // the other two banners, because it is a warning about the numbers you are
  // about to bet off, not about a bet already placed (Tate 2026-09-13).
  const card =
    board.week === null ? null : await getLatestCard(season, board.week);
  const filters = parseFilters(sp);
  const games = all.filter((g) => matchesFilters(g, filters));
  const filtered = games.length !== all.length;
  const signals = games.filter(
    (g) => !g.kickedOff && g.hold === null && g.edge.tier === "BET",
  ).length;
  const watched = games.filter(
    (g) => !g.kickedOff && g.edge.tier === "EDGE",
  ).length;
  // A game that has kicked off is not a decision: it drops out of the ranked
  // list into its own group at the end, instead of sitting among the week's
  // bets with no rank.
  const upcoming = games.filter((g) => !g.kickedOff);
  const played = games.filter((g) => g.kickedOff);
  // Held (BETTING_POLICY, B3 2026-10-14): a failed input on the scheduled
  // build touched these; paper only until a clean build, in their own group.
  const held = upcoming.filter((g) => g.hold === "degraded");
  // One list in rank order (Tate 2026-10-15, Q2): `games` is already in the
  // order assignBoardRanks numbered, so #1 comes first; each row keeps its day
  // and kickoff. Pass rows sort last (their score is under the amber band) and
  // get one heading instead of the same sentence on every row (Q4).
  const ranked = upcoming.filter((g) => g.hold !== "degraded");
  const firstPass = ranked.findIndex((g) => g.edge.tier === "PASS");

  return (
    <div className="mx-auto max-w-5xl">
      {/* One slim line (Tate 2026-10-15, Q1): what this is and where the
          research stands, then straight to the games. It reads the stored
          Monday row and never changes a rating. */}
      <ResearchStrip cards={cardsFor(await getArmPositions())} />

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

      <SeasonFallbackNotice fallbackFrom={fallbackFrom} season={season} />

      {/* Audit 2026-10-17 (Tate): the rank is the model's view, green is only a
          paper signal, and the model has trailed Hard Rock's line this season
          (280 graded games, 8.9 vs 8.4 points a game; the query is in
          CLAUDE.md). Re-check this sentence at each Monday read. */}
      <p
        data-testid="board-honesty"
        className="mb-3 max-w-3xl text-xs leading-relaxed text-[var(--text-dim)]"
      >
        {BOARD_HONESTY_TEXT}
      </p>

      {/* The bar line and the key line went 2026-10-16 (Tate): the badges
          and each row's sentence say it; the page reads cleaner without. */}
      <div className="mb-3">
        <BoardFilters current={filters} />
      </div>

      {/* The build and ops warnings render for everyone (2026-10-18, D17):
          a research record shows its own state. */}
      <CardStatusBanner card={card} />

      <OpsBanner />

      {buildHealth.missed && (
        <div className="bv-card mb-4 border-l-2 border-[var(--bad)] p-4 text-sm text-[var(--text-muted)]">
          <p className="font-medium text-[var(--text)]">
            {`${buildHealth.day}'s build did not run.`}
          </p>
          <p className="mt-1">
            {`A build is also the week's line sweep, so the numbers below are older than they should be`}
            {buildHealth.lastBuiltAt
              ? ` — the last card was built ${etClock12(buildHealth.lastBuiltAt)}.`
              : `.`}
          </p>
        </div>
      )}

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
            {`The week has not been scored yet. Until it is, the ranking comes from pace, weather, the spread and last season’s first halves, so a rating this week is a price rating, not a model rating.`}
          </p>
        </div>
      )}

      {board.noHrLine && board.games.length > 0 && (
        <div className="bv-card mb-4 border-l-2 border-[var(--accent)] p-4 text-sm text-[var(--text-muted)]">
          <p className="font-medium text-[var(--text)]">
            Hard Rock has not posted first-half lines yet.
          </p>
          <p className="mt-1">
            {`First-half totals usually post later in the week. Each game says the line and price that would make it a paper signal.`}
          </p>
        </div>
      )}

      {board.games.length === 0 ? (
        <p className="bv-card p-6 text-sm text-[var(--text-muted)]">
          {`Nothing on the board for ${season} yet. The week’s lines are swept on Tuesday, Thursday and Friday afternoons and Saturday morning, and the model scores the full week on Sunday.`}
        </p>
      ) : (
        <>
          {/* The tier-count line went with the log path (2026-10-18): the
              badges say it. The pre-filter count stays for the Hard Rock chip. */}
          {filtered && (
            <p className="mb-3 text-sm text-[var(--text-dim)]">
              {`· ${all.length} games before filters`}
            </p>
          )}

          {games.length === 0 ? (
            <p className="bv-card p-5 text-sm text-[var(--text-muted)]">
              {`No games match those filters. Clear a filter to see the rest of the week.`}
            </p>
          ) : (
            <>
              {signals === 0 && watched === 0 && (
                <p className="bv-card mb-4 p-5 text-sm text-[var(--text-muted)]">
                  {`Nothing clears the bar this week: no paper signals, nothing to watch. Zero is a normal week.`}
                </p>
              )}
              {held.length > 0 && (
                <section aria-label="Held">
                  <h2 className="bv-day-head">{`Held · ${held.length}`}</h2>
                  <p className="mb-2 text-xs text-[var(--text-dim)]">
                    An input failed on the latest scheduled build for these
                    games, so they are paper only until a clean build.
                  </p>
                  <div className="flex flex-col gap-3">
                    {held.map((g) => (
                      <GameRow key={g.row.gameId} g={g} />
                    ))}
                  </div>
                </section>
              )}
              {ranked.length > 0 && (
                <section aria-label="Ranked">
                  <div className="flex flex-col gap-3">
                    {ranked.map((g, i) => (
                      <Fragment key={g.row.gameId}>
                        {i === firstPass && (
                          <p
                            aria-label="Pass games"
                            className="bv-day-head mt-3"
                          >
                            {PASS_HEAD}
                          </p>
                        )}
                        <GameRow g={g} />
                      </Fragment>
                    ))}
                  </div>
                </section>
              )}

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
