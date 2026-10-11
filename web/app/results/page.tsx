import { getSeasons } from "@/lib/board";
import { getBetLedger } from "@/lib/betLedgerDb";
import { bankrollCurve, bankrollEnv } from "@/lib/homeBoard";
import { getLedger } from "@/lib/ledger";
import { loadPicks } from "@/lib/picks";
import { resolveSeason } from "@/lib/season";
import { viewerIsAuthed } from "@/lib/session";
import { getWeeklyReview } from "@/lib/weeklyReview";
import type { RecordTableRow } from "@/app/components/RecordTable";
import BetLedger from "@/app/components/BetLedger";
import PicksList from "@/app/components/PicksList";
import RecordTable from "@/app/components/RecordTable";
import Section from "@/app/components/Section";
import SeasonFallbackNotice from "@/app/components/SeasonFallbackNotice";
import SeasonSelect from "@/app/components/SeasonSelect";
import WeekSelect from "@/app/components/WeekSelect";
import { gateLedger } from "@/lib/signalGate";

export const dynamic = "force-dynamic";

// Results is READ-ONLY (Tate 2026-09-13: "all the logging should happen on the
// board page. The results is just to see what I picked and how it turned out").
//
// One page since 2026-09-28 (site review): Results and Track record both
// headlined the same record, so they merged, ledger first. A visitor sees the
// bet ledger (our bets in units, the curve, every bet as logged, the CSV) and
// a three-row season comparison. Behind the cookie: the owner's pick list with
// its edit and delete controls (the only place a pending real ticket is edited
// before kickoff) and the full-game comparison row. The Monday review's
// breakdown, decisions strip and factor read went with roadmap v2.0
// (2026-10-11): the site is a public record and nothing more.
//
// The kill numbers are enforced server-side for every path by
// lib/pickRules.ts::checkPolicy; nothing on this page gates a bet.

export default async function ResultsPage({
  searchParams,
}: {
  searchParams: Promise<{ season?: string; week?: string }>;
}) {
  const authed = await viewerIsAuthed();
  const seasons = await getSeasons();
  const sp = await searchParams;
  const { season, fallbackFrom } = resolveSeason(seasons, sp.season);
  const wantWeek: number | "all" | undefined =
    sp.week === "all"
      ? "all"
      : sp.week && Number.isFinite(Number(sp.week))
        ? Number(sp.week)
        : undefined;

  const [ledger, review, allPicks, bets] = await Promise.all([
    getLedger(season),
    getWeeklyReview(season, wantWeek),
    loadPicks(season),
    getBetLedger(season),
  ]);
  const weekLabel = review.week === null ? "all weeks" : `week ${review.week}`;
  const { startUsd, unitUsd } = bankrollEnv();
  const curve = bankrollCurve(allPicks, startUsd, unitUsd);
  const hasRecord =
    ledger.market !== null ||
    ledger.you !== null ||
    ledger.paper !== null ||
    ledger.marketFull !== null;

  // Three rows a visitor can read without a paragraph; the full-game market
  // is the owner's baseline.
  const comparison: RecordTableRow[] = [
    {
      key: "market",
      label: "Every first-half under at the close",
      note: "the baseline to beat",
      rec: ledger.market,
      empty: "nothing graded yet",
    },
    {
      key: "paper",
      label: "Every game that cleared the bar, on paper",
      note: "no 5-a-week cap · tracked with no money",
      rec: ledger.paper,
      empty: "no paper picks graded yet",
    },
    {
      key: "you",
      label: "Our bets",
      lead: true,
      rec: ledger.you,
      empty: "no real bets graded yet",
    },
    ...(authed
      ? ([
          {
            key: "fg",
            label: "Market — full game",
            note: "context only",
            rec: ledger.marketFull,
            dim: true,
            empty: "nothing graded yet",
          },
        ] satisfies RecordTableRow[])
      : []),
  ];

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

      {/* The ledger leads: our bets, in units, then every bet as logged. */}
      <BetLedger
        rows={gateLedger(bets, authed, new Date())}
        season={season}
        curve={curve}
      />

      <Section
        title={`Season comparison · ${season}`}
        empty={
          hasRecord
            ? null
            : "nothing has settled yet. It fills in as games are graded."
        }
      >
        <RecordTable ariaLabel="Season summary" showClv rows={comparison} />
      </Section>

      {authed && (
        <section
          aria-label="Your picks, signed in"
          className="mt-12 border-t border-dashed border-[var(--border-strong)] pt-6"
        >
          <p className="mb-4 text-[0.65rem] font-semibold uppercase tracking-[0.12em] text-[var(--accent)]">
            Signed in only · your picks
          </p>

          <h2 className="mb-2 text-sm font-semibold text-[var(--text)]">
            Your picks
            <span className="ml-2 text-xs font-normal text-[var(--text-dim)]">
              {weekLabel}
            </span>
          </h2>
          <PicksList
            picks={review.picks}
            showWeek={review.week === null}
            authed={authed}
          />
        </section>
      )}
    </div>
  );
}
