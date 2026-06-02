import { prisma } from "@/lib/prisma";
import { Factors, parseFactors } from "@/lib/score";

// Opportunities board data layer — ports the SQL in beatvegas/dashboard/app.py
// (the predictions+games board query and the odds_snapshots consensus logic).

export type BoardRow = {
  gameId: number;
  week: number;
  away: string;
  home: string;
  underScore: number | null;
  underProb: number | null;
  rank: number | null;
  fullGameTotal: number | null;
  factors: Factors;
  openLine: number | null;
  curLine: number | null;
};

const num = (v: unknown): number | null =>
  v === null || v === undefined ? null : Number(v);

function median(xs: number[]): number | null {
  if (xs.length === 0) return null;
  const s = [...xs].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}

type PredRow = {
  game_id: number | bigint;
  under_score: number | bigint | null;
  under_probability: number | null;
  rank: number | bigint | null;
  factors_json: string | null;
  week: number | bigint;
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

// Opening/current consensus per game (app.py:158-169): for each game, take each
// book's first capture → median across books = open; each book's last → current.
async function consensusLines(): Promise<
  Map<number, { open: number | null; cur: number | null }>
> {
  const snaps = await prisma.$queryRaw<SnapRow[]>`
    SELECT game_id, book, line, CAST(captured_at AS TEXT) AS captured_at
    FROM odds_snapshots
    WHERE market = '1H_total'
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
  const out = new Map<number, { open: number | null; cur: number | null }>();
  for (const [gid, books] of byGame) {
    const firsts: number[] = [];
    const lasts: number[] = [];
    for (const caps of books.values()) {
      // ISO-ish timestamps sort chronologically as strings.
      caps.sort((a, b) => (a.captured_at ?? "").localeCompare(b.captured_at ?? ""));
      firsts.push(Number(caps[0].line));
      lasts.push(Number(caps[caps.length - 1].line));
    }
    out.set(gid, { open: median(firsts), cur: median(lasts) });
  }
  return out;
}

export async function getBoard(season: number): Promise<BoardRow[]> {
  const preds = await prisma.$queryRaw<PredRow[]>`
    SELECT p.game_id, p.under_score, p.under_probability, p.rank, p.factors_json,
           g.week, g.away_team, g.home_team, g.full_game_total
    FROM predictions p JOIN games g ON g.id = p.game_id
    WHERE g.season = ${season}
      AND p.model_version = (SELECT model_version FROM predictions
                             ORDER BY created_at DESC LIMIT 1)
    ORDER BY p.rank
  `;
  const lines = await consensusLines();
  return preds.map((p) => {
    const gid = Number(p.game_id);
    const l = lines.get(gid);
    return {
      gameId: gid,
      week: Number(p.week),
      away: p.away_team ?? "?",
      home: p.home_team ?? "?",
      underScore: num(p.under_score),
      underProb: p.under_probability ?? null,
      rank: num(p.rank),
      fullGameTotal: p.full_game_total ?? null,
      factors: parseFactors(p.factors_json),
      openLine: l?.open ?? null,
      curLine: l?.cur ?? null,
    };
  });
}

export async function getSeasons(): Promise<number[]> {
  const rows = await prisma.$queryRaw<{ season: number | bigint }[]>`
    SELECT DISTINCT season FROM games ORDER BY season DESC
  `;
  return rows.map((r) => Number(r.season));
}
