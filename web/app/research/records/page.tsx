import Link from "next/link";

import { getRecordSeasons, getSeasonRecords, RecordRow } from "@/lib/records";

export const dynamic = "force-dynamic";

const OUTCOME_COLOR: Record<string, string> = {
  under: "#16a34a",
  over: "#dc2626",
  push: "#6b7280",
};

function fmt(v: number | null, digits = 1): string {
  return v === null ? "—" : v.toFixed(digits);
}

export default async function RecordsPage({
  searchParams,
}: {
  searchParams: Promise<{ season?: string }>;
}) {
  const seasons = await getRecordSeasons();
  const sp = await searchParams;
  const season = Number(sp.season) || seasons[0] || new Date().getFullYear();
  const rows: RecordRow[] = seasons.length
    ? await getSeasonRecords(season)
    : [];

  return (
    <div className="mx-auto max-w-6xl">
      <h1 className="bv-page-title">Our records</h1>
      <p className="bv-page-sub mb-5">
        Every game, our number vs the line, and how it actually landed — our own
        season-by-season record. Export to a spreadsheet to keep your own copy.
      </p>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        {seasons.map((s) => (
          <Link
            key={s}
            href={`/research/records?season=${s}`}
            className={`bv-pill ${s === season ? "ring-1 ring-[var(--accent)]" : ""}`}
          >
            <span className="bv-pill-value">{s}</span>
          </Link>
        ))}
        <a
          href={`/api/records?season=${season}`}
          className="bv-btn ml-auto"
          download
        >
          Download CSV
        </a>
      </div>

      {rows.length === 0 ? (
        <p className="bv-card p-6 text-sm text-[var(--text-muted)]">
          No games recorded for {season} yet.
        </p>
      ) : (
        <div className="bv-table-wrap">
          <table className="bv-table">
            <thead>
              <tr>
                <th>Wk</th>
                <th>Matchup</th>
                <th title="Full-game total.">Total</th>
                <th title="First-half line used at scoring.">1H line</th>
                <th title="Our market-blind first-half number.">Our #</th>
                <th title="Line − our number (toward the under).">Gap</th>
                <th title="Gap in residual sigmas (noise-aware).">Gap σ</th>
                <th title="Under score, 0–100 (50 = coin flip).">Score</th>
                <th title="Actual first-half points.">Actual 1H</th>
                <th>Outcome</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  <td className="text-[var(--text-dim)]">{r.week}</td>
                  <td className="text-[var(--text)]">
                    {r.away} <span className="text-[var(--text-dim)]">@</span>{" "}
                    {r.home}
                  </td>
                  <td className="font-mono text-[var(--text-muted)]">
                    {fmt(r.fullGameTotal)}
                  </td>
                  <td className="font-mono text-[var(--text-muted)]">
                    {fmt(r.line)}
                  </td>
                  <td className="font-mono text-[var(--text-muted)]">
                    {fmt(r.bvLine)}
                  </td>
                  <td className="font-mono text-[var(--text-muted)]">
                    {r.bvGap === null
                      ? "—"
                      : `${r.bvGap > 0 ? "+" : ""}${r.bvGap.toFixed(1)}`}
                  </td>
                  <td className="font-mono text-[var(--text-dim)]">
                    {fmt(r.bvGapZ, 2)}
                  </td>
                  <td className="font-mono text-[var(--text-muted)]">
                    {r.underScore ?? "—"}
                  </td>
                  <td className="font-mono text-[var(--text-muted)]">
                    {r.firstHalfTotal ?? "—"}
                  </td>
                  <td
                    className="font-semibold"
                    style={{
                      color: r.outcome ? OUTCOME_COLOR[r.outcome] : "#6b7280",
                    }}
                  >
                    {r.outcome ?? "—"}
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
