import { getSeasons } from "@/lib/board";
import { getWeeklyReview } from "@/lib/weeklyReview";
import { getTrends } from "@/lib/trends";
import SeasonSelect from "@/app/components/SeasonSelect";
import WeekSelect from "@/app/components/WeekSelect";

export const dynamic = "force-dynamic";

const unitColor = (s: string | undefined) =>
  s === undefined || s === "—"
    ? "var(--text-dim)"
    : s.startsWith("-")
      ? "var(--over)"
      : "var(--under-strong)";

export default async function WeeklyReviewPage({
  searchParams,
}: {
  searchParams: Promise<{ season?: string; week?: string }>;
}) {
  const seasons = await getSeasons();
  const sp = await searchParams;
  const requested = sp.season ? Number(sp.season) : NaN;
  const season =
    Number.isFinite(requested) && seasons.includes(requested)
      ? requested
      : (seasons[0] ?? new Date().getFullYear());
  const wantWeek = sp.week ? Number(sp.week) : undefined;

  const [review, trends] = await Promise.all([
    getWeeklyReview(season, wantWeek),
    getTrends(),
  ]);
  const settled = review.lines.filter((l) => l.rec);

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="bv-page-title">Weekly Review</h1>
          <p className="bv-page-sub">
            How the market, the model, and you did this week — full game and first
            half — once the games finished.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {review.weeks.length > 0 && review.week !== null && (
            <WeekSelect weeks={review.weeks} current={review.week} />
          )}
          {seasons.length > 0 && (
            <SeasonSelect seasons={seasons} current={season} />
          )}
        </div>
      </div>

      {review.week === null ? (
        <p className="bv-card p-6 text-sm text-[var(--text-muted)]">
          Nothing graded for {season} yet. The review fills in after a week&apos;s
          games finish and grading runs.
        </p>
      ) : (
        <>
          <h2 className="mb-2 text-sm font-semibold text-[var(--text)]">
            Week {review.week} scorecard
          </h2>
          <div className="bv-table-wrap mb-7">
            <table className="bv-table">
              <thead>
                <tr>
                  <th>Who</th>
                  <th>Market</th>
                  <th>Record</th>
                  <th>Under %</th>
                  <th title="Profit in units. 1 unit = one standard bet.">
                    Units
                  </th>
                  <th title="Average line value: positive = the line moved toward the under after the bet.">
                    Avg CLV
                  </th>
                </tr>
              </thead>
              <tbody>
                {settled.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="text-[var(--text-muted)]">
                      No graded bets for week {review.week} yet.
                    </td>
                  </tr>
                ) : (
                  settled.map((l, i) => (
                    <tr key={i}>
                      <td className="text-[var(--text)]">{l.entity}</td>
                      <td className="text-[var(--text-muted)]">{l.market}</td>
                      <td className="font-mono text-[var(--text)]">
                        {l.rec!.record}
                      </td>
                      <td className="font-mono text-[var(--text-muted)]">
                        {l.rec!.hit}
                      </td>
                      <td
                        className="font-mono"
                        style={{ color: unitColor(l.rec!.units) }}
                      >
                        {l.rec!.units}
                      </td>
                      <td className="font-mono text-[var(--text-muted)]">
                        {l.rec!.clv}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <h2 className="mb-2 text-sm font-semibold text-[var(--text)]">
            Your picks — week {review.week}
          </h2>
          {review.picks.length === 0 ? (
            <p className="bv-card p-4 text-sm text-[var(--text-muted)]">
              You didn&apos;t log any picks for week {review.week}.
            </p>
          ) : (
            <div className="bv-table-wrap">
              <table className="bv-table">
                <thead>
                  <tr>
                    <th>Matchup</th>
                    <th>Market</th>
                    <th>Your line</th>
                    <th>Result</th>
                    <th>Units</th>
                    <th>CLV</th>
                  </tr>
                </thead>
                <tbody>
                  {review.picks.map((p, i) => (
                    <tr key={i}>
                      <td className="text-[var(--text)]">
                        {p.away}{" "}
                        <span className="text-[var(--text-dim)]">@</span> {p.home}
                      </td>
                      <td className="text-[var(--text-muted)]">{p.market}</td>
                      <td className="text-[var(--text-muted)]">
                        {p.line !== null ? `under ${p.line}` : "—"}
                      </td>
                      <td
                        style={{
                          color:
                            p.result === "under"
                              ? "var(--under-strong)"
                              : p.result === "over"
                                ? "var(--over)"
                                : "var(--text-dim)",
                        }}
                      >
                        {p.result}
                      </td>
                      <td
                        className="font-mono"
                        style={{
                          color:
                            p.units === null
                              ? "var(--text-dim)"
                              : p.units >= 0
                                ? "var(--under-strong)"
                                : "var(--over)",
                        }}
                      >
                        {p.units === null
                          ? "—"
                          : `${p.units >= 0 ? "+" : ""}${p.units.toFixed(2)}`}
                      </td>
                      <td className="font-mono text-[var(--text-muted)]">
                        {p.clv === null
                          ? "—"
                          : `${p.clv >= 0 ? "+" : ""}${p.clv.toFixed(2)}`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      <h2 className="mb-1 mt-8 text-sm font-semibold text-[var(--text)]">
        Candidate trends{" "}
        <span className="text-[var(--neutral)]">(UNCONFIRMED)</span>
      </h2>
      <p className="bv-page-sub mb-3 max-w-3xl">
        Top factors from the latest ranking run — <strong>hypotheses, not edges</strong>.
        A season is only ~14 weeks, so anything here is a multiple-testing candidate:
        pre-register it and confirm out-of-sample (and opponent-adjust — low scoring is
        often a blowout, i.e. the spread, already priced) before betting it.
      </p>
      {trends.length === 0 ? (
        <p className="bv-card p-4 text-sm text-[var(--text-muted)]">
          No factor-ranking run found yet. Run{" "}
          <code className="text-[var(--text)]">scripts/rank_factors.py</code> to populate
          candidate trends.
        </p>
      ) : (
        <div className="bv-table-wrap">
          <table className="bv-table">
            <thead>
              <tr>
                <th>Factor</th>
                <th>Family</th>
                <th title="Under% in the top-fraction selection (OOS).">Under %</th>
                <th title="ROI on that selection at -110 (OOS).">ROI</th>
                <th title="Pearson corr(factor, under) out-of-sample.">Corr</th>
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
                  <td className="font-mono text-[var(--text-dim)]">{t.n ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
