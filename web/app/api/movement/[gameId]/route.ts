import { NextResponse } from "next/server";
import { getMovement } from "@/lib/movement";

// GET /api/movement/<gameId> — per-book 1H line history for one game.
export async function GET(
  _req: Request,
  { params }: { params: Promise<{ gameId: string }> },
) {
  const { gameId } = await params;
  const id = Number(gameId);
  if (!Number.isFinite(id)) {
    return NextResponse.json({ error: "invalid gameId" }, { status: 400 });
  }
  return NextResponse.json(await getMovement(id));
}
