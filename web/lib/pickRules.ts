import { WEEKLY_BET_CAP, type PickReason, type Verdict } from "@/lib/verdict";

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

const REASONS: readonly PickReason[] = ["model_gap", "price_edge", "manual"];
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
  if (!body || typeof body !== "object") return reject("invalid JSON body");
  const b = body as Record<string, unknown>;

  const gameId = Number(b.gameId);
  // Number(null) is 0 and would pass isFinite — reject missing values first.
  if (b.gameId == null || !Number.isFinite(gameId)) {
    return reject("gameId required");
  }
  const line = Number(b.line);
  if (b.line == null || !Number.isFinite(line) || line <= 0) {
    return reject("line required (positive number)");
  }
  const market: "1H" | "full" = b.market === "full" ? "full" : "1H";
  const isPaper = b.isPaper === true;

  // Real money is first-half only. Full game is context — paper is fine.
  if (market === "full" && !isPaper) {
    return reject(
      "Full-game picks are context only — real money is first-half unders. Log it as a paper pick instead.",
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
      return reject("price must be integer American odds (e.g. -110)");
    }
  }

  const note =
    typeof b.note === "string" && b.note.trim() ? b.note.trim() : undefined;

  let verdict: Verdict | undefined;
  if (b.verdict !== undefined && b.verdict !== null) {
    if (!VERDICTS.includes(b.verdict as Verdict)) {
      return reject("verdict must be BET, WATCH or PASS");
    }
    verdict = b.verdict as Verdict;
  }
  let reason: PickReason | undefined;
  if (b.reason !== undefined && b.reason !== null) {
    if (!REASONS.includes(b.reason as PickReason)) {
      return reject("reason must be model_gap, price_edge or manual");
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
};

/** Betting-policy checks that need DB facts (passed in). */
export function checkPolicy(
  pick: PickRequest,
  ctx: PolicyContext,
): { ok: true } | Rejection {
  if (!ctx.inSlate) return reject("game is not in the current scored slate");
  if (ctx.kickedOff) return reject("game has already kicked off", 409);
  if (ctx.duplicate) {
    return reject(`a ${pick.market} pick already exists on this game`, 409);
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
      `Weekly cap reached: ${WEEKLY_BET_CAP} real-money first-half bets are already logged for week ${ctx.week ?? "?"}. The cap is a ceiling — log this one as paper if you want to track it.`,
      409,
    );
  }
  return { ok: true };
}
