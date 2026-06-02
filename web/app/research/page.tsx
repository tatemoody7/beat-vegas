import { getEdgeStats, getModelRuns } from "@/lib/research";

export const dynamic = "force-dynamic";

export default async function ResearchPage() {
  const [edge, runs] = await Promise.all([getEdgeStats(), getModelRuns()]);

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-xl font-semibold">Research</h1>
      <p className="mb-5 text-sm text-gray-500">The edge question</p>

      {edge ? (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Stat label="Games analyzed" value={edge.games.toLocaleString()} />
            <Stat label="Realized 1H / full (mean)" value={edge.mean.toFixed(3)} />
            <Stat label="Median" value={edge.median.toFixed(3)} />
          </div>
          <p className="mt-4 text-sm leading-relaxed text-gray-400">
            First halves realize <b className="text-gray-200">~52% of the full-game
            total</b> — right where books price the 1H line. Blanket and
            model-selected 1H unders did <b className="text-gray-200">not</b> reliably
            beat the −110 breakeven (52.4%) against a proxy line, and the apparent
            signal sits inside the ±1.5 pt proxy uncertainty.
          </p>
          <p className="mt-2 text-sm leading-relaxed text-gray-400">
            <b className="text-gray-200">Verdict:</b> no edge is{" "}
            <i>confirmable</i> on free historical data — there are no historical 1H
            lines to grade against. The real test is the live ledger, built from real
            first-half lines captured this season.
          </p>
        </>
      ) : (
        <p className="rounded-lg border border-gray-800 bg-gray-900 p-6 text-sm text-gray-400">
          Load history with <code className="text-gray-300">scripts/backfill.py</code>{" "}
          to see calibration.
        </p>
      )}

      <hr className="my-6 border-gray-800" />

      <h2 className="mb-1 text-sm font-semibold text-gray-200">
        Model runs over time
      </h2>
      <p className="mb-3 text-xs text-gray-500">
        Does it sharpen as seasons are added? (baseline vs top-fraction under% + ROI)
      </p>

      {runs.length === 0 ? (
        <p className="rounded-lg border border-gray-800 bg-gray-900 p-4 text-sm text-gray-400">
          No runs logged yet — run{" "}
          <code className="text-gray-300">scripts/retrain.py</code>.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-800">
          <table className="w-full text-sm">
            <thead className="bg-gray-900 text-left text-gray-400">
              <tr>
                <th className="px-3 py-2 font-medium">Run</th>
                <th className="px-3 py-2 font-medium">Train</th>
                <th className="px-3 py-2 font-medium">Test</th>
                <th className="px-3 py-2 font-medium">Baseline U%</th>
                <th className="px-3 py-2 font-medium">Top U%</th>
                <th className="px-3 py-2 font-medium">Top ROI</th>
                <th className="px-3 py-2 font-medium">Notes</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r, i) => (
                <tr key={i} className="border-t border-gray-800 align-top">
                  <td className="px-3 py-1.5 text-gray-400">
                    {r.created_at.slice(0, 16)}
                  </td>
                  <td className="px-3 py-1.5 text-gray-400">{r.train_window ?? "—"}</td>
                  <td className="px-3 py-1.5 text-gray-400">{r.test_window ?? "—"}</td>
                  <td className="px-3 py-1.5 text-gray-300">
                    {r.baseline_under_pct ?? "—"}
                  </td>
                  <td
                    className="px-3 py-1.5 font-medium"
                    style={{
                      color:
                        r.top_under_pct !== null && r.top_under_pct >= 52.4
                          ? "#16a34a"
                          : "#dc2626",
                    }}
                  >
                    {r.top_under_pct ?? "—"}
                  </td>
                  <td
                    className="px-3 py-1.5"
                    style={{
                      color:
                        r.top_roi !== null && r.top_roi >= 0 ? "#16a34a" : "#dc2626",
                    }}
                  >
                    {r.top_roi !== null ? r.top_roi.toFixed(4) : "—"}
                  </td>
                  <td className="max-w-xs px-3 py-1.5 text-gray-500">
                    {r.notes ?? "—"}
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

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-950 p-4">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="mt-1 text-2xl font-bold text-gray-100">{value}</div>
    </div>
  );
}
