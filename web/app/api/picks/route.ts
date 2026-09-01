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
  // Number(null) is 0 and would pass isFinite — reject missing values first.
  if (b.gameId == null || !Number.isFinite(gameId)) {
    return NextResponse.json({ error: "gameId required" }, { status: 400 });
  }
  const line = Number(b.line);
  if (b.line == null || !Number.isFinite(line) || line <= 0) {
    return NextResponse.json(
      { error: "line required (positive number)" },
      { status: 400 },
    );
  }
  // Paper pick: nothing at risk. Stake is forced to 0 server-side (never
  // trust the client's number) so the season's units math can't be polluted.
  const isPaper = b.isPaper === true;
  // stake/price: one NaN here would poison the whole season's units math.
  let stake: number | undefined;
  if (isPaper) {
    stake = 0;
  } else if (b.stake !== undefined) {
    stake = Number(b.stake);
    if (b.stake === null || !Number.isFinite(stake) || stake <= 0) {
      return NextResponse.json(
        { error: "stake must be a positive number" },
        { status: 400 },
      );
    }
  }
  let price: number | undefined;
  if (b.price !== undefined) {
    price = Number(b.price);
    // American odds are integers with |price| >= 100 (the column is an int).
    if (b.price === null || !Number.isInteger(price) || Math.abs(price) < 100) {
      return NextResponse.json(
        { error: "price must be integer American odds (e.g. -110)" },
        { status: 400 },
      );
    }
  }

  // gameId must be in the current scored slate.
  const game = await prisma.games.findUnique({
    where: { id: gameId },
    select: { season: true, start_date: true },
  });
  const slate = game ? await getSlate(game.season) : [];
  if (!game || !slate.some((g) => g.gameId === gameId)) {
    return NextResponse.json(
      { error: "game is not in the current scored slate" },
      { status: 400 },
    );
  }
  // A pick after kickoff isn't a real bet (start_date is naive UTC).
  if (game.start_date && game.start_date <= new Date()) {
    return NextResponse.json(
      { error: "game has already kicked off" },
      { status: 409 },
    );
  }

  const note =
    typeof b.note === "string" && b.note.trim() ? b.note.trim() : undefined;
  const market = b.market === "full" ? "full" : "1H";

  // One pick per game/market: a double-click must not double the record.
  const dup = await prisma.$queryRaw<{ id: number }[]>`
    SELECT id FROM manual_picks
    WHERE game_id = ${gameId} AND COALESCE(market, '1H') = ${market}
    LIMIT 1
  `;
  if (dup.length > 0) {
    return NextResponse.json(
      { error: `a ${market} pick already exists on this game` },
      { status: 409 },
    );
  }

  await createPick({ gameId, market, line, stake, price, note, isPaper });
  return NextResponse.json({ ok: true }, { status: 201 });
}
