import { getSeasons } from "@/lib/board";
import { getPicks, getSlate } from "@/lib/picks";
import SeasonSelect from "@/app/components/SeasonSelect";
import LogPickForm from "@/app/components/LogPickForm";
import PicksList from "@/app/components/PicksList";

export const dynamic = "force-dynamic";

export default async function PicksPage({
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

  const [slate, { picks, record }] = await Promise.all([
    getSlate(season),
    getPicks(season),
  ]);

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-1 flex items-center justify-between">
        <h1 className="text-xl font-semibold">My Picks</h1>
        {seasons.length > 0 && <SeasonSelect seasons={seasons} current={season} />}
      </div>
      <p className="mb-4 text-sm text-gray-500">
        Log your 1H unders — stored and graded so the record sharpens each week.
      </p>

      {/* Running record */}
      <div className="mb-5 rounded-xl border border-gray-800 bg-gray-950 p-4">
        <h2 className="mb-2 text-sm font-semibold text-gray-200">Your record</h2>
        {record ? (
          <div className="flex flex-wrap items-baseline gap-x-8 gap-y-2">
            <div>
              <span className="text-2xl font-bold text-gray-100">{record.hit}</span>{" "}
              <span className="text-sm text-gray-500">{record.record}</span>
            </div>
            <div className="text-sm text-gray-400">
              Units{" "}
              <b style={{ color: record.units.startsWith("-") ? "#dc2626" : "#16a34a" }}>
                {record.units}
              </b>
            </div>
            <div className="text-sm text-gray-400">
              Avg CLV <b className="text-gray-300">{record.clv}</b>
            </div>
          </div>
        ) : (
          <p className="text-xs text-gray-500">
            No graded picks yet — log some below; the local grader fills results
            after games finish.
          </p>
        )}
      </div>

      <h2 className="mb-2 text-sm font-semibold text-gray-200">Log a pick</h2>
      <LogPickForm slate={slate} />

      <h2 className="mb-2 mt-6 text-sm font-semibold text-gray-200">History</h2>
      <PicksList picks={picks} />
    </div>
  );
}
