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
import { getBvCalibration, getEdgeStats } from "@/lib/proof";
import { proxyShareText } from "@/lib/proxy";
import { getRecordSeasons } from "@/lib/records";
import { BET_GAP_PTS, STRONG_GAP_PTS, WEEKLY_BET_CAP } from "@/lib/verdict";
import BandTable from "@/app/components/BandTable";
import PmFlags from "@/app/components/PmFlags";
import PmLiveNotes from "@/app/components/PmLiveNotes";
import LineStudyView from "@/app/components/LineStudyView";
import MinGamesSelect from "@/app/components/MinGamesSelect";
import RecordCard from "@/app/components/RecordCard";
import Section, { EmptyLine } from "@/app/components/Section";
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
  // resolves to, so it is deliberately deferred — do not "fix" this in
  // passing (Tate 2026-09-10).
  const seasons = await getRecordSeasons();
  // No ?season= means ALL seasons here, inverting the old Research default:
  // 2026 has no total with enough graded games to reach the minimum, so a
  // single-season default would show an empty study every time.
  const one =
    sp.season && sp.season !== "all" && Number.isFinite(Number(sp.season))
      ? Number(sp.season)
      : null;
  const studySeasons = one !== null ? [one] : seasons;
  const scopeLabel = one !== null ? `${one}` : "all seasons";

  const [pm, edge, calib, study] = await Promise.all([
    loadPostMortem(),
    getEdgeStats(one ?? undefined),
    getBvCalibration(),
    studySeasons.length > 0
      ? getLineStudy(studySeasons, minGames)
      : Promise.resolve(null),
  ]);

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

      {/* 5-7 — how the number is built. Below the conclusion on purpose:
          methodology is what you go looking for, not what you lead with. */}
      <hr className="mt-10 border-[var(--border)]" />

      <Section
        title="How the number is built"
        empty={edge ? null : `no finished games for ${scopeLabel} yet.`}
        caption={`Every finished game in ${scopeLabel}, FBS teams playing FBS teams only.`}
      >
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Stat
            label="Games looked at"
            value={edge ? edge.games.toLocaleString() : "—"}
            note="FBS teams playing FBS teams only."
          />
          <Stat
            label="First half’s share of the full game"
            value={edge ? `${(100 * edge.mean).toFixed(1)}%` : "—"}
            note="On average, how much of the full-game total the first half was worth."
          />
          <Stat
            label="Middle value"
            value={edge ? `${(100 * edge.median).toFixed(1)}%` : "—"}
            note="Half the games were above this, half below."
          />
        </div>
        {edge && (
          <>
            <p className="mt-4 text-sm leading-relaxed text-[var(--text-muted)]">
              {`First halves come out around ${(100 * edge.mean).toFixed(1)}% of the full-game total, which is about where books set the first-half line. Where no real first-half line exists we estimate one: ${proxyShareText()}.`}
            </p>
            <p className="mt-2 text-sm leading-relaxed text-[var(--text-muted)]">
              {`Graded against that estimate, nothing here beat the ${BREAKEVEN_PCT}% you need at -110.`}
            </p>
          </>
        )}
      </Section>

      <Section
        title="How accurate our number is"
        empty={
          calib
            ? null
            : "no model run has recorded its out-of-sample misses yet."
        }
        caption={
          calib
            ? `Average miss = actual first-half points minus our number, over ${calib.n.toLocaleString()} games it never trained on. Near zero is on target. A steady positive miss means our number runs low, which would wrongly lean it under.`
            : undefined
        }
      >
        {calib && (
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
                    <td className="text-[var(--text-muted)]">{sg.label}</td>
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
        )}
      </Section>

      <div className="mb-3 mt-8 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-[var(--text)]">
            {`Which first-half totals go under most often (${scopeLabel})`}
          </h2>
          {study && (
            <p className="mt-1 max-w-3xl text-xs leading-relaxed text-[var(--text-dim)]">
              {`Grouped by the ${study.anyReal ? "first-half total each book opened at" : `estimated opening line (${proxyShareText()})`}${study.fbsPartial ? " — no FBS list for some of these seasons, so their games are all included" : study.fbsFiltered ? ", FBS teams only" : " — no FBS list for this season, so every game is included"}. You need ${BREAKEVEN_PCT}% to break even at -110.${study.anyReal ? "" : " On estimated lines this ordering partly reflects which games were high-scoring, so read it as a hint."}`}
            </p>
          )}
        </div>
        <MinGamesSelect current={minGames} />
      </div>
      {!study || study.buckets.length === 0 ? (
        <EmptyLine>
          {`No total has ${minGames}+ graded games in ${scopeLabel} yet. Lower the minimum, or check back later in the season.`}
        </EmptyLine>
      ) : (
        <LineStudyView buckets={study.buckets} breakeven={BREAKEVEN_PCT} />
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
  note: string;
}) {
  return (
    <div className="bv-card p-4">
      <p className="bv-stat-label">{label}</p>
      <p className="mt-1 font-[family-name:var(--font-display)] text-2xl font-extrabold tabular-nums text-[var(--text)]">
        {value}
      </p>
      <p className="mt-1 text-xs leading-relaxed text-[var(--text-dim)]">
        {note}
      </p>
    </div>
  );
}
