import { getBoard, getSeasons } from "@/lib/board";
import { getMovements } from "@/lib/movement";
import { resolveSeason } from "@/lib/season";
import { BET_GAP_PTS } from "@/lib/verdict";
import { defaultWeek, weeksOf } from "@/lib/week";
import OpportunityCard from "@/app/components/OpportunityCard";
import SeasonFallbackNotice from "@/app/components/SeasonFallbackNotice";
import SeasonSelect from "@/app/components/SeasonSelect";
import SortSelect, { type SortKey } from "@/app/components/SortSelect";
import WeekSelect from "@/app/components/WeekSelect";

export const dynamic = "force-dynamic"; // always read live DB

// The research board: every scored game for one week (defaulting to the week
// you are about to bet), the factor story behind each rating, and each game's
// line-movement history as an expandable row.
export default async function BoardPage({
  searchParams,
}: {
  searchParams: Promise<{ season?: string; sort?: string; week?: string }>;
}) {
  const seasons = await getSeasons();
  const sp = await searchParams;
  const { season, fallbackFrom } = resolveSeason(seasons, sp.season);
  const sort: SortKey = sp.sort === "gap" ? "gap" : "rank";

  const all = await getBoard(season);
  const weeks = weeksOf(all);
  const reqWeek = Number(sp.week);
  const week =
    Number.isFinite(reqWeek) && weeks.includes(reqWeek)
      ? reqWeek
      : defaultWeek(all);
  const rows = all.filter((r) => r.week === week);
  if (sort === "gap") {
    // Biggest under-leaning gaps first (Vegas above our number); nulls last.
    rows.sort((a, b) => (b.liveGap ?? -Infinity) - (a.liveGap ?? -Infinity));
  }
  const movements = await getMovements(rows.map((r) => r.gameId));

  // Derived board = posted full-game lines run through our 1H pricing, no model.
  const derivedBoard =
    rows.length > 0 && rows.every((r) => r.factors.line_kind === "derived_fg");

  // Games in the bettable band (not derived, gap at/above the validated cutoff).
  const edgeCount = rows.filter(
    (r) =>
      r.factors.line_kind !== "derived_fg" &&
      r.liveGap !== null &&
      r.liveGap >= BET_GAP_PTS,
  ).length;

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="bv-page-title">
            {week !== null ? `Board · Week ${week}` : "Board"}
          </h1>
          <p className="bv-page-sub mt-1">
            {derivedBoard
              ? "Reference first-half lines from the posted full-game totals — not model picks"
              : "First-half games we lean under, best first · under score 0–100 (50 = coin flip) · open a card’s line movement to see how each book has moved"}
          </p>
          {!derivedBoard && rows.length > 0 && (
            <p className="mt-2 text-sm text-[var(--text-dim)]">
              <span className="font-mono font-semibold text-[var(--text)]">
                {rows.length}
              </span>
              {` games`}
              <span className="mx-2 text-[var(--border)]">·</span>
              <span className="font-mono font-semibold text-[var(--accent)]">
                {edgeCount}
              </span>
              {` in the bettable band (vs the market consensus — the This Week verdict uses Hard Rock’s own number)`}
            </p>
          )}
        </div>
        <div className="bv-toolbar flex flex-wrap items-center gap-3">
          <SortSelect current={sort} />
          {weeks.length > 0 && week !== null && (
            <WeekSelect weeks={weeks} current={week} />
          )}
          {seasons.length > 0 && (
            <SeasonSelect seasons={seasons} current={season} />
          )}
        </div>
      </div>

      <SeasonFallbackNotice fallbackFrom={fallbackFrom} season={season} />

      {rows.length === 0 ? (
        <p className="bv-card p-6 text-sm text-[var(--text-muted)]">
          {`Nothing on the board for ${season} yet. It fills in automatically on Sunday afternoon once the week’s opening lines post.`}
        </p>
      ) : (
        <div className="flex flex-col gap-3.5">
          {rows.map((row) => (
            <OpportunityCard
              key={row.gameId}
              row={row}
              movement={movements.get(row.gameId) ?? null}
            />
          ))}
        </div>
      )}
    </div>
  );
}
