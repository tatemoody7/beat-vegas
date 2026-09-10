import { american, fmt } from "@/lib/format";
import {
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
  /** The card's kill numbers for this game (lib/card.ts CardItem); null = no card item. */
  killLine: number | null;
  killPrice: number | null;
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
  // A real BET below the card's kill line, or at a worse price, is not the
  // bet the card rated: the edge is gone. Paper and WATCH/PASS (an owner
  // override, already off-policy) are exempt.
  if (!pick.isPaper && pick.market === "1H" && pick.verdict === "BET") {
    if (ctx.killLine !== null && pick.line < ctx.killLine) {
      return reject(
        `u${fmt(pick.line)} is below the kill line. We rated this at u${fmt(ctx.killLine)} or higher — at a lower total it is a different bet. Pass on it.`,
        409,
      );
    }
    // American odds: the larger signed value pays better (-105 beats -120).
    if (ctx.killPrice !== null && pick.price < ctx.killPrice) {
      return reject(
        `${american(pick.price)} is worse than the kill price. We rated this at ${american(ctx.killPrice)} or better — at a worse price it is a different bet. Pass on it.`,
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
