import { bookLabel } from "@/lib/books";
import { etClock12, etParts } from "@/lib/et";
import { settledOf, type Settled } from "@/lib/grade";
import { getBoard, type BoardRow } from "@/lib/board";
import {
  edgeScore,
  type EdgeContext,
  type EdgeInput,
  type EdgeResult,
  type LineBasis,
} from "@/lib/edge";
import { round2 } from "@/lib/format";
import { getLineCheck, type LineCheckRow } from "@/lib/lineCheck";
import { getMovements, type Movement } from "@/lib/movement";
import {
  getPicks,
  isRealFirstHalf,
  type PickFull,
  type WeekPick,
} from "@/lib/picks";
import { getPreviewByGame, type PreviewGame } from "@/lib/preview";
import type { Record3 } from "@/lib/record";
import type { BoardFactor, Factors } from "@/lib/score";
import { priceSentence, WEEKLY_BET_CAP } from "@/lib/verdict";
import { defaultWeek, weeksOf } from "@/lib/week";

// The home board data layer: one ranked list of every game on the week, each
// with an edge score 0-100, a tier (BET / EDGE / PASS), the line history, the
// injury/news preview and the pick ledger behind it. Replaces lib/thisWeek.ts
// (its bankroll logic lives here now). Reads only.

// --- bankroll ---------------------------------------------------------------

export type Bankroll = {
  startUsd: number;
  unitUsd: number;
  /** Signed units from graded real-money 1H picks this season. */
  realUnits: number;
  currentUsd: number;
  /** Real-money 1H picks logged for the displayed week (pending or graded). */
  weekBets: number;
  cap: number;
  real: Record3 | null;
  paper: Record3 | null;
};

// Bankroll policy (docs/BETTING_POLICY.md): fixed dollar unit, flat staking.
// Env-driven so a top-up is a Vercel setting, not a deploy.
function envNum(name: string, fallback: number): number {
  const v = Number(process.env[name]);
  return Number.isFinite(v) && v > 0 ? v : fallback;
}

/** Starting bankroll + unit size from the environment (BANKROLL_USD/UNIT_USD). */
export function bankrollEnv(): { startUsd: number; unitUsd: number } {
  return {
    startUsd: envNum("BANKROLL_USD", 100),
    unitUsd: envNum("UNIT_USD", 10),
  };
}

export type BankrollPoint = { week: number; units: number; usd: number };

/**
 * Pure: cumulative real-money first-half units by week, oldest first, with a
 * week-0 starting point so the curve begins at the starting bankroll. Only
 * GRADED picks move it — a pending bet has not won or lost anything yet.
 */
export function bankrollCurve(
  picks: PickFull[],
  startUsd: number,
  unitUsd: number,
): BankrollPoint[] {
  const settled = picks.filter(
    (p) => isRealFirstHalf(p) && p.graded && p.week !== null,
  );
  const weeks = [...new Set(settled.map((p) => p.week as number))].sort(
    (a, b) => a - b,
  );
  const out: BankrollPoint[] = [
    { week: weeks.length > 0 ? weeks[0] - 1 : 0, units: 0, usd: startUsd },
  ];
  let cum = 0;
  for (const w of weeks) {
    for (const p of settled.filter((p) => p.week === w)) cum += p.units ?? 0;
    out.push({
      week: w,
      units: round2(cum),
      usd: Math.round((startUsd + cum * unitUsd) * 100) / 100,
    });
  }
  return out;
}

// --- kickoff ----------------------------------------------------------------

function asDate(d: Date | string | null): Date | null {
  if (d === null) return null;
  const t = new Date(d);
  return Number.isNaN(t.getTime()) ? null : t;
}

/** "Sat 7:30p" in ET; null when the kickoff time is unknown. */
export function kickoffET(d: Date | string | null): string | null {
  const t = asDate(d);
  if (t === null) return null;
  return etClock12(t, ["a", "p"]);
}

export const DAYS = ["thu", "fri", "sat", "sun"] as const;
export type DayKey = (typeof DAYS)[number] | "other";
export const DAY_LABEL: Record<(typeof DAYS)[number], string> = {
  thu: "Thu",
  fri: "Fri",
  sat: "Sat",
  sun: "Sun",
};

/** Lower-case ET day key for the day filter; null when the kickoff is unknown. */
export function dayKey(d: Date | string | null): DayKey | null {
  const t = asDate(d);
  if (t === null) return null;
  const wd = etParts(t).weekday.toLowerCase();
  return (DAYS as readonly string[]).includes(wd) ? (wd as DayKey) : "other";
}

// --- filters ----------------------------------------------------------------

/** The four programs Tate follows (exact team names as CFBD writes them). */
export const MY_TEAMS = [
  "Kansas State",
  "Kansas",
  "Missouri",
  "Florida",
] as const;

export type BoardFilters = {
  /** Empty = every day. */
  days: string[];
  myTeams: boolean;
  /** Only games Hard Rock has posted a first-half line for. */
  hrOnly: boolean;
};

export const NO_FILTERS: BoardFilters = {
  days: [],
  myTeams: false,
  hrOnly: false,
};

/** Pure: does this game survive the board filters? */
export function matchesFilters(g: HomeGame, f: BoardFilters): boolean {
  if (f.days.length > 0 && (g.day === null || !f.days.includes(g.day))) {
    return false;
  }
  if (
    f.myTeams &&
    !(MY_TEAMS as readonly string[]).includes(g.row.away) &&
    !(MY_TEAMS as readonly string[]).includes(g.row.home)
  ) {
    return false;
  }
  if (f.hrOnly && g.check?.hrLine == null) return false;
  return true;
}

/** Read the board filters out of a URL search-param bag. */
export function parseFilters(sp: {
  days?: string;
  mine?: string;
  hr?: string;
}): BoardFilters {
  const days = (sp.days ?? "")
    .split(",")
    .map((d) => d.trim().toLowerCase())
    .filter((d) => (DAYS as readonly string[]).includes(d));
  return {
    days: [...new Set(days)],
    myTeams: sp.mine === "1",
    hrOnly: sp.hr === "1",
  };
}

// --- context + explainers ---------------------------------------------------

/** Pull the no-model context leans out of a game's factors_json. Every key is
 *  optional (the context job may not have run) — absent reads as null. */
export function edgeContext(f: Factors): EdgeContext {
  const n = (v: number | null | undefined): number | null =>
    v === null || v === undefined || !Number.isFinite(Number(v))
      ? null
      : Number(v);
  const dome =
    f.dome === true || f.dome === false
      ? f.dome
      : f.wx_dome === null || f.wx_dome === undefined
        ? null
        : Number(f.wx_dome) === 1;
  const homePf = n(f.home_fh_pf ?? f.fh_home_pf);
  const awayPf = n(f.away_fh_pf ?? f.fh_away_pf);
  return {
    combinedSecPlay: n(f.combined_sec_play),
    windMph: n(f.wx_wind),
    dome,
    spread: n(f.spread),
    fhPrior:
      homePf !== null && awayPf !== null ? round2(homePf + awayPf) : null,
  };
}

/** The one factor arguing hardest AGAINST the under, as a sentence. Null when
 *  the board has no red factor (or no board at all). */
export function strongestRed(
  board: BoardFactor[] | null | undefined,
): string | null {
  const reds = (board ?? []).filter(
    (f) => f.color === "red" && !f.hypothesis && f.sentence,
  );
  if (reds.length === 0) return null;
  reds.sort((a, b) => Math.abs(b.lean) - Math.abs(a.lean));
  return reds[0].sentence.trim();
}

/**
 * Pure. Whether a row has a model number: a score and our number, whatever
 * line it was scored against. The ONE meaning of "has a model" on the site
 * (edge.ts / verdict.ts / card.py agree) — which line the gap is measured
 * against is a separate question (`GapBasis`), decided from the live lines at
 * request time.
 */
export function lineState(row: Pick<BoardRow, "underScore" | "bvLine">): {
  hasModel: boolean;
} {
  return { hasModel: row.underScore !== null && row.bvLine !== null };
}

export type GapBasis = LineBasis;

/**
 * Pure. How the first-half under settled, graded ONLY against a real book line
 * (Hard Rock's, else the market's). A game whose only line was our reference
 * number has nothing to grade: null, so the card stays neutral once played.
 */
export function settledAgainst(
  basis: GapBasis | null,
  actualFirstHalf: number | null,
  line: number | null,
): Settled | null {
  if (basis !== "hardrock" && basis !== "market") return null;
  return settledOf(actualFirstHalf, line);
}

/** Early season: a team on this row has fewer than 2 prior games this season. */
export function earlySeasonFrom(f: Factors): boolean {
  const gp = [f.h_games_played, f.a_games_played];
  return gp.some((v) => typeof v === "number" && Number.isFinite(v) && v < 2);
}

/** The non-Hard-Rock, non-exchange books behind the market line, best first (max 2). */
export function basisBooksFrom(check: LineCheckRow | null): string[] {
  if (check === null) return [];
  return check.books
    .filter((b) => !b.isHR && !b.isExchange)
    .slice(0, 2)
    .map((b) => bookLabel(b.book));
}

export type DayGroup = { day: DayKey | null; label: string; games: HomeGame[] };

/**
 * Pure: the rolling week grouped by ET day in schedule order (Thu, Fri, Sat,
 * Sun, then unknown), each group sorted like the board so kicked-off games
 * sink within their own day. Empty days are omitted.
 */
export function groupByDay(games: HomeGame[]): DayGroup[] {
  const order: (DayKey | null)[] = [...DAYS, "other", null];
  return order
    .map((day) => ({
      day,
      label:
        day === null || day === "other"
          ? "Other days"
          : DAY_LABEL[day as (typeof DAYS)[number]],
      games: sortGames(games.filter((g) => g.day === day)),
    }))
    .filter((grp) => grp.games.length > 0);
}

export const GAP_BASIS_LABEL: Record<GapBasis, string> = {
  hardrock: "vs Hard Rock",
  market: "vs the market",
  reference: "vs our reference line",
};

// --- the board --------------------------------------------------------------

export type HomeGame = {
  row: BoardRow;
  check: LineCheckRow | null;
  edge: EdgeResult;
  movement: Movement | null;
  /** Injuries + news for the game (unofficial), when the preview job has run. */
  preview: PreviewGame | null;
  /** A real-money 1H pick already logged on this game this season. */
  picked: boolean;
  /** Kickoff has passed (no more bets). */
  kickedOff: boolean;
  /** "Sat 7:30p" ET, or null when the kickoff time is unknown. */
  kickoff: string | null;
  day: DayKey | null;
  /** Our gap and the line it is measured against. Both null on no-model rows
   *  (no gap without our number), even when a book or reference line exists. */
  gap: number | null;
  gapBasis: GapBasis | null;
  /** Books behind the market line when that is the basis (max 2), for the basis phrase. */
  basisBooks: string[];
  /** A team on this row has played fewer than 2 games this season. */
  earlySeason: boolean;
  /** How the first-half under settled at a REAL book line (Hard Rock, else the
   *  market); null until played, and null when no book ever posted one. Needs
   *  no model: a played game grades the under at the book line it had. */
  settled: Settled | null;
  /** The line `settled` was graded against; null whenever `settled` is null. */
  settledLine: number | null;
  /** One sentence on Hard Rock's price vs the market's no-vig fair price. */
  priceLine: string;
  /** Rank among the week's BETs by gap (1 = biggest gap); null on non-BETs. */
  capRank: number | null;
  /** BET beyond the weekly cap: every gate passed, paper only (docs/BETTING_POLICY.md). */
  overCap: boolean;
};

export type HomeBoard = {
  season: number;
  week: number | null;
  /** Weeks that have games on the board (for the week selector). */
  weeks: number[];
  /** No row carries a model number — the week has not been scored yet. */
  noModel: boolean;
  /** No book has posted a first-half line for any game on the week. */
  noHrLine: boolean;
  games: HomeGame[];
  counts: { bet: number; edge: number; pass: number };
  bankroll: Bankroll;
  /** Real-money 1H picks logged on this week (the bet slip's "logged" state). */
  weekPicks: WeekPick[];
};

/** Pure: upcoming before kicked-off, then score desc, earliest kickoff, away team. */
export function sortGames(games: HomeGame[]): HomeGame[] {
  const ms = (g: HomeGame): number => {
    const t = asDate(g.row.startDate);
    return t === null ? Number.POSITIVE_INFINITY : t.getTime();
  };
  // Games that have kicked off are no longer actionable: they sink below every
  // upcoming game regardless of score.
  return [...games].sort(
    (a, b) =>
      Number(a.kickedOff) - Number(b.kickedOff) ||
      b.edge.score - a.edge.score ||
      ms(a) - ms(b) ||
      a.row.away.localeCompare(b.row.away),
  );
}

/**
 * Pure: rank this week's BETs for the real-money cap, by gap (the cap-5 rule
 * the real-close backtest measured — beatvegas/card.py apply_weekly_cap).
 * Games already bet (`held`) keep their slot ahead of new arrivals; the rest
 * follow by gap desc, then Hard Rock's price, then kickoff. Rank > cap marks
 * overCap: every gate passed, paper only. Non-BETs get capRank null.
 */
export function assignCapRanks(
  games: HomeGame[],
  held: Set<number>,
  cap: number = WEEKLY_BET_CAP,
): HomeGame[] {
  const bets = games.filter((g) => g.edge.tier === "BET" && !g.kickedOff);
  const ms = (g: HomeGame): number => {
    const t = asDate(g.row.startDate);
    return t === null ? Number.POSITIVE_INFINITY : t.getTime();
  };
  const ranked = [...bets].sort(
    (a, b) =>
      Number(!held.has(a.row.gameId)) - Number(!held.has(b.row.gameId)) ||
      (b.gap ?? Number.NEGATIVE_INFINITY) -
        (a.gap ?? Number.NEGATIVE_INFINITY) ||
      (b.check?.ev ?? Number.NEGATIVE_INFINITY) -
        (a.check?.ev ?? Number.NEGATIVE_INFINITY) ||
      ms(a) - ms(b) ||
      a.row.away.localeCompare(b.row.away),
  );
  const rank = new Map(ranked.map((g, i) => [g.row.gameId, i + 1]));
  return games.map((g) => {
    const r = rank.get(g.row.gameId) ?? null;
    return { ...g, capRank: r, overCap: r !== null && r > cap };
  });
}

/** Pure: how many games sit in each tier. */
export function tierCounts(games: HomeGame[]): {
  bet: number;
  edge: number;
  pass: number;
} {
  return {
    bet: games.filter((g) => g.edge.tier === "BET").length,
    edge: games.filter((g) => g.edge.tier === "EDGE").length,
    pass: games.filter((g) => g.edge.tier === "PASS").length,
  };
}

export async function getHomeBoard(
  season: number,
  requestedWeek?: number,
  now: Date = new Date(),
): Promise<HomeBoard> {
  const [board, checks, { picks, record, paperRecord }] = await Promise.all([
    getBoard(season),
    getLineCheck(season, "1h"),
    getPicks(season),
  ]);

  // Default to the week you are about to bet (earliest week with a game still
  // to kick off — lib/week.ts); ?week= lets Tate review a past one.
  const weeks = weeksOf(board);
  const week =
    requestedWeek !== undefined && weeks.includes(requestedWeek)
      ? requestedWeek
      : defaultWeek(board, now);
  const rows = board.filter((b) => b.week === week);
  const [previews, movements] = await Promise.all([
    week === null
      ? Promise.resolve(new Map<number, PreviewGame>())
      : getPreviewByGame(season, week),
    getMovements(rows.map((r) => r.gameId)),
  ]);
  const checkById = new Map(checks.map((c) => [c.gameId, c]));
  const noModel = rows.length > 0 && rows.every((r) => !lineState(r).hasModel);

  // Only real-money FIRST-HALF picks count toward the record, the bankroll and
  // the weekly cap (full game is context, paper is tracked apart).
  const real1H = picks.filter(isRealFirstHalf);
  const pickedGames = new Set(real1H.map((p) => p.gameId));
  const pickedKey = new Set(real1H.map((p) => `${p.away}@${p.home}`));

  const games: HomeGame[] = rows.map((row) => {
    const check = checkById.get(row.gameId) ?? null;
    const fallbackLine = row.factors.line ?? null;
    const state = lineState(row);
    const input: EdgeInput = {
      away: row.away,
      home: row.home,
      underScore: row.underScore,
      bvLine: row.bvLine,
      liveLine: row.curLine,
      fallbackLine,
      gap: row.liveGap,
      hrLine: check?.hrLine ?? null,
      hrUnderPrice: check?.hrUnderPrice ?? null,
      ev: check?.ev ?? null,
      evVerdict: check?.evVerdict ?? "na",
      fhShare: row.factors.fh_share ?? null,
      qbOut: Boolean(row.factors.qb_out_home || row.factors.qb_out_away),
      qbOutDetail: row.factors.qb_out_detail ?? null,
      bvAdjust: row.bvAdjust,
      bvAdjustReason: row.bvAdjustReason,
      factorBoard: row.factors.factor_board,
      marketLine: row.curLine,
      bestLine: check?.best ?? null,
      marketFairUnder: check?.marketFairUnder ?? null,
      context: edgeContext(row.factors),
    };
    const edge = edgeScore(input);
    // Same basis edge.ts scores on: the number you can bet, else the market,
    // else the reference line baked in at scoring time.
    const basisLine = check?.hrLine ?? row.curLine ?? fallbackLine;
    const gapBasis: GapBasis | null =
      check?.hrLine != null
        ? "hardrock"
        : row.curLine !== null
          ? "market"
          : fallbackLine !== null
            ? "reference"
            : null;
    const hasModel = state.hasModel;
    const start = asDate(row.startDate);
    const settled = settledAgainst(gapBasis, row.firstHalfTotal, basisLine);
    return {
      row,
      check,
      edge,
      movement: movements.get(row.gameId) ?? null,
      preview: previews.get(row.gameId) ?? null,
      picked:
        pickedGames.has(row.gameId) || pickedKey.has(`${row.away}@${row.home}`),
      kickedOff: start !== null && start.getTime() <= now.getTime(),
      kickoff: kickoffET(row.startDate),
      day: dayKey(row.startDate),
      gap:
        hasModel && basisLine !== null && row.bvLine !== null
          ? round2(basisLine - row.bvLine)
          : null,
      gapBasis: hasModel ? gapBasis : null,
      basisBooks: basisBooksFrom(check),
      earlySeason: earlySeasonFrom(row.factors),
      settled,
      settledLine: settled === null ? null : basisLine,
      priceLine: priceSentence(input),
      capRank: null,
      overCap: false,
    };
  });

  const heldIds = new Set(
    [...pickedGames].filter((g): g is number => g !== null),
  );
  const sorted = assignCapRanks(sortGames(games), heldIds, WEEKLY_BET_CAP);
  const weekPicks: WeekPick[] = real1H
    .filter((p) => p.week === week)
    .map((p) => ({
      gameId: p.gameId,
      away: p.away,
      home: p.home,
      line: p.line,
      price: p.price,
    }));
  const { startUsd, unitUsd } = bankrollEnv();
  const realUnits = round2(
    real1H.filter((p) => p.graded).reduce((a, p) => a + (p.units ?? 0), 0),
  );

  return {
    season,
    week,
    weeks,
    noModel,
    noHrLine: rows.length > 0 && sorted.every((g) => g.check?.hrLine == null),
    games: sorted,
    counts: tierCounts(sorted),
    bankroll: {
      startUsd,
      unitUsd,
      realUnits,
      currentUsd: Math.round((startUsd + realUnits * unitUsd) * 100) / 100,
      weekBets: real1H.filter((p) => p.week === week).length,
      cap: WEEKLY_BET_CAP,
      real: record,
      paper: paperRecord,
    },
    weekPicks,
  };
}
