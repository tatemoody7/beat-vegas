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
  getModelRuns,
} from "@/lib/research";
import { resolveSeason } from "@/lib/season";
import { getTrends } from "@/lib/trends";
import LineStudyView from "@/app/components/LineStudyView";
import MinGamesSelect from "@/app/components/MinGamesSelect";
import SeasonFallbackNotice from "@/app/components/SeasonFallbackNotice";
import SeasonSelect from "@/app/components/SeasonSelect";

export const dynamic = "force-dynamic";

// Research: is there really an edge? Season-scoped (with an all-seasons view):
// the realized first-half share, gap vs closing-line value, the line study
// (which opening lines go under), calibration, model runs, candidate trends,
// and the link to the exportable per-game records.
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

  const [edge, runs, gaps, calib, study, trends] = await Promise.all([
    getEdgeStats(scope),
    getModelRuns(),
    getGapClvBuckets(scope),
    getBvCalibration(),
    getLineStudy(season, minGames),
    getTrends(),
  ]);
  const gapGraded = gaps.reduce((a, b) => a + b.n, 0);
  const scopeLabel = allSeasons ? "all seasons" : `${season}`;

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="bv-page-title">Research</h1>
          <p className="bv-page-sub mt-1">
            {`Is there really an edge? Showing ${scopeLabel}.`}
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
            Our records — every game, exportable →
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
              label="Games analyzed (FBS vs FBS)"
              value={edge.games.toLocaleString()}
            />
            <Stat
              label="1st-half share of full game (avg)"
              value={`${(100 * edge.mean).toFixed(1)}%`}
            />
            <Stat label="Median" value={`${(100 * edge.median).toFixed(1)}%`} />
          </div>
          <p className="mt-4 text-sm leading-relaxed text-[var(--text-muted)]">
            {`First halves end up worth about ${(100 * edge.mean).toFixed(1)}% of the full-game total in this sample — about half, and right where sportsbooks set the first-half line. Our estimated line uses a step share fitted on 2023–25 FBS games: ${proxyShareText()}. Graded against that fair estimate, neither betting every first-half under nor only the model’s top-20% picks reliably beat the −110 break-even (you need to win ${BREAKEVEN_PCT}%).`}
          </p>
          <p className="mt-2 text-sm leading-relaxed text-[var(--text-muted)]">
            <b className="text-[var(--text)]">Bottom line:</b>
            {` the backtest validates the gap band as a way to rank games, not as a profit. We cannot confirm an edge on free past data — there are no past first-half lines to check against. The real test is the live record below and on Results, built from real first-half lines captured this season.`}
          </p>
        </>
      ) : (
        <p className="bv-card p-6 text-sm text-[var(--text-muted)]">
          {`No played games loaded for ${scopeLabel} yet — this fills in once first-half results are in the database.`}
        </p>
      )}

      <hr className="my-6 border-[var(--border-soft)]" />

      <h2 className="mb-1 text-sm font-semibold text-[var(--text)]">
        Edge vs line value — do our biggest edges actually move the line our
        way?
      </h2>
      <p className="mb-3 text-xs leading-relaxed text-[var(--text-dim)]">
        {`Edge = Vegas line − our number (toward the under). If our number really finds value, the line on our biggest-edge games should drift toward us before kickoff — average line value rises with the size of the edge. If it is flat or negative, the big edges are blind spots, not value. Positive line value = the under closed at a more favorable number than the open.`}
      </p>

      {gapGraded === 0 ? (
        <p className="bv-card p-4 text-sm text-[var(--text-muted)]">
          {`No settled games with our number and a real closing line for ${scopeLabel} yet. This fills in through the season as first-half lines are captured before kickoff and the games are graded on Mondays.`}
        </p>
      ) : (
        <div className="bv-table-wrap">
          <table className="bv-table">
            <thead>
              <tr>
                <th>Edge size</th>
                <th title="Number of games in this group.">Games</th>
                <th>Avg edge</th>
                <th title="Average line value (CLV): positive = the line moved our way.">
                  Avg line value
                </th>
                <th title="Average profit in units at the closing line. 1 unit = one standard bet.">
                  Avg units
                </th>
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
                          ? "var(--text-dim)"
                          : b.meanClv > 0
                            ? "var(--under-strong)"
                            : "var(--over)",
                    }}
                  >
                    {b.meanClv ?? "—"}
                  </td>
                  <td className="font-mono text-[var(--text-muted)]">
                    {b.meanUnits ?? "—"}
                  </td>
                  <td className="font-mono text-[var(--text-muted)]">
                    {b.underPct !== null ? `${b.underPct}%` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <hr className="my-6 border-[var(--border-soft)]" />

      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-[var(--text)]">
            {`Line study — which opening first-half lines hit the under most often (${season})`}
          </h2>
          <p className="mt-1 text-xs leading-relaxed text-[var(--text-dim)]">
            {`Grouped by ${study.anyReal ? "real pre-kickoff opening lines" : `estimated lines (${proxyShareText()})`}${study.fbsFiltered ? ", FBS vs FBS only" : " — no FBS list for this season, so every game is included"}. You need to win ${BREAKEVEN_PCT}% to break even at −110.${study.anyReal ? "" : " On estimated lines this ranking partly reflects how high-scoring the games are, not a signal you can bet — treat it as a hint until real lines build up."}`}
          </p>
        </div>
        <MinGamesSelect current={minGames} />
      </div>
      {study.buckets.length === 0 ? (
        <p className="bv-card p-6 text-sm text-[var(--text-muted)]">
          {`No line buckets hold ${minGames}+ games for ${season} yet — early in a season there isn’t enough graded history to bucket. Lower the min-games filter or check back after a few weeks.`}
        </p>
      ) : (
        <LineStudyView buckets={study.buckets} breakeven={BREAKEVEN_PCT} />
      )}

      {calib && (
        <>
          <hr className="my-6 border-[var(--border-soft)]" />
          <h2 className="mb-1 text-sm font-semibold text-[var(--text)]">
            How accurate is our number? (on unseen games, all seasons)
          </h2>
          <p className="mb-3 text-xs leading-relaxed text-[var(--text-dim)]">
            {`Average miss = actual first-half points − our number, per segment (${calib.n.toLocaleString()} games). Near 0 = on target. A steady positive miss means our number runs low (it would wrongly lean "under"); the first post-2023 season can't be corrected from data that doesn't exist yet — so it's shown here, not hidden.`}
          </p>
          <div className="bv-table-wrap">
            <table className="bv-table">
              <thead>
                <tr>
                  <th>Segment</th>
                  <th title="Number of games.">Games</th>
                  <th title="Average of (actual first-half points − our number). 0 = on target.">
                    Avg miss
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="font-medium text-[var(--text)]">overall</td>
                  <td className="text-[var(--text-muted)]">{calib.n}</td>
                  <td className="font-mono text-[var(--text-muted)]">
                    {calib.overall ?? "—"}
                  </td>
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
                            ? "var(--text-dim)"
                            : Math.abs(s.meanResidual) <= 0.5
                              ? "var(--text)"
                              : "var(--neutral)",
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
        Model runs over time (all seasons)
      </h2>
      <p className="mb-3 text-xs text-[var(--text-dim)]">
        {`Does it get sharper as seasons are added? Under % for all picks vs the top picks, plus return — proxy-graded, so directional only.`}
      </p>

      {runs.length === 0 ? (
        <p className="bv-card p-4 text-sm text-[var(--text-muted)]">
          No model training runs logged yet.
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
                <th title="Under win rate on just the strongest picks.">
                  Under % (top)
                </th>
                <th title="Return on units risked for the top picks.">
                  Return (top)
                </th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r, i) => (
                <tr key={i} className="align-top">
                  <td className="font-mono text-[var(--text-muted)]">
                    {r.created_at.slice(0, 16)}
                  </td>
                  <td className="text-[var(--text-muted)]">
                    {r.train_window ?? "—"}
                  </td>
                  <td className="text-[var(--text-muted)]">
                    {r.test_window ?? "—"}
                  </td>
                  <td className="font-mono text-[var(--text-muted)]">
                    {r.baseline_under_pct ?? "—"}
                  </td>
                  <td
                    className="font-mono font-semibold"
                    style={{
                      color:
                        r.top_under_pct !== null &&
                        r.top_under_pct >= BREAKEVEN_PCT
                          ? "var(--under-strong)"
                          : "var(--over)",
                    }}
                  >
                    {r.top_under_pct ?? "—"}
                  </td>
                  <td
                    className="font-mono"
                    style={{
                      color:
                        r.top_roi !== null && r.top_roi >= 0
                          ? "var(--under-strong)"
                          : "var(--over)",
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

      <hr className="my-6 border-[var(--border-soft)]" />

      <h2 className="mb-1 text-sm font-semibold text-[var(--text)]">
        Candidate trends
        <span className="ml-2 text-[var(--neutral)]">(unconfirmed)</span>
      </h2>
      <p className="mb-3 max-w-3xl text-xs leading-relaxed text-[var(--text-dim)]">
        {`Top factors from the latest ranking run — hypotheses, not edges. A season is only ~14 weeks, so anything here is a multiple-testing candidate: pre-register it and confirm out-of-sample (and opponent-adjust — low scoring is often a blowout, i.e. the spread, already priced) before betting it.`}
      </p>
      {trends.length === 0 ? (
        <p className="bv-card p-4 text-sm text-[var(--text-muted)]">
          No factor ranking has been run yet — this table fills in once one is.
        </p>
      ) : (
        <div className="bv-table-wrap">
          <table className="bv-table">
            <thead>
              <tr>
                <th>Factor</th>
                <th>Family</th>
                <th title="Under % in the top-fraction selection (out of sample, proxy-graded).">
                  Under %
                </th>
                <th title="ROI on that selection at −110 (out of sample, proxy-graded).">
                  ROI
                </th>
                <th title="Correlation between the factor and the under, out of sample.">
                  Corr
                </th>
                <th>n</th>
              </tr>
            </thead>
            <tbody>
              {trends.map((t, i) => (
                <tr key={i}>
                  <td className="text-[var(--text)]">{t.factor}</td>
                  <td className="text-[var(--text-dim)]">{t.family ?? "—"}</td>
                  <td className="font-mono text-[var(--text-muted)]">
                    {t.underPct === null ? "—" : `${t.underPct.toFixed(1)}%`}
                  </td>
                  <td className="font-mono text-[var(--text-muted)]">
                    {t.roi === null ? "—" : `${(t.roi * 100).toFixed(1)}%`}
                  </td>
                  <td className="font-mono text-[var(--text-muted)]">
                    {t.corr === null ? "—" : t.corr.toFixed(3)}
                  </td>
                  <td className="font-mono text-[var(--text-dim)]">
                    {t.n ?? "—"}
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
