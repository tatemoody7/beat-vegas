import { american, fmt } from "@/lib/format";
import type { RulePause } from "@/lib/rulePause";
import {
  MIN_GAMES_FOR_REAL_MONEY,
  REASONS,
  WEEKLY_BET_CAP,
  type PickReason,
  type Verdict,
} from "@/lib/verdict";

// Pure request validation + betting-policy checks for POST /api/picks, kept
// out of the route so the rules are unit-tested. docs/BETTING_POLICY.md:
// real money = first-half unders only, flat 1 unit, at most WEEKLY_BET_CAP a
// week. Paper picks are also 1 flat unit (so their record shows units) but
// `is_paper` keeps them out of the bankroll and the real record.

export const PAPER_STAKE = 1.0;
export const DEFAULT_STAKE = 1.0;
export const DEFAULT_PRICE = -110;

export type PickRequest = {
  gameId: number;
  market: "1H" | "full";
  line: number;
  stake: number;
  price: number;
  isPaper: boolean;
  note?: string;
  // Tracking (shared contract with scripts/pick.py add --verdict/--reason/...):
  verdict?: Verdict;
  reason?: PickReason;
  gap?: number | null;
  ev?: number | null;
  hrLine?: number | null;
};

/**
 * Real money placed where the site graded WATCH/PASS. A legacy pick with no
 * frozen verdict is NOT off-policy — we cannot know. Flagged on Results.
 *
 * It lives HERE, not beside the ledger in lib/picks.ts, because
 * app/components/PicksList.tsx is a client component and calls it: importing it
 * from lib/picks pulled prisma — and with Prisma 7, `pg` and its dns/net/tls
 * requires — into the browser bundle. The parameter is structural so this module
 * never imports the ledger. lib/picks re-exports it for server callers.
 */
export const isOffPolicy = (p: {
  isPaper: boolean;
  verdictAtPick: Verdict | null;
}): boolean =>
  !p.isPaper && p.verdictAtPick !== null && p.verdictAtPick !== "BET";

export type Rejection = { ok: false; error: string; status: number };
export type Parsed = { ok: true; pick: PickRequest };

const VERDICTS: readonly Verdict[] = ["BET", "WATCH", "PASS"];

const reject = (error: string, status = 400): Rejection => ({
  ok: false,
  error,
  status,
});

function optNumber(
  v: unknown,
  name: string,
): { ok: true; value: number | null | undefined } | Rejection {
  if (v === undefined) return { ok: true, value: undefined };
  if (v === null) return { ok: true, value: null };
  const n = Number(v);
  if (!Number.isFinite(n)) return reject(`${name} must be a number`);
  return { ok: true, value: n };
}

/** Shape + type checks on the JSON body. No DB. */
export function parsePickBody(body: unknown): Parsed | Rejection {
  if (!body || typeof body !== "object") {
    return reject("Could not read the request.");
  }
  const b = body as Record<string, unknown>;

  const gameId = Number(b.gameId);
  // Number(null) is 0 and would pass isFinite — reject missing values first.
  if (b.gameId == null || !Number.isFinite(gameId)) {
    return reject("Missing the game.");
  }
  const line = Number(b.line);
  if (b.line == null || !Number.isFinite(line) || line <= 0) {
    return reject("Enter the first-half total.");
  }
  const market: "1H" | "full" = b.market === "full" ? "full" : "1H";
  const isPaper = b.isPaper === true;

  // Real money is first-half only. Full game is context — paper is fine.
  if (market === "full" && !isPaper) {
    return reject(
      "Real money is first-half unders only. Log the full game as a paper pick.",
    );
  }

  // Stake: ALWAYS flat 1 unit (docs/BETTING_POLICY.md) — the client's `stake`
  // is ignored so a stray 0/NaN/3 can never size a real bet. Paper picks are
  // 1 unit too (so their record reads in units); is_paper keeps them out of
  // the bankroll.
  const stake = isPaper ? PAPER_STAKE : DEFAULT_STAKE;

  let price = DEFAULT_PRICE;
  if (b.price !== undefined) {
    price = Number(b.price);
    // American odds are integers with |price| >= 100 (the column is an int).
    if (b.price === null || !Number.isInteger(price) || Math.abs(price) < 100) {
      return reject("Enter the odds as a whole number, like -110.");
    }
  }

  const note =
    typeof b.note === "string" && b.note.trim() ? b.note.trim() : undefined;

  let verdict: Verdict | undefined;
  if (b.verdict !== undefined && b.verdict !== null) {
    if (!VERDICTS.includes(b.verdict as Verdict)) {
      return reject("Unrecognized rating.");
    }
    verdict = b.verdict as Verdict;
  }
  let reason: PickReason | undefined;
  if (b.reason !== undefined && b.reason !== null) {
    if (!REASONS.includes(b.reason as PickReason)) {
      return reject("Unrecognized reason.");
    }
    reason = b.reason as PickReason;
  }
  const gap = optNumber(b.gap, "gap");
  if (!gap.ok) return gap;
  const ev = optNumber(b.ev, "ev");
  if (!ev.ok) return ev;
  const hrLine = optNumber(b.hrLine, "hrLine");
  if (!hrLine.ok) return hrLine;

  return {
    ok: true,
    pick: {
      gameId,
      market,
      line,
      stake,
      price,
      isPaper,
      note,
      verdict,
      reason,
      gap: gap.value,
      ev: ev.value,
      hrLine: hrLine.value,
    },
  };
}

export type PolicyContext = {
  /** The game is on the current scored slate. */
  inSlate: boolean;
  /** Kickoff has passed. */
  kickedOff: boolean;
  /** A pick already exists on this game + market. */
  duplicate: boolean;
  /** Real-money 1H picks already logged for this season + week. */
  realWeekCount: number;
  week: number | null;
  /**
   * Fewest current-season games played by either team, or null when unknown.
   * Under MIN_GAMES_FOR_REAL_MONEY this game is PAPER ONLY -- see checkPolicy.
   */
  minGamesPlayed: number | null;
  /** The card's kill numbers for this game (lib/card.ts CardItem); null = no card item. */
  killLine: number | null;
  killPrice: number | null;
  /**
   * Whether the LIVE price could be verified at log time, and the kill price it
   * implies. The route recomputes this from the same loaders the board renders
   * from (lib/lineCheck.ts), rather than reading the card payload, so the screen
   * and the gate cannot be looking at different numbers — the card is built on a
   * Tuesday and the bet is placed on a Saturday.
   *
   * `ok: false` FAILS THE REAL-MONEY BET CLOSED. A cached card price may be
   * displayed for context; it may never authorize money. Stale data that looks
   * like a price is worse than no price, because it reads as verified.
   */
  livePrice:
    | { ok: true; killPrice: number | null }
    | { ok: false; reason: string };
  /**
   * The real-money pause (docs/STOPPING_RULE.md; lib/rulePause.ts). REQUIRED,
   * like livePrice, so a new caller cannot skip it by omission. `paused: true`
   * refuses every real-money 1H pick, overrides included; "unreadable" refuses
   * them too — a switch we cannot see is not a switch that is off. Paper never
   * reads it.
   */
  rulePause: RulePause;
};

/** Betting-policy checks that need DB facts (passed in). */
export function checkPolicy(
  pick: PickRequest,
  ctx: PolicyContext,
): { ok: true } | Rejection {
  if (!ctx.inSlate) return reject("That game is not on this week’s board.");
  if (ctx.kickedOff) return reject("That game has already kicked off.", 409);
  if (ctx.duplicate) {
    return reject(
      `You already have a ${
        pick.market === "full" ? "full-game" : "first-half"
      } pick on that game.`,
      409,
    );
  }
  // THE PAUSE comes before every other money gate and applies to EVERY
  // real-money first-half pick, WATCH/PASS overrides included: the switch is
  // thrown because something is wrong, and an override while paused is exactly
  // the bet it must stop. Two rejections on purpose — "switched off" and "cannot
  // see the switch" are different facts, and a post-mortem must tell them apart
  // from each other and from PRICE UNAVAILABLE. Paper is never touched.
  if (!pick.isPaper && pick.market === "1H") {
    if (ctx.rulePause.paused === "unreadable") {
      return reject(
        `RULE STATE UNREADABLE — ${ctx.rulePause.reason}. Real money needs the pause switch to be readable right now. Log it as paper, or re-try once the database is back.`,
        409,
      );
    }
    if (ctx.rulePause.paused === true) {
      return reject(
        `RULE PAUSED — real money is switched off${ctx.rulePause.note ? ` (${ctx.rulePause.note})` : ""}. Log it as paper; it still counts toward the record. scripts/rule_pause.py off resumes.`,
        409,
      );
    }
  }
  // A real BET below the card's kill line, or at a worse price, is not the
  // bet the card rated: the edge is gone. Paper and WATCH/PASS (an owner
  // override, already off-policy) are exempt.
  if (!pick.isPaper && pick.market === "1H" && pick.verdict === "BET") {
    // FAIL CLOSED. No verified live price, no real-money BET. This is a
    // distinct rejection from the kill-price one below on purpose: "we could
    // not check" and "we checked and it is too expensive" are different
    // failures, and a post-mortem that cannot tell them apart will read an
    // outage as a run of discipline.
    if (!ctx.livePrice.ok) {
      return reject(
        `PRICE UNAVAILABLE — ${ctx.livePrice.reason}. A real bet needs a price we can check against the market right now; the card's number is from the last build, not from this moment. Log it as paper, or re-try once the line is back.`,
        409,
      );
    }
    // EARLY SEASON IS PAPER ONLY. The model can score a week-1 game, but being
    // able to produce a number is not the same as that regime being validated
    // for money: the blowout blind spot sits in weeks 1-2 (~59% of features
    // NaN) and the backtest behind the gap rule is weeks 3+. Its own rejection,
    // distinct from the kill-line and price ones, so a post-mortem can tell
    // "we never bet this regime" apart from "the price moved".
    if (
      ctx.minGamesPlayed !== null &&
      ctx.minGamesPlayed < MIN_GAMES_FOR_REAL_MONEY
    ) {
      return reject(
        `EARLY SEASON — a team here has played ${ctx.minGamesPlayed} game${ctx.minGamesPlayed === 1 ? "" : "s"} this season, and real money needs ${MIN_GAMES_FOR_REAL_MONEY}. The model scores it, but that regime has never been validated for money. Log it as paper; it still counts toward the record.`,
        409,
      );
    }
    if (ctx.killLine !== null && pick.line < ctx.killLine) {
      return reject(
        `u${fmt(pick.line)} is below the kill line. We rated this at u${fmt(ctx.killLine)} or higher — at a lower total it is a different bet. Pass on it.`,
        409,
      );
    }
    // American odds: the larger signed value pays better (-105 beats -120).
    //
    // The LIVE kill price wins over the card's whenever it exists. Both are
    // breakEvenPrice(marketFairUnder) at the same bar; they differ only because
    // the market moved since the build, and the number the bettor is being
    // offered right now is the one that decides whether this is still the bet
    // the card rated.
    const killPrice = ctx.livePrice.killPrice ?? ctx.killPrice;
    if (killPrice !== null && pick.price < killPrice) {
      return reject(
        `${american(pick.price)} is worse than the kill price. We rated this at ${american(killPrice)} or better — at a worse price it is a different bet. Pass on it.`,
        409,
      );
    }
  }
  // Real money on a WATCH/PASS verdict is allowed but OFF-POLICY: the record
  // must capture every bet actually placed, and Results flags these so the
  // owner can see how overrides do (lib/picks.ts isOffPolicy). The cap and
  // the flat unit still apply.
  if (
    !pick.isPaper &&
    pick.market === "1H" &&
    ctx.realWeekCount >= WEEKLY_BET_CAP
  ) {
    return reject(
      `${WEEKLY_BET_CAP} real-money bets are already logged for week ${ctx.week ?? "?"}. That is the ceiling. Log this one as paper if you want to track it.`,
      409,
    );
  }
  return { ok: true };
}

// --- editing a logged pick ---------------------------------------------------

/** The most a stake may be edited to, in units. A guard against a typo turning
 *  a $20 ticket into a $2,000 one in a ledger meant to measure a $100 roll. */
export const MAX_EDIT_STAKE = 10;

export type PickEdit = {
  price?: number | null;
  stake?: number;
  note?: string | null;
  isBonus?: boolean;
};

export type ParsedEdit = { ok: true; edit: PickEdit };

/**
 * Shape checks for PATCH /api/picks/<id>. No DB.
 *
 * Only price, stake, note and the bonus flag are editable, and only before the
 * pick is graded (the route enforces that). Line, side, market and game are
 * NOT editable: those identify the bet, and letting them change after the fact
 * would turn the ledger into something that cannot be evidence of anything.
 */
export function parsePickEdit(body: unknown): ParsedEdit | Rejection {
  if (!body || typeof body !== "object") {
    return reject("Could not read the request.");
  }
  const b = body as Record<string, unknown>;
  const edit: PickEdit = {};

  if ("price" in b) {
    const p = optNumber(b.price, "price");
    if ("ok" in p && p.ok === false) return p;
    const v = (p as { value: number | null | undefined }).value;
    if (v !== undefined) {
      if (v !== null && (!Number.isInteger(v) || Math.abs(v) < 100)) {
        return reject("Price must be American odds, like -125 or +100.");
      }
      edit.price = v;
    }
  }

  if ("stake" in b) {
    const n = Number(b.stake);
    if (!Number.isFinite(n) || n <= 0) {
      return reject("Stake must be a positive number of units.");
    }
    if (n > MAX_EDIT_STAKE) {
      return reject(`Stake above ${MAX_EDIT_STAKE} units looks like a typo.`);
    }
    edit.stake = n;
  }

  if ("note" in b) {
    if (b.note !== null && typeof b.note !== "string") {
      return reject("Note must be text.");
    }
    edit.note = b.note as string | null;
  }

  if ("isBonus" in b) {
    if (typeof b.isBonus !== "boolean") {
      return reject("isBonus must be true or false.");
    }
    edit.isBonus = b.isBonus;
  }

  if (Object.keys(edit).length === 0) {
    return reject("Nothing to change.");
  }
  return { ok: true, edit };
}
