import { getSeasons } from "@/lib/board";
import { buildBetSlip, liveLinesFrom } from "@/lib/betSlip";
import { getLatestCard } from "@/lib/card";
import { getDecisionQuality } from "@/lib/decision-quality";
import { unitColor, usd } from "@/lib/format";
import { bankrollCurve, bankrollEnv, getHomeBoard } from "@/lib/homeBoard";
import { GATE_TEXT, labelOf, REASON_TEXT } from "@/lib/labels";
import { getLedger } from "@/lib/ledger";
import { loadPicks } from "@/lib/picks";
import type { Record3 } from "@/lib/record";
import { resolveSeason } from "@/lib/season";
import { BET_GAP_PTS } from "@/lib/verdict";
import { getWeeklyReview } from "@/lib/weeklyReview";
import BankrollHero from "@/app/components/BankrollHero";
import BankrollStrip from "@/app/components/BankrollStrip";
import BetSlip from "@/app/components/BetSlip";
import CardPanel from "@/app/components/CardPanel";
import CardStatusBanner from "@/app/components/CardStatusBanner";
import PicksList from "@/app/components/PicksList";
import RecordCard from "@/app/components/RecordCard";
import Section, { EmptyLine } from "@/app/components/Section";
import SeasonFallbackNotice from "@/app/components/SeasonFallbackNotice";
import SeasonSelect from "@/app/components/SeasonSelect";
import WeekSelect from "@/app/components/WeekSelect";

export const dynamic = "force-dynamic";

// Results is the money page: the bet slip first (the only thing here you act
// on), then the bankroll, then how the market, the model and you did — season
// summary, week by week, by the reason each pick was logged, the decision
// lens, and every pick (delete while ungraded). Replaces
// the old /ledger, /weekly-review and /picks pages, and the short-lived /slip
// (Tate 2026-09-10: a dedicated slip page was not worth a tab).
//
// Copy rule (docs/superpowers/specs/2026-09-08-site-copy.md §21-§23): nothing
// this page explains lives in a `title=` tooltip — a phone never shows one —
// so every definition is a visible caption, and every enum word (a reason, a
// blocker, an outcome) is rendered through lib/labels.

const pct = (v: number | null | undefined) =>
  v == null ? "—" : `${v.toFixed(1)}%`;

function RecCells({ rec }: { rec: Record3 | null }) {
  if (!rec) {
    return (
      <>
        <td className="bv-num text-[var(--text-dim)]">—</td>
        <td className="bv-num text-[var(--text-dim)]">—</td>
        <td className="bv-num text-[var(--text-dim)]">—</td>
        <td className="bv-num text-[var(--text-dim)]">—</td>
      </>
    );
  }
  return (
    <>
      <td className="bv-num font-mono text-[var(--text)]">{rec.record}</td>
      <td className="bv-num font-mono" style={{ color: unitColor(rec.units) }}>
        {rec.units}
      </td>
      <td className="bv-num font-mono text-[var(--text-muted)]">{rec.roi}</td>
      <td className="bv-num font-mono text-[var(--text-muted)]">{rec.clv}</td>
    </>
  );
}

function RecHead() {
  return (
    <>
      <th className="bv-num">W-L-P</th>
      <th className="bv-num">Units</th>
      <th className="bv-num">ROI</th>
      <th className="bv-num">Line value</th>
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

  const [ledger, review, dq, allPicks, board] = await Promise.all([
    getLedger(season),
    getWeeklyReview(season, wantWeek),
    getDecisionQuality(season),
    loadPicks(season),
    // The slip is an ACTION panel, not a review panel, so it always shows the
    // week you are about to bet — never the week ?week= is reviewing. It is
    // labelled with its own week number, so the two cannot be confused.
    getHomeBoard(season),
  ]);
  const card =
    board.week === null ? null : await getLatestCard(season, board.week);
  // Reconciled against the live Hard Rock numbers this render just read, so a
  // moved line or a breached kill number shows before the tap.
  const slip = buildBetSlip(
    card,
    board.weekPicks,
    board.bankroll.cap,
    new Date(),
    liveLinesFrom(board.games),
  );
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

      {/* The slip sits first: it is the only thing on this page you act on.
          Everything below it is review. */}
      <section aria-label="Bet slip">
        {card === null ? (
          <p className="bv-card mb-4 p-4 text-sm text-[var(--text-muted)]">
            {`No card has been built for this week yet. Builds land Tuesday, Thursday and Friday afternoons and Saturday morning.`}
          </p>
        ) : (
          <>
            <CardStatusBanner card={card} />
            <BetSlip
              slip={slip}
              week={board.week}
              unitUsd={board.bankroll.unitUsd}
            />
            <CardPanel card={card} />
          </>
        )}
        <BankrollStrip b={board.bankroll} />
      </section>

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

      <Section
        title="Week by week"
        empty={
          review.byWeek.length === 0
            ? `no picks logged for ${season} yet. Log bets from the board.`
            : null
        }
        caption="Your own picks only, real money and paper side by side. Bets and Picks count everything logged, including bets not yet graded."
      >
        <div className="bv-table-wrap">
          <table className="bv-table">
            <thead>
              <tr>
                <th rowSpan={2} className="bv-num">
                  Week
                </th>
                <th colSpan={5}>Real money</th>
                <th colSpan={5}>Paper</th>
              </tr>
              <tr>
                <th className="bv-num">Bets</th>
                <RecHead />
                <th className="bv-num">Picks</th>
                <RecHead />
              </tr>
            </thead>
            <tbody>
              {review.byWeek.map((w) => (
                <tr key={w.week}>
                  <td className="bv-num font-mono text-[var(--text)]">
                    {w.week}
                  </td>
                  <td className="bv-num font-mono text-[var(--text-muted)]">
                    {w.realBets}
                  </td>
                  <RecCells rec={w.real} />
                  <td className="bv-num font-mono text-[var(--text-muted)]">
                    {w.paperBets}
                  </td>
                  <RecCells rec={w.paper} />
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section
        title="By reason"
        empty={review.byReason.length === 0 ? "no picks logged yet." : null}
        caption="Which kind of bet is paying. The reason is frozen onto the pick when you log it, so it cannot be rewritten later."
      >
        <div className="bv-table-wrap">
          <table className="bv-table">
            <thead>
              <tr>
                <th rowSpan={2}>Reason</th>
                <th colSpan={5}>Real money</th>
                <th colSpan={5}>Paper</th>
              </tr>
              <tr>
                <th className="bv-num">Bets</th>
                <RecHead />
                <th className="bv-num">Picks</th>
                <RecHead />
              </tr>
            </thead>
            <tbody>
              {review.byReason.map((r) => (
                <tr key={r.reason}>
                  <td className="text-[var(--text)]">
                    {REASON_TEXT[r.reason].long}
                  </td>
                  <td className="bv-num font-mono text-[var(--text-muted)]">
                    {r.realBets}
                  </td>
                  <RecCells rec={r.real} />
                  <td className="bv-num font-mono text-[var(--text-muted)]">
                    {r.paperBets}
                  </td>
                  <RecCells rec={r.paper} />
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {/* Paper ledger by what blocked a real bet */}
      <Section
        title="Paper record by what blocked it"
        empty={review.byBlocker.length === 0 ? "nothing logged yet." : null}
        caption={`Every game whose Hard Rock line sat ${BET_GAP_PTS}+ above our number is logged as a paper pick, tagged with the one thing that stopped a real bet. Counts, not conclusions, until a row has 30 graded picks.`}
      >
        <div className="bv-table-wrap">
          <table className="bv-table">
            <thead>
              <tr>
                <th>What blocked it</th>
                <th className="bv-num">Picks</th>
                <RecHead />
              </tr>
            </thead>
            <tbody>
              {review.byBlocker.map((r) => (
                <tr key={r.blocker}>
                  <td className="text-[var(--text)]">
                    {labelOf(GATE_TEXT, r.blocker, "An input failed")}
                  </td>
                  <td className="bv-num font-mono text-[var(--text-muted)]">
                    {r.paperBets}
                  </td>
                  <RecCells rec={r.paper} />
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section
        title="Your decisions"
        empty={
          dq.n === 0
            ? "nothing graded yet. This opens up once your own bets settle."
            : null
        }
        caption="Every graded pick of yours: whether your calls beat our number, beat the closing line, and which factors you read well."
      >
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="bv-card p-4">
              <h3 className="text-sm font-semibold text-[var(--text)]">
                Vs our number
              </h3>
              <p className="mb-2 mt-0.5 text-xs text-[var(--text-dim)]">
                Your win rate when you agreed with our number, and when you went
                against it.
              </p>
              <dl className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <dt className="bv-stat-label">Agreed with it</dt>
                  <dd className="font-mono text-[var(--text-muted)]">
                    {`${pct(dq.beatModel.agreed.hitPct)} (${dq.beatModel.agreed.n})`}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="bv-stat-label">Went against it</dt>
                  <dd className="font-mono text-[var(--text-muted)]">
                    {`${pct(dq.beatModel.against.hitPct)} (${dq.beatModel.against.n})`}
                  </dd>
                </div>
              </dl>
            </div>
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
      <PicksList picks={review.picks} />
    </div>
  );
}
