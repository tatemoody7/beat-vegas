import { getLatestCard } from "@/lib/card";
import { breakEvenPrice } from "@/lib/edge";
import { getLineCheck, HR_PRICE_MAX_AGE_H } from "@/lib/lineCheck";
import { getSlate } from "@/lib/picks";
import {
  betAtCheck,
  checkPolicy,
  isBackdated,
  serverVerdict,
  verdictAtBetTime,
} from "@/lib/pickRules";
import type { PickRequest, PolicyContext, Rejection } from "@/lib/pickRules";
import { prisma } from "@/lib/prisma";
import { getRulePause } from "@/lib/rulePause";
import type { RulePause } from "@/lib/rulePause";
import type { Verdict } from "@/lib/verdict";

// THE ONE PLACE a real ticket is judged (2026-10-07, M1A). POST /api/picks
// (a new ticket) and PATCH /api/picks/<id> (a price correction) both call
// evaluateRealTicket, so the two paths cannot drift apart: before this the
// POST route ran every gate and PATCH ran none, which let a ticket logged at a
// passing price be edited to a worse one, cleared to no price, or flipped to a
// bonus bet that frees a cap slot.
//
// The read a ticket is judged by is chosen by evaluationMode and passed in
// explicitly -- neither route decides "live or backdated" on its own:
//  - "live": the ticket was written within BACKDATE_MIN_MINUTES of now, so the
//    LIVE Hard Rock read (lib/lineCheck.ts) is the read the bet saw.
//  - "as_of_bet_time": the ticket was written earlier, so it is judged as of
//    the bet time (M1B, 2026-10-07): the card in force then must have rated
//    the game BET (a new log only; an edit keeps the verdict frozen on it), and
//    the price and kill price come from Hard Rock's newest main-line snapshot
//    at or before the bet time, which must have been seen within
//    HR_PRICE_MAX_AGE_H of it. Nothing after the bet time is reconstructed: a
//    ticket that cannot be verified from what existed then is refused.
//
// Paper never comes here: since 2026-10-07 every paper pick is written by the
// card build (scripts/build_card.py), never by hand.

export type EvaluationMode = "live" | "as_of_bet_time";

/** Which read judges a ticket written at `betAt` (null = now). */
export function evaluationMode(
  betAt: string | null,
  now: Date,
): EvaluationMode {
  return isBackdated(betAt, now) ? "as_of_bet_time" : "live";
}

export type TicketEvaluation = { ok: true; verdict: Verdict } | Rejection;

/**
 * Was Hard Rock's quote last SEEN more than HR_PRICE_MAX_AGE_H before the bet
 * time? `seenAt` is naive UTC text, max(captured_at, last_seen_at); a sighting
 * after the bet time confirms the quote was still in force at it (an unchanged
 * poll writes no row, so no newer quote existed in between).
 */
export function staleAtBet(seenAt: string | null, betAt: Date): boolean {
  if (seenAt === null) return true;
  const seen = Date.parse(`${seenAt.trim().replace(" ", "T")}Z`);
  if (!Number.isFinite(seen)) return true;
  const confirmed = Math.min(seen, betAt.getTime());
  return betAt.getTime() - confirmed > HR_PRICE_MAX_AGE_H * 3_600_000;
}

function dbError(where: string, e: unknown): Rejection {
  console.error(`[ticketPolicy] ${where} failed:`, e);
  return {
    ok: false,
    error: "could not reach the database — nothing was saved",
    status: 503,
  };
}

export async function evaluateRealTicket(args: {
  /** The ticket as it would be stored. Must be real money (isPaper false). */
  pick: PickRequest;
  /** From evaluationMode(pick.betAt, now); "as_of_bet_time" needs pick.betAt. */
  mode: EvaluationMode;
  now: Date;
  /** PATCH: the pick being edited, left out of the duplicate and cap counts. */
  excludePickId?: number;
  /** PATCH: the verdict frozen on the ticket when it was logged. The edit
   *  corrects what the ticket says; it does not re-rate it. null/undefined =
   *  decide it here, as for a new ticket. */
  frozenVerdict?: Verdict | null;
}): Promise<TicketEvaluation> {
  const { pick, mode, now } = args;
  if (pick.isPaper) {
    throw new Error("evaluateRealTicket: paper is written by the build only");
  }
  const betAt = pick.betAt ?? null;
  if (mode === "as_of_bet_time" && betAt === null) {
    throw new Error("evaluateRealTicket: as_of_bet_time needs a bet time");
  }
  const betAtDate = betAt === null ? null : new Date(betAt);
  const excludeId = args.excludePickId ?? -1;

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
  // The bet time needs only the kickoff: refuse a future, stale or post-kickoff
  // one here, before the policy queries are spent on it.
  const when = betAtCheck(betAt, now, game?.start_date ?? null);
  if (!when.ok) return when;

  // One pick per game/market PER LEDGER: a double-click must not double the
  // record, but the card's paper pick on a game must never block the real
  // ticket on it. An edit is not a duplicate of itself.
  const dupQ = game
    ? prisma.$queryRaw<{ id: number }[]>`
        SELECT id FROM manual_picks
        WHERE game_id = ${pick.gameId} AND COALESCE(market, '1H') = ${pick.market}
          AND COALESCE(is_paper, false) = false
          AND id <> ${excludeId}
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
          AND id <> ${excludeId}
      `
    : Promise.resolve([]);
  // The week's card, for this game's kill numbers (null without a card row);
  // as of bet time, the card in force when the ticket was written.
  const cardQ = game
    ? getLatestCard(
        game.season,
        game.week,
        mode === "as_of_bet_time" ? (betAtDate ?? undefined) : undefined,
      )
    : Promise.resolve(null);
  // The market read — the same loader the board renders from, so the gate and
  // the screen cannot disagree. Live: now. As of bet time: only the snapshots
  // captured at or before the bet time.
  const checkQ = game
    ? getLineCheck(
        game.season,
        "1h",
        undefined,
        mode === "as_of_bet_time" ? (betAtDate ?? undefined) : undefined,
      )
    : Promise.resolve([] as Awaited<ReturnType<typeof getLineCheck>>);
  // The real-money pause (docs/STOPPING_RULE.md). getRulePause never throws —
  // a failed read comes back as the UNREADABLE state, which checkPolicy
  // refuses with its own reason.
  let dup: { id: number }[];
  let cap: { n: number | bigint }[];
  let card: Awaited<ReturnType<typeof getLatestCard>>;
  let checks: Awaited<ReturnType<typeof getLineCheck>>;
  let rulePause: RulePause;
  try {
    [dup, cap, card, checks, rulePause] = await Promise.all([
      dupQ,
      capQ,
      cardQ,
      checkQ,
      getRulePause(),
    ]);
  } catch (e) {
    return dbError("policy checks", e);
  }
  const item = card?.items.find((i) => i.gameId === pick.gameId) ?? null;

  // THE VERDICT IS DECIDED HERE, not by the client. A request that says
  // "WATCH" on a game the server rates BET is gated as a BET; a request that
  // says "BET" on a game the server rates WATCH is logged as the off-policy
  // WATCH it is. The read that decides it is the mode's:
  //  - as_of_bet_time: the card in force at bet time -- its tier is the
  //    verdict and its kill numbers judge the line and price (checkPolicy
  //    falls back to ctx.killLine / killPrice when the live killPrice is null).
  //  - live: the LIVE Hard Rock line/price/centring and consensus, with the
  //    card's model read, slate bar and QB-out flag and the season's games
  //    played -- the same gates the card and the board apply. Fail closed:
  //    every branch that cannot produce a checkable price returns
  //    { ok: false }, and checkPolicy refuses the real-money BET rather than
  //    falling back to the card's cached number. Mirrors verdict.ts, where the
  //    BET branch requires a non-null ev and otherwise reads WATCH.
  const row = checks.find((c) => c.gameId === pick.gameId) ?? null;
  const asOfBet = mode === "as_of_bet_time";
  const priceAt = asOfBet ? "at the time the ticket was written" : "right now";
  let livePrice: PolicyContext["livePrice"];
  if (row === null) {
    livePrice = {
      ok: false,
      reason: asOfBet
        ? "no Hard Rock read existed for this game at the time the ticket was written"
        : "no live line read for this game",
    };
  } else if (row.hrLive === false) {
    // hrLine/hrUnderPrice are Hard Rock's last MAIN line, held over while the
    // feed serves an alternate: shown on the board, never a live price.
    livePrice = {
      ok: false,
      reason: `Hard Rock’s feed was showing an alternate line ${priceAt}, so its price cannot be verified`,
    };
  } else if (row.hrUnderPrice === null) {
    livePrice = {
      ok: false,
      reason: `Hard Rock had not priced its under ${priceAt}`,
    };
  } else if (row.marketFairUnder === null) {
    livePrice = {
      ok: false,
      reason: `no other book or exchange was priced at Hard Rock’s number ${priceAt}`,
    };
  } else if (asOfBet && staleAtBet(row.hrSeenAt ?? null, betAtDate!)) {
    livePrice = {
      ok: false,
      reason: `Hard Rock’s last confirmed price before the bet time was more than ${HR_PRICE_MAX_AGE_H} hours old, so the price the ticket was written at cannot be verified`,
    };
  } else {
    livePrice = { ok: true, killPrice: breakEvenPrice(row.marketFairUnder) };
  }
  // A NEW backdated log must have been a BET on the card in force then
  // (2026-10-07, Tate's call): an off-card ticket written earlier cannot be
  // verified from what the system said at the time, so it is not recorded.
  // An edit keeps the verdict frozen on the ticket and skips this.
  if (asOfBet && args.frozenVerdict == null) {
    const tier = verdictAtBetTime(item);
    if (tier !== "BET") {
      return {
        ok: false,
        error: `NOT A BET THEN — the card in force when the ticket was written ${
          item === null ? "did not rate this game" : `rated it ${tier}, not BET`
        }. A late log is recorded only when it can be checked against that card; log tickets when they are written.`,
        status: 409,
      };
    }
  }

  const verdict: Verdict =
    args.frozenVerdict ??
    (mode === "as_of_bet_time"
      ? verdictAtBetTime(item)
      : serverVerdict({
          bvLine: item?.bvLine ?? null,
          bar: item?.bar ?? null,
          hrLine: row?.hrLine ?? null,
          hrUnderPrice: row?.hrUnderPrice ?? null,
          hrCentred: row?.hrCentred ?? null,
          ev: row?.ev ?? null,
          marketLine: row?.median ?? null,
          qbOut: item?.blocker === "qb_out" || item?.paperBlocker === "qb_out",
          minGamesPlayed,
        }));

  const policy = checkPolicy(
    { ...pick, verdict },
    {
      inSlate,
      // A pick after kickoff isn't a real bet (start_date is naive UTC).
      kickedOff: !!game?.start_date && game.start_date <= now,
      duplicate: dup.length > 0,
      realWeekCount: Number(cap[0]?.n ?? 0),
      week: game?.week ?? null,
      minGamesPlayed,
      killLine: item?.killLine ?? null,
      killPrice: item?.killPrice ?? null,
      rulePause,
      livePrice,
    },
  );
  if (!policy.ok) return policy;
  return { ok: true, verdict };
}
