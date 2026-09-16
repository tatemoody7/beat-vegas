import { isCentredQuote } from "@/lib/devig";
import { Prisma } from "@prisma/client";
import { cache } from "react";
import { prisma } from "@/lib/prisma";
import { Factors, parseFactors } from "@/lib/score";
import { median } from "@/lib/format";

// Opportunities board data layer — ports the SQL in beatvegas/dashboard/app.py
// (the predictions+games board query and the odds_snapshots consensus logic).

export type BoardRow = {
  gameId: number;
  week: number;
  /** Kickoff (stored naive UTC); null when unknown. */
  startDate: Date | null;
  away: string;
  home: string;
  /** CFBD team ids (= the logo ids in web/data/team_logos.json); null if unknown. */
  awayTeamId: number | null;
  homeTeamId: number | null;
  underScore: number | null;
  underProb: number | null;
  rank: number | null;
  factors: Factors;
  openLine: number | null;
  curLine: number | null;
  bvLine: number | null;
  bvLo: number | null;
  bvHi: number | null;
  /** Actual first-half points once the game is played (grading input); null before. */
  firstHalfTotal: number | null;
  // gap vs the live consensus (curLine − bvLine), under direction: positive =
  // Vegas above our number. Falls back to the gap stored at scoring time.
  liveGap: number | null;
  // manual display-only nudge applied to the BV line (e.g. confirmed QB-out).
  bvAdjust: number | null;
  bvAdjustReason: string | null;
};

const num = (v: unknown): number | null =>
  v === null || v === undefined ? null : Number(v);

type PredRow = {
  game_id: number | bigint;
  under_score: number | bigint | null;
  under_probability: number | null;
  rank: number | bigint | null;
  factors_json: string | null;
  first_half_total: number | bigint | null;
  bv_line: number | null;
  bv_gap: number | null;
  bv_lo: number | null;
  bv_hi: number | null;
  week: number | bigint;
  start_date: Date | null;
  away_team: string | null;
  home_team: string | null;
  away_team_id: number | bigint | null;
  home_team_id: number | bigint | null;
};

type SnapRow = {
  game_id: number | bigint;
  book: string | null;
  line: number | null;
  over_price: number | null;
  under_price: number | null;
  captured_at: string | null; // CAST to TEXT — Prisma can't coerce SQLite DateTime via raw select
};

export type ConsensusLine = { open: number | null; cur: number | null };

// Opening/current consensus per game (mirrors beatvegas/lines.py
// consensus_open_close + closing_before_kickoff): for each game, take each
// book's first capture → median across books = open; each book's last → current.
// Only PRE-KICKOFF snapshots count (a poll that ran after the game started is
// not a closing line), the CFBD synthetic "consensus" row is dropped (it would
// double-count the real books), and book keys are case-folded so a legacy
// "DraftKings" row and an Odds API "draftkings" row are one book.
// Season-scoped: an unbounded scan grows with every season of movement history.
// Week-scoped when `week` is given (the board only ever renders one week, and
// this query was ~210 KB per render season-wide against a 5 GB/month egress
// cap that took the site down on 2026-09-16); season-wide for the research
// readers (lib/lineStudy.ts) that genuinely need every game.
export async function consensusLines(
  season: number,
  market = "1H_total",
  week?: number,
): Promise<Map<number, ConsensusLine>> {
  const snaps = await prisma.$queryRaw<SnapRow[]>`
    SELECT s.game_id, LOWER(s.book) AS book, s.line, s.over_price, s.under_price,
           CAST(s.captured_at AS TEXT) AS captured_at
    FROM odds_snapshots s JOIN games g ON g.id = s.game_id
    WHERE s.market = ${market} AND g.season = ${season}
      ${weekClause(week)}
      AND (g.start_date IS NULL OR s.captured_at IS NULL
           OR s.captured_at <= g.start_date)
      AND LOWER(COALESCE(s.book, '')) <> 'consensus'
  `;
  // game_id -> book -> sorted captures
  const byGame = new Map<number, Map<string, SnapRow[]>>();
  for (const s of snaps) {
    if (s.line === null || s.line === undefined) continue;
    // A rung of the alternate ladder served as the main total is not a line;
    // it must never drag the consensus median. See lib/devig.ts::isCentredQuote.
    if (!isCentredQuote(s.over_price, s.under_price)) continue;
    const gid = Number(s.game_id);
    const book = s.book ?? "?";
    if (!byGame.has(gid)) byGame.set(gid, new Map());
    const bm = byGame.get(gid)!;
    if (!bm.has(book)) bm.set(book, []);
    bm.get(book)!.push(s);
  }
  const out = new Map<number, ConsensusLine>();
  for (const [gid, books] of byGame) {
    const firsts: number[] = [];
    const lasts: number[] = [];
    for (const caps of books.values()) {
      // ISO-ish timestamps sort chronologically as strings.
      caps.sort((a, b) =>
        (a.captured_at ?? "").localeCompare(b.captured_at ?? ""),
      );
      firsts.push(Number(caps[0].line));
      lasts.push(Number(caps[caps.length - 1].line));
    }
    out.set(gid, { open: median(firsts), cur: median(lasts) });
  }
  return out;
}

// Latest manual BV adjustment per game (display-only nudge, e.g. QB-out).
// Season-scoped like every other board read: an unbounded scan grows with each
// season of nudges and the board only ever needs this season's games.
async function bvAdjustments(
  season: number,
): Promise<Map<number, { delta: number; reason: string | null }>> {
  const rows = await prisma.$queryRaw<
    {
      game_id: number | bigint;
      delta_pts: number | null;
      reason: string | null;
      created_at: string | null;
    }[]
  >`
    SELECT a.game_id, a.delta_pts, a.reason,
           CAST(a.created_at AS TEXT) AS created_at
    FROM bv_adjustments a JOIN games g ON g.id = a.game_id
    WHERE g.season = ${season}
    ORDER BY a.created_at
  `;
  const out = new Map<number, { delta: number; reason: string | null }>();
  for (const r of rows) {
    if (r.delta_pts === null || r.delta_pts === undefined) continue;
    out.set(Number(r.game_id), {
      delta: Number(r.delta_pts),
      reason: r.reason,
    });
  }
  return out; // later rows overwrite earlier → latest wins
}

/** `AND g.week = N` when a week is given, nothing otherwise. */
function weekClause(week: number | undefined): Prisma.Sql {
  return week === undefined ? Prisma.empty : Prisma.sql`AND g.week = ${week}`;
}

/**
 * The ONE definition of the board's game universe, as a WHERE fragment over
 * `predictions p JOIN games g`: this season, games Hard Rock has posted a
 * full-game total on (the only book Tate can bet), the newest real model
 * version (display-only derived_lines never outranks a model), optionally one
 * week. boardGames and boardUniverse both build on it so they cannot drift.
 */
function universeWhere(season: number, week?: number): Prisma.Sql {
  return Prisma.sql`
    WHERE g.season = ${season}
      ${weekClause(week)}
      -- The site's game universe: games Hard Rock has posted a full-game total
      -- on (the only book Tate can bet). Everything else stays out of view.
      AND EXISTS (
        SELECT 1 FROM odds_snapshots hr
        WHERE hr.game_id = g.id AND hr.market = 'full_game_total'
          AND LOWER(hr.book) = 'hardrockbet')
      AND p.model_version = (
        SELECT p2.model_version FROM predictions p2
        JOIN games g2 ON g2.id = p2.game_id
        WHERE g2.season = ${season}
        -- A real model version always outranks display-only derived_lines:
        -- re-running post_derived_lines after a Sunday scoring must not hide
        -- the model's picks behind "DERIVED — no model pick" cards.
        ORDER BY (p2.model_version = 'derived_lines') ASC,
                 p2.created_at DESC
        LIMIT 1)`;
}

/**
 * The board's GAME UNIVERSE for a season — the predictions rows and their game
 * facts, without the two expensive joins getBoard adds on top (the
 * consensus-line scan and the adjustment lookup). `week` narrows it to one
 * week's rows; factors_json is ~5 KB a row, so the season-wide pull was the
 * single heaviest payload on a board render (~283 KB).
 *
 * Split out so a caller that only needs "which games are on the board" does not
 * pay for line medians it will not read. getBoard still composes on top of it,
 * so there is exactly ONE definition of the universe and the two cannot drift.
 */
export async function boardGames(
  season: number,
  week?: number,
): Promise<PredRow[]> {
  return prisma.$queryRaw<PredRow[]>`
    SELECT p.game_id, p.under_score, p.under_probability, p.rank, p.factors_json,
           p.bv_line, p.bv_gap, p.bv_lo, p.bv_hi,
           g.week, g.start_date, g.away_team, g.home_team, g.first_half_total,
           g.away_team_id, g.home_team_id
    FROM predictions p JOIN games g ON g.id = p.game_id
    ${universeWhere(season, week)}
    ORDER BY p.rank
  `;
}

export type UniverseRow = {
  gameId: number;
  week: number;
  startDate: Date | null;
};

/**
 * The same universe as boardGames, three columns wide: enough to know which
 * weeks exist and which one is "this week" (lib/week.ts), so getHomeBoard can
 * pick the week BEFORE it pays for that week's rows, lines and books. ~1 KB
 * where the full rows were ~283 KB. cache()d per request (season is a stable
 * key).
 */
export const boardUniverse = cache(async function boardUniverse(
  season: number,
): Promise<UniverseRow[]> {
  const rows = await prisma.$queryRaw<
    {
      game_id: number | bigint;
      week: number | bigint;
      start_date: Date | null;
    }[]
  >`
    SELECT p.game_id, g.week, g.start_date
    FROM predictions p JOIN games g ON g.id = p.game_id
    ${universeWhere(season)}
  `;
  return rows.map((r) => ({
    gameId: Number(r.game_id),
    week: Number(r.week),
    startDate: r.start_date ?? null,
  }));
});

/**
 * The board for a season, ONCE per request.
 *
 * This is the most expensive query path in the app — consensusLines() alone
 * scans every pre-kickoff snapshot for the season across every book. /game/[id]
 * ran the whole thing TWICE per page view, because generateMetadata and the
 * page body both call getHomeGame and Next dedupes fetch(), not Prisma.
 *
 * cache() is keyed on `season` (and the optional `week`) only, which is why the
 * caching lives here rather than on getHomeBoard: that takes a `now` defaulting
 * to new Date(), so every call would be a fresh key and dedupe nothing. `now`
 * only affects pure derivation downstream, never the query.
 *
 * `week` scopes the rows AND the consensus scan to one week (the home board
 * and the game page know their week before they call). Omitted = the whole
 * season, for callers that need it.
 */
export const getBoard = cache(async function getBoard(
  season: number,
  week?: number,
): Promise<BoardRow[]> {
  const [preds, lines, adjustments] = await Promise.all([
    boardGames(season, week),
    consensusLines(season, "1H_total", week),
    bvAdjustments(season),
  ]);
  return preds.map((p) => {
    const gid = Number(p.game_id);
    const l = lines.get(gid);
    const curLine = l?.cur ?? null;
    const adj = adjustments.get(gid) ?? null;
    const rawBv = num(p.bv_line);
    // Apply the manual nudge to the displayed BV line + band (clearly labeled).
    const bvLine =
      rawBv !== null && adj
        ? Math.round((rawBv + adj.delta) * 100) / 100
        : rawBv;
    // Prefer the gap vs the live consensus; fall back to the gap baked in at
    // scoring time (bv_gap = line_used − bv_line) when no live line exists.
    const liveGap =
      curLine !== null && bvLine !== null
        ? Math.round((curLine - bvLine) * 100) / 100
        : num(p.bv_gap);
    return {
      gameId: gid,
      week: Number(p.week),
      startDate: p.start_date ?? null,
      away: p.away_team ?? "?",
      home: p.home_team ?? "?",
      awayTeamId: num(p.away_team_id),
      homeTeamId: num(p.home_team_id),
      underScore: num(p.under_score),
      underProb: p.under_probability ?? null,
      rank: num(p.rank),
      factors: parseFactors(p.factors_json),
      openLine: l?.open ?? null,
      curLine,
      bvLine,
      firstHalfTotal: num(p.first_half_total),
      bvLo:
        adj && num(p.bv_lo) !== null ? num(p.bv_lo)! + adj.delta : num(p.bv_lo),
      bvHi:
        adj && num(p.bv_hi) !== null ? num(p.bv_hi)! + adj.delta : num(p.bv_hi),
      liveGap,
      bvAdjust: adj?.delta ?? null,
      bvAdjustReason: adj?.reason ?? null,
    };
  });
});

export async function getSeasons(): Promise<number[]> {
  // Only seasons that actually have a board (predictions) — so the app lands on
  // a populated week by default instead of an empty backfilled future schedule.
  const rows = await prisma.$queryRaw<{ season: number | bigint }[]>`
    SELECT DISTINCT g.season
    FROM games g JOIN predictions p ON p.game_id = g.id
    ORDER BY g.season DESC
  `;
  return rows.map((r) => Number(r.season));
}
