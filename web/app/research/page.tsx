import {
  getBvCalibration,
  getEdgeStats,
  getGapClvBuckets,
  getModelRuns,
} from "@/lib/research";

export const dynamic = "force-dynamic";

export default async function ResearchPage() {
  const [edge, runs, gaps, calib] = await Promise.all([
    getEdgeStats(),
    getModelRuns(),
    getGapClvBuckets(),
    getBvCalibration(),
  ]);
  const gapGraded = gaps.reduce((a, b) => a + b.n, 0);

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
        Gap vs CLV — do our biggest gaps earn closing-line value?
      </h2>
      <p className="mb-3 text-xs leading-relaxed text-gray-500">
        Gap = Vegas line − BV line (under direction). If the BV number finds real
        value, the lines on our biggest-gap picks should move{" "}
        <i>toward</i> us before close — i.e. mean CLV rises with the gap bucket.
        If it&apos;s flat or negative, the big gaps are model blind spots, not
        edges. CLV positive = the under closed at a softer number.
      </p>

      {gapGraded === 0 ? (
        <p className="rounded-lg border border-gray-800 bg-gray-900 p-4 text-sm text-gray-400">
          No graded games with a BV line and real closing line yet. This fills in
          as real 1H lines are polled (<code className="text-gray-300">scripts/poll_lines.py</code>)
          and graded (<code className="text-gray-300">scripts/grade.py</code>)
          through the season.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-800">
          <table className="w-full text-sm">
            <thead className="bg-gray-900 text-left text-gray-400">
              <tr>
                <th className="px-3 py-2 font-medium">Gap bucket</th>
                <th className="px-3 py-2 font-medium">N</th>
                <th className="px-3 py-2 font-medium">Mean gap</th>
                <th className="px-3 py-2 font-medium">Mean CLV</th>
                <th className="px-3 py-2 font-medium">Mean units</th>
                <th className="px-3 py-2 font-medium">Under %</th>
              </tr>
            </thead>
            <tbody>
              {gaps.map((b) => (
                <tr key={b.label} className="border-t border-gray-800">
                  <td className="px-3 py-1.5 text-gray-300">{b.label}</td>
                  <td className="px-3 py-1.5 text-gray-400">{b.n}</td>
                  <td className="px-3 py-1.5 text-gray-400">
                    {b.meanGap ?? "—"}
                  </td>
                  <td
                    className="px-3 py-1.5 font-medium"
                    style={{
                      color:
                        b.meanClv === null
                          ? "#6b7280"
                          : b.meanClv > 0
                            ? "#16a34a"
                            : "#dc2626",
                    }}
                  >
                    {b.meanClv ?? "—"}
                  </td>
                  <td className="px-3 py-1.5 text-gray-300">{b.meanUnits ?? "—"}</td>
                  <td className="px-3 py-1.5 text-gray-400">
                    {b.underPct !== null ? `${b.underPct}%` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {calib && (
        <>
          <h2 className="mb-1 mt-6 text-sm font-semibold text-gray-200">
            BV-line calibration (out-of-fold)
          </h2>
          <p className="mb-3 text-xs leading-relaxed text-gray-500">
            Mean residual = actual − BV line, per segment ({calib.n.toLocaleString()}{" "}
            games). Near 0 = unbiased. A persistent positive residual means the BV
            line runs low (would falsely scream &quot;under&quot;); the first
            post-2023 season can&apos;t be de-biased from data that doesn&apos;t
            exist yet — it&apos;s surfaced here, not hidden.
          </p>
          <div className="overflow-x-auto rounded-xl border border-gray-800">
            <table className="w-full text-sm">
              <thead className="bg-gray-900 text-left text-gray-400">
                <tr>
                  <th className="px-3 py-2 font-medium">Segment</th>
                  <th className="px-3 py-2 font-medium">N</th>
                  <th className="px-3 py-2 font-medium">Mean residual</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-t border-gray-800">
                  <td className="px-3 py-1.5 font-medium text-gray-200">overall</td>
                  <td className="px-3 py-1.5 text-gray-400">{calib.n}</td>
                  <td className="px-3 py-1.5 text-gray-300">{calib.overall ?? "—"}</td>
                </tr>
                {calib.segments.map((s) => (
                  <tr key={s.label} className="border-t border-gray-800">
                    <td className="px-3 py-1.5 text-gray-400">{s.label}</td>
                    <td className="px-3 py-1.5 text-gray-400">{s.n}</td>
                    <td
                      className="px-3 py-1.5"
                      style={{
                        color:
                          s.meanResidual === null
                            ? "#6b7280"
                            : Math.abs(s.meanResidual) <= 0.5
                              ? "#16a34a"
                              : "#ca8a04",
                      }}
                    >
                      {s.meanResidual ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
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
