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
    <div className="mx-auto max-w-5xl">
      <div className="mb-1 flex items-center justify-between">
        <h1 className="bv-page-title">My Picks</h1>
        {seasons.length > 0 && (
          <SeasonSelect seasons={seasons} current={season} />
        )}
      </div>
      <p className="bv-page-sub mb-5">
        Log your unders — full game or first half — saved and settled after games
        finish, so your record builds each week.
      </p>

      {/* Running record */}
      <div className="bv-card mb-6 p-4">
        <h2 className="mb-3 text-sm font-semibold text-[var(--text)]">
          Your record
        </h2>
        {record ? (
          <div className="flex flex-wrap items-baseline gap-x-10 gap-y-2">
            <div>
              <span className="font-[family-name:var(--font-display)] text-2xl font-extrabold tabular-nums text-[var(--text)]">
                {record.hit}
              </span>{" "}
              <span className="text-sm text-[var(--text-dim)]">
                {record.record}
              </span>
            </div>
            <div
              className="text-sm text-[var(--text-muted)]"
              title="Profit in units. 1 unit = one standard bet."
            >
              Units{" "}
              <b
                className="font-mono tabular-nums"
                style={{
                  color: record.units.startsWith("-") ? "#dc2626" : "#16a34a",
                }}
              >
                {record.units}
              </b>
            </div>
            <div
              className="text-sm text-[var(--text-muted)]"
              title="Average line value (CLV): positive = the line moved your way after you'd bet."
            >
              Avg line value{" "}
              <b className="font-mono tabular-nums text-[var(--text)]">
                {record.clv}
              </b>
            </div>
          </div>
        ) : (
          <p className="text-xs text-[var(--text-dim)]">
            No settled picks yet — log some below; results fill in after the
            games finish.
          </p>
        )}
      </div>

      <h2 className="mb-2 text-sm font-semibold text-[var(--text)]">
        Log a pick
      </h2>
      <LogPickForm slate={slate} />

      <h2 className="mb-2 mt-7 text-sm font-semibold text-[var(--text)]">
        History
      </h2>
      <PicksList picks={picks} />
    </div>
  );
}
