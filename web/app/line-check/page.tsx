import { getSeasons } from "@/lib/board";
import { getLineCheck, type Market } from "@/lib/lineCheck";
import { resolveSeason } from "@/lib/season";
import SeasonFallbackNotice from "@/app/components/SeasonFallbackNotice";
import SeasonSelect from "@/app/components/SeasonSelect";
import MarketToggle from "@/app/components/MarketToggle";
import LineCheckCard from "@/app/components/LineCheckCard";

export const dynamic = "force-dynamic";

export default async function LineCheckPage({
  searchParams,
}: {
  searchParams: Promise<{ season?: string; market?: string }>;
}) {
  const seasons = await getSeasons();
  const sp = await searchParams;
  const { season, fallbackFrom } = resolveSeason(seasons, sp.season);
  const market: Market = sp.market === "1h" ? "1h" : "full_game";

  const rows = await getLineCheck(season, market);
  const priced = rows.filter((r) => r.hrLine !== null);
  const good = priced.filter((r) => r.verdict === "good").length;

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="bv-page-title">Line Check</h1>
          <p className="bv-page-sub">
            Is Hard Rock giving you a good number? For an under, a higher total
            is better — verdict is Hard Rock vs the best total in the market.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <MarketToggle current={market} />
          {seasons.length > 0 && (
            <SeasonSelect seasons={seasons} current={season} />
          )}
        </div>
      </div>

      <SeasonFallbackNotice fallbackFrom={fallbackFrom} season={season} />

      {priced.length > 0 && (
        <p className="mb-4 text-sm text-[var(--text-muted)]">
          Hard Rock has priced{" "}
          <span className="font-semibold text-[var(--text)]">
            {priced.length}
          </span>{" "}
          {market === "1h" ? "first-half" : "full-game"} game
          {priced.length === 1 ? "" : "s"} —{" "}
          <span style={{ color: "var(--under-strong)" }}>{good} good</span>.
        </p>
      )}

      {rows.length === 0 ? (
        <p className="bv-card p-6 text-sm text-[var(--text-muted)]">
          {`No ${market === "1h" ? "first-half" : "full-game"} lines captured for ${season} yet. ${market === "1h" ? "First-half lines are swept Friday afternoon and Saturday morning." : "Full-game openers are captured Sunday afternoon."}`}
        </p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {rows.map((r) => (
            <LineCheckCard key={r.gameId} row={r} />
          ))}
        </div>
      )}
    </div>
  );
}
