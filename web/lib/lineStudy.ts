import { prisma } from "@/lib/prisma";

// Port of beatvegas/analysis/line_study.py — for a season, how often the 1H
// under hit bucketed by the OPENING line (real consensus open if snapshots
// exist, else proxy = 0.52×full-game total). Pure-ish; DB read at the top.

export const BREAKEVEN_PCT = 52.4; // under% needed to beat -110 juice

export type LineBucket = {
  line: number;
  games: number;
  under: number;
  push: number;
  under_pct: number;
  line_source: "real_open" | "proxy";
};

const roundHalf = (x: number) => Math.round(x * 2) / 2;
const proxyTotal = (fullTotal: number, ratio = 0.52) =>
  roundHalf(fullTotal * ratio);

function median(xs: number[]): number | null {
  if (xs.length === 0) return null;
  const s = [...xs].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}

type GameRow = {
  id: number | bigint;
  first_half_total: number | bigint;
  full_game_total: number;
};
type SnapRow = {
  game_id: number | bigint;
  book: string | null;
  line: number | null;
  captured_at: string | null;
};

// Consensus OPENING line per game (median across books of each book's first
// capture) — matches lines.consensus_open_close's open element.
async function openByGame(season: number): Promise<Map<number, number>> {
  const snaps = await prisma.$queryRaw<SnapRow[]>`
    SELECT s.game_id, s.book, s.line, CAST(s.captured_at AS TEXT) AS captured_at
    FROM odds_snapshots s JOIN games g ON g.id = s.game_id
    WHERE g.season = ${season} AND s.market = '1H_total'
  `;
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
  const out = new Map<number, number>();
  for (const [gid, books] of byGame) {
    const firsts: number[] = [];
    for (const caps of books.values()) {
      caps.sort((a, b) =>
        (a.captured_at ?? "").localeCompare(b.captured_at ?? ""),
      );
      firsts.push(Number(caps[0].line));
    }
    const m = median(firsts);
    if (m !== null) out.set(gid, m);
  }
  return out;
}

export async function getLineStudy(
  season: number,
  minGames = 30,
): Promise<{ buckets: LineBucket[]; anyReal: boolean }> {
  const games = await prisma.$queryRaw<GameRow[]>`
    SELECT id, first_half_total, full_game_total
    FROM games
    WHERE season = ${season}
      AND first_half_total IS NOT NULL
      AND full_game_total > 0
  `;
  const opens = await openByGame(season);

  // Assign each game a line + source.
  type Tagged = { fh: number; line: number; source: "real_open" | "proxy" };
  const tagged: Tagged[] = games.map((g) => {
    const gid = Number(g.id);
    const real = opens.get(gid);
    return real !== undefined
      ? {
          fh: Number(g.first_half_total),
          line: roundHalf(real),
          source: "real_open",
        }
      : {
          fh: Number(g.first_half_total),
          line: proxyTotal(g.full_game_total),
          source: "proxy",
        };
  });

  // Bucket by line.
  const groups = new Map<number, Tagged[]>();
  for (const t of tagged) {
    if (!groups.has(t.line)) groups.set(t.line, []);
    groups.get(t.line)!.push(t);
  }

  const buckets: LineBucket[] = [];
  for (const [line, rows] of groups) {
    const games_n = rows.length;
    if (games_n < minGames) continue;
    const under = rows.filter((r) => r.fh < r.line).length;
    const push = rows.filter((r) => r.fh === r.line).length;
    const decisive = games_n - push;
    const under_pct =
      decisive > 0 ? Math.round((1000 * under) / decisive) / 10 : 0;
    const real = rows.filter((r) => r.source === "real_open").length;
    const line_source = real > games_n / 2 ? "real_open" : "proxy";
    buckets.push({ line, games: games_n, under, push, under_pct, line_source });
  }
  buckets.sort((a, b) => b.under_pct - a.under_pct);
  const anyReal = buckets.some((b) => b.line_source === "real_open");
  return { buckets, anyReal };
}
