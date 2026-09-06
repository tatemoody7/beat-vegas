import { getSeasons } from "@/lib/board";
import { getDecisionQuality } from "@/lib/decision-quality";
import { bankrollCurve, bankrollEnv } from "@/lib/homeBoard";
import { getLedger } from "@/lib/ledger";
import { loadPicks } from "@/lib/picks";
import { loadPostMortem } from "@/lib/postmortem";
import type { Record3 } from "@/lib/record";
import { resolveSeason } from "@/lib/season";
import { getWeeklyReview, REASON_LABEL } from "@/lib/weeklyReview";
import BankrollCurve from "@/app/components/BankrollCurve";
import PicksList from "@/app/components/PicksList";
import PostMortemPanel from "@/app/components/PostMortemPanel";
import SeasonFallbackNotice from "@/app/components/SeasonFallbackNotice";
import SeasonSelect from "@/app/components/SeasonSelect";
import WeekSelect from "@/app/components/WeekSelect";

export const dynamic = "force-dynamic";

// Results: how the market, the model and you did — season summary, one week's
// scorecard, week by week, by the reason each pick was logged, the
// decision-quality lens, and every pick (delete while ungraded). Replaces the
// old /ledger, /weekly-review and /picks pages.

const pct = (v: number | null | undefined) =>
  v == null ? "—" : `${v.toFixed(1)}%`;

// Green/red are OUTCOME colors: signed units only.
const unitColor = (s: string | undefined | null) =>
  !s || s === "—"
    ? "var(--text-dim)"
    : s.startsWith("-")
      ? "var(--over)"
      : "var(--under-strong)";

function RecordCard({
  title,
  rec,
  emptyHint,
  hint,
}: {
  title: string;
  rec: Record3 | null;
  emptyHint: string;
  hint?: string;
}) {
  return (
    <div className="bv-card p-4" title={hint}>
      <h3 className="mb-2 text-sm font-semibold text-[var(--text)]">{title}</h3>
      {rec === null ? (
        <p className="text-xs text-[var(--text-dim)]">{emptyHint}</p>
      ) : (
        <dl className="space-y-3">
          <div>
            <dt
              className="bv-stat-label"
              title="Share of decided bets that won."
            >
              Win rate
            </dt>
            <dd className="mt-0.5 font-[family-name:var(--font-display)] text-2xl font-extrabold tabular-nums text-[var(--text)]">
              {rec.hit}
              <span className="ml-2 font-sans text-sm font-normal text-[var(--text-dim)]">
                {rec.record}
              </span>
            </dd>
          </div>
          <div className="flex flex-wrap gap-x-5 gap-y-2">
            <div>
              <dt
                className="bv-stat-label"
                title="Profit in units. 1 unit = one standard bet."
              >
                Units
              </dt>
              <dd
                className="mt-0.5 font-mono text-lg font-semibold tabular-nums"
                style={{ color: unitColor(rec.units) }}
              >
                {rec.units}
              </dd>
            </div>
            <div>
              <dt
                className="bv-stat-label"
                title="Return on units staked: units won ÷ units risked over graded bets."
              >
                ROI
              </dt>
              <dd className="mt-0.5 font-mono text-lg font-semibold tabular-nums text-[var(--text-muted)]">
                {rec.roi}
              </dd>
            </div>
            <div>
              <dt
                className="bv-stat-label"
                title="Average line value (CLV): did the line move our way after the bet? Positive = beat the close."
              >
                Avg line value
              </dt>
              <dd className="mt-0.5 font-mono text-lg font-semibold tabular-nums text-[var(--text-muted)]">
                {rec.clv}
              </dd>
            </div>
          </div>
        </dl>
      )}
    </div>
  );
}

function RecCells({ rec }: { rec: Record3 | null }) {
  if (!rec) {
    return (
      <>
        <td className="text-[var(--text-dim)]">—</td>
        <td className="text-[var(--text-dim)]">—</td>
        <td className="text-[var(--text-dim)]">—</td>
        <td className="text-[var(--text-dim)]">—</td>
      </>
    );
  }
  return (
    <>
      <td className="font-mono text-[var(--text)]">{rec.record}</td>
      <td className="font-mono" style={{ color: unitColor(rec.units) }}>
        {rec.units}
      </td>
      <td className="font-mono text-[var(--text-muted)]">{rec.roi}</td>
      <td className="font-mono text-[var(--text-muted)]">{rec.clv}</td>
    </>
  );
}

function RecHead() {
  return (
    <>
      <th title="Wins-losses(-pushes) on graded bets.">W-L-P</th>
      <th title="Profit in units. 1 unit = one standard bet.">Units</th>
      <th title="Units won ÷ units staked.">ROI</th>
      <th title="Average line value (CLV): positive = the line moved our way after the bet.">
        Avg CLV
      </th>
    </>
  );
}

export default async function ResultsPage({
  searchParams,
}: {
  searchParams: Promise<{ season?: string; week?: string }>;
}) {
  const seasons = await getSeasons();
  const sp = await searchParams;
  const { season, fallbackFrom } = resolveSeason(seasons, sp.season);
  const wantWeek: number | "all" | undefined =
    sp.week === "all"
      ? "all"
      : sp.week && Number.isFinite(Number(sp.week))
        ? Number(sp.week)
        : undefined;

  const [ledger, review, dq, allPicks, pm] = await Promise.all([
    getLedger(season),
    getWeeklyReview(season, wantWeek),
    getDecisionQuality(season),
    loadPicks(season),
    loadPostMortem(),
  ]);
  const settled = review.lines.filter((l) => l.rec);
  const weekLabel = review.week === null ? "all weeks" : `week ${review.week}`;
  const { startUsd, unitUsd } = bankrollEnv();
  const curve = bankrollCurve(allPicks, startUsd, unitUsd);

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="bv-page-title">Results</h1>
          <p className="bv-page-sub mt-1">
            {`How the market, the model and you did in ${season}. Market = the first-half under at the real closing line · Model = the model’s picks · You = your real-money first-half bets, with paper picks kept apart.`}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {review.weeks.length > 0 && (
            <WeekSelect
              weeks={review.weeks}
              current={review.week ?? "all"}
              allowAll
            />
          )}
          {seasons.length > 0 && (
            <SeasonSelect seasons={seasons} current={season} />
          )}
        </div>
      </div>

      <SeasonFallbackNotice fallbackFrom={fallbackFrom} season={season} />

      {/* Season summary */}
      <h2 className="mb-2 text-sm font-semibold text-[var(--text)]">
        {`Season summary · ${season}`}
      </h2>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <RecordCard
          title="Market — first half"
          rec={ledger.market}
          emptyHint="Fills in once first-half lines are captured before kickoff and the games settle."
          hint="Every game's first-half under at the real closing line — the blanket-under baseline."
        />
        <RecordCard
          title="Model — first half"
          rec={ledger.model}
          emptyHint="Fills in once the week is scored and settled (the model sits out weeks 1–2)."
          hint="The model's under picks graded at the closing line."
        />
        <RecordCard
          title="You — real money (first half)"
          rec={ledger.you}
          emptyHint="No settled real-money bets yet. Log bets from the board."
          hint="Real-money first-half picks only — the record the bankroll follows."
        />
        <RecordCard
          title="You — paper (no money)"
          rec={ledger.paper}
          emptyHint="No settled paper picks yet."
          hint="Tracked with nothing at risk; never merged into the real record."
        />
        <RecordCard
          title="Market — full game"
          rec={ledger.marketFull}
          emptyHint="Fills in once full-game lines settle."
          hint="Context only: the full-game under at the closing line. We do not bet full game."
        />
      </div>

      {/* Bankroll curve */}
      <h2 className="mb-2 mt-8 text-sm font-semibold text-[var(--text)]">
        Bankroll, week by week
      </h2>
      {curve.length < 2 ? (
        <p className="bv-card p-4 text-sm text-[var(--text-muted)]">
          {`No settled real-money bets yet — the curve starts once a week grades. Starting bankroll is $${startUsd}, one unit is $${unitUsd}.`}
        </p>
      ) : (
        <>
          <BankrollCurve points={curve} startUsd={startUsd} />
          <p className="mt-1 text-xs text-[var(--text-dim)]">
            {`Settled real-money first-half bets only, at $${unitUsd} a unit. The dashed line is the $${startUsd} starting bankroll; pending bets do not move it.`}
          </p>
        </>
      )}

      {/* One week's scorecard */}
      {review.week !== null && (
        <>
          <h2 className="mb-2 mt-8 text-sm font-semibold text-[var(--text)]">
            {`Week ${review.week} scorecard`}
          </h2>
          <div className="bv-table-wrap">
            <table className="bv-table">
              <thead>
                <tr>
                  <th>Who</th>
                  <th>Market</th>
                  <th>Under %</th>
                  <RecHead />
                </tr>
              </thead>
              <tbody>
                {settled.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="text-[var(--text-muted)]">
                      {`Nothing graded for week ${review.week} yet — grading runs Monday morning.`}
                    </td>
                  </tr>
                ) : (
                  settled.map((l, i) => (
                    <tr key={i}>
                      <td className="text-[var(--text)]">{l.entity}</td>
                      <td className="text-[var(--text-muted)]">{l.market}</td>
                      <td className="font-mono text-[var(--text-muted)]">
                        {l.rec!.hit}
                      </td>
                      <RecCells rec={l.rec} />
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Week by week */}
      <h2 className="mb-2 mt-8 text-sm font-semibold text-[var(--text)]">
        Week by week — your first-half picks
      </h2>
      {review.byWeek.length === 0 ? (
        <p className="bv-card p-4 text-sm text-[var(--text-muted)]">
          {`No picks logged for ${season} yet. Log bets from the board; this table fills in as weeks settle.`}
        </p>
      ) : (
        <div className="bv-table-wrap">
          <table className="bv-table">
            <thead>
              <tr>
                <th rowSpan={2}>Week</th>
                <th colSpan={5}>Real money</th>
                <th colSpan={5}>Paper</th>
              </tr>
              <tr>
                <th title="Real-money first-half bets logged (pending included).">
                  Bets
                </th>
                <RecHead />
                <th title="Paper first-half picks logged (pending included).">
                  Picks
                </th>
                <RecHead />
              </tr>
            </thead>
            <tbody>
              {review.byWeek.map((w) => (
                <tr key={w.week}>
                  <td className="font-mono text-[var(--text)]">{w.week}</td>
                  <td className="font-mono text-[var(--text-muted)]">
                    {w.realBets}
                  </td>
                  <RecCells rec={w.real} />
                  <td className="font-mono text-[var(--text-muted)]">
                    {w.paperBets}
                  </td>
                  <RecCells rec={w.paper} />
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* By reason */}
      <h2 className="mb-1 mt-8 text-sm font-semibold text-[var(--text)]">
        By reason — which kind of bet is paying?
      </h2>
      <p className="mb-2 text-xs text-[var(--text-dim)]">
        The reason is frozen onto the pick when you log it, so this cannot be
        rewritten after the fact.
      </p>
      {review.byReason.length === 0 ? (
        <p className="bv-card p-4 text-sm text-[var(--text-muted)]">
          No picks logged yet.
        </p>
      ) : (
        <div className="bv-table-wrap">
          <table className="bv-table">
            <thead>
              <tr>
                <th rowSpan={2}>Reason</th>
                <th colSpan={5}>Real money</th>
                <th colSpan={5}>Paper</th>
              </tr>
              <tr>
                <th>Bets</th>
                <RecHead />
                <th>Picks</th>
                <RecHead />
              </tr>
            </thead>
            <tbody>
              {review.byReason.map((r) => (
                <tr key={r.reason}>
                  <td className="text-[var(--text)]">
                    {REASON_LABEL[r.reason]}
                  </td>
                  <td className="font-mono text-[var(--text-muted)]">
                    {r.realBets}
                  </td>
                  <RecCells rec={r.real} />
                  <td className="font-mono text-[var(--text-muted)]">
                    {r.paperBets}
                  </td>
                  <RecCells rec={r.paper} />
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Decision quality */}
      <h2 className="mb-2 mt-8 text-sm font-semibold text-[var(--text)]">
        Decision quality — all graded picks
      </h2>
      {dq.n === 0 ? (
        <p className="bv-card p-4 text-sm text-[var(--text-muted)]">
          No graded picks yet. Once picks settle this shows whether your calls
          beat your model, beat the close, and which factors you lean on well.
        </p>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="bv-card p-4">
              <h3 className="mb-2 text-sm font-semibold text-[var(--text)]">
                Beat my model
              </h3>
              <dl className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <dt
                    className="bv-stat-label"
                    title="Win rate when the line you took sat above our number (the model agreed)."
                  >
                    With model
                  </dt>
                  <dd className="font-mono text-[var(--text-muted)]">
                    {`${pct(dq.beatModel.agreed.hitPct)} (${dq.beatModel.agreed.n})`}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt
                    className="bv-stat-label"
                    title="Win rate when you picked against our number."
                  >
                    Against model
                  </dt>
                  <dd className="font-mono text-[var(--text-muted)]">
                    {`${pct(dq.beatModel.against.hitPct)} (${dq.beatModel.against.n})`}
                  </dd>
                </div>
              </dl>
            </div>
            <div className="bv-card p-4">
              <h3 className="mb-2 text-sm font-semibold text-[var(--text)]">
                Beat the close
              </h3>
              <dl className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <dt
                    className="bv-stat-label"
                    title="Average closing-line value."
                  >
                    Avg CLV
                  </dt>
                  <dd className="font-mono text-[var(--text-muted)]">
                    {`${dq.clv.avg == null ? "—" : dq.clv.avg.toFixed(2)} (${dq.clv.n})`}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt
                    className="bv-stat-label"
                    title="Share of picks with positive CLV."
                  >
                    % positive
                  </dt>
                  <dd className="font-mono text-[var(--text-muted)]">
                    {`${pct(dq.clv.pctPositive)} (${dq.clv.n})`}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt
                    className="bv-stat-label"
                    title="No-vig PRICE CLV: average open-to-close move in the under's fair price, in percentage points. Isolates the juice; line movement is in Avg CLV."
                  >
                    Price CLV
                  </dt>
                  <dd className="font-mono text-[var(--text-muted)]">
                    {`${dq.clv.avgPricePp == null ? "—" : `${dq.clv.avgPricePp >= 0 ? "+" : ""}${dq.clv.avgPricePp.toFixed(2)}pp`} (${dq.clv.nPrice})`}
                  </dd>
                </div>
              </dl>
            </div>
            <div className="bv-card p-4">
              <h3 className="mb-2 text-sm font-semibold text-[var(--text)]">
                Timing
              </h3>
              <dl className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <dt
                    className="bv-stat-label"
                    title="Share of picks taken at or above the opening line (for an under, higher is better)."
                  >
                    At or above open
                  </dt>
                  <dd className="font-mono text-[var(--text-muted)]">
                    {`${pct(dq.timing.pctAtOrBetterThanOpen)} (${dq.timing.nOpen})`}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt
                    className="bv-stat-label"
                    title="Share of picks with a better number than the close."
                  >
                    Beat close
                  </dt>
                  <dd className="font-mono text-[var(--text-muted)]">
                    {`${pct(dq.timing.pctBeatingClose)} (${dq.timing.nClose})`}
                  </dd>
                </div>
              </dl>
            </div>
          </div>
          {dq.factors.length > 0 && (
            <div className="bv-table-wrap mt-3">
              <table className="bv-table">
                <thead>
                  <tr>
                    <th>Factor (green on your picks)</th>
                    <th>Your n</th>
                    <th>Your hit %</th>
                    <th title="Real-line under rate when this factor is green, from the factor ledger.">
                      Ledger hit %
                    </th>
                    <th>Read</th>
                  </tr>
                </thead>
                <tbody>
                  {dq.factors.map((f) => (
                    <tr key={f.key}>
                      <td className="text-[var(--text)]">{f.label}</td>
                      <td className="font-mono text-[var(--text-muted)]">
                        {f.n}
                      </td>
                      <td className="font-mono text-[var(--text-muted)]">
                        {pct(f.yourHitPct)}
                      </td>
                      <td className="font-mono text-[var(--text-muted)]">
                        {f.ledgerHitPct == null ? "—" : pct(f.ledgerHitPct)}
                      </td>
                      <td>
                        <span className="bv-pill">
                          <span className="bv-pill-value">
                            {f.weight === "even"
                              ? "balanced"
                              : f.weight === "under"
                                ? "you use it well"
                                : "you over-lean on it"}
                          </span>
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* Post-mortem */}
      <PostMortemPanel pm={pm} />

      {/* Pick history */}
      <h2 className="mb-2 mt-8 text-sm font-semibold text-[var(--text)]">
        {`Your picks — ${weekLabel}`}
      </h2>
      <PicksList picks={review.picks} />
    </div>
  );
}
