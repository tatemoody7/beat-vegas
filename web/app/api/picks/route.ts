import { NextRequest, NextResponse } from "next/server";
import { createPick, getPicks, getSlate } from "@/lib/picks";
import { prisma } from "@/lib/prisma";

// GET /api/picks?season=2025 — user's picks + running record for the season.
export async function GET(req: NextRequest) {
  const season = Number(req.nextUrl.searchParams.get("season"));
  if (!Number.isFinite(season)) {
    return NextResponse.json(
      { error: "missing or invalid ?season" },
      { status: 400 },
    );
  }
  return NextResponse.json(await getPicks(season));
}

// POST /api/picks — log a pick on a scored-slate game.
export async function POST(req: NextRequest) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
  }
  const b = body as Record<string, unknown>;
  const gameId = Number(b.gameId);
  const line = Number(b.line);
  if (!Number.isFinite(gameId)) {
    return NextResponse.json({ error: "gameId required" }, { status: 400 });
  }
  if (!Number.isFinite(line)) {
    return NextResponse.json(
      { error: "line required (number)" },
      { status: 400 },
    );
  }

  // gameId must be in the current scored slate.
  const game = await prisma.games.findUnique({
    where: { id: gameId },
    select: { season: true },
  });
  const slate = game ? await getSlate(game.season) : [];
  if (!slate.some((g) => g.gameId === gameId)) {
    return NextResponse.json(
      { error: "game is not in the current scored slate" },
      { status: 400 },
    );
  }

  const stake = b.stake !== undefined ? Number(b.stake) : undefined;
  const price = b.price !== undefined ? Number(b.price) : undefined;
  const note =
    typeof b.note === "string" && b.note.trim() ? b.note.trim() : undefined;
  const market = b.market === "full" ? "full" : "1H";

  await createPick({ gameId, market, line, stake, price, note });
  return NextResponse.json({ ok: true }, { status: 201 });
}
