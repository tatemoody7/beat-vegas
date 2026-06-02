import { getBoard, getSeasons } from "@/lib/board";
import OpportunityCard from "@/app/components/OpportunityCard";
import SeasonSelect from "@/app/components/SeasonSelect";

export const dynamic = "force-dynamic"; // always read live DB

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ season?: string }>;
}) {
  const seasons = await getSeasons();
  const sp = await searchParams;
  const requested = sp.season ? Number(sp.season) : NaN;
  const season =
    Number.isFinite(requested) && seasons.includes(requested)
      ? requested
      : (seasons[0] ?? new Date().getFullYear());

  const rows = await getBoard(season);

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Opportunities</h1>
          <p className="text-sm text-gray-500">
            Ranked 1H-under leans · score 0–100 (50 = breakeven)
          </p>
        </div>
        {seasons.length > 0 && (
          <SeasonSelect seasons={seasons} current={season} />
        )}
      </div>

      {rows.length === 0 ? (
        <p className="rounded-lg border border-gray-800 bg-gray-900 p-6 text-sm text-gray-400">
          No predictions for {season}. Score a slate
          (<code className="text-gray-300">scripts/weekly_update.py</code>) or
          point <code className="text-gray-300">DATABASE_URL</code> at a DB that
          has them.
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          {rows.map((row) => (
            <OpportunityCard key={row.gameId} row={row} />
          ))}
        </div>
      )}
    </div>
  );
}
