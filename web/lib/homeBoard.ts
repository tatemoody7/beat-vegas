import { getBoard, type BoardRow } from "@/lib/board";
import {
  edgeScore,
  type EdgeContext,
  type EdgeInput,
  type EdgeResult,
} from "@/lib/edge";
import { round2 } from "@/lib/format";
import { getLineCheck, type LineCheckRow } from "@/lib/lineCheck";
import { getMovements, type Movement } from "@/lib/movement";
import { getPicks, isRealFirstHalf, type PickFull } from "@/lib/picks";
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

const ET = "America/New_York";

function asDate(d: Date | string | null): Date | null {
  if (d === null) return null;
  const t = new Date(d);
  return Number.isNaN(t.getTime()) ? null : t;
}

/** "Sat 7:30p" in ET; null when the kickoff time is unknown. */
export function kickoffET(d: Date | string | null): string | null {
  const t = asDate(d);
  if (t === null) return null;
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: ET,
    weekday: "short",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  }).formatToParts(t);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  const ampm = get("dayPeriod").toLowerCase().startsWith("p") ? "p" : "a";
  return `${get("weekday")} ${get("hour")}:${get("minute")}${ampm}`;
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
  const wd = new Intl.DateTimeFormat("en-US", {
    timeZone: ET,
    weekday: "short",
  })
    .format(t)
    .toLowerCase();
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

/** Which number the gap is measured against. */
export type GapBasis = "hardrock" | "market" | "reference";

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
  /** The line the gap is measured against, and which line that is. */
  gap: number | null;
  gapBasis: GapBasis | null;
  /** One sentence on Hard Rock's price vs the market's no-vig fair price. */
  priceLine: string;
};

export type HomeBoard = {
  season: number;
  week: number | null;
  /** Weeks that have games on the board (for the week selector). */
  weeks: number[];
  /** Every row is a derived reference line — the model has no read this week. */
  noModel: boolean;
  /** No book has posted a first-half line for any game on the week. */
  noHrLine: boolean;
  games: HomeGame[];
  counts: { bet: number; edge: number; pass: number };
  bankroll: Bankroll;
};

/** Pure: score desc, then the earliest kickoff, then the away team. */
export function sortGames(games: HomeGame[]): HomeGame[] {
  const ms = (g: HomeGame): number => {
    const t = asDate(g.row.startDate);
    return t === null ? Number.POSITIVE_INFINITY : t.getTime();
  };
  return [...games].sort(
    (a, b) =>
      b.edge.score - a.edge.score ||
      ms(a) - ms(b) ||
      a.row.away.localeCompare(b.row.away),
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
  const noModel =
    rows.length > 0 &&
    rows.every(
      (r) => r.factors.line_kind === "derived_fg" || r.underScore === null,
    );

  // Only real-money FIRST-HALF picks count toward the record, the bankroll and
  // the weekly cap (full game is context, paper is tracked apart).
  const real1H = picks.filter(isRealFirstHalf);
  const pickedGames = new Set(real1H.map((p) => p.gameId));
  const pickedKey = new Set(real1H.map((p) => `${p.away}@${p.home}`));

  const games: HomeGame[] = rows.map((row) => {
    const check = checkById.get(row.gameId) ?? null;
    const fallbackLine = row.factors.line ?? null;
    const input: EdgeInput = {
      away: row.away,
      home: row.home,
      derived: row.factors.line_kind === "derived_fg",
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
    const hasModel =
      row.factors.line_kind !== "derived_fg" &&
      row.underScore !== null &&
      row.bvLine !== null;
    const start = asDate(row.startDate);
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
      priceLine: priceSentence(input),
    };
  });

  const sorted = sortGames(games);
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
  };
}
