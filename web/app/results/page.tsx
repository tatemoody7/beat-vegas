import { getSeasons } from "@/lib/board";
import { getDecisionQuality } from "@/lib/decision-quality";
import { usd } from "@/lib/format";
import { bankrollCurve, bankrollEnv, getHomeBoard } from "@/lib/homeBoard";
import { GATE_TEXT, labelOf, REASON_TEXT } from "@/lib/labels";
import { getLedger } from "@/lib/ledger";
import { loadPicks } from "@/lib/picks";
import { resolveSeason } from "@/lib/season";
import { BET_GAP_PTS } from "@/lib/verdict";
import { getWeeklyReview } from "@/lib/weeklyReview";
import BankrollHero from "@/app/components/BankrollHero";
import Breakdown from "@/app/components/Breakdown";
import PicksList from "@/app/components/PicksList";
import RecordCard from "@/app/components/RecordCard";
import Section, { EmptyLine } from "@/app/components/Section";
import SeasonFallbackNotice from "@/app/components/SeasonFallbackNotice";
import SeasonSelect from "@/app/components/SeasonSelect";
import WeekSelect from "@/app/components/WeekSelect";

export const dynamic = "force-dynamic";

// Results is READ-ONLY (Tate 2026-09-13: "all the logging should happen on the
// board page. The results is just to see what I picked and how it turned out").
// Three questions in order: am I up or down (the bankroll hero), what should I
// fix (the season summary + the breakdown), and what did I bet and how did it
// land (the picks table).
//
// The bet slip, the card panel and the bankroll strip USED to head this page.
// They are all about a bet not yet placed, which is the Board's job: a board
// row links to /game/[id], where LogPickForm logs it, and the kill numbers are
// enforced server-side for every path by lib/pickRules.ts::checkPolicy. Nothing
// was lost in the move except a duplicate rendering of the same games.
//
// Copy rule (docs/superpowers/specs/2026-09-08-site-copy.md §21-§23): nothing
// this page explains lives in a `title=` tooltip — a phone never shows one —
// so every definition is a visible caption, and every enum word (a reason, a
// blocker, an outcome) is rendered through lib/labels.

const pct = (v: number | null | undefined) =>
  v == null ? "—" : `${v.toFixed(1)}%`;

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
          <p className="bv-page-sub mt-1">
            {`How the market, the model and you did in ${season}.`}
          </p>
          <p className="mt-1 max-w-2xl text-xs leading-relaxed text-[var(--text-dim)]">
            Market = betting every first-half under at the closing line. Model =
            the model’s picks. You = your own real-money bets, with paper kept
            separate.
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

      <BankrollHero b={board.bankroll} points={curve} />

      {/* Season summary. Only records with something in them render: five
          near-empty cards in week 2 is the placeholder problem in card form
          (Tate 2026-09-10). */}
      <Section
        title={`Season summary · ${season}`}
        empty={
          hasRecord
            ? null
            : "nothing has settled yet. The market and model records fill in as games are graded, your own once a bet settles."
        }
        caption={`Win rate is the share of settled bets that won — pushes do not count either way. Units are what was won or lost, at one unit = ${usd(unitUsd)}. ROI is units won divided by units risked. Line value is how far the line moved our way after the bet, on average; positive is good.`}
      >
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <RecordCard
            title="Market — first half"
            rec={ledger.market}
            showClv
            hint="Every game’s first-half under at the closing line. The baseline to beat."
          />
          <RecordCard
            title="Model — first half"
            rec={ledger.model}
            showClv
            hint="The model’s own under picks, graded at the closing line."
          />
          <RecordCard
            title="You — real money"
            rec={ledger.you}
            showClv
            hint="Your real-money first-half bets. This is the record the bankroll follows."
          />
          <RecordCard
            title="You — paper"
            rec={ledger.paper}
            showClv
            hint="Tracked with no money on them. Never mixed into the real record."
          />
          <RecordCard
            title="Market — full game"
            rec={ledger.marketFull}
            showClv
            hint="Context only. We do not bet the full game."
          />
        </div>
      </Section>

      <Breakdown
        views={[
          {
            id: "week",
            tab: "By week",
            head: "Week",
            caption:
              "Your own picks only, real money and paper side by side. Bets and Picks count everything logged, including bets not yet graded.",
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
            caption:
              "Which kind of bet is paying. The reason is frozen onto the pick when you log it, so it cannot be rewritten later.",
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
            caption: `Every game whose Hard Rock line sat ${BET_GAP_PTS}+ above our number is logged as a paper pick, tagged with the one thing that stopped a real bet. Counts, not conclusions, until a row has 30 graded picks.`,
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
        empty={
          dq.n === 0
            ? "nothing graded yet. This opens up once your own bets settle."
            : null
        }
        caption="Every graded pick of yours: whether the line moved your way after you bet, and which factors you read well."
      >
        {/* There is no "Vs our number" card. It compared your win rate when you
            agreed with our number against when you went against it, and the
            second half can never populate: a game is only logged when Hard
            Rock's line sits ABOVE our number, so `line - model_line` is positive
            by construction. It read "— (0)" for the life of the page (Tate
            2026-09-13). beatModel still exists in decision-quality.ts for a
            future hand-logged pick that does go against the model. */}
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="bv-card p-4">
              <h3 className="text-sm font-semibold text-[var(--text)]">
                Vs the closing line
              </h3>
              <p className="mb-2 mt-0.5 text-xs text-[var(--text-dim)]">
                {`Whether the line moved your way after you bet. Every bet here is an under, so the total dropping is good: +1.0 means the market came a point toward you. Price movement is the same idea for the odds instead of the total, in percentage points.`}
              </p>
              <dl className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <dt className="bv-stat-label">Line value</dt>
                  <dd className="font-mono text-[var(--text-muted)]">
                    {`${dq.clv.avgPointsGained == null ? "—" : `${dq.clv.avgPointsGained >= 0 ? "+" : ""}${dq.clv.avgPointsGained.toFixed(2)}`} (${dq.clv.n})`}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="bv-stat-label">Share that moved your way</dt>
                  <dd className="font-mono text-[var(--text-muted)]">
                    {`${pct(dq.clv.pctFavourable)} (${dq.clv.n})`}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="bv-stat-label">Price movement</dt>
                  <dd className="font-mono text-[var(--text-muted)]">
                    {`${dq.clv.avgPricePp == null ? "—" : `${dq.clv.avgPricePp >= 0 ? "+" : ""}${dq.clv.avgPricePp.toFixed(2)}pp`} (${dq.clv.nPrice})`}
                  </dd>
                </div>
              </dl>
            </div>
            <div className="bv-card p-4">
              <h3 className="text-sm font-semibold text-[var(--text)]">
                Timing
              </h3>
              <p className="mb-2 mt-0.5 text-xs text-[var(--text-dim)]">
                Whether you got in at a good number. For an under, a higher
                total is better.
              </p>
              <dl className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <dt className="bv-stat-label">At or better than the open</dt>
                  <dd className="font-mono text-[var(--text-muted)]">
                    {`${pct(dq.timing.pctAtOrBetterThanOpen)} (${dq.timing.nOpen})`}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="bv-stat-label">Better than the close</dt>
                  <dd className="font-mono text-[var(--text-muted)]">
                    {`${pct(dq.timing.pctBeatingClose)} (${dq.timing.nClose})`}
                  </dd>
                </div>
              </dl>
            </div>
          </div>
          {dq.factors.length > 0 && (
            <>
              <p className="mt-3 text-xs leading-relaxed text-[var(--text-dim)]">
                Only factors that were green on your picks. “Rate across all
                games” is how the under did whenever that factor was green.
              </p>
              <div className="bv-table-wrap mt-1">
                <table className="bv-table">
                  <thead>
                    <tr>
                      <th>Factor</th>
                      <th className="bv-num">Your picks</th>
                      <th className="bv-num">Your win rate</th>
                      <th className="bv-num">Rate across all games</th>
                      <th>Read</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dq.factors.map((f) => (
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
                        <td>
                          <span className="bv-pill">
                            <span className="bv-pill-value">
                              {f.weight === "even"
                                ? "about right"
                                : f.weight === "under"
                                  ? "you read this well"
                                  : "you lean on this too much"}
                            </span>
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </>
      </Section>

      {/* Pick history */}
      <h2 className="mb-2 mt-8 text-sm font-semibold text-[var(--text)]">
        {`Your picks — ${weekLabel}`}
      </h2>
      <PicksList picks={review.picks} showWeek={review.week === null} />
    </div>
  );
}
