import { getSeasons } from "@/lib/board";
import { BREAKEVEN_PCT, getLineStudy } from "@/lib/lineStudy";
import { resolveSeason } from "@/lib/season";
import LineStudyView from "@/app/components/LineStudyView";
import SeasonFallbackNotice from "@/app/components/SeasonFallbackNotice";
import SeasonSelect from "@/app/components/SeasonSelect";
import MinGamesSelect from "@/app/components/MinGamesSelect";

export const dynamic = "force-dynamic";

export default async function LineStudyPage({
  searchParams,
}: {
  searchParams: Promise<{ season?: string; minGames?: string }>;
}) {
  const seasons = await getSeasons();
  const sp = await searchParams;
  const { season, fallbackFrom } = resolveSeason(seasons, sp.season);
  const minGames = sp.minGames ? Number(sp.minGames) : 30;

  const { buckets, anyReal } = await getLineStudy(season, minGames);

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="bv-page-title">Line Study</h1>
          <p className="bv-page-sub">
            Which opening first-half lines hit the under most often — {season}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <MinGamesSelect current={minGames} />
          {seasons.length > 0 && (
            <SeasonSelect seasons={seasons} current={season} />
          )}
        </div>
      </div>

      <p className="mb-4 text-xs text-[var(--text-dim)]">
        Grouped by{" "}
        <span className="text-[var(--text-muted)]">
          {anyReal
            ? "real opening lines"
            : "estimated lines (0.52 × full-game total)"}
        </span>
        . You need to win {BREAKEVEN_PCT}% to break even at −110.
        {!anyReal &&
          " ⚠️ On estimated lines this ranking partly reflects how high-scoring the" +
            " games are, not a standalone signal you can bet — treat it as a hint" +
            " until real lines build up."}
      </p>

      <SeasonFallbackNotice fallbackFrom={fallbackFrom} season={season} />

      {buckets.length === 0 ? (
        <p className="bv-card p-6 text-sm text-[var(--text-muted)]">
          {/* One template literal — Next 16 dev can collapse the space after a
              JSX expression ("2025yet"). */}
          {`No line buckets hold ≥ ${minGames} games for ${season} yet — early in a season there isn't enough graded history to bucket. Lower the min-games filter or check back after a few weeks.`}
        </p>
      ) : (
        <LineStudyView buckets={buckets} breakeven={BREAKEVEN_PCT} />
      )}
    </div>
  );
}
