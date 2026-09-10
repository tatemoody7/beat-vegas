import { labelOf, SEVERITY_TEXT } from "@/lib/labels";
import type { Record3 } from "@/lib/record";
import RecordCard from "@/app/components/RecordCard";
import { EmptyLine } from "@/app/components/Section";
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
import {
  BET_GAP_PTS,
  EV_FLOOR_PCT,
  STRONG_GAP_PTS,
  WEEKLY_BET_CAP,
} from "@/lib/verdict";
import { unitColor } from "@/lib/format";
import { BREAKEVEN_PCT } from "@/lib/lineStudy";

// Post-mortem panel on Results: what the record would have been had every
// bet-worthy score been bet, whether higher scores won more, and what the
// tables say to change. Seasons before this one are graded against an estimated
// first-half line — none existed to capture. Cross-season by design; it ignores
// the page's season selector.
//
// Copy rule (spec §23): no `title=` tooltips, no raw enum codes, no repo paths.

function BandTable({
  title,
  rows,
  caption,
}: {
  title: string;
  rows: BandRow[];
  caption: string;
}) {
  return (
    <>
      <h3 className="mb-1 mt-4 text-sm font-semibold text-[var(--text)]">
        {title}
      </h3>
      <p className="mb-2 text-xs leading-relaxed text-[var(--text-dim)]">
        {caption}
      </p>
      <div className="bv-table-wrap">
        <table className="bv-table">
          <thead>
            <tr>
              <th>Gap</th>
              <th className="bv-num">Games</th>
              <th className="bv-num">W-L-P</th>
              <th className="bv-num">Under %</th>
              <th className="bv-num">Range</th>
              <th className="bv-num">Chance it beats break-even</th>
              <th className="bv-num">Units</th>
              <th className="bv-num">ROI</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={8} className="text-[var(--text-muted)]">
                  Nothing graded here yet.
                </td>
              </tr>
            ) : (
              rows.map((r) => {
                const dim = r.size === "small";
                const cls = dim
                  ? "text-[var(--text-dim)]"
                  : "text-[var(--text-muted)]";
                return (
                  <tr key={r.bucket}>
                    <td
                      className={`whitespace-nowrap ${
                        dim ? "text-[var(--text-dim)]" : "text-[var(--text)]"
                      }`}
                    >
                      {r.bucket}
                    </td>
                    <td className={`bv-num font-mono ${cls}`}>{r.n}</td>
                    <td className={`bv-num font-mono whitespace-nowrap ${cls}`}>
                      {r.record}
                    </td>
                    <td className={`bv-num font-mono ${cls}`}>
                      {dim ? "too few" : r.hit}
                    </td>
                    <td className={`bv-num font-mono whitespace-nowrap ${cls}`}>
                      {dim ? "—" : r.ci}
                    </td>
                    <td className={`bv-num font-mono ${cls}`}>
                      {dim ? "—" : r.pBeat}
                    </td>
                    <td
                      className="bv-num font-mono"
                      style={{
                        color: dim ? "var(--text-dim)" : unitColor(r.units),
                      }}
                    >
                      {r.units}
                    </td>
                    <td className={`bv-num font-mono ${cls}`}>{r.roi}</td>
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

function Flags({ flags }: { flags: PmFlag[] }) {
  if (flags.length === 0) {
    return <EmptyLine>Nothing flagged yet.</EmptyLine>;
  }
  return (
    <ul className="space-y-2">
      {flags.map((f) => (
        <li key={f.code} className="bv-card flex items-start gap-3 p-3">
          <span className="bv-pill shrink-0">
            <span className="bv-pill-value">
              {labelOf(SEVERITY_TEXT, f.severity, "watch")}
            </span>
          </span>
          <p className="text-sm text-[var(--text-muted)]">{f.text}</p>
        </li>
      ))}
    </ul>
  );
}

/**
 * One entry per flag code. The historical and the live run each derive the same
 * statements from their own numbers, so concatenating them printed every flag
 * twice; the historical run has the sample size, so it wins a tie and a
 * live-only flag still shows.
 */
function dedupeByCode(flags: PmFlag[]): PmFlag[] {
  const seen = new Set<string>();
  return flags.filter((f) => (seen.has(f.code) ? false : seen.add(f.code)));
}

export default function PostMortemPanel({ pm }: { pm: PostMortem | null }) {
  const heading = (
    <>
      <h2 className="mb-1 mt-8 text-sm font-semibold text-[var(--text)]">
        Every game we rated, vs what happened
      </h2>
      <p className="mb-2 text-xs leading-relaxed text-[var(--text-dim)]">
        What the record would have been if every bet-worthy score had been bet,
        and whether higher scores won more. All seasons at once — the season
        picker above does not change it. Redone after each morning’s grading.
      </p>
    </>
  );
  if (!pm || pm.runs.length === 0) {
    return (
      <>
        {heading}
        <EmptyLine>Not computed yet. It runs after grading.</EmptyLine>
      </>
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

  const gapFair = bandTable(
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

  return (
    <>
      {heading}

      <p className="mb-2 text-xs text-[var(--text-dim)]">
        Win rate is the share of settled bets that won. Units are at one unit a
        bet. ROI counts pushes as risked.
      </p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <RecordCard
          title="2023–25, at the real closing line"
          rec={headline(buckets, HIST_SCOPE, "fbs_only", "real", "cap5")}
          emptyHint="No real first-half closes captured for 2023–25 yet."
          hint="Our picks graded at the first-half line other books actually closed at, about half an hour before kickoff. Hard Rock did not exist then. The only column that is not an estimate."
        />
        <RecordCard
          title="2023–25, at an estimated line"
          rec={headline(buckets, HIST_SCOPE, "fbs_only", "step", "cap5")}
          emptyHint="No historical scores graded."
          hint={`Up to ${WEEKLY_BET_CAP} bets a week by gap, gap ${BET_GAP_PTS}+, FBS teams only, graded against an estimated first-half line. The honest headline.`}
        />
        <RecordCard
          title={`2023–25, every gap ${BET_GAP_PTS}+`}
          rec={headline(buckets, HIST_SCOPE, "fbs_only", "step", "gap175")}
          emptyHint="No historical scores graded."
          hint="No weekly cap: every game that cleared the gap bar."
        />
        <RecordCard
          title={`${liveSeason} bets, at Hard Rock’s line`}
          rec={
            liveScope ? headline(buckets, liveScope, "live", "hr", "bet") : null
          }
          emptyHint="No bets yet."
          hint="Games we rated Bet, graded at Hard Rock’s own line and price."
        />
        <RecordCard
          title={`${liveSeason} good prices, at Hard Rock’s line`}
          rec={
            liveScope
              ? headline(buckets, liveScope, "live", "hr", "price_read")
              : null
          }
          emptyHint="No Hard Rock under has beaten the fair price yet."
          hint="Games where Hard Rock’s under paid at least the fair price."
        />
        <RecordCard
          title={`${liveSeason} every Hard Rock number`}
          rec={
            liveScope
              ? headline(buckets, liveScope, "live", "hr", "all_hr")
              : null
          }
          emptyHint="No Hard Rock first-half numbers graded yet."
          hint="The under at every Hard Rock first-half line we carried. The baseline our picks have to beat."
        />
      </div>

      <BandTable
        title="Win rate by gap size, 2023–25"
        rows={gapFair}
        caption={`Gap = the line minus our number, in points. The ${BET_GAP_PTS} and ${STRONG_GAP_PTS} edges are our own bars. Rows under 30 games are greyed out — too few to read. Range is how wide the true rate could plausibly be. “Chance it beats break-even” is the chance the real rate is above ${BREAKEVEN_PCT}%, the rate you need at -110. ROI is hidden under 100 games.`}
      />

      {liveScope && (
        <>
          <h3 className="mb-1 mt-4 text-sm font-semibold text-[var(--text)]">
            {`${liveSeason} so far`}
          </h3>
          <p className="mb-2 text-xs text-[var(--text-dim)]">
            {`${ln.nGraded} of ${ln.nItems} rated games graded, ${ln.nBets} bets. Counts, not rates, until a group has 30 games.`}
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="bv-card p-4">
              <h4 className="text-sm font-semibold text-[var(--text)]">
                How close the lines have been
              </h4>
              <p className="mb-2 mt-0.5 text-xs leading-relaxed text-[var(--text-dim)]">
                Average points each line missed the actual first half by. Lower
                is closer. Actual first-half share is how much of the full-game
                total the first half really was.
              </p>
              <dl className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <dt className="bv-stat-label">Our reference line</dt>
                  <dd className="font-mono text-[var(--text-muted)]">
                    {ln.derivedMae === null ? "—" : ln.derivedMae.toFixed(1)}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="bv-stat-label">Hard Rock’s line</dt>
                  <dd className="font-mono text-[var(--text-muted)]">
                    {ln.hrMae === null ? "—" : ln.hrMae.toFixed(1)}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="bv-stat-label">The market line</dt>
                  <dd className="font-mono text-[var(--text-muted)]">
                    {ln.marketMae === null ? "—" : ln.marketMae.toFixed(1)}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="bv-stat-label">Actual first-half share</dt>
                  <dd className="font-mono text-[var(--text-muted)]">
                    {ln.share === null ? "—" : ln.share.toFixed(3)}
                  </dd>
                </div>
              </dl>
            </div>
            <div className="bv-card p-4">
              <h4 className="text-sm font-semibold text-[var(--text)]">
                Results by price
              </h4>
              <p className="mb-2 mt-0.5 text-xs leading-relaxed text-[var(--text-dim)]">
                Whether a good Hard Rock price actually meant a better result.
              </p>
              {ln.priceReads.length === 0 ? (
                <p className="text-xs text-[var(--text-dim)]">
                  No priced games graded yet.
                </p>
              ) : (
                <dl className="space-y-1 text-sm">
                  {ln.priceReads.map((p) => (
                    <div key={p.band} className="flex justify-between">
                      <dt className="bv-stat-label">
                        {p.band === "pos"
                          ? "Better than fair"
                          : p.band === "neg"
                            ? `More than ${EV_FLOOR_PCT}% worse than fair`
                            : "About fair"}
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
              <h4 className="text-sm font-semibold text-[var(--text)]">
                When Hard Rock is off the market
              </h4>
              <p className="mb-2 mt-0.5 text-xs leading-relaxed text-[var(--text-dim)]">
                The under at Hard Rock’s line vs the under at the market’s
                close, same games.
              </p>
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
                        <dt className="bv-stat-label">{r.bucket}</dt>
                        <dd className="font-mono text-[var(--text-muted)]">
                          {`${r.record} at Hard Rock · ${close?.record ?? "—"} at the close`}
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
      <p className="mb-2 text-xs leading-relaxed text-[var(--text-dim)]">
        {`Each line is a statement the tables above judge. “change” means act on it, “watch” means it is suggestive, “holds up” means leave it alone.${mc ? ` ${mc.text}` : ""}`}
      </p>
      <Flags flags={flags} />

      <p className="mt-2 text-xs leading-relaxed text-[var(--text-dim)]">
        {`Computed ${(hist?.computed_at ?? live?.computed_at ?? "").slice(0, 16).replace("T", " ")} UTC. Seasons before this one are graded against estimated lines — there were no real first-half lines to use.`}
      </p>
    </>
  );
}
