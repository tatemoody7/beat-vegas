import Link from "next/link";

import {
  labelOf,
  RESULT_COLOR,
  RESULT_NO_LINE,
  RESULT_PENDING,
  RESULT_TEXT,
} from "@/lib/labels";
import { getRecordSeasons, getSeasonRecords, RecordRow } from "@/lib/records";
import { resolveSeason } from "@/lib/season";
import { BET_GAP_PTS } from "@/lib/verdict";
import SeasonFallbackNotice from "@/app/components/SeasonFallbackNotice";

export const dynamic = "force-dynamic";

// The legend IS the explanation of the columns — a `title=` on a header is
// invisible on a phone, so the table carries none (spec §25.10).
const LEGEND: [string, string][] = [
  ["Full game", "the full-game total the books posted"],
  ["Line", "the first-half total we scored against"],
  [
    "Our number",
    "our own first-half estimate; it never sees the sportsbook line",
  ],
  [
    "Gap",
    `the line minus our number. Positive means the line is above us, which leans under. ${BET_GAP_PTS}+ is the band we bet`,
  ],
];

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
  const { season, fallbackFrom } = resolveSeason(seasons, sp.season);
  const rows: RecordRow[] = seasons.length
    ? await getSeasonRecords(season)
    : [];

  return (
    <div className="mx-auto max-w-6xl">
      <h1 className="bv-page-title">Every game we have rated</h1>
      <p className="bv-page-sub mb-1">
        Our number, the line, and how the first half actually landed. Download
        it if you want your own copy.
      </p>
      <p className="mb-5 text-xs text-[var(--text-dim)]">
        Games with no first-half line show No line; they are in the table for
        the score, not the record.
      </p>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        {seasons.map((s) => (
          <Link
            key={s}
            href={`/proof/records?season=${s}`}
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
          Download spreadsheet
        </a>
      </div>

      <SeasonFallbackNotice fallbackFrom={fallbackFrom} season={season} />

      <dl className="bv-card mb-4 grid grid-cols-1 gap-x-6 gap-y-1 p-3 text-xs sm:grid-cols-2">
        {LEGEND.map(([k, v]) => (
          <div key={k} className="flex gap-2">
            <dt className="shrink-0 font-semibold text-[var(--text)]">{k}</dt>
            <dd className="text-[var(--text-muted)]">{v}</dd>
          </div>
        ))}
      </dl>

      {rows.length === 0 ? (
        <p className="bv-card p-6 text-sm text-[var(--text-muted)]">
          {`No games recorded for ${season} yet.`}
        </p>
      ) : (
        <div className="bv-table-wrap">
          <table className="bv-table">
            <thead>
              <tr>
                <th className="bv-num">Week</th>
                <th>Matchup</th>
                <th className="bv-num">Full game</th>
                <th className="bv-num">Line</th>
                <th className="bv-num">Our number</th>
                <th className="bv-num">Gap</th>
                <th className="bv-num">Actual first half</th>
                <th>Result</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  <td className="bv-num text-[var(--text-dim)]">{r.week}</td>
                  <td className="text-[var(--text)]">
                    {r.away} <span className="text-[var(--text-dim)]">@</span>{" "}
                    {r.home}
                  </td>
                  <td className="bv-num font-mono text-[var(--text-muted)]">
                    {fmt(r.fullGameTotal)}
                  </td>
                  <td className="bv-num font-mono text-[var(--text-muted)]">
                    {fmt(r.line)}
                  </td>
                  <td className="bv-num font-mono text-[var(--text-muted)]">
                    {fmt(r.bvLine)}
                  </td>
                  <td className="bv-num font-mono text-[var(--text-muted)]">
                    {r.bvGap === null
                      ? "—"
                      : `${r.bvGap > 0 ? "+" : ""}${r.bvGap.toFixed(1)}`}
                  </td>
                  <td className="bv-num font-mono text-[var(--text-muted)]">
                    {r.firstHalfTotal ?? "—"}
                  </td>
                  <td
                    className="font-semibold"
                    style={{
                      color: labelOf(
                        RESULT_COLOR,
                        r.outcome,
                        "var(--text-dim)",
                      ),
                    }}
                  >
                    {r.firstHalfTotal !== null && r.line === null
                      ? RESULT_NO_LINE
                      : labelOf(RESULT_TEXT, r.outcome, RESULT_PENDING)}
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
