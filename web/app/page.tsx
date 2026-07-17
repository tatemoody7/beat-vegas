import { getBoard, getSeasons } from "@/lib/board";
import { resolveSeason } from "@/lib/season";
import OpportunityCard from "@/app/components/OpportunityCard";
import SeasonFallbackNotice from "@/app/components/SeasonFallbackNotice";
import SeasonSelect from "@/app/components/SeasonSelect";
import SortSelect from "@/app/components/SortSelect";

export const dynamic = "force-dynamic"; // always read live DB

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ season?: string; sort?: string }>;
}) {
  const seasons = await getSeasons();
  const sp = await searchParams;
  const { season, fallbackFrom } = resolveSeason(seasons, sp.season);
  const sort = sp.sort === "gap" ? "gap" : sp.sort === "gapz" ? "gapz" : "rank";

  const rows = await getBoard(season);
  if (sort === "gap") {
    // Biggest under-leaning gaps first (Vegas above our number); nulls last.
    rows.sort((a, b) => (b.liveGap ?? -Infinity) - (a.liveGap ?? -Infinity));
  } else if (sort === "gapz") {
    // Noise-adjusted: biggest gaps relative to the BV line's own σ.
    rows.sort((a, b) => (b.liveGapZ ?? -Infinity) - (a.liveGapZ ?? -Infinity));
  }
  // Derived board = posted full-game lines run through our 1H pricing, no model.
  const derivedBoard =
    rows.length > 0 && rows.every((r) => r.factors.line_kind === "derived_fg");

  // Count of games showing a clear edge (not derived, significant gap).
  const edgeCount = rows.filter(
    (r) =>
      r.factors.line_kind !== "derived_fg" &&
      r.liveGapZ !== null &&
      Math.abs(r.liveGapZ) >= 1 &&
      (r.liveGap ?? 0) > 0,
  ).length;

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-[family-name:var(--font-display)] text-3xl font-extrabold tracking-tight text-[var(--text)]">
            Opportunities
          </h1>
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            {derivedBoard
              ? "Reference first-half lines from the posted full-game totals — not model picks"
              : "First-half games we lean under, best first · under score 0–100 (50 = coin flip)"}
          </p>
          {!derivedBoard && rows.length > 0 && (
            <p className="mt-2 text-sm text-[var(--text-dim)]">
              <span className="font-mono font-semibold text-[var(--text)]">
                {rows.length}
              </span>{" "}
              games
              <span className="mx-2 text-[var(--border)]">·</span>
              <span className="font-mono font-semibold text-[var(--accent)]">
                {edgeCount}
              </span>{" "}
              with a clear edge
            </p>
          )}
        </div>
        <div className="bv-toolbar flex flex-wrap items-center gap-3">
          <SortSelect current={sort} />
          {seasons.length > 0 && (
            <SeasonSelect seasons={seasons} current={season} />
          )}
        </div>
      </div>

      <SeasonFallbackNotice fallbackFrom={fallbackFrom} season={season} />

      {rows.length === 0 ? (
        <p className="bv-card p-6 text-sm text-[var(--text-muted)]">
          No predictions for {season}. Score a slate (
          <code className="text-[var(--text)]">scripts/weekly_update.py</code>)
          or point <code className="text-[var(--text)]">DATABASE_URL</code> at a
          DB that has them.
        </p>
      ) : (
        <div className="flex flex-col gap-3.5">
          {rows.map((row) => (
            <OpportunityCard key={row.gameId} row={row} />
          ))}
        </div>
      )}
    </div>
  );
}
