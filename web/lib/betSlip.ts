import { slipBlockText, type SlipBlockContext } from "@/lib/labels";
import {
  killLabel,
  lineLabel,
  type Card,
  type CardStatus,
  type FairSource,
} from "@/lib/card";
import { american } from "@/lib/format";
import { kickoffET } from "@/lib/homeBoard";
import type { WeekPick } from "@/lib/picks";
import type { PickReason } from "@/lib/verdict";

// The Saturday-morning bet slip (decided 2026-09-07): the week's BETs from the
// latest card, ranked by gap, each with Hard Rock's line + price and the kill
// numbers, and ONE tap to log the real ticket at the shown number. Pure here;
// app/components/BetSlip.tsx draws it and posts to /api/picks.
//
// 2026-09: each row also carries the LIVE Hard Rock number the same board
// render loaded (lib/lineCheck.ts), flags a move off the card's number, and
// says what blocks the bet (a degraded input, the kill line, the kill price,
// the weekly cap) so the tap can be disabled before the server says no.

export const HARD_ROCK_URL = "https://app.hardrock.bet"; // TODO Tate verifies on-device before 9/19
/** A live line this far from the card's number is a "moved" line. */
export const MOVED_PTS = 0.5;

export type SlipStatus =
  /** Bettable: inside the cap, not yet logged, not kicked off. */
  | "open"
  /** A real-money 1H pick is logged on this game (line/price below). */
  | "logged"
  /** BET beyond the weekly cap: every gate passed, paper only. */
  | "over_cap"
  | "kicked_off";

export type SlipBlock = "degraded" | "kill_line" | "kill_price" | "cap";

export type LiveLine = { hrLine: number | null; hrPrice: number | null };

export type BetSlipRow = {
  gameId: number;
  capRank: number | null;
  matchup: string;
  away: string;
  home: string;
  /** "Sat 7:30p" ET or null. */
  kick: string | null;
  kickIso: string | null;
  /** "kicks in 3h 10m" / "kicks in 25m" / "kicked off"; null without a kickoff. */
  kicksIn: string | null;
  /** Whole minutes to kickoff (0 once kicked off); null without a kickoff. */
  kickMinutes: number | null;
  /** The card's Hard Rock number at build time. */
  hrLine: number | null;
  hrPrice: number | null;
  /** Hard Rock's number on the board right now (falls back to the card's). */
  liveLine: number | null;
  livePrice: number | null;
  /** The live line sits MOVED_PTS+ from the card's (both known). */
  moved: boolean;
  /** "u24.5 -110" (the card's number) */
  line: string;
  /** "below u24.5 or worse than -120", "" when unknown. */
  kill: string;
  killLine: number | null;
  killPrice: number | null;
  gap: number | null;
  ev: number | null;
  bvLine: number | null;
  fairUnder: number | null;
  /** Card's Hard Rock 1H line minus the market's; null when unknown. */
  hrVsMarket: number | null;
  fairSource: FairSource | null;
  /** The reason a tap logs (the card's, else model_gap). */
  reason: PickReason;
  status: SlipStatus;
  /** What stops a real bet at the live number right now; null = nothing. */
  blockedBy: SlipBlock | null;
  loggedLine: number | null;
  loggedPrice: number | null;
};

export type BetSlip = {
  rows: BetSlipRow[];
  /** Real-money 1H picks already logged this week. */
  used: number;
  cap: number;
  builtAt: string | null;
  /** The card's build status; null without a card. */
  cardStatus: CardStatus | null;
};

const pickKey = (away: string | null, home: string | null) => `${away}@${home}`;

/**
 * The "logged" chip text: "logged u24.5 -115"; "logged u24.5" when the pick
 * was logged before Hard Rock priced it (price NULL); "logged" with no line.
 */
export function loggedLabel(line: number | null, price: number | null): string {
  if (line === null) return "logged";
  return `logged u${line}${price !== null ? ` ${american(price)}` : ""}`;
}

/**
 * Hard Rock's live 1H line + under price per game id, from the board rows the
 * same render loaded (HomeGame.check is lib/lineCheck.ts's row). Games with
 * no line check are left out; a present check with no Hard Rock line maps to
 * nulls so the slip falls back to the card's number.
 */
export function liveLinesFrom(
  games: readonly {
    row: { gameId: number };
    check: { hrLine: number | null; hrUnderPrice: number | null } | null;
  }[],
): Map<number, LiveLine> {
  const m = new Map<number, LiveLine>();
  for (const g of games) {
    if (g.check === null) continue;
    m.set(g.row.gameId, {
      hrLine: g.check.hrLine,
      hrPrice: g.check.hrUnderPrice,
    });
  }
  return m;
}

/**
 * Does this line/price fall outside the card's kill numbers? The line is
 * checked first (a lower total is a different bet), then the price (American
 * odds: the larger signed value pays better, so -125 is worse than -120). A
 * missing side cannot block.
 */
export function killBlocks(
  line: number | null,
  price: number | null,
  killLine: number | null,
  killPrice: number | null,
): "kill_line" | "kill_price" | null {
  if (line !== null && killLine !== null && line < killLine) return "kill_line";
  if (price !== null && killPrice !== null && price < killPrice) {
    return "kill_price";
  }
  return null;
}

/**
 * The disabled-reason text for a slip block, in plain English (lib/labels.ts
 * slipBlockText). `live` is true when the block came from Hard Rock's live
 * number (row.blockedBy), false when it came from the line/price the user
 * typed in; `ctx` carries the numbers so the sentence can name them.
 */
export function blockReason(
  block: SlipBlock,
  live: boolean,
  ctx: SlipBlockContext = {},
): string {
  return slipBlockText(block, live, ctx);
}

export type EffectiveBlock = { block: SlipBlock | null; isLive: boolean };

/**
 * What actually stops the tap right now, given what's entered in the two
 * inputs. `degraded`/`cap` are hard blocks off the card/cap and hold no
 * matter what's typed in. A kill block is instead RE-EVALUATED against the
 * entered line/price — never trusted from row.blockedBy, which was computed
 * against Hard Rock's live snapshot at render time and can go stale the
 * moment the user edits a field. This mirrors the server's own check
 * (lib/pickRules.ts checkPolicy), which judges the SUBMITTED line/price, so
 * the slip is never stricter than the rule it fronts: raise the entered line
 * to the kill line (or better the price) and the block clears. `isLive` is
 * true only when the block still applies to what's currently on the live
 * board, so the UI can say "Hard Rock's live …" instead of a generic warning.
 */
export function effectiveBlock(
  row: Pick<
    BetSlipRow,
    "blockedBy" | "killLine" | "killPrice" | "liveLine" | "livePrice"
  >,
  line: number | null,
  price: number | null,
): EffectiveBlock {
  const hard =
    row.blockedBy === "degraded" || row.blockedBy === "cap"
      ? row.blockedBy
      : null;
  const block = hard ?? killBlocks(line, price, row.killLine, row.killPrice);
  const isLive =
    block !== null && line === row.liveLine && price === row.livePrice;
  return { block, isLive };
}

/** Whole minutes from now to kickoff (0 once kicked off); null without a usable kickoff. */
function minutesToKick(kickIso: string | null, now: Date): number | null {
  if (kickIso === null) return null;
  const t = new Date(kickIso).getTime();
  if (Number.isNaN(t)) return null;
  return Math.max(0, Math.floor((t - now.getTime()) / 60_000));
}

/** "kicks in 3h 10m" / "kicks in 3h" / "kicks in 25m" / "kicked off"; null without a kickoff. */
export function timeToKick(kickIso: string | null, now: Date): string | null {
  const mins = minutesToKick(kickIso, now);
  if (mins === null) return null;
  if (mins <= 0) return "kicked off";
  if (mins < 60) return `kicks in ${mins}m`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m === 0 ? `kicks in ${h}h` : `kicks in ${h}h ${m}m`;
}

/** Pure: the slip from the latest card, this week's real 1H picks, and the board's live lines. */
/**
 * Cap slots used this week. A bonus bet is logged and deduped like any other
 * pick, but risks none of the bankroll, so it does not spend a slot — the
 * same rule POST /api/picks enforces.
 */
const capUsedBy = (weekPicks: WeekPick[]): number =>
  weekPicks.filter((p) => !p.isBonus).length;

export function buildBetSlip(
  card: Card | null,
  weekPicks: WeekPick[],
  cap: number,
  now: Date = new Date(),
  live: Map<number, LiveLine> = new Map(),
): BetSlip {
  if (card === null) {
    return {
      rows: [],
      used: capUsedBy(weekPicks),
      cap,
      builtAt: null,
      cardStatus: null,
    };
  }
  const byGame = new Map<number, WeekPick>();
  const byKey = new Map<string, WeekPick>();
  for (const p of weekPicks) {
    if (p.gameId !== null && !byGame.has(p.gameId)) byGame.set(p.gameId, p);
    const k = pickKey(p.away, p.home);
    if (!byKey.has(k)) byKey.set(k, p);
  }
  const used = capUsedBy(weekPicks);
  const rows = card.items
    .filter((i) => i.tier === "BET")
    .sort(
      (a, b) =>
        (a.capRank ?? Number.POSITIVE_INFINITY) -
          (b.capRank ?? Number.POSITIVE_INFINITY) ||
        (b.gap ?? Number.NEGATIVE_INFINITY) -
          (a.gap ?? Number.NEGATIVE_INFINITY),
    )
    .map((i): BetSlipRow => {
      const logged =
        byGame.get(i.gameId) ?? byKey.get(pickKey(i.away, i.home)) ?? null;
      const kickMinutes = minutesToKick(i.kick, now);
      const kicked = kickMinutes !== null && kickMinutes <= 0;
      const status: SlipStatus =
        logged !== null
          ? "logged"
          : kicked
            ? "kicked_off"
            : i.overCap
              ? "over_cap"
              : "open";
      const l = live.get(i.gameId);
      const liveLine = l?.hrLine ?? i.hrLine;
      const livePrice = l?.hrPrice ?? i.hrPrice;
      const moved =
        l?.hrLine != null &&
        i.hrLine !== null &&
        Math.abs(l.hrLine - i.hrLine) >= MOVED_PTS;
      const degraded = i.blocker === "degraded" || i.degradedInputs.length > 0;
      const blockedBy: SlipBlock | null = degraded
        ? "degraded"
        : (killBlocks(liveLine, livePrice, i.killLine, i.killPrice) ??
          (status === "open" && used >= cap ? "cap" : null));
      return {
        gameId: i.gameId,
        capRank: i.capRank,
        matchup: `${i.away} @ ${i.home}`,
        away: i.away,
        home: i.home,
        kick: kickoffET(i.kick),
        kickIso: i.kick,
        kicksIn: timeToKick(i.kick, now),
        kickMinutes,
        hrLine: i.hrLine,
        hrPrice: i.hrPrice,
        liveLine,
        livePrice,
        moved,
        line: lineLabel(i),
        kill: killLabel(i),
        killLine: i.killLine,
        killPrice: i.killPrice,
        gap: i.gap,
        ev: i.ev,
        bvLine: i.bvLine,
        fairUnder: i.fairUnder,
        hrVsMarket: i.hrVsMarket,
        fairSource: i.fairSource,
        reason: i.reason ?? "model_gap",
        status,
        blockedBy,
        loggedLine: logged?.line ?? null,
        loggedPrice: logged?.price ?? null,
      };
    });
  return { rows, used, cap, builtAt: card.builtAt, cardStatus: card.status };
}
