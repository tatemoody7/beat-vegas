import { killLabel, lineLabel, type Card } from "@/lib/card";
import { american } from "@/lib/format";
import { kickoffET } from "@/lib/homeBoard";
import type { WeekPick } from "@/lib/picks";

// The Saturday-morning bet slip (decided 2026-09-07): the week's BETs from the
// latest card, ranked by gap, each with Hard Rock's line + price and the kill
// numbers, and ONE tap to log the real ticket at the shown number. Pure here;
// app/components/BetSlip.tsx draws it and posts to /api/picks.

export type SlipStatus =
  /** Bettable: inside the cap, not yet logged, not kicked off. */
  | "open"
  /** A real-money 1H pick is logged on this game (line/price below). */
  | "logged"
  /** BET beyond the weekly cap: every gate passed, paper only. */
  | "over_cap"
  | "kicked_off";

export type BetSlipRow = {
  gameId: number;
  capRank: number | null;
  matchup: string;
  away: string;
  home: string;
  /** "Sat 7:30p" ET or null. */
  kick: string | null;
  kickIso: string | null;
  hrLine: number | null;
  hrPrice: number | null;
  /** "u24.5 -110" */
  line: string;
  /** "below u24.5 or worse than -120", "" when unknown. */
  kill: string;
  killLine: number | null;
  killPrice: number | null;
  gap: number | null;
  ev: number | null;
  bvLine: number | null;
  fairUnder: number | null;
  status: SlipStatus;
  loggedLine: number | null;
  loggedPrice: number | null;
};

export type BetSlip = {
  rows: BetSlipRow[];
  /** Real-money 1H picks already logged this week. */
  used: number;
  cap: number;
  builtAt: string | null;
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

/** Pure: the slip from the latest card and this week's real 1H picks. */
export function buildBetSlip(
  card: Card | null,
  weekPicks: WeekPick[],
  cap: number,
  now: Date = new Date(),
): BetSlip {
  if (card === null)
    return { rows: [], used: weekPicks.length, cap, builtAt: null };
  const byGame = new Map<number, WeekPick>();
  const byKey = new Map<string, WeekPick>();
  for (const p of weekPicks) {
    if (p.gameId !== null && !byGame.has(p.gameId)) byGame.set(p.gameId, p);
    const k = pickKey(p.away, p.home);
    if (!byKey.has(k)) byKey.set(k, p);
  }
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
      const kicked =
        i.kick !== null && new Date(i.kick).getTime() <= now.getTime();
      const status: SlipStatus =
        logged !== null
          ? "logged"
          : kicked
            ? "kicked_off"
            : i.overCap
              ? "over_cap"
              : "open";
      return {
        gameId: i.gameId,
        capRank: i.capRank,
        matchup: `${i.away} @ ${i.home}`,
        away: i.away,
        home: i.home,
        kick: kickoffET(i.kick),
        kickIso: i.kick,
        hrLine: i.hrLine,
        hrPrice: i.hrPrice,
        line: lineLabel(i),
        kill: killLabel(i),
        killLine: i.killLine,
        killPrice: i.killPrice,
        gap: i.gap,
        ev: i.ev,
        bvLine: i.bvLine,
        fairUnder: i.fairUnder,
        status,
        loggedLine: logged?.line ?? null,
        loggedPrice: logged?.price ?? null,
      };
    });
  return { rows, used: weekPicks.length, cap, builtAt: card.builtAt };
}
