import { notFound } from "next/navigation";
import GameDetail from "@/app/components/GameDetail";
import { getCardForecast } from "@/lib/forecast";
import { getHomeGame } from "@/lib/homeBoard";
import { getKickZones } from "@/lib/kickoffClockDb";

// One game, in full. The board row links here rather than expanding in place,
// so the board stays a scan and everything analytical has room to be a picture.
// Loads the whole week behind the scenes (lib/homeBoard.getHomeGame) so the rank
// shown here is the one the board assigned. Nothing is logged from here since
// 2026-10-18 (final-2026 plan, D2): the page is a read-only record.

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const found = await getHomeGame(Number(id));
  if (found === null) return { title: "Game · Beat Vegas" };
  const { row } = found.game;
  return { title: `${row.away} @ ${row.home} · Beat Vegas` };
}

export default async function GamePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const gameId = Number(id);
  // A non-numeric or negative id is a bad URL, not an empty game — 404 rather
  // than handing Prisma something it will refuse.
  if (!Number.isInteger(gameId) || gameId <= 0) notFound();

  const found = await getHomeGame(gameId);
  if (found === null) notFound();

  return (
    <GameDetail
      g={found.game}
      backHref={`/#game-${gameId}`}
      forecast={await getCardForecast(gameId)}
      zones={await getKickZones(gameId)}
    />
  );
}
