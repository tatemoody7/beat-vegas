import { notFound } from "next/navigation";
import GameDetail from "@/app/components/GameDetail";
import { bankrollEnv, getHomeGame } from "@/lib/homeBoard";
import { viewerIsAuthed } from "@/lib/session";

// One game, in full. The board row links here rather than expanding in place,
// so the board stays a scan and everything analytical has room to be a picture.
// Loads the whole week behind the scenes (lib/homeBoard.getHomeGame) so the rank
// and cap slot shown here are the same ones the board assigned.

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

  const { unitUsd } = bankrollEnv();
  const authed = await viewerIsAuthed();
  return (
    <GameDetail
      g={found.game}
      authed={authed}
      unitUsd={unitUsd}
      backHref={`/#game-${gameId}`}
    />
  );
}
