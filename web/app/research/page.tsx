import Link from "next/link";

import {
  BREAKEVEN_PCT,
  DEFAULT_MIN_GAMES,
  getLineStudy,
} from "@/lib/lineStudy";
import { proxyShareText } from "@/lib/proxy";
import { getRecordSeasons } from "@/lib/records";
import {
  getBvCalibration,
  getEdgeStats,
  getGapClvBuckets,
} from "@/lib/research";
import { resolveSeason } from "@/lib/season";
import LineStudyView from "@/app/components/LineStudyView";
import MinGamesSelect from "@/app/components/MinGamesSelect";
import SeasonFallbackNotice from "@/app/components/SeasonFallbackNotice";
import SeasonSelect from "@/app/components/SeasonSelect";

export const dynamic = "force-dynamic";

// Research: whether the numbers hold up. Season-scoped (with an all-seasons
// view): the realized first-half share, gap vs line value, the line study
// (which totals go under), how accurate our number is, and the link to the
// per-game records.
//
// Copy rule (spec §24): "gap" is never called an edge here, no headings are
// questions, and the honesty caveat is said once, above, rather than being
// repeated under every table.
export default async function ResearchPage({
  searchParams,
}: {
  searchParams: Promise<{ season?: string; minGames?: string }>;
}) {
  const seasons = await getRecordSeasons();
  const sp = await searchParams;
  const allSeasons = sp.season === "all";
  const { season, fallbackFrom } = resolveSeason(
    seasons,
    allSeasons ? undefined : sp.season,
  );
  const scope = allSeasons ? undefined : season;
  const minGamesReq = Number(sp.minGames);
  const minGames =
    Number.isFinite(minGamesReq) && minGamesReq > 0
      ? minGamesReq
      : DEFAULT_MIN_GAMES;

  const [edge, gaps, calib, study] = await Promise.all([
    getEdgeStats(scope),
    getGapClvBuckets(scope),
    getBvCalibration(),
    getLineStudy(season, minGames),
  ]);
  const gapGraded = gaps.reduce((a, b) => a + b.n, 0);
  const scopeLabel = allSeasons ? "all seasons" : `${season}`;

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="bv-page-title">Research</h1>
          <p className="bv-page-sub mt-1">
            {`Whether the numbers hold up. Showing ${scopeLabel}.`}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {seasons.length > 0 && (
            <SeasonSelect
              seasons={seasons}
              current={allSeasons ? "all" : season}
              allowAll
            />
          )}
          <Link href="/research/records" className="bv-btn">
            Every game we have rated →
          </Link>
        </div>
      </div>

      {!allSeasons && (
        <SeasonFallbackNotice fallbackFrom={fallbackFrom} season={season} />
      )}

      {edge ? (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Stat
              label="Games looked at"
              value={edge.games.toLocaleString()}
              note="FBS teams playing FBS teams only."
            />
            <Stat
              label="First half’s share of the full game"
              value={`${(100 * edge.mean).toFixed(1)}%`}
              note="On average, how much of the full-game total the first half was worth."
            />
            <Stat
              label="Middle value"
              value={`${(100 * edge.median).toFixed(1)}%`}
              note="Half the games were above this, half below."
            />
          </div>
          <p className="mt-4 text-sm leading-relaxed text-[var(--text-muted)]">
            {`First halves come out around ${(100 * edge.mean).toFixed(1)}% of the full-game total, which is about where books set the first-half line. Where no real first-half line exists we estimate one: ${proxyShareText()}.`}
          </p>
          <p className="mt-2 text-sm leading-relaxed text-[var(--text-muted)]">
            {`Graded against that estimate, nothing here beat the ${BREAKEVEN_PCT}% you need at -110.`}
          </p>
        </>
      ) : (
        <p className="bv-card p-6 text-sm text-[var(--text-muted)]">
          {`No finished games for ${scopeLabel} yet.`}
        </p>
      )}

      <hr className="my-6 border-[var(--border-soft)]" />

      <h2 className="mb-1 text-sm font-semibold text-[var(--text)]">
        Gap vs line value
      </h2>
      <p className="mb-3 text-xs leading-relaxed text-[var(--text-dim)]">
        If our number finds real value, the line on our biggest-gap games should
        drift toward us before kickoff. Flat or negative means the big gaps are
        blind spots, not value. Gap = the line minus our number. Positive line
        value = the under closed at a better number than it opened.
      </p>

      {gapGraded === 0 ? (
        <p className="bv-card p-4 text-sm text-[var(--text-muted)]">
          {`Nothing settled for ${scopeLabel} yet. This fills in as first-half lines are captured and games are graded the morning after they are played.`}
        </p>
      ) : (
        <>
          <div className="bv-table-wrap">
            <table className="bv-table">
              <thead>
                <tr>
                  <th>Gap size</th>
                  <th className="bv-num">Games</th>
                  <th className="bv-num">Average gap</th>
                  <th className="bv-num">Average line value</th>
                  <th className="bv-num">Average units</th>
                  <th className="bv-num">Under %</th>
                </tr>
              </thead>
              <tbody>
                {gaps.map((b) => (
                  <tr key={b.label}>
                    <td className="text-[var(--text-muted)]">{b.label}</td>
                    <td className="bv-num text-[var(--text-muted)]">{b.n}</td>
                    <td className="bv-num font-mono text-[var(--text-muted)]">
                      {b.meanGap ?? "—"}
                    </td>
                    <td
                      className="bv-num font-mono font-semibold"
                      style={{
                        color:
                          b.meanClv === null
                            ? "var(--text-dim)"
                            : b.meanClv > 0
                              ? "var(--good)"
                              : "var(--bad)",
                      }}
                    >
                      {b.meanClv ?? "—"}
                    </td>
                    <td className="bv-num font-mono text-[var(--text-muted)]">
                      {b.meanUnits ?? "—"}
                    </td>
                    <td className="bv-num font-mono text-[var(--text-muted)]">
                      {b.underPct !== null ? `${b.underPct}%` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-1 text-xs text-[var(--text-dim)]">
            Gap size is in points. Average units is the profit per bet at the
            closing line, at one unit a bet.
          </p>
        </>
      )}

      <hr className="my-6 border-[var(--border-soft)]" />

      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-[var(--text)]">
            {`Line study — which first-half totals go under most often (${season})`}
          </h2>
          <p className="mt-1 text-xs leading-relaxed text-[var(--text-dim)]">
            {`Grouped by the ${study.anyReal ? "first-half total each book opened at" : `estimated opening line (${proxyShareText()})`}${study.fbsFiltered ? ", FBS teams only" : " — no FBS list for this season, so every game is included"}. You need ${BREAKEVEN_PCT}% to break even at -110.${study.anyReal ? "" : " On estimated lines this ordering partly reflects which games were high-scoring, so read it as a hint."}`}
          </p>
        </div>
        <MinGamesSelect current={minGames} />
      </div>
      {study.buckets.length === 0 ? (
        <p className="bv-card p-6 text-sm text-[var(--text-muted)]">
          {`No total has ${minGames}+ graded games in ${season} yet. Lower the minimum, or check back later in the season.`}
        </p>
      ) : (
        <LineStudyView buckets={study.buckets} breakeven={BREAKEVEN_PCT} />
      )}

      {calib && (
        <>
          <hr className="my-6 border-[var(--border-soft)]" />
          <h2 className="mb-1 text-sm font-semibold text-[var(--text)]">
            How accurate our number is
          </h2>
          <p className="mb-3 text-xs leading-relaxed text-[var(--text-dim)]">
            {`Average miss = actual first-half points minus our number, over ${calib.n.toLocaleString()} games it never trained on. Near zero is on target. A steady positive miss means our number runs low, which would wrongly lean it under.`}
          </p>
          <div className="bv-table-wrap">
            <table className="bv-table">
              <thead>
                <tr>
                  <th>Group</th>
                  <th className="bv-num">Games</th>
                  <th className="bv-num">Average miss</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="font-medium text-[var(--text)]">Overall</td>
                  <td className="bv-num text-[var(--text-muted)]">{calib.n}</td>
                  <td className="bv-num font-mono text-[var(--text-muted)]">
                    {calib.overall ?? "—"}
                  </td>
                </tr>
                {calib.segments.map((s) => (
                  <tr key={s.label}>
                    <td className="text-[var(--text-muted)]">{s.label}</td>
                    <td className="bv-num text-[var(--text-muted)]">{s.n}</td>
                    <td
                      className="bv-num font-mono"
                      style={{
                        color:
                          s.meanResidual === null
                            ? "var(--text-dim)"
                            : Math.abs(s.meanResidual) <= 0.5
                              ? "var(--text)"
                              : "var(--warn)",
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
    </div>
  );
}

function Stat({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  /** Visible line, never a tooltip: what the number counts. */
  note: string;
}) {
  return (
    <div className="bv-card p-4">
      <div className="bv-stat-label">{label}</div>
      <div className="mt-1.5 font-[family-name:var(--font-display)] text-2xl font-extrabold tabular-nums text-[var(--text)]">
        {value}
      </div>
      <p className="mt-1 text-xs leading-relaxed text-[var(--text-dim)]">
        {note}
      </p>
    </div>
  );
}
