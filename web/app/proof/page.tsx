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
import { BREAKEVEN_PCT } from "@/lib/lineStudy";
import { BET_GAP_PTS, STRONG_GAP_PTS, WEEKLY_BET_CAP } from "@/lib/verdict";
import BandTable from "@/app/components/BandTable";
import PmFlags from "@/app/components/PmFlags";
import PmLiveNotes from "@/app/components/PmLiveNotes";
import RecordCard from "@/app/components/RecordCard";
import { EmptyLine } from "@/app/components/Section";
import Link from "next/link";

export const dynamic = "force-dynamic";

// Track record: is the edge real. Cross-season, changes slowly, and split by
// GRADING BASIS rather than by era.
//
// That split is the point of the page (Tate 2026-09-10). Only 2023–25 games a
// book actually priced carry a real closing line; the rest are graded against
// a line we worked out, and the two answers differ by a lot — the same cap-5
// rule returns +15.9% at the real close and +5.4% at the estimate. So they
// live in two blocks, and everything in the estimated block renders NEUTRAL:
// green and red only ever appear on a real closing line.
//
// Copy rule (spec §21-§23): no `title=` tooltips, no raw enum codes.

export default async function ProofPage() {
  const pm = await loadPostMortem();

  if (!pm || pm.runs.length === 0) {
    return (
      <div className="mx-auto max-w-5xl">
        <h1 className="bv-page-title">Track record</h1>
        <p className="bv-page-sub mt-1">Whether the edge is real.</p>
        <EmptyLine className="mt-6">
          Not computed yet. It runs after each morning’s grading.
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

  const BAND_CAPTION = `Gap = the line minus our number, in points. The ${BET_GAP_PTS} and ${STRONG_GAP_PTS} edges are our own bars. Rows under 30 games are greyed out — too few to read. Range is how wide the true rate could plausibly be. “Chance it beats break-even” is the chance the real rate is above ${BREAKEVEN_PCT}%, the rate you need at -110. ROI is hidden under 100 games.`;

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="bv-page-title">Track record</h1>
          <p className="bv-page-sub mt-1">
            Whether the edge is real. All seasons at once.
          </p>
        </div>
        <Link href="/proof/records" className="bv-btn">
          Every game we have rated →
        </Link>
      </div>

      {/* 1 — the one honest number, caveated in the same breath. */}
      <section aria-label="Headline" className="bv-card mb-8 p-5">
        {lead === null ? (
          <EmptyLine>
            No 2023–25 games with a real captured close have been graded yet.
          </EmptyLine>
        ) : (
          <>
            <p className="bv-stat-label">
              First-half unders won, 2023–25, graded at the first-half line
              other books actually closed at
            </p>
            <p className="mt-2 font-[family-name:var(--font-display)] text-6xl font-extrabold leading-none tabular-nums text-[var(--text)]">
              {lead.hit}
            </p>
            <p className="mt-3 font-mono text-sm text-[var(--text-muted)]">
              {lead.record}
              {" · "}
              <span style={{ color: unitColor(lead.units) }}>{lead.units}</span>
              {` · ROI ${lead.roi} · ${lead.n} bets`}
            </p>
            <ul className="mt-4 space-y-1.5 text-sm leading-relaxed text-[var(--text-muted)]">
              <li>{`${lead.n} bets across three seasons. Small enough that a good month moves it.`}</li>
              <li>
                {`The ${WEEKLY_BET_CAP}-a-week cap was applied to the whole history afterwards, not lived week by week.`}
              </li>
              <li>
                Hard Rock did not exist in these seasons. This is what the
                method would have returned, not money that was won.
              </li>
            </ul>
          </>
        )}
      </section>

      {/* 2 — everything graded against a line a book actually posted. */}
      <h2 className="mb-1 text-sm font-semibold text-[var(--text)]">
        Measured against real closing lines
      </h2>
      <p className="mb-3 text-xs leading-relaxed text-[var(--text-dim)]">
        {cov
          ? `Games another book actually priced — ${cov.real.toLocaleString()} of the ${cov.total.toLocaleString()} FBS-vs-FBS games in 2023–25 — plus ${liveSeason || "this season"} at Hard Rock’s own number. These are the numbers to believe.`
          : "Games another book actually priced, plus this season at Hard Rock’s own number. These are the numbers to believe."}
      </p>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <RecordCard
          title={`2023–25, every gap ${BET_GAP_PTS}+`}
          rec={headline(buckets, HIST_SCOPE, "fbs_only", "real", "gap175")}
          hint="No weekly cap: every game that cleared the gap bar, at the real close."
        />
        <RecordCard
          title={`${liveSeason} bets, at Hard Rock’s line`}
          rec={
            liveScope ? headline(buckets, liveScope, "live", "hr", "bet") : null
          }
          emptyHint="No bets graded yet."
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
        title="Win rate by gap size, at the real close"
        rows={gapReal}
        caption={BAND_CAPTION}
      />

      {liveScope && (
        <PmLiveNotes
          liveSeason={liveSeason}
          ln={ln}
          hrVsMarket={hrVsMarket}
          hrVsMarketClose={hrVsMarketClose}
        />
      )}

      {/* 3 — the proxy. Demoted, and colourless on purpose. */}
      <hr className="mt-10 border-[var(--border)]" />
      <h2 className="mb-1 mt-6 text-sm font-semibold text-[var(--text-muted)]">
        Measured against an estimated line
      </h2>
      <p className="mb-3 text-xs leading-relaxed text-[var(--text-dim)]">
        No book posted a first-half number on these games, so they are graded
        against one we worked out. Nothing here is coloured: an estimated grade
        is not a grade. Read it as a sanity check on the block above, never as a
        result — the same rule returns a different answer on each basis.
      </p>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <RecordCard
          title="2023–25, the same cap-5 rule"
          rec={headline(buckets, HIST_SCOPE, "fbs_only", "step", "cap5")}
          basis="estimated"
          hint={`Up to ${WEEKLY_BET_CAP} bets a week by gap, gap ${BET_GAP_PTS}+, FBS teams only — the headline rule, against the estimate instead of the close.`}
        />
        <RecordCard
          title={`2023–25, every gap ${BET_GAP_PTS}+`}
          rec={headline(buckets, HIST_SCOPE, "fbs_only", "step", "gap175")}
          basis="estimated"
          hint="No weekly cap, against the estimate."
        />
      </div>

      <BandTable
        title="Win rate by gap size, at an estimated line"
        rows={gapEstimated}
        caption={BAND_CAPTION}
        basis="estimated"
      />

      {/* 4 — the actionable conclusion, above the methodology. */}
      <h2 className="mb-1 mt-10 text-sm font-semibold text-[var(--text)]">
        What to change
      </h2>
      <p className="mb-2 text-xs leading-relaxed text-[var(--text-dim)]">
        {`Each line is a statement the tables above judge. “change” means act on it, “watch” means it is suggestive, “holds up” means leave it alone.${mc ? ` ${mc.text}` : ""}`}
      </p>
      <PmFlags flags={flags} />

      <p className="mt-3 text-xs leading-relaxed text-[var(--text-dim)]">
        {`Computed ${(hist?.computed_at ?? live?.computed_at ?? "").slice(0, 16).replace("T", " ")} UTC, after each morning’s grading.`}
      </p>
    </div>
  );
}
