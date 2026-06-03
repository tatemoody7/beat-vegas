import { getSeasons } from "@/lib/board";
import { getLedger, Record3 } from "@/lib/ledger";
import SeasonSelect from "@/app/components/SeasonSelect";

export const dynamic = "force-dynamic";

function LedgerCard({
  title,
  rec,
  emptyHint,
}: {
  title: string;
  rec: Record3 | null;
  emptyHint: string;
}) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-950 p-4">
      <h3 className="mb-2 text-sm font-semibold text-gray-200">{title}</h3>
      {rec === null ? (
        <p className="text-xs text-gray-500">{emptyHint}</p>
      ) : (
        <dl className="space-y-2">
          <div>
            <dt className="text-xs text-gray-500" title="Share of bets that won.">
              Win rate
            </dt>
            <dd className="text-2xl font-bold text-gray-100">
              {rec.hit}{" "}
              <span className="text-sm font-normal text-gray-500">{rec.record}</span>
            </dd>
          </div>
          <div className="flex gap-6">
            <div>
              <dt
                className="text-xs text-gray-500"
                title="Profit in units. 1 unit = one standard bet."
              >
                Units
              </dt>
              <dd
                className="text-lg font-semibold"
                style={{ color: rec.units.startsWith("-") ? "#dc2626" : "#16a34a" }}
              >
                {rec.units}
              </dd>
            </div>
            <div>
              <dt
                className="text-xs text-gray-500"
                title="Average line value (CLV): did the line move our way after we'd bet? Positive = we beat the closing line."
              >
                Avg line value
              </dt>
              <dd className="text-lg font-semibold text-gray-300">{rec.clv}</dd>
            </div>
          </div>
        </dl>
      )}
    </div>
  );
}

export default async function LedgerPage({
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

  const { market, model, you, picks } = await getLedger(season);

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-1 flex items-center justify-between">
        <h1 className="text-xl font-semibold">Ledger</h1>
        {seasons.length > 0 && <SeasonSelect seasons={seasons} current={season} />}
      </div>
      <p className="mb-4 text-sm text-gray-500">
        Settled results for {season} · Market = how the under did at the closing line
        (the final line before kickoff) · Model = the model&apos;s under picks · You =
        your own logged bets.
      </p>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <LedgerCard title="📊 Market" rec={market} emptyHint="Fills in once games are settled." />
        <LedgerCard
          title="🤖 Model"
          rec={model}
          emptyHint="Fills in once the week is scored and settled."
        />
        <LedgerCard title="✍️ You" rec={you} emptyHint="Log bets in My Picks." />
      </div>

      <h2 className="mb-2 mt-6 text-sm font-semibold text-gray-200">Your bets</h2>
      {picks.length === 0 ? (
        <p className="rounded-lg border border-gray-800 bg-gray-900 p-4 text-sm text-gray-400">
          No logged picks for {season}.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-800">
          <table className="w-full text-sm">
            <thead className="bg-gray-900 text-left text-gray-400">
              <tr>
                <th className="px-3 py-2 font-medium">Wk</th>
                <th className="px-3 py-2 font-medium">Matchup</th>
                <th className="px-3 py-2 font-medium">Line</th>
                <th className="px-3 py-2 font-medium" title="The odds / price (e.g. −110).">Odds</th>
                <th className="px-3 py-2 font-medium">Result</th>
                <th className="px-3 py-2 font-medium" title="Profit in units. 1 unit = one standard bet.">Units</th>
                <th className="px-3 py-2 font-medium" title="Line value (CLV): positive = the line moved our way after we'd bet.">Line value</th>
              </tr>
            </thead>
            <tbody>
              {picks.map((p, i) => (
                <tr key={i} className="border-t border-gray-800">
                  <td className="px-3 py-1.5 text-gray-400">{p.week ?? "—"}</td>
                  <td className="px-3 py-1.5 text-gray-200">
                    {p.away} <span className="text-gray-600">@</span> {p.home}
                  </td>
                  <td className="px-3 py-1.5 text-gray-400">
                    {p.line !== null ? `under ${p.line}` : "—"}
                  </td>
                  <td className="px-3 py-1.5 text-gray-500">{p.price ?? "—"}</td>
                  <td className="px-3 py-1.5">
                    <span
                      style={{
                        color:
                          p.result === "under"
                            ? "#16a34a"
                            : p.result === "over"
                              ? "#dc2626"
                              : "#9ca3af",
                      }}
                    >
                      {p.result}
                    </span>
                  </td>
                  <td
                    className="px-3 py-1.5"
                    style={{
                      color:
                        p.units === null
                          ? "#9ca3af"
                          : p.units >= 0
                            ? "#16a34a"
                            : "#dc2626",
                    }}
                  >
                    {p.units !== null ? `${p.units >= 0 ? "+" : ""}${p.units.toFixed(2)}` : "—"}
                  </td>
                  <td className="px-3 py-1.5 text-gray-400">
                    {p.clv !== null ? `${p.clv >= 0 ? "+" : ""}${p.clv.toFixed(2)}` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
