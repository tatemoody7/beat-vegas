import type { Record3 } from "@/lib/record";
import {
  bandTable,
  flagsFrom,
  headline,
  HIST_SCOPE,
  liveNotesFrom,
  liveScopeOf,
  type BandRow,
  type PmFlag,
  type PostMortem,
} from "@/lib/postmortem";

// Post-mortem panel on Results: what the record would have been had every
// bet-worthy rating been bet, whether higher ratings hit more, and the change
// flags. Historical numbers are proxy-graded (no real 1H lines existed), so the
// fair-line column is the headline and the old 0.52 column is shown as the
// artefact it is. Cross-season by design; ignores the page's season selector.

// Green/red are OUTCOME colors: signed units only.
const unitColor = (s: string | undefined | null) =>
  !s || s === "—"
    ? "var(--text-dim)"
    : s.startsWith("-")
      ? "var(--over)"
      : "var(--under-strong)";

function PmCard({
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
                title="Profit in units at 1 unit a bet, -110."
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
                title="Units won ÷ bets (pushes count as staked)."
              >
                ROI
              </dt>
              <dd className="mt-0.5 font-mono text-lg font-semibold tabular-nums text-[var(--text-muted)]">
                {rec.roi}
              </dd>
            </div>
          </div>
        </dl>
      )}
    </div>
  );
}

function BandTable({
  title,
  fair,
  flat,
  caption,
}: {
  title: string;
  fair: BandRow[];
  flat: BandRow[];
  caption: string;
}) {
  const flatBy = new Map(flat.map((r) => [r.bucket, r]));
  return (
    <>
      <h3 className="mb-1 mt-4 text-sm font-semibold text-[var(--text)]">
        {title}
      </h3>
      <p className="mb-2 text-xs text-[var(--text-dim)]">{caption}</p>
      <div className="bv-table-wrap">
        <table className="bv-table">
          <thead>
            <tr>
              <th>Band</th>
              <th title="Graded games in the band.">n</th>
              <th title="Wins-losses(-pushes) of the first-half under.">
                W-L(-P)
              </th>
              <th title="Under hit rate against the fair (spread-aware) proxy line.">
                Under % · fair line
              </th>
              <th title="95% Wilson interval on that hit rate.">95% CI</th>
              <th title="Probability the true rate beats the 52.4% breakeven (Beta posterior).">
                P(&gt;52.4%)
              </th>
              <th title="Units at 1 unit a bet.">Units</th>
              <th title="Units ÷ bets; hidden under 100 games.">ROI</th>
              <th title="The same band graded at the old flat 0.52 line — the number earlier reports showed.">
                Under % · old 0.52 line
              </th>
            </tr>
          </thead>
          <tbody>
            {fair.length === 0 ? (
              <tr>
                <td colSpan={9} className="text-[var(--text-muted)]">
                  Nothing graded in this dimension yet.
                </td>
              </tr>
            ) : (
              fair.map((r) => {
                const dim = r.size === "small";
                const cls = dim
                  ? "text-[var(--text-dim)]"
                  : "text-[var(--text-muted)]";
                return (
                  <tr key={r.bucket}>
                    <td
                      className={
                        dim ? "text-[var(--text-dim)]" : "text-[var(--text)]"
                      }
                    >
                      {r.bucket}
                    </td>
                    <td className={`font-mono ${cls}`}>{r.n}</td>
                    <td className={`font-mono ${cls}`}>{r.record}</td>
                    <td className={`font-mono ${cls}`}>
                      {dim ? "n<30" : r.hit}
                    </td>
                    <td className={`font-mono ${cls}`}>{dim ? "—" : r.ci}</td>
                    <td className={`font-mono ${cls}`}>
                      {dim ? "—" : r.pBeat}
                    </td>
                    <td
                      className="font-mono"
                      style={{
                        color: dim ? "var(--text-dim)" : unitColor(r.units),
                      }}
                    >
                      {r.units}
                    </td>
                    <td className={`font-mono ${cls}`}>{r.roi}</td>
                    <td className={`font-mono ${cls}`}>
                      {flatBy.get(r.bucket)?.hit ?? "—"}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}

const SEVERITY_LABEL: Record<string, string> = {
  change: "change",
  watch: "watch",
  ok: "holds up",
};

function Flags({ flags }: { flags: PmFlag[] }) {
  if (flags.length === 0) {
    return (
      <p className="bv-card p-4 text-sm text-[var(--text-muted)]">
        No flags written yet.
      </p>
    );
  }
  return (
    <ul className="space-y-2">
      {flags.map((f) => (
        <li key={f.code} className="bv-card flex items-start gap-3 p-3">
          <span className="bv-pill shrink-0" title={f.code}>
            <span className="bv-pill-value">
              {SEVERITY_LABEL[f.severity] ?? f.severity}
            </span>
          </span>
          <p className="text-sm text-[var(--text-muted)]">{f.text}</p>
        </li>
      ))}
    </ul>
  );
}

export default function PostMortemPanel({ pm }: { pm: PostMortem | null }) {
  const heading = (
    <>
      <h2 className="mb-1 mt-8 text-sm font-semibold text-[var(--text)]">
        Post-mortem — every rated game vs its outcome
      </h2>
      <p className="mb-2 text-xs text-[var(--text-dim)]">
        {`What the record would have been had every bet-worthy rating been bet, and whether higher ratings hit more. Cross-season by design (2023–25 ratings plus this season’s cards); it ignores the season selector. Recomputed every Monday after grading.`}
      </p>
    </>
  );
  if (!pm || pm.runs.length === 0) {
    return (
      <>
        {heading}
        <p className="bv-card p-4 text-sm text-[var(--text-muted)]">
          Post-mortem not computed yet — it runs Monday after grading.
        </p>
      </>
    );
  }

  const { runs, buckets } = pm;
  const hist = runs.find((r) => r.scope === HIST_SCOPE);
  const liveScope = liveScopeOf(runs);
  const live = liveScope ? runs.find((r) => r.scope === liveScope) : undefined;
  const liveSeason = liveScope ? liveScope.replace("live_", "") : "";
  const ln = liveNotesFrom(live);
  const flags = [...flagsFrom(hist), ...flagsFrom(live)].filter(
    (f) => f.code !== "multiple_comparisons",
  );
  const mc = flagsFrom(hist).find((f) => f.code === "multiple_comparisons");

  const gapFair = bandTable(
    buckets,
    HIST_SCOPE,
    "fbs_only",
    "step",
    "gap_band",
  );
  const gapFlat = bandTable(
    buckets,
    HIST_SCOPE,
    "fbs_only",
    "flat",
    "gap_band",
  );
  const scoreFair = bandTable(
    buckets,
    HIST_SCOPE,
    "fbs_only",
    "step",
    "score_band",
  );
  const scoreFlat = bandTable(
    buckets,
    HIST_SCOPE,
    "fbs_only",
    "flat",
    "score_band",
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

  return (
    <>
      {heading}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <PmCard
          title="Followed the system, 2023–25 · fair line"
          rec={headline(buckets, HIST_SCOPE, "fbs_only", "step", "cap5")}
          emptyHint="No historical ratings graded."
          hint="Up to 5 bets a week by gap among gap ≥ 1.75, FBS-vs-FBS, graded at the fair spread-aware proxy line. The honest headline."
        />
        <PmCard
          title="Same picks · old 0.52 line"
          rec={headline(buckets, HIST_SCOPE, "fbs_only", "flat", "cap5")}
          emptyHint="No historical ratings graded."
          hint="The same selection graded at the flat 0.52 × full-game line the ratings were built on. The gap between this card and the first is the grading artefact, not the picks."
        />
        <PmCard
          title="Every gap ≥ 1.75, 2023–25 · fair line"
          rec={headline(buckets, HIST_SCOPE, "fbs_only", "step", "gap175")}
          emptyHint="No historical ratings graded."
          hint="No weekly cap: every FBS game clearing the gap gate, graded at the fair line."
        />
        <PmCard
          title={`${liveSeason} card BET tier · Hard Rock's number`}
          rec={
            liveScope ? headline(buckets, liveScope, "live", "hr", "bet") : null
          }
          emptyHint="Zero bets so far — by design in weeks 1–2 (no model read). There is no record to grade yet."
          hint="Games the card rated BET, graded at Hard Rock's own number and price."
        />
        <PmCard
          title={`${liveSeason} price reads · Hard Rock's number`}
          rec={
            liveScope
              ? headline(buckets, liveScope, "live", "hr", "price_read")
              : null
          }
          emptyHint="No Hard Rock under has paid better than the market's fair price yet."
          hint="Card items where Hard Rock's under paid at least the no-vig fair price (EV ≥ 0), graded at Hard Rock's number."
        />
        <PmCard
          title={`${liveSeason} blanket under · every Hard Rock number`}
          rec={
            liveScope
              ? headline(buckets, liveScope, "live", "hr", "all_hr")
              : null
          }
          emptyHint="No Hard Rock first-half numbers graded yet."
          hint="The under at every Hard Rock first-half number the cards carried — the baseline the price reads have to beat."
        />
      </div>

      <BandTable
        title="Does a bigger gap hit more? (FBS-vs-FBS, 2023–25, every rated game)"
        fair={gapFair}
        flat={gapFlat}
        caption="Gap = the line minus our number, in points. The 1.75 and 3.0 edges are the policy gates. Bands under 30 games are greyed."
      />
      <BandTable
        title="Does a higher under_score hit more? (same games)"
        fair={scoreFair}
        flat={scoreFlat}
        caption="under_score is the classifier lean (50 = breakeven). 53 is the confidence-label clause; 60 mirrors the edge-score EDGE cut."
      />

      {liveScope && (
        <>
          <h3 className="mb-1 mt-4 text-sm font-semibold text-[var(--text)]">
            {`${liveSeason} so far — inputs, not a record`}
          </h3>
          <p className="mb-2 text-xs text-[var(--text-dim)]">
            {`${ln.nGraded} of ${ln.nItems} rated games graded; ${ln.nBets} bets. Counts, not rates, until a bucket has 30 games.`}
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="bv-card p-4">
              <h4 className="mb-2 text-sm font-semibold text-[var(--text)]">
                Reference line accuracy
              </h4>
              <dl className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <dt
                    className="bv-stat-label"
                    title="Mean absolute error of the derived first-half reference line vs the actual first half."
                  >
                    Derived line MAE
                  </dt>
                  <dd className="font-mono text-[var(--text-muted)]">
                    {ln.derivedMae === null ? "—" : ln.derivedMae.toFixed(1)}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt
                    className="bv-stat-label"
                    title="Same, for Hard Rock's first-half number."
                  >
                    Hard Rock MAE
                  </dt>
                  <dd className="font-mono text-[var(--text-muted)]">
                    {ln.hrMae === null ? "—" : ln.hrMae.toFixed(1)}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt
                    className="bv-stat-label"
                    title="Same, for the consensus first-half number."
                  >
                    Consensus MAE
                  </dt>
                  <dd className="font-mono text-[var(--text-muted)]">
                    {ln.marketMae === null ? "—" : ln.marketMae.toFixed(1)}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt
                    className="bv-stat-label"
                    title="Realized first-half share of the full-game total across graded games."
                  >
                    Realized 1H share
                  </dt>
                  <dd className="font-mono text-[var(--text-muted)]">
                    {ln.share === null ? "—" : ln.share.toFixed(3)}
                  </dd>
                </div>
              </dl>
            </div>
            <div className="bv-card p-4">
              <h4 className="mb-2 text-sm font-semibold text-[var(--text)]">
                Price reads at Hard Rock’s number
              </h4>
              {ln.priceReads.length === 0 ? (
                <p className="text-xs text-[var(--text-dim)]">
                  No priced items graded yet.
                </p>
              ) : (
                <dl className="space-y-1 text-sm">
                  {ln.priceReads.map((p) => (
                    <div key={p.band} className="flex justify-between">
                      <dt className="bv-stat-label">
                        {p.band === "pos"
                          ? "Pays better than fair"
                          : p.band === "neg"
                            ? "Worse than the -5% floor"
                            : "Fair"}
                      </dt>
                      <dd className="font-mono text-[var(--text-muted)]">
                        {`${p.under} of ${p.under + p.over}${p.push ? ` (+${p.push} push)` : ""} under`}
                      </dd>
                    </div>
                  ))}
                </dl>
              )}
            </div>
            <div className="bv-card p-4">
              <h4 className="mb-2 text-sm font-semibold text-[var(--text)]">
                Hard Rock off the consensus
              </h4>
              {hrVsMarket.length === 0 ? (
                <p className="text-xs text-[var(--text-dim)]">
                  No graded Hard Rock numbers yet.
                </p>
              ) : (
                <dl className="space-y-1 text-sm">
                  {hrVsMarket.map((r) => {
                    const close = hrVsMarketClose.find(
                      (c) => c.bucket === r.bucket,
                    );
                    return (
                      <div key={r.bucket} className="flex justify-between">
                        <dt
                          className="bv-stat-label"
                          title="Under at Hard Rock's number vs under at the consensus close, same games."
                        >
                          {r.bucket}
                        </dt>
                        <dd className="font-mono text-[var(--text-muted)]">
                          {`${r.record} at HR · ${close?.record ?? "—"} at close`}
                        </dd>
                      </div>
                    );
                  })}
                </dl>
              )}
            </div>
          </div>
        </>
      )}

      <h3 className="mb-1 mt-4 text-sm font-semibold text-[var(--text)]">
        What to change
      </h3>
      <p className="mb-2 text-xs text-[var(--text-dim)]">
        {`Each flag is a testable statement judged on the tables above. "change" = the evidence says act, "watch" = suggestive, "holds up" = no change. ${mc ? mc.text : ""}`}
      </p>
      <Flags flags={flags} />

      <p className="mt-2 text-xs text-[var(--text-dim)]">
        {`Computed ${hist?.computed_at ?? live?.computed_at ?? ""}. Historical ratings are graded against proxy lines (no real first-half lines existed); ${hist?.notes?.caveats?.[3] ?? "about 2,300 bets separate a 55% bettor from breakeven, so this cannot confirm a realistic edge."} Full tables in docs/POST_MORTEM.md.`}
      </p>
    </>
  );
}
