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
    <div className="mx-auto max-w-5xl">
      <h1 className="bv-page-title">Research</h1>
      <p className="bv-page-sub mb-5">Is there really an edge?</p>

      {edge ? (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Stat label="Games analyzed" value={edge.games.toLocaleString()} />
            <Stat label="1st-half share of full game (avg)" value={edge.mean.toFixed(3)} />
            <Stat label="Median" value={edge.median.toFixed(3)} />
          </div>
          <p className="mt-4 text-sm leading-relaxed text-[var(--text-muted)]">
            First halves end up worth <b className="text-[var(--text)]">~52% of the
            full-game total</b> — right where sportsbooks set the first-half line.
            Betting every first-half under, or only the model&apos;s picks, did{" "}
            <b className="text-gray-200">not</b> reliably beat the −110 break-even
            (you need to win 52.4%) against an estimated line, and the apparent edge
            sits inside the ±1.5-point margin of that estimate.
          </p>
          <p className="mt-2 text-sm leading-relaxed text-[var(--text-muted)]">
            <b className="text-[var(--text)]">Bottom line:</b> we can&apos;t{" "}
            <i>confirm</i> an edge on free past data — there are no past first-half
            lines to check against. The real test is the live record, built from real
            first-half lines captured this season.
          </p>
        </>
      ) : (
        <p className="bv-card p-6 text-sm text-[var(--text-muted)]">
          Load history with <code className="text-[var(--text)]">scripts/backfill.py</code>{" "}
          to see this.
        </p>
      )}

      <hr className="my-6 border-[var(--border-soft)]" />

      <h2 className="mb-1 text-sm font-semibold text-[var(--text)]">
        Edge vs line value — do our biggest edges actually move the line our way?
      </h2>
      <p className="mb-3 text-xs leading-relaxed text-[var(--text-dim)]">
        Edge = Vegas line − our number (toward the under). If our number really
        finds value, the line on our biggest-edge picks should drift{" "}
        <i>toward</i> us before kickoff — i.e. average line value rises with the size
        of the edge. If it&apos;s flat or negative, the big edges are blind spots,
        not real value. Positive line value = the under closed at a more favorable
        number than we bet.
      </p>

      {gapGraded === 0 ? (
        <p className="bv-card p-4 text-sm text-[var(--text-muted)]">
          No settled games with our number and a real closing line yet. This fills in
          as real first-half lines are checked (<code className="text-[var(--text)]">scripts/poll_lines.py</code>)
          and settled (<code className="text-[var(--text)]">scripts/grade.py</code>)
          through the season.
        </p>
      ) : (
        <div className="bv-table-wrap">
          <table className="bv-table">
            <thead>
              <tr>
                <th>Edge size</th>
                <th title="Number of games in this group.">Games</th>
                <th>Avg edge</th>
                <th title="Average line value (CLV): positive = the line moved our way.">Avg line value</th>
                <th title="Average profit in units. 1 unit = one standard bet.">Avg units</th>
                <th>Under %</th>
              </tr>
            </thead>
            <tbody>
              {gaps.map((b) => (
                <tr key={b.label}>
                  <td className="text-[var(--text-muted)]">{b.label}</td>
                  <td className="text-[var(--text-muted)]">{b.n}</td>
                  <td className="font-mono text-[var(--text-muted)]">
                    {b.meanGap ?? "—"}
                  </td>
                  <td
                    className="font-mono font-semibold"
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
                  <td className="font-mono text-[var(--text-muted)]">{b.meanUnits ?? "—"}</td>
                  <td className="font-mono text-[var(--text-muted)]">
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
          <h2 className="mb-1 mt-6 text-sm font-semibold text-[var(--text)]">
            How accurate is our number? (on unseen games)
          </h2>
          <p className="mb-3 text-xs leading-relaxed text-[var(--text-dim)]">
            Average miss = actual first-half points − our number, per segment
            ({calib.n.toLocaleString()} games). Near 0 = on target. A steady positive
            miss means our number runs low (it would wrongly scream &quot;under&quot;);
            the first post-2023 season can&apos;t be corrected from data that
            doesn&apos;t exist yet — so it&apos;s shown here, not hidden.
          </p>
          <div className="bv-table-wrap">
            <table className="bv-table">
              <thead>
                <tr>
                  <th>Segment</th>
                  <th title="Number of games.">Games</th>
                  <th title="Average of (actual first-half points − our number). 0 = on target.">Avg miss</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="font-medium text-[var(--text)]">overall</td>
                  <td className="text-[var(--text-muted)]">{calib.n}</td>
                  <td className="font-mono text-[var(--text-muted)]">{calib.overall ?? "—"}</td>
                </tr>
                {calib.segments.map((s) => (
                  <tr key={s.label}>
                    <td className="text-[var(--text-muted)]">{s.label}</td>
                    <td className="text-[var(--text-muted)]">{s.n}</td>
                    <td
                      className="font-mono"
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

      <hr className="my-6 border-[var(--border-soft)]" />

      <h2 className="mb-1 text-sm font-semibold text-[var(--text)]">
        Model runs over time
      </h2>
      <p className="mb-3 text-xs text-[var(--text-dim)]">
        Does it get sharper as seasons are added? (under % for all picks vs the top
        picks, plus return)
      </p>

      {runs.length === 0 ? (
        <p className="bv-card p-4 text-sm text-[var(--text-muted)]">
          No runs logged yet — run{" "}
          <code className="text-[var(--text)]">scripts/retrain.py</code>.
        </p>
      ) : (
        <div className="bv-table-wrap">
          <table className="bv-table">
            <thead>
              <tr>
                <th>Run</th>
                <th title="Seasons the model learned from.">Trained on</th>
                <th title="Seasons it was checked against.">Tested on</th>
                <th title="Under win rate across every game.">Under % (all)</th>
                <th title="Under win rate on just the strongest picks.">Under % (top)</th>
                <th title="Return on units risked for the top picks.">Return (top)</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r, i) => (
                <tr key={i} className="align-top">
                  <td className="font-mono text-[var(--text-muted)]">
                    {r.created_at.slice(0, 16)}
                  </td>
                  <td className="text-[var(--text-muted)]">{r.train_window ?? "—"}</td>
                  <td className="text-[var(--text-muted)]">{r.test_window ?? "—"}</td>
                  <td className="font-mono text-[var(--text-muted)]">
                    {r.baseline_under_pct ?? "—"}
                  </td>
                  <td
                    className="font-mono font-semibold"
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
                    className="font-mono"
                    style={{
                      color:
                        r.top_roi !== null && r.top_roi >= 0 ? "#16a34a" : "#dc2626",
                    }}
                  >
                    {r.top_roi !== null ? r.top_roi.toFixed(4) : "—"}
                  </td>
                  <td className="max-w-xs text-[var(--text-dim)]">
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
    <div className="bv-card p-4">
      <div className="bv-stat-label">{label}</div>
      <div className="mt-1.5 font-[family-name:var(--font-display)] text-2xl font-extrabold tabular-nums text-[var(--text)]">
        {value}
      </div>
    </div>
  );
}
