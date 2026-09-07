import { NextRequest, NextResponse } from "next/server";
import { getLatestCard } from "@/lib/card";
import { createPick, getSlate } from "@/lib/picks";
import { checkPolicy, parsePickBody } from "@/lib/pickRules";
import { prisma } from "@/lib/prisma";

// POST /api/picks — log a pick on a current-slate game. Validation and the
// betting policy (1H-only real money, flat 1 unit, 5-bet weekly cap, the
// card's kill numbers) live in lib/pickRules.ts so they are unit-tested; this
// route only gathers DB facts.
export async function POST(req: NextRequest) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
  }
  const parsed = parsePickBody(body);
  if (!parsed.ok) {
    return NextResponse.json(
      { error: parsed.error },
      { status: parsed.status },
    );
  }
  const { pick } = parsed;

  const game = await prisma.games.findUnique({
    where: { id: pick.gameId },
    select: { season: true, week: true, start_date: true },
  });
  const slate = game ? await getSlate(game.season) : [];
  const inSlate = !!game && slate.some((g) => g.gameId === pick.gameId);

  // One pick per game/market PER LEDGER: a double-click must not double the
  // record, but the card's paper pick on a game (the paper ledger now logs
  // every qualifying game) must never block Tate's real ticket on it.
  const dupQ = game
    ? prisma.$queryRaw<{ id: number }[]>`
        SELECT id FROM manual_picks
        WHERE game_id = ${pick.gameId} AND COALESCE(market, '1H') = ${pick.market}
          AND COALESCE(is_paper, false) = ${pick.isPaper}
        LIMIT 1
      `
    : Promise.resolve([]);
  // Real-money first-half bets already logged this week (the cap).
  const capQ = game
    ? prisma.$queryRaw<{ n: number | bigint }[]>`
        SELECT COUNT(*) AS n FROM manual_picks
        WHERE season = ${game.season} AND week = ${game.week}
          AND COALESCE(is_paper, false) = false
          AND COALESCE(market, '1H') = '1H'
      `
    : Promise.resolve([]);
  // The week's card, for this game's kill numbers (null without a card row).
  const cardQ = game
    ? getLatestCard(game.season, game.week)
    : Promise.resolve(null);
  const [dup, cap, card] = await Promise.all([dupQ, capQ, cardQ]);
  const item = card?.items.find((i) => i.gameId === pick.gameId) ?? null;

  const policy = checkPolicy(pick, {
    inSlate,
    // A pick after kickoff isn't a real bet (start_date is naive UTC).
    kickedOff: !!game?.start_date && game.start_date <= new Date(),
    duplicate: dup.length > 0,
    realWeekCount: Number(cap[0]?.n ?? 0),
    week: game?.week ?? null,
    killLine: item?.killLine ?? null,
    killPrice: item?.killPrice ?? null,
  });
  if (!policy.ok) {
    return NextResponse.json(
      { error: policy.error },
      { status: policy.status },
    );
  }

  const { tracked } = await createPick(pick);
  return NextResponse.json(
    {
      ok: true,
      ...(tracked
        ? {}
        : {
            warning:
              "Pick saved, but the verdict snapshot was not stored — the tracking columns are missing (run the manual_picks migration).",
          }),
    },
    { status: 201 },
  );
}
