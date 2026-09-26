import { unitColor } from "@/lib/format";
import {
  bandTable,
  coverage,
  dedupeByCode,
  flagsFrom,
  headline,
  HIST_SCOPE,
  liveNotesFrom,
  liveScopeOf,
  loadPostMortem,
} from "@/lib/postmortem";
import {
  BREAKEVEN_PCT,
  DEFAULT_MIN_GAMES,
  getLineStudy,
} from "@/lib/lineStudy";
import { CALIB_SEGMENT_TEXT, labelOf } from "@/lib/labels";
import { getBvCalibration, getEdgeStats } from "@/lib/proof";
import { getRecordSeasons } from "@/lib/records";
import { getBetLedger, getBetSeasons } from "@/lib/betLedgerDb";
import { currentCfbSeason } from "@/lib/season";
import { BET_GAP_PTS, WEEKLY_BET_CAP } from "@/lib/verdict";
import BandTable from "@/app/components/BandTable";
import BetLedger from "@/app/components/BetLedger";
import Fold from "@/app/components/Fold";
import GapLadderChart from "@/app/components/GapLadderChart";
import Glossary from "@/app/components/Glossary";
import LineStudyView from "@/app/components/LineStudyView";
import MinGamesSelect from "@/app/components/MinGamesSelect";
import PmFlags from "@/app/components/PmFlags";
import PmLiveNotes from "@/app/components/PmLiveNotes";
import RecordTable from "@/app/components/RecordTable";
import { EmptyLine } from "@/app/components/Section";
import type { Record3 } from "@/lib/record";
import Link from "next/link";

export const dynamic = "force-dynamic";

// Track record: is the edge real. Cross-season, changes slowly, and split by
// GRADING BASIS rather than by era: only 2023–25 games a book actually priced
// carry a real closing line; the rest are graded against a line we worked out,
// and everything on that basis renders NEUTRAL and lives behind the one fold.
//
// Concept A "One finding" (Tate 2026-09-16): the headline and the gap ladder
// share one card, with games and units under each bar so no band table
// follows it; the records are one table with a "plausibly" column; the live
// season is one panel; the flags are rows; method, sanity checks and the line
// study sit behind ONE fold; the glossary is two columns of one-liners.

export default async function ProofPage({
  searchParams,
}: {
  searchParams: Promise<{ season?: string; minGames?: string }>;
}) {
  const sp = await searchParams;
  const minGames =
    sp.minGames && Number(sp.minGames) > 0
      ? Number(sp.minGames)
      : DEFAULT_MIN_GAMES;

  // Season lists still disagree with board.getSeasons (which has no
  // model_version guard). Unifying them changes which season the BOARD
  // resolves to, so it is deliberately deferred (Tate 2026-09-10).
  const seasons = await getRecordSeasons();
  // No ?season= means ALL seasons: 2026 has no total with enough graded games
  // to reach the minimum, so a single-season default shows an empty study.
  const one =
    sp.season && sp.season !== "all" && Number.isFinite(Number(sp.season))
      ? Number(sp.season)
      : null;
  const studySeasons = one !== null ? [one] : seasons;
  const scopeLabel = one !== null ? `${one}` : "all seasons";

  // The ledger's season: the one asked for, else the current CFB season, else
  // the latest season that holds a pick (the off-season, or a fresh database).
  const betSeasons = await getBetSeasons();
  const current = currentCfbSeason();
  const ledgerSeason =
    one ??
    (betSeasons.includes(current) ? current : (betSeasons[0] ?? current));

  const [pm, edge, calib, study, bets] = await Promise.all([
    loadPostMortem(),
    getEdgeStats(one ?? undefined),
    getBvCalibration(),
    studySeasons.length > 0
      ? getLineStudy(studySeasons, minGames)
      : Promise.resolve(null),
    getBetLedger(ledgerSeason),
  ]);

  // The ledger leads (Tate 2026-09-26): every bet, as logged, before the
  // 2023-25 finding. It renders even when the post-mortem has never run.
  const header = (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="bv-page-title">Track record</h1>
        <p className="bv-page-sub">
          {`Every bet since ${ledgerSeason} at Hard Rock’s number, then 2023–25 at real closing lines.`}
        </p>
      </div>
      <Link href="/proof/records" className="bv-btn">
        Every game we have rated →
      </Link>
    </div>
  );
  const ledger = <BetLedger rows={bets} season={ledgerSeason} />;

  if (!pm || pm.runs.length === 0) {
    return (
      <div className="mx-auto max-w-5xl">
        {header}
        {ledger}
        <EmptyLine className="mt-6">
          The 2023–25 finding is not computed yet. It runs after each morning’s
          grading.
        </EmptyLine>
      </div>
    );
  }

  const { runs, buckets } = pm;
  const hist = runs.find((r) => r.scope === HIST_SCOPE);
  const liveScope = liveScopeOf(runs);
  const live = liveScope ? runs.find((r) => r.scope === liveScope) : undefined;
  const liveSeason = liveScope ? liveScope.replace("live_", "") : "";
  const ln = liveNotesFrom(live);
  const flags = dedupeByCode([...flagsFrom(hist), ...flagsFrom(live)]).filter(
    (f) => f.code !== "multiple_comparisons",
  );
  const mc = flagsFrom(hist).find((f) => f.code === "multiple_comparisons");

  const lead = headline(buckets, HIST_SCOPE, "fbs_only", "real", "cap5");
  // The rule as lived -- no cap applied afterwards -- with its interval, so the
  // page never shows a win rate without the range that contains break-even.
  const ruleReal = headline(buckets, HIST_SCOPE, "fbs_only", "real", "gap175");
  const pctOf = (v: number | null) =>
    v === null ? "—" : `${(100 * v).toFixed(1)}%`;
  const beInside = (r: Record3 | null) =>
    r !== null && r.hitLo !== null && r.hitHi !== null
      ? 100 * r.hitLo <= BREAKEVEN_PCT && BREAKEVEN_PCT <= 100 * r.hitHi
      : null;
  const cov = coverage(buckets, HIST_SCOPE, "fbs_only");
  const gapReal = bandTable(
    buckets,
    HIST_SCOPE,
    "fbs_only",
    "real",
    "gap_band",
  );
  const gapEstimated = bandTable(
    buckets,
    HIST_SCOPE,
    "fbs_only",
    "step",
    "gap_band",
  );
  const hrVsMarket = liveScope
    ? bandTable(buckets, liveScope, "live", "hr", "hr_vs_market", "all_hr")
    : [];
  const hrVsMarketClose = liveScope
    ? bandTable(
        buckets,
        liveScope,
        "live",
        "market_close",
        "hr_vs_market",
        "all_hr",
      )
    : [];
  const computed = (hist?.computed_at ?? live?.computed_at ?? "")
    .slice(0, 16)
    .replace("T", " ");

  return (
    <div className="mx-auto max-w-5xl">
      {header}
      {ledger}

      {/* 1 — the finding: the one honest number and the picture that explains
          it, in one card. */}
      <section
        aria-label="The finding"
        className="bv-card mb-8 grid grid-cols-1 gap-x-8 gap-y-6 p-5 lg:grid-cols-[1fr_1.5fr] lg:items-center"
      >
        {lead === null ? (
          <EmptyLine>
            No 2023–25 games with a real captured close have been graded yet.
          </EmptyLine>
        ) : (
          <div>
            <p className="bv-stat-label">
              {`First-half unders won, 2023–25, ${WEEKLY_BET_CAP} a week`}
            </p>
            <p className="mt-2 font-[family-name:var(--font-display)] text-6xl font-extrabold leading-none tabular-nums text-[var(--text)]">
              {lead.hit}
            </p>
            <p className="mt-3 font-mono text-sm text-[var(--text-muted)]">
              {lead.record}
              {" · "}
              <span style={{ color: unitColor(lead.units) }}>
                {`${lead.units}u`}
              </span>
              {` · ROI ${lead.roi}`}
            </p>
            <p className="mt-2 text-xs leading-relaxed text-[var(--text-dim)]">
              {`${lead.n} bets, plausibly ${pctOf(lead.hitLo)}–${pctOf(lead.hitHi)}. Hard Rock did not exist in these seasons and the cap was applied afterwards, not lived — what the method would have returned, not money won.`}
            </p>
            {ruleReal !== null && (
              <p className="mt-2 text-xs leading-relaxed text-[var(--text-dim)]">
                {`Without the cap — every game the rule qualified — it won ${ruleReal.hit} of ${ruleReal.n}, plausibly ${pctOf(ruleReal.hitLo)}–${pctOf(ruleReal.hitHi)}. Break-even at −110 is ${BREAKEVEN_PCT.toFixed(1)}%, which is ${beInside(ruleReal) === false ? "outside" : "inside"} that range.`}
              </p>
            )}
          </div>
        )}
        <div>
          <p className="bv-stat-label mb-1">
            The wider the gap, the more often the under wins
          </p>
          <GapLadderChart rows={gapReal} breakeven={BREAKEVEN_PCT} />
        </div>
      </section>

      {/* 2 — everything graded against a line a book actually posted. */}
      <h2 className="mb-2 text-sm font-semibold text-[var(--text)]">
        At real closing lines
        <span className="ml-2 text-xs font-normal text-[var(--text-dim)]">
          {cov
            ? `${cov.real.toLocaleString()} of ${cov.total.toLocaleString()} FBS games in 2023–25 were priced`
            : "the numbers to believe"}
        </span>
      </h2>
      <RecordTable
        ariaLabel="Records at real closing lines"
        showInterval
        rows={[
          {
            key: "gap175",
            label: `2023–25, every gap ${BET_GAP_PTS}+`,
            note: "no weekly cap",
            rec: headline(buckets, HIST_SCOPE, "fbs_only", "real", "gap175"),
            empty: "nothing graded yet",
          },
          {
            key: "bet",
            label: `${liveSeason || "This season"}, bets at Hard Rock’s line`,
            rec: liveScope
              ? headline(buckets, liveScope, "live", "hr", "bet")
              : null,
            empty: "no bets graded yet",
          },
          {
            key: "price",
            label: `${liveSeason || "This season"}, good prices at Hard Rock’s line`,
            note: "the under paid at least the fair price",
            rec: liveScope
              ? headline(buckets, liveScope, "live", "hr", "price_read")
              : null,
            empty: "no Hard Rock under has beaten the fair price yet",
          },
          {
            key: "all_hr",
            label: `${liveSeason || "This season"}, every Hard Rock number`,
            note: "the baseline our picks have to beat",
            rec: liveScope
              ? headline(buckets, liveScope, "live", "hr", "all_hr")
              : null,
            empty: "no Hard Rock first-half numbers graded yet",
          },
        ]}
      />

      {liveScope && (
        <PmLiveNotes
          liveSeason={liveSeason}
          ln={ln}
          hrVsMarket={hrVsMarket}
          hrVsMarketClose={hrVsMarketClose}
        />
      )}

      {/* 3 — the actionable conclusion. */}
      <h2 className="mb-2 mt-10 text-sm font-semibold text-[var(--text)]">
        What to change
        {computed && (
          <span className="ml-2 text-xs font-normal text-[var(--text-dim)]">
            {`computed ${computed} UTC`}
          </span>
        )}
      </h2>
      {mc && (
        <p className="mb-2 text-xs leading-relaxed text-[var(--text-dim)]">
          {mc.text}
        </p>
      )}
      <PmFlags flags={flags} />

      {/* 4 — method and sanity checks, behind ONE fold. */}
      <Fold
        title="Method and sanity checks"
        hint="the estimated-line grade, how the number is built, its out-of-sample miss, and which totals go under most"
      >
        <h3 className="mb-2 text-sm font-semibold text-[var(--text)]">
          Against an estimated line
          <span className="ml-2 text-xs font-normal text-[var(--text-dim)]">
            no book priced these games; nothing here is coloured
          </span>
        </h3>
        <RecordTable
          ariaLabel="Records at an estimated line"
          basis="estimated"
          rows={[
            {
              key: "cap5",
              label: `2023–25, the same cap-${WEEKLY_BET_CAP} rule`,
              rec: headline(buckets, HIST_SCOPE, "fbs_only", "step", "cap5"),
              empty: "nothing graded yet",
            },
            {
              key: "gap175",
              label: `2023–25, every gap ${BET_GAP_PTS}+`,
              rec: headline(buckets, HIST_SCOPE, "fbs_only", "step", "gap175"),
              empty: "nothing graded yet",
            },
          ]}
        />
        <BandTable
          title="Win rate by gap size, at an estimated line"
          rows={gapEstimated}
          basis="estimated"
        />

        <h3 className="mb-2 mt-8 text-sm font-semibold text-[var(--text)]">
          How the number is built
          <span className="ml-2 text-xs font-normal text-[var(--text-dim)]">
            {`every finished FBS-vs-FBS game, ${scopeLabel}`}
          </span>
        </h3>
        {edge ? (
          <div className="bv-table-wrap px-4 py-1">
            <dl className="grid grid-cols-1 gap-x-10 sm:grid-cols-3">
              <Stat
                label="Games looked at"
                value={edge.games.toLocaleString()}
              />
              <Stat
                label="First half’s share of the full game"
                value={`${(100 * edge.mean).toFixed(1)}%`}
              />
              <Stat
                label="Middle value"
                value={`${(100 * edge.median).toFixed(1)}%`}
              />
            </dl>
          </div>
        ) : (
          <EmptyLine>{`No finished games for ${scopeLabel} yet.`}</EmptyLine>
        )}

        <h3 className="mb-2 mt-8 text-sm font-semibold text-[var(--text)]">
          How accurate our number is
          {calib && (
            <span className="ml-2 text-xs font-normal text-[var(--text-dim)]">
              {`average miss in points over ${calib.n.toLocaleString()} games it never trained on; near zero is on target`}
            </span>
          )}
        </h3>
        {calib ? (
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
                {calib.segments.map((sg) => (
                  <tr key={sg.label}>
                    <td className="text-[var(--text-muted)]">
                      {labelOf(CALIB_SEGMENT_TEXT, sg.label, sg.label)}
                    </td>
                    <td className="bv-num text-[var(--text-muted)]">{sg.n}</td>
                    <td
                      className="bv-num font-mono"
                      style={{
                        color:
                          sg.meanResidual === null
                            ? "var(--text-dim)"
                            : Math.abs(sg.meanResidual) <= 0.5
                              ? "var(--text)"
                              : "var(--warn)",
                      }}
                    >
                      {sg.meanResidual ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyLine>
            No model run has recorded its out-of-sample misses yet.
          </EmptyLine>
        )}

        <div className="mb-2 mt-8 flex flex-wrap items-end justify-between gap-3">
          <h3 className="text-sm font-semibold text-[var(--text)]">
            {`Which first-half totals go under most often`}
            <span className="ml-2 text-xs font-normal text-[var(--text-dim)]">
              {`${scopeLabel} · by the total the book opened at`}
            </span>
          </h3>
          <MinGamesSelect current={minGames} />
        </div>
        {!study || study.buckets.length === 0 ? (
          <EmptyLine>
            {`No total has ${minGames}+ graded games in ${scopeLabel} yet. Lower the minimum, or check back later in the season.`}
          </EmptyLine>
        ) : (
          <LineStudyView buckets={study.buckets} breakeven={BREAKEVEN_PCT} />
        )}
      </Fold>

      <Glossary />
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-t border-[var(--border)] py-2 text-sm first:border-t-0 sm:border-t-0">
      <dt className="text-[var(--text-muted)]">{label}</dt>
      <dd className="font-mono tabular-nums text-[var(--text)]">{value}</dd>
    </div>
  );
}
