import { bookLabel } from "@/lib/books";
import { prisma } from "@/lib/prisma";
import { etClock12, etParts } from "@/lib/et";
import { settledOf, type Settled } from "@/lib/grade";
import { boardUniverse, getBoard, type BoardRow } from "@/lib/board";
import { cache } from "react";
import {
  edgeScore,
  type EdgeContext,
  type EdgeInput,
  type EdgeResult,
  type LineBasis,
} from "@/lib/edge";
import { round2 } from "@/lib/format";
import { MIN_GAMES_FOR_REAL_MONEY } from "@/lib/verdict";
import { getLineCheck, type LineCheckRow } from "@/lib/lineCheck";
import { getScheduledCard, isHeld, type CardItem } from "@/lib/card";
import { getMovements, type Movement } from "@/lib/movement";
import { getPreviewByGame, type PreviewGame } from "@/lib/preview";
import { hardRockAtLastCard, type HrQuote } from "@/lib/records";
import type { BoardFactor, Factors } from "@/lib/score";
import { BET_GAP_PTS, PCT_SHARE, priceSentence, slateBar } from "@/lib/verdict";
import { defaultWeek, weeksOf } from "@/lib/week";

// The home board data layer: one ranked list of every game on the week, each
// with an edge score 0-100, a tier (BET / EDGE / PASS), the line history and
// the injury/news preview behind it. Reads only. The bankroll, the weekly cap
// ranks and the "bet logged" state left on 2026-10-18 (final-2026 plan, D2):
// the board reads no pick and every BET sentence opens as a paper signal.

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
 * Pure. Whether a row has a model number: our number (bvLine), whatever
 * line it was scored against. The ONE meaning of "has a model" on the site
 * (edge.ts / verdict.ts / card.py agree) — which line the gap is measured
 * against is a separate question (`LineBasis`), decided from the live lines at
 * request time.
 */
export function lineState(row: Pick<BoardRow, "bvLine">): {
  hasModel: boolean;
} {
  return { hasModel: row.bvLine !== null };
}

/**
 * Pure. How the first-half under settled, graded ONLY against a real book line
 * (Hard Rock's, else the market's). A game whose only line was our reference
 * number has nothing to grade: null, so the card stays neutral once played.
 */
export function settledAgainst(
  basis: LineBasis | null,
  actualFirstHalf: number | null,
  line: number | null,
): Settled | null {
  if (basis !== "hardrock" && basis !== "market") return null;
  return settledOf(actualFirstHalf, line);
}

/**
 * Fewest current-season games played by either team, or null when unknown.
 *
 * One definition for the display tag below and the edge gate, so the chip on
 * the board and the rule can never disagree about what "early season" means.
 */
export function minGamesPlayedFrom(f: Factors): number | null {
  const gp = [f.h_games_played, f.a_games_played].filter(
    (v): v is number => typeof v === "number" && Number.isFinite(v),
  );
  return gp.length ? Math.min(...gp) : null;
}

/** Early season: a team on this row has fewer than 2 prior games this season. */
export function earlySeasonFrom(f: Factors): boolean {
  const n = minGamesPlayedFrom(f);
  return n !== null && n < MIN_GAMES_FOR_REAL_MONEY;
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

// --- the board --------------------------------------------------------------

export type HomeGame = {
  row: BoardRow;
  check: LineCheckRow | null;
  edge: EdgeResult;
  /** Board alignment (2026-10-14): a game the card's rule would rate BET but
   *  that is not lit -- "degraded" (a failed input touched it on the scheduled
   *  build: Held, paper only) or "unread" (no scheduled build has read it yet).
   *  null otherwise. */
  hold: "degraded" | "unread" | null;
  movement: Movement | null;
  /** Injuries + news for the game (unofficial), when the preview job has run. */
  preview: PreviewGame | null;
  /** Kickoff has passed: no longer a decision. */
  kickedOff: boolean;
  /** "Sat 7:30p" ET, or null when the kickoff time is unknown. */
  kickoff: string | null;
  day: DayKey | null;
  /** Our gap and the line it is measured against. Both null on no-model rows
   *  (no gap without our number), even when a book or reference line exists. */
  gap: number | null;
  gapBasis: LineBasis | null;
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
  /** Kicked off recently enough that it could still be in progress. */
  inPlay: boolean;
  /** Place on the board this week (1 = best), over every game, before filters.
   *  null once the game has kicked off: it is no longer a decision. */
  boardRank: number | null;
};

export type SlateBar = {
  bar: number;
  n: number;
  share: number;
  basis: "slate" | "fallback";
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
  /** H-PCT: this week's bar, how many games set it, and whether it fell back to the constant. */
  slate: SlateBar;
};

/** Hours after kickoff a game could still be in progress. Past it, a game with
 *  no result is over — it was simply never graded (no real book line to grade
 *  against), so the board says FINAL rather than claiming it is still live. */
export const LIVE_WINDOW_H = 5;

/** Pure: has this game kicked off recently enough to still be in progress? */
export function inPlayAt(start: Date | null, now: Date): boolean {
  if (start === null) return false;
  const since = now.getTime() - start.getTime();
  return since >= 0 && since < LIVE_WINDOW_H * 3_600_000;
}

/** Pure: upcoming before kicked-off, then score desc, gap desc, earliest
 *  kickoff, away team. The gap breaks the tie because the score clamps at 100
 *  — a slate can pin a dozen games there, and without it the board would call
 *  the earliest kickoff the best game of the week. */
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
      (b.gap ?? Number.NEGATIVE_INFINITY) -
        (a.gap ?? Number.NEGATIVE_INFINITY) ||
      ms(a) - ms(b) ||
      a.row.away.localeCompare(b.row.away),
  );
}

/**
 * Pure: number the week best to worst over an ALREADY-SORTED list (sortGames).
 * Only a game you can still bet gets a number; one that has kicked off is not a
 * decision any more, so it carries null and shows its result instead. Ranks are
 * assigned over the whole board, so a day or team filter never renumbers them.
 */
export function assignBoardRanks(games: HomeGame[]): HomeGame[] {
  let n = 0;
  return games.map((g) =>
    g.kickedOff ? { ...g, boardRank: null } : { ...g, boardRank: ++n },
  );
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

/** The season and week one game sits in, so a game page can rebuild the same
 *  board context the board itself uses. Null when the id is not a game. */
export const gameSeasonWeek = cache(async function gameSeasonWeek(
  gameId: number,
): Promise<{ season: number; week: number } | null> {
  const rows = await prisma.$queryRaw<
    { season: number | bigint; week: number | bigint }[]
  >`SELECT season, week FROM games WHERE id = ${gameId} LIMIT 1`;
  if (rows.length === 0) return null;
  return { season: Number(rows[0].season), week: Number(rows[0].week) };
});

/**
 * One game, with the whole week's context behind it. It loads the full board on
 * purpose: the rank and the slate bar are assigned across every game, so a game
 * page that queried its own row alone would show a different rank from the
 * board that linked to it.
 */
export async function getHomeGame(
  gameId: number,
  now: Date = new Date(),
): Promise<{ game: HomeGame; board: HomeBoard } | null> {
  const sw = await gameSeasonWeek(gameId);
  if (sw === null) return null;
  const board = await getHomeBoard(sw.season, sw.week, now);
  const game = board.games.find((g) => g.row.gameId === gameId);
  return game === undefined ? null : { game, board };
}

/** B1 (pure): the slate's gaps over the week's UPCOMING rows with a centred
 *  Hard Rock quote and a model read -- the card's universe. A kicked-off game
 *  is null, so its last pre-kick quote no longer moves the bar. */
export function upcomingSlateGaps(
  rows: Pick<BoardRow, "gameId" | "bvLine" | "startDate">[],
  checkById: Map<number, Pick<LineCheckRow, "hrLine" | "hrCentred">>,
  now: Date,
): (number | null)[] {
  return rows.map((row) => {
    const start = asDate(row.startDate);
    if (start === null || start.getTime() <= now.getTime()) return null;
    const c = checkById.get(row.gameId);
    if (!c || c.hrLine === null || row.bvLine === null || c.hrCentred === false)
      return null;
    return round2(c.hrLine - row.bvLine);
  });
}

/** B4 (pure): the QB read the Board uses -- the scheduled build's own. A card
 *  from before the field was parsed falls back to its blocker; no card item
 *  means no read, which `applyCardHold` keeps from ever lighting a BET. */
export function qbOutFrom(item: CardItem | null): boolean {
  if (item === null) return false; // the hold below decides; never lit
  return (
    item.qbOut ?? (item.blocker === "qb_out" || item.paperBlocker === "qb_out")
  );
}

/** B3 + B4 (pure): a row the rule rates BET is not lit when the scheduled
 *  build held it (a failed input touched it: Held, paper only) or has not read
 *  it at all (no injury read, no card line). Missing information never becomes
 *  a lit signal. Played rows pass through: there is nothing left to decide. */
export function applyCardHold(
  edge: EdgeResult,
  item: CardItem | null,
  kickedOff: boolean,
): { edge: EdgeResult; hold: "degraded" | "unread" | null } {
  if (edge.tier !== "BET" || kickedOff) return { edge, hold: null };
  if (item === null) {
    return {
      edge: {
        ...edge,
        tier: "EDGE",
        blocker: "not_on_card",
        action:
          "Not a paper signal yet: no scheduled build has read this game’s Hard Rock line and injury report; it is not a bet until one does.",
      },
      hold: "unread",
    };
  }
  if (isHeld(item)) {
    return {
      edge: { ...edge, tier: "EDGE", blocker: "held", action: item.action },
      hold: "degraded",
    };
  }
  return { edge, hold: null };
}

export async function getHomeBoard(
  season: number,
  requestedWeek?: number,
  now: Date = new Date(),
): Promise<HomeBoard> {
  // Pick the week FIRST, off the three-column universe (~1 KB), then pay for
  // that week's rows, consensus lines and book quotes only. Measured with a
  // per-query byte meter on the 2026 week-3 board: 2.28 MB -> 1.05 MB per
  // board render, 2.74 MB -> 0.98 MB per game page. Season-wide renders, times
  // every dev refresh and screenshot pass pointed at production, are what
  // exhausted the Free plan's 5 GB/month egress on 2026-09-16.
  const universe = await boardUniverse(season);
  // Default to the week you are about to bet (earliest week with a game still
  // to kick off — lib/week.ts); ?week= lets Tate review a past one.
  const weeks = weeksOf(universe);
  const week =
    requestedWeek !== undefined && weeks.includes(requestedWeek)
      ? requestedWeek
      : defaultWeek(universe, now);
  const [board, checks, card, hrAtCard] = await Promise.all([
    week === null ? Promise.resolve([] as BoardRow[]) : getBoard(season, week),
    week === null
      ? Promise.resolve([] as LineCheckRow[])
      : getLineCheck(season, "1h", week),
    // Board alignment (2026-10-14): the newest SCHEDULED build of the week
    // decides the QB read and the hold, as it does for the server.
    week === null ? Promise.resolve(null) : getScheduledCard(season, week),
    // A played game settles on Hard Rock's line at the last scheduled card
    // before its kickoff, as /records does (fact-check audit 2026-10-17).
    week === null
      ? Promise.resolve(new Map<number, HrQuote>())
      : hardRockAtLastCard(season, week),
  ]);
  const itemById = new Map<number, CardItem>(
    (card?.items ?? []).map((i) => [i.gameId, i]),
  );
  const rows = board.filter((b) => b.week === week);
  const [previews, movements] = await Promise.all([
    week === null
      ? Promise.resolve(new Map<number, PreviewGame>())
      : getPreviewByGame(season, week),
    getMovements(rows.map((r) => r.gameId)),
  ]);
  const checkById = new Map(checks.map((c) => [c.gameId, c]));
  // H-PCT: the bar is a property of the SLATE. Read it over the week's rows
  // with a centred Hard Rock quote and a model read -- the same universe the
  // card uses -- before any row is judged. BET_GAP_PTS only when none qualify.
  // B1 (2026-10-14): UPCOMING games only, as the card computes it, so the
  // Board, the card, the paper arm and the server read one bar after the
  // week's first kickoffs.
  const slateGaps = upcomingSlateGaps(rows, checkById, now);
  const barValue = slateBar(slateGaps);
  const slate: SlateBar = {
    bar: barValue ?? BET_GAP_PTS,
    n: slateGaps.filter((g) => g !== null).length,
    share: PCT_SHARE,
    basis: barValue === null ? "fallback" : "slate",
  };
  const noModel = rows.length > 0 && rows.every((r) => !lineState(r).hasModel);

  const games: HomeGame[] = rows.map((row) => {
    const check = checkById.get(row.gameId) ?? null;
    const fallbackLine = row.factors.line ?? null;
    const { hasModel } = lineState(row);
    const input: EdgeInput = {
      away: row.away,
      home: row.home,
      bvLine: row.bvLine,
      liveLine: row.curLine,
      fallbackLine,
      gap: row.liveGap,
      hrLine: check?.hrLine ?? null,
      hrUnderPrice: check?.hrUnderPrice ?? null,
      ev: check?.ev ?? null,
      evVerdict: check?.evVerdict ?? "na",
      fhShare: row.factors.fh_share ?? null,
      // B4: the scheduled build's own injury read; Sunday's flag is not used.
      qbOut: qbOutFrom(itemById.get(row.gameId) ?? null),
      qbOutDetail: itemById.get(row.gameId)?.qbOutDetail ?? null,
      minGamesPlayed: minGamesPlayedFrom(row.factors),
      bvAdjust: row.bvAdjust,
      bvAdjustReason: row.bvAdjustReason,
      factorBoard: row.factors.factor_board,
      marketLine: row.curLine,
      bestLine: check?.best ?? null,
      marketFairUnder: check?.marketFairUnder ?? null,
      context: edgeContext(row.factors),
      bar: slate.bar,
      hrCentred: check?.hrCentred ?? null,
      hrLive: check?.hrLive ?? null,
    };
    const scored = edgeScore(input);
    const start0 = asDate(row.startDate);
    const kicked0 = start0 !== null && start0.getTime() <= now.getTime();
    const { edge, hold } = applyCardHold(
      scored,
      itemById.get(row.gameId) ?? null,
      kicked0,
    );
    // edge.ts names the basis (`edge.lineBasis`: Hard Rock, else the market,
    // else the reference line) and measures the gap against it; the value of
    // that line is the same lookup, in the same order. `edge.lineBasis` is set
    // whenever any line exists — settling needs no model — while the board's
    // own `gapBasis` is null without one (no gap without our number).
    // Settles ONLY on Hard Rock's line at the last scheduled card before
    // kickoff (fact-check audit 2026-10-17, Tate): no market or reference
    // fallback; without that line the game reads "No verified Hard Rock line".
    const atCard = hrAtCard.get(row.gameId) ?? null;
    const start = asDate(row.startDate);
    const settled =
      atCard === null ? null : settledOf(row.firstHalfTrusted, atCard.line);
    return {
      row,
      check,
      edge,
      movement: movements.get(row.gameId) ?? null,
      preview: previews.get(row.gameId) ?? null,
      kickedOff: start !== null && start.getTime() <= now.getTime(),
      inPlay: inPlayAt(start, now),
      kickoff: kickoffET(row.startDate),
      day: dayKey(row.startDate),
      gap: edge.gap,
      gapBasis: hasModel ? edge.lineBasis : null,
      basisBooks: basisBooksFrom(check),
      earlySeason: earlySeasonFrom(row.factors),
      settled,
      settledLine: settled === null ? null : (atCard?.line ?? null),
      priceLine: priceSentence(input),
      boardRank: null,
      hold,
    };
  });

  const sorted = assignBoardRanks(sortGames(games));

  return {
    season,
    week,
    weeks,
    noModel,
    noHrLine: rows.length > 0 && sorted.every((g) => g.check?.hrLine == null),
    games: sorted,
    counts: tierCounts(sorted),
    slate,
  };
}
