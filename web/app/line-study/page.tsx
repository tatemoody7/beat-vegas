import { getSeasons } from "@/lib/board";
import { BREAKEVEN_PCT, getLineStudy } from "@/lib/lineStudy";
import LineStudyView from "@/app/components/LineStudyView";
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
  const requested = sp.season ? Number(sp.season) : NaN;
  const season =
    Number.isFinite(requested) && seasons.includes(requested)
      ? requested
      : (seasons[0] ?? new Date().getFullYear());
  const minGames = sp.minGames ? Number(sp.minGames) : 30;

  const { buckets, anyReal } = await getLineStudy(season, minGames);

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Line Study</h1>
          <p className="text-sm text-gray-500">
            Which opening first-half lines hit the under most often — {season}
          </p>
        </div>
        <div className="flex items-center gap-4">
          <MinGamesSelect current={minGames} />
          {seasons.length > 0 && (
            <SeasonSelect seasons={seasons} current={season} />
          )}
        </div>
      </div>

      <p className="mb-4 text-xs text-gray-500">
        Grouped by{" "}
        <span className="text-gray-300">
          {anyReal ? "real opening lines" : "estimated lines (0.52 × full-game total)"}
        </span>
        . You need to win {BREAKEVEN_PCT}% to break even at −110.
        {!anyReal &&
          " ⚠️ On estimated lines this ranking partly reflects how high-scoring the" +
            " games are, not a standalone signal you can bet — treat it as a hint" +
            " until real lines build up."}
      </p>

      {buckets.length === 0 ? (
        <p className="rounded-lg border border-gray-800 bg-gray-900 p-6 text-sm text-gray-400">
          No line buckets with ≥ {minGames} games for {season}.
        </p>
      ) : (
        <LineStudyView buckets={buckets} breakeven={BREAKEVEN_PCT} />
      )}
    </div>
  );
}
