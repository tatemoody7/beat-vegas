import { getSeasons } from "@/lib/board";
import { getArmPicks, getPricingOpportunities } from "@/lib/armPicks";
import ArmPicksSection from "@/app/components/ArmPicksSection";
import PricingOpportunities from "@/app/components/PricingOpportunities";
import { getLedger } from "@/lib/ledger";
import { resolveSeason } from "@/lib/season";
import type { RecordTableRow } from "@/app/components/RecordTable";
import RecordTable from "@/app/components/RecordTable";
import Section from "@/app/components/Section";
import SeasonFallbackNotice from "@/app/components/SeasonFallbackNotice";
import SeasonSelect from "@/app/components/SeasonSelect";

export const dynamic = "force-dynamic";

// Record (final-2026 plan, D16, 2026-10-18; the path stays /results so every
// link and redirect keeps working): the arms' forward picks with the judge's
// reading or the reason there is none, then the pricing study's forward
// opportunities, then the season comparison. The personal real-money ledger
// left the live site the same day (D2/D16): the 30 tickets stay in
// `manual_picks`, untouched, and appear only in the final report. Nothing on
// this page is a bet, and nothing here can be logged, edited or deleted.

export default async function RecordPage({
  searchParams,
}: {
  searchParams: Promise<{ season?: string }>;
}) {
  const seasons = await getSeasons();
  const sp = await searchParams;
  const { season, fallbackFrom } = resolveSeason(seasons, sp.season);

  const [ledger, armPicks, opportunities] = await Promise.all([
    getLedger(season),
    getArmPicks(season),
    getPricingOpportunities(),
  ]);
  const hasRecord =
    ledger.market !== null ||
    ledger.paper !== null ||
    ledger.marketFull !== null;

  // Three rows a reader can take in without a paragraph; no personal stake.
  const comparison: RecordTableRow[] = [
    {
      key: "market",
      label: "Market research: every first-half under at the consensus close",
      note: "a benchmark, not a bet: no one can bet the consensus, so no units",
      // Record only (fact-check audit 2026-10-17, Tate): the stored rows
      // carry an assumed -110 that no one was offered.
      rec:
        ledger.market === null
          ? null
          : { ...ledger.market, units: "—", roi: "—" },
      empty: "nothing graded yet",
    },
    {
      key: "paper",
      label: "Every game that cleared the bar, on paper",
      note: `no 5-a-week cap · development before 2026-10-13${
        ledger.paperExcluded > 0
          ? ` · ${ledger.paperExcluded} picks logged on a Hard Rock alternate line (weeks 2-4) left out`
          : ""
      }`,
      rec: ledger.paper,
      empty: "no paper picks graded yet",
    },
    {
      key: "fg",
      label: "Market — full game",
      note: "context only",
      rec: ledger.marketFull,
      dim: true,
      empty: "nothing graded yet",
    },
  ];

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="bv-page-title">Record</h1>
          <p className="bv-page-sub">{`${season} season`}</p>
        </div>
        {seasons.length > 0 && (
          <SeasonSelect seasons={seasons} current={season} />
        )}
      </div>

      <SeasonFallbackNotice fallbackFrom={fallbackFrom} season={season} />

      <ArmPicksSection picks={armPicks} />

      <PricingOpportunities rows={opportunities} />

      <Section
        title={`Season comparison · ${season}`}
        empty={
          hasRecord
            ? null
            : "nothing has settled yet. It fills in as games are graded."
        }
      >
        <RecordTable
          ariaLabel="Season summary"
          showClv
          showInterval
          rows={comparison}
        />
      </Section>
    </div>
  );
}
