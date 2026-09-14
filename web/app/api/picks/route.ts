import { NextRequest, NextResponse } from "next/server";
import { getLatestCard } from "@/lib/card";
import { breakEvenPrice } from "@/lib/edge";
import { getLineCheck } from "@/lib/lineCheck";
import { createPick, DuplicatePickError, getSlate } from "@/lib/picks";
import { checkPolicy, parsePickBody } from "@/lib/pickRules";
import { prisma } from "@/lib/prisma";
import type { PolicyContext } from "@/lib/pickRules";

// POST /api/picks — log a pick on a current-slate game. Validation and the
// betting policy (1H-only real money, flat 1 unit, 5-bet weekly cap, the
// card's kill numbers) live in lib/pickRules.ts so they are unit-tested; this
// route only gathers DB facts.
function dbError(where: string, e: unknown) {
  console.error(`[api/picks] ${where} failed:`, e);
  return NextResponse.json(
    { error: "could not reach the database — the pick was NOT logged" },
    { status: 503 },
  );
}

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

  // Everything from here down touches the database. A Neon blip used to return
  // a bare framework 500 with no JSON body, which the client rendered as
  // "failed (500)" on the one screen where money is logged.
  let game: { season: number; week: number; start_date: Date | null } | null;
  let inSlate = false;
  let minGamesPlayed: number | null = null;
  try {
    game = await prisma.games.findUnique({
      where: { id: pick.gameId },
      select: { season: true, week: true, start_date: true },
    });
    const slate = game ? await getSlate(game.season) : [];
    const row = slate.find((g) => g.gameId === pick.gameId);
    inSlate = !!game && !!row;
    minGamesPlayed = row?.minGamesPlayed ?? null;
  } catch (e) {
    return dbError("slate lookup", e);
  }

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
  // Bankroll-funded first-half bets already logged this week (the cap). A
  // bonus bet is excluded: the cap limits how much of the roll is at risk, and
  // the book funded that stake, so a free bet must not crowd out a real one.
  const capQ = game
    ? prisma.$queryRaw<{ n: number | bigint }[]>`
        SELECT COUNT(*) AS n FROM manual_picks
        WHERE season = ${game.season} AND week = ${game.week}
          AND COALESCE(is_paper, false) = false
          AND COALESCE(is_bonus, false) = false
          AND COALESCE(market, '1H') = '1H'
      `
    : Promise.resolve([]);
  // The week's card, for this game's kill numbers (null without a card row).
  const cardQ = game
    ? getLatestCard(game.season, game.week)
    : Promise.resolve(null);
  // The LIVE market read — the same loader the board renders from, so the gate
  // and the screen cannot disagree. The card is built on a Tuesday; the bet is
  // placed on a Saturday, and marketFairUnder moves in between.
  const checkQ = game
    ? getLineCheck(game.season, "1h")
    : Promise.resolve([] as Awaited<ReturnType<typeof getLineCheck>>);
  let dup: { id: number }[];
  let cap: { n: number | bigint }[];
  let card: Awaited<ReturnType<typeof getLatestCard>>;
  let checks: Awaited<ReturnType<typeof getLineCheck>>;
  try {
    [dup, cap, card, checks] = await Promise.all([dupQ, capQ, cardQ, checkQ]);
  } catch (e) {
    return dbError("policy checks", e);
  }
  const item = card?.items.find((i) => i.gameId === pick.gameId) ?? null;

  // Fail closed: every branch that cannot produce a checkable price returns
  // { ok: false }, and checkPolicy refuses the real-money BET rather than
  // falling back to the card's cached number. Mirrors verdict.ts, where the BET
  // branch requires a non-null ev and otherwise reads WATCH — so a game the
  // board will not colour green is also a game the API will not log.
  const row = checks.find((c) => c.gameId === pick.gameId) ?? null;
  let livePrice: PolicyContext["livePrice"];
  if (row === null) {
    livePrice = { ok: false, reason: "no live line read for this game" };
  } else if (row.hrUnderPrice === null) {
    livePrice = { ok: false, reason: "Hard Rock has not priced its under" };
  } else if (row.marketFairUnder === null) {
    livePrice = {
      ok: false,
      reason: "no other book or exchange is priced at Hard Rock’s number",
    };
  } else {
    livePrice = { ok: true, killPrice: breakEvenPrice(row.marketFairUnder) };
  }

  const policy = checkPolicy(pick, {
    inSlate,
    // A pick after kickoff isn't a real bet (start_date is naive UTC).
    kickedOff: !!game?.start_date && game.start_date <= new Date(),
    duplicate: dup.length > 0,
    realWeekCount: Number(cap[0]?.n ?? 0),
    week: game?.week ?? null,
    minGamesPlayed,
    killLine: item?.killLine ?? null,
    killPrice: item?.killPrice ?? null,
    livePrice,
  });
  if (!policy.ok) {
    return NextResponse.json(
      { error: policy.error },
      { status: policy.status },
    );
  }

  let tracked: boolean;
  try {
    ({ tracked } = await createPick(pick));
  } catch (e) {
    // The uq_manual_pick_per_ledger backstop fired. The duplicate check above
    // already passed, so this is the race it cannot close — a double-click, or
    // a retry of a request that had in fact succeeded. Either way the pick the
    // caller wanted is on file, so 409 (the same status the check itself
    // returns) is the honest answer, not a 500.
    if (e instanceof DuplicatePickError) {
      return NextResponse.json({ error: e.message }, { status: 409 });
    }
    return dbError("createPick", e);
  }
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
