import { getSeasons } from "@/lib/board";
import { buildBetSlip, liveLinesFrom } from "@/lib/betSlip";
import { getLatestCard } from "@/lib/card";
import { getHomeBoard } from "@/lib/homeBoard";
import { resolveSeason } from "@/lib/season";
import BankrollStrip from "@/app/components/BankrollStrip";
import BetSlip from "@/app/components/BetSlip";
import CardPanel from "@/app/components/CardPanel";
import CardStatusBanner from "@/app/components/CardStatusBanner";
import SeasonFallbackNotice from "@/app/components/SeasonFallbackNotice";

export const dynamic = "force-dynamic";

// The Saturday screen: the one place money gets committed. It carries the
// frozen card reconciled against the live Hard Rock numbers, what the card
// wanted but a gate or the cap stopped, and the bankroll the stake comes out
// of. All three used to sit above (then below) the board, where Tate never
// scrolled to them.
//
// It loads the board for the same reason the game page does: the slip has to be
// reconciled against the live lines this render just read, so a moved line or a
// breached kill number shows before the tap rather than after the server says
// no.
export default async function SlipPage({
  searchParams,
}: {
  searchParams: Promise<{ season?: string; week?: string }>;
}) {
  const seasons = await getSeasons();
  const sp = await searchParams;
  const { season, fallbackFrom } = resolveSeason(seasons, sp.season);
  const reqWeek = Number(sp.week);
  const weekArg =
    Number.isInteger(reqWeek) && reqWeek > 0 ? reqWeek : undefined;

  // Settle the week first, then read the card FOR that week, so a stale card
  // never describes a different week's games.
  const board = await getHomeBoard(season, weekArg);
  const card =
    board.week === null ? null : await getLatestCard(season, board.week);
  const slip = buildBetSlip(
    card,
    board.weekPicks,
    board.bankroll.cap,
    new Date(),
    liveLinesFrom(board.games),
  );

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="bv-page-title">
        {board.week !== null ? `Bet slip · Week ${board.week}` : "Bet slip"}
      </h1>
      <p className="bv-page-sub mb-4 mt-1">
        {`What to place, at what number and price. Match Hard Rock's ticket before the second tap.`}
      </p>

      <SeasonFallbackNotice fallbackFrom={fallbackFrom} season={season} />

      {card === null ? (
        <p className="bv-card p-6 text-sm text-[var(--text-muted)]">
          {`No card has been built for this week yet. Builds land Tuesday, Thursday and Friday afternoons and Saturday morning.`}
        </p>
      ) : (
        <>
          <CardStatusBanner card={card} />
          <BetSlip slip={slip} unitUsd={board.bankroll.unitUsd} />
          <CardPanel card={card} />
        </>
      )}

      <BankrollStrip b={board.bankroll} />
    </div>
  );
}
