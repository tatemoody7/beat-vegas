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
import { viewerIsAuthed } from "@/lib/session";
import { BET_GAP_PTS, WEEKLY_BET_CAP } from "@/lib/verdict";
import BandTable from "@/app/components/BandTable";
import Fold from "@/app/components/Fold";
import GapLadderChart from "@/app/components/GapLadderChart";
import Glossary from "@/app/components/Glossary";
import LineStudyView from "@/app/components/LineStudyView";
import MinGamesSelect from "@/app/components/MinGamesSelect";
import PmFlags from "@/app/components/PmFlags";
import PmLiveNotes from "@/app/components/PmLiveNotes";
import RecordTable from "@/app/components/RecordTable";
import { EmptyLine } from "@/app/components/Section";
import Link from "next/link";

export const dynamic = "force-dynamic";

// How it works (2026-09-28, site review): the page a first-time visitor reads
// after the Board. What this is, how to read a row, where the bets are priced,
// the 2023–25 backtest labelled as a backtest, what we do not know, nine
// terms, and the helpline. It took over the research half of the old Track
// record page (/proof); the ledger half went to Results.
//
// Everything a visitor would not need or understand -- the live season's
// diagnostic strip, the post-mortem's flags and the method fold -- renders
// only behind the cookie. Nothing here gates a bet.

const KEYS: { color: string; term: string; text: string }[] = [
  {
    color: "var(--good)",
    term: "Green",
    text: "bet one unit. The row says the line and price: “Bet one unit: first-half under 24.5 at -110 on Hard Rock.”",
  },
  {
    color: "var(--warn)",
    term: "Amber, “Not yet”",
    text: "close, but a line or price is missing. The row says what would make it a bet.",
  },
  {
    color: "var(--bad)",
    term: "Red, “Pass”",
    text: "the numbers do not disagree enough, or the line leans over. We only bet unders.",
  },
];

export default async function HowItWorksPage({
  searchParams,
}: {
  searchParams: Promise<{ season?: string; minGames?: string }>;
}) {
  const authed = await viewerIsAuthed();
  const sp = await searchParams;
  const minGames =
    sp.minGames && Number(sp.minGames) > 0
      ? Number(sp.minGames)
      : DEFAULT_MIN_GAMES;
  const one =
    sp.season && sp.season !== "all" && Number.isFinite(Number(sp.season))
      ? Number(sp.season)
      : null;

  // The visitor's page needs only the post-mortem. The owner's research
  // section (behind the cookie) needs the rest; nothing is loaded for a
  // visitor that they will not see.
  const pm = await loadPostMortem();
  const seasons = authed ? await getRecordSeasons() : [];
  const studySeasons = one !== null ? [one] : seasons;
  const scopeLabel = one !== null ? `${one}` : "all seasons";
  const [edge, calib, study] = authed
    ? await Promise.all([
        getEdgeStats(one ?? undefined),
        getBvCalibration(),
        studySeasons.length > 0
          ? getLineStudy(studySeasons, minGames)
          : Promise.resolve(null),
      ])
    : [null, null, null];

  const runs = pm?.runs ?? [];
  const buckets = pm?.buckets ?? [];
  const hist = runs.find((r) => r.scope === HIST_SCOPE);
  const liveScope = liveScopeOf(runs);
  const live = liveScope ? runs.find((r) => r.scope === liveScope) : undefined;
  const liveSeason = liveScope ? liveScope.replace("live_", "") : "";
  const ln = liveNotesFrom(live);
  const flags = dedupeByCode([...flagsFrom(hist), ...flagsFrom(live)]).filter(
    (f) => f.code !== "multiple_comparisons",
  );
  const mc = flagsFrom(hist).find((f) => f.code === "multiple_comparisons");

  const lead =
    runs.length > 0
      ? headline(buckets, HIST_SCOPE, "fbs_only", "real", "cap5")
      : null;
  const pct0 = (v: number | null) =>
    v === null ? "—" : `${(100 * v).toFixed(0)}%`;
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
      <h1 className="bv-page-title mb-6">How it works</h1>

      <section aria-label="What this is" className="mb-8 max-w-[68ch]">
        <h2 className="mb-2 text-lg font-semibold text-[var(--text)]">
          What this is
        </h2>
        <p className="text-base leading-relaxed text-[var(--text-muted)]">
          <span className="text-[var(--text)]">
            Beat Vegas rates one bet: the college football first-half under.
          </span>{" "}
          Our model estimates first-half points without ever seeing the
          sportsbook line, so the gap between our number and the line is a real
          disagreement. When the gap is wide enough and the price is fair, it is
          a bet: one unit, at most {WEEKLY_BET_CAP} a week. We bet these
          ourselves and publish every one.
        </p>
      </section>

      <section aria-label="How to read the Board" className="mb-8 max-w-[68ch]">
        <h2 className="mb-2 text-lg font-semibold text-[var(--text)]">
          How to read the Board
        </h2>
        <ul className="flex flex-col gap-2">
          {KEYS.map((k) => (
            <li
              key={k.term}
              className="grid grid-cols-[14px_1fr] items-baseline gap-2.5 text-sm text-[var(--text-muted)]"
            >
              <span
                aria-hidden="true"
                className="mt-1 inline-block h-3 w-3 rounded-[3px]"
                style={{ background: k.color }}
              />
              <span>
                <span className="font-semibold text-[var(--text)]">
                  {k.term}
                </span>
                {` — ${k.text}`}
              </span>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-sm leading-relaxed text-[var(--text-muted)]">
          Best time to look: Friday after 5:30pm ET, and Saturday morning, once
          Hard Rock’s first-half lines are up.
        </p>
      </section>

      <section aria-label="Where bets are priced" className="mb-8 max-w-[68ch]">
        <h2 className="mb-2 text-lg font-semibold text-[var(--text)]">
          Where bets are priced
        </h2>
        <p className="text-sm leading-relaxed text-[var(--text-muted)]">
          Every bet is priced at Hard Rock Bet, the only sportsbook in Florida.
          Your book’s first-half total may differ; the line and price to beat
          are the ones shown.
        </p>
      </section>

      {/* The backtest: the one historical number, headed as what it is, with
          the picture that explains it, in one card. */}
      <section
        aria-label="The finding"
        className="bv-card mb-8 grid grid-cols-1 gap-x-8 gap-y-6 p-5 lg:grid-cols-[1fr_1.5fr] lg:items-center"
      >
        {lead === null ? (
          <EmptyLine>
            The 2023–25 backtest is not computed yet. It runs after each
            morning’s grading.
          </EmptyLine>
        ) : (
          <div>
            <p className="bv-stat-label">
              {`Backtest, 2023–25 (not money bet) · first-half unders, ${WEEKLY_BET_CAP} a week`}
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
              {`${lead.n} bets, could plausibly be ${pct0(lead.hitLo)}–${pct0(lead.hitHi)}. Hard Rock did not exist in these seasons. This is what the method would have returned, not money won.`}
            </p>
          </div>
        )}
        <div>
          <p className="bv-stat-label mb-1">
            The wider the gap, the more often the under wins
            {cov && (
              <span className="ml-2 font-normal normal-case tracking-normal">
                {`· ${cov.real.toLocaleString()} games at real closing lines`}
              </span>
            )}
          </p>
          <GapLadderChart rows={gapReal} breakeven={BREAKEVEN_PCT} />
        </div>
        <div className="lg:col-span-2">
          <RecordTable
            ariaLabel="Records at real closing lines"
            showInterval
            rows={[
              {
                key: "gap175",
                label: `2023–25, every gap ${BET_GAP_PTS}+`,
                note: "no weekly cap",
                rec:
                  runs.length > 0
                    ? headline(
                        buckets,
                        HIST_SCOPE,
                        "fbs_only",
                        "real",
                        "gap175",
                      )
                    : null,
                empty: "nothing graded yet",
              },
            ]}
          />
        </div>
      </section>

      <section aria-label="What we don’t know" className="mb-8 max-w-[68ch]">
        <h2 className="mb-2 text-lg font-semibold text-[var(--text)]">
          What we don’t know
        </h2>
        <div className="flex flex-col gap-3 text-sm leading-relaxed text-[var(--text-muted)]">
          <p>
            One first half is close to a coin flip. Our number misses a typical
            game by far more than any gap between it and the line, so a rating
            only means something across hundreds of bets.
          </p>
          <p>
            Hard Rock’s line has been at least as accurate as our number so far.
            The gap is a disagreement, not proof of who is right.
          </p>
          <p>
            So the real test is the live record: Hard Rock’s actual lines, the
            bets we log, and whether the line moves our way after we bet. It is
            on{" "}
            <Link
              href="/results"
              className="inline-flex min-h-6 items-center text-[var(--accent)] hover:underline"
            >
              Results
            </Link>
            . Until that record is large, read every rating as an opinion with a
            number on it.
          </p>
        </div>
      </section>

      <Glossary />

      <div className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-3">
        <Link href="/records" className="bv-btn">
          Every game we have rated →
        </Link>
        <p className="text-xs text-[var(--text-dim)]">
          If gambling is a problem for you or someone you know, call
          1-800-GAMBLER.
        </p>
      </div>

      {authed && runs.length > 0 && (
        <section
          aria-label="Research, signed in"
          className="mt-12 border-t border-dashed border-[var(--border-strong)] pt-6"
        >
          <p className="mb-4 text-[0.65rem] font-semibold uppercase tracking-[0.12em] text-[var(--accent)]">
            Signed in only · research
          </p>

          {liveScope && (
            <PmLiveNotes
              liveSeason={liveSeason}
              ln={ln}
              hrVsMarket={hrVsMarket}
              hrVsMarketClose={hrVsMarketClose}
            />
          )}

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
                  rec: headline(
                    buckets,
                    HIST_SCOPE,
                    "fbs_only",
                    "step",
                    "cap5",
                  ),
                  empty: "nothing graded yet",
                },
                {
                  key: "gap175",
                  label: `2023–25, every gap ${BET_GAP_PTS}+`,
                  rec: headline(
                    buckets,
                    HIST_SCOPE,
                    "fbs_only",
                    "step",
                    "gap175",
                  ),
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
                      <td className="font-medium text-[var(--text)]">
                        Overall
                      </td>
                      <td className="bv-num text-[var(--text-muted)]">
                        {calib.n}
                      </td>
                      <td className="bv-num font-mono text-[var(--text-muted)]">
                        {calib.overall ?? "—"}
                      </td>
                    </tr>
                    {calib.segments.map((sg) => (
                      <tr key={sg.label}>
                        <td className="text-[var(--text-muted)]">
                          {labelOf(CALIB_SEGMENT_TEXT, sg.label, sg.label)}
                        </td>
                        <td className="bv-num text-[var(--text-muted)]">
                          {sg.n}
                        </td>
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
              <LineStudyView
                buckets={study.buckets}
                breakeven={BREAKEVEN_PCT}
              />
            )}
          </Fold>
        </section>
      )}
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
