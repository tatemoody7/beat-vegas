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
  underScore: number | null;
  underProb: number | null;
  rank: number | null;
  fullGameTotal: number | null;
  factors: Factors;
  openLine: number | null;
  curLine: number | null;
  bvLine: number | null;
  bvLo: number | null;
  bvHi: number | null;
  // gap vs the live consensus (curLine − bvLine), under direction: positive =
  // Vegas above our number. Falls back to the gap stored at scoring time.
  liveGap: number | null;
  // gap in units of the BV line's own noise (σ) — context only, never a gate.
  liveGapZ: number | null;
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
  bv_line: number | null;
  bv_gap: number | null;
  bv_lo: number | null;
  bv_hi: number | null;
  bv_sigma: number | null;
  week: number | bigint;
  start_date: Date | null;
  away_team: string | null;
  home_team: string | null;
  full_game_total: number | null;
};

type SnapRow = {
  game_id: number | bigint;
  book: string | null;
  line: number | null;
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
export async function consensusLines(
  season: number,
  market = "1H_total",
): Promise<Map<number, ConsensusLine>> {
  const snaps = await prisma.$queryRaw<SnapRow[]>`
    SELECT s.game_id, LOWER(s.book) AS book, s.line,
           CAST(s.captured_at AS TEXT) AS captured_at
    FROM odds_snapshots s JOIN games g ON g.id = s.game_id
    WHERE s.market = ${market} AND g.season = ${season}
      AND (g.start_date IS NULL OR s.captured_at IS NULL
           OR s.captured_at <= g.start_date)
      AND LOWER(COALESCE(s.book, '')) <> 'consensus'
  `;
  // game_id -> book -> sorted captures
  const byGame = new Map<number, Map<string, SnapRow[]>>();
  for (const s of snaps) {
    if (s.line === null || s.line === undefined) continue;
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
async function bvAdjustments(): Promise<
  Map<number, { delta: number; reason: string | null }>
> {
  const rows = await prisma.$queryRaw<
    {
      game_id: number | bigint;
      delta_pts: number | null;
      reason: string | null;
      created_at: string | null;
    }[]
  >`
    SELECT game_id, delta_pts, reason, CAST(created_at AS TEXT) AS created_at
    FROM bv_adjustments ORDER BY created_at
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

export async function getBoard(season: number): Promise<BoardRow[]> {
  const preds = await prisma.$queryRaw<PredRow[]>`
    SELECT p.game_id, p.under_score, p.under_probability, p.rank, p.factors_json,
           p.bv_line, p.bv_gap, p.bv_lo, p.bv_hi, p.bv_sigma,
           g.week, g.start_date, g.away_team, g.home_team, g.full_game_total
    FROM predictions p JOIN games g ON g.id = p.game_id
    WHERE g.season = ${season}
      AND p.model_version = (
        SELECT p2.model_version FROM predictions p2
        JOIN games g2 ON g2.id = p2.game_id
        WHERE g2.season = ${season}
        -- A real model version always outranks display-only derived_lines:
        -- re-running post_derived_lines after a Sunday scoring must not hide
        -- the model's picks behind "DERIVED — no model pick" cards.
        ORDER BY (p2.model_version = 'derived_lines') ASC,
                 p2.created_at DESC
        LIMIT 1)
    ORDER BY p.rank
  `;
  const [lines, adjustments] = await Promise.all([
    consensusLines(season),
    bvAdjustments(),
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
    const bvSigma = num(p.bv_sigma);
    // Prefer the gap vs the live consensus; fall back to the gap baked in at
    // scoring time (bv_gap = line_used − bv_line) when no live line exists.
    const liveGap =
      curLine !== null && bvLine !== null
        ? Math.round((curLine - bvLine) * 100) / 100
        : num(p.bv_gap);
    const liveGapZ =
      liveGap !== null && bvSigma && bvSigma > 0
        ? Math.round((liveGap / bvSigma) * 100) / 100
        : null;
    return {
      gameId: gid,
      week: Number(p.week),
      startDate: p.start_date ?? null,
      away: p.away_team ?? "?",
      home: p.home_team ?? "?",
      underScore: num(p.under_score),
      underProb: p.under_probability ?? null,
      rank: num(p.rank),
      fullGameTotal: p.full_game_total ?? null,
      factors: parseFactors(p.factors_json),
      openLine: l?.open ?? null,
      curLine,
      bvLine,
      bvLo:
        adj && num(p.bv_lo) !== null ? num(p.bv_lo)! + adj.delta : num(p.bv_lo),
      bvHi:
        adj && num(p.bv_hi) !== null ? num(p.bv_hi)! + adj.delta : num(p.bv_hi),
      liveGap,
      liveGapZ,
      bvAdjust: adj?.delta ?? null,
      bvAdjustReason: adj?.reason ?? null,
    };
  });
}

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
