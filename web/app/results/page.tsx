import { getSeasons } from "@/lib/board";
import { getDecisionQuality } from "@/lib/decision-quality";
import { bankrollCurve, bankrollEnv, getHomeBoard } from "@/lib/homeBoard";
import { GATE_TEXT, labelOf, REASON_TEXT } from "@/lib/labels";
import { getLedger } from "@/lib/ledger";
import { isOffPolicy, isRealFirstHalf, loadPicks } from "@/lib/picks";
import { resolveSeason } from "@/lib/season";
import { getWeeklyReview } from "@/lib/weeklyReview";
import Breakdown from "@/app/components/Breakdown";
import DecisionsStrip from "@/app/components/DecisionsStrip";
import PicksList from "@/app/components/PicksList";
import RecordTable from "@/app/components/RecordTable";
import ScoreboardBand from "@/app/components/ScoreboardBand";
import Section from "@/app/components/Section";
import SeasonFallbackNotice from "@/app/components/SeasonFallbackNotice";
import SeasonSelect from "@/app/components/SeasonSelect";
import WeekSelect from "@/app/components/WeekSelect";

export const dynamic = "force-dynamic";

// Results is READ-ONLY (Tate 2026-09-13: "all the logging should happen on the
// board page. The results is just to see what I picked and how it turned out").
//
// Concept A "Scoreboard" (Tate 2026-09-16): one band with the three numbers
// that answer the page — the rule's paper record, my money, line value — with
// the bankroll curve inside it; then every comparison as a TABLE (market,
// model, the rule, you, the full game), the breakdown toggle, the decisions
// strip, the factor read, and the picks ledger. Cards that only held numbers
// are gone; so is every caption a returning reader does not need. A definition
// lives once, in the glossary on Track record.
//
// The kill numbers are enforced server-side for every path by
// lib/pickRules.ts::checkPolicy; nothing on this page gates a bet.

const pct = (v: number | null | undefined) =>
  v == null ? "—" : `${v.toFixed(1)}%`;

const READ_WORD: Record<string, { text: string; color: string }> = {
  under: { text: "read well", color: "var(--good)" },
  even: { text: "about right", color: "var(--text-muted)" },
  over: { text: "leaning on it too much", color: "var(--warn)" },
};

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

  const [ledger, review, dq, allPicks, board] = await Promise.all([
    getLedger(season),
    getWeeklyReview(season, wantWeek),
    getDecisionQuality(season),
    loadPicks(season),
    // Still needed for the bankroll (cap, unit size, the real record).
    getHomeBoard(season),
  ]);
  const weekLabel = review.week === null ? "all weeks" : `week ${review.week}`;
  const { startUsd, unitUsd } = bankrollEnv();
  const curve = bankrollCurve(allPicks, startUsd, unitUsd);
  const realBets = allPicks.filter(isRealFirstHalf).length;
  const againstVerdict = allPicks.filter(isOffPolicy).length;
  const hasRecord =
    ledger.market !== null ||
    ledger.model !== null ||
    ledger.you !== null ||
    ledger.paper !== null ||
    ledger.marketFull !== null;

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="bv-page-title">Results</h1>
          <p className="bv-page-sub">{`${weekLabel} · ${season}`}</p>
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

      <ScoreboardBand
        paper={ledger.paper}
        bankroll={board.bankroll}
        points={curve}
        realBets={realBets}
        againstVerdict={againstVerdict}
        linesMoved={{ n: dq.clv.n, pctFavourable: dq.clv.pctFavourable }}
      />

      {/* The ledger sits right under the scoreboard (Tate 2026-09-16): what I
          bet and how it landed is the second thing on the page, before the
          comparisons. It opens on real money; Paper and All are one click. */}
      <h2 className="mb-2 text-sm font-semibold text-[var(--text)]">
        Your picks
        <span className="ml-2 text-xs font-normal text-[var(--text-dim)]">
          {weekLabel}
        </span>
      </h2>
      <PicksList picks={review.picks} showWeek={review.week === null} />

      <Section
        title={`Season summary · ${season}`}
        empty={
          hasRecord
            ? null
            : "nothing has settled yet. It fills in as games are graded."
        }
      >
        <RecordTable
          ariaLabel="Season summary"
          showClv
          rows={[
            {
              key: "market",
              label: "Market — first half",
              note: "the baseline to beat",
              rec: ledger.market,
              empty: "nothing graded yet",
            },
            {
              key: "model",
              label: "Model — first half",
              rec: ledger.model,
              empty: "nothing graded yet",
            },
            {
              key: "paper",
              label: "The rule — paper",
              rec: ledger.paper,
              empty: "no paper picks graded yet",
            },
            {
              key: "you",
              label: "You — real money",
              lead: true,
              rec: ledger.you,
              empty: "no real bets graded yet",
            },
            {
              key: "fg",
              label: "Market — full game",
              note: "context only",
              rec: ledger.marketFull,
              dim: true,
              empty: "nothing graded yet",
            },
          ]}
        />
      </Section>

      <Breakdown
        views={[
          {
            id: "week",
            tab: "By week",
            head: "Week",
            empty: `No picks logged for ${season} yet. Log bets from the board.`,
            rows: review.byWeek.map((w) => ({
              key: String(w.week),
              label: String(w.week),
              realBets: w.realBets,
              real: w.real,
              paperBets: w.paperBets,
              paper: w.paper,
            })),
          },
          {
            id: "reason",
            tab: "By reason",
            head: "Reason",
            empty: "No picks logged yet.",
            rows: review.byReason.map((r) => ({
              key: r.reason,
              label: REASON_TEXT[r.reason].long,
              realBets: r.realBets,
              real: r.real,
              paperBets: r.paperBets,
              paper: r.paper,
            })),
          },
          {
            id: "blocker",
            tab: "By blocker",
            head: "What blocked it",
            empty: "Nothing logged yet.",
            rows: review.byBlocker.map((r) => ({
              key: r.blocker,
              label: labelOf(GATE_TEXT, r.blocker, "An input failed"),
              realBets: null,
              real: null,
              paperBets: r.paperBets,
              paper: r.paper,
            })),
          },
        ]}
      />

      <Section
        title="Your decisions"
        caption={dq.n > 0 ? `${dq.n} graded picks` : undefined}
        empty={dq.n === 0 ? "nothing graded yet." : null}
      >
        <DecisionsStrip
          dq={dq}
          realBets={realBets}
          againstVerdict={againstVerdict}
        />
        {dq.factors.length > 0 && (
          <div className="bv-table-wrap mt-3">
            <table className="bv-table" aria-label="Factors you leaned on">
              <thead>
                <tr>
                  <th>Factor you leaned on</th>
                  <th className="bv-num">Picks</th>
                  <th className="bv-num">Your win rate</th>
                  <th className="bv-num">All games</th>
                  <th>Read</th>
                </tr>
              </thead>
              <tbody>
                {dq.factors.map((f) => {
                  const read = READ_WORD[f.weight] ?? READ_WORD.even;
                  return (
                    <tr key={f.key}>
                      <td className="text-[var(--text)]">{f.label}</td>
                      <td className="bv-num font-mono text-[var(--text-muted)]">
                        {f.n}
                      </td>
                      <td className="bv-num font-mono text-[var(--text-muted)]">
                        {pct(f.yourHitPct)}
                      </td>
                      <td className="bv-num font-mono text-[var(--text-muted)]">
                        {f.ledgerHitPct == null ? "—" : pct(f.ledgerHitPct)}
                      </td>
                      <td style={{ color: read.color }}>{read.text}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Section>
    </div>
  );
}
