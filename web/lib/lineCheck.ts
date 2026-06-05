import { prisma } from "@/lib/prisma";

// "Line Check" — is Hard Rock giving Tate a good number vs the rest of the market?
// He can only bet Hard Rock (Florida), so this is a quality/CLV check, not price
// shopping. For an UNDER, a HIGHER total at HR is better. Verdict is HR vs the
// BEST (highest) total available in the market.

export type Market = "full_game" | "1h";

const MARKET_DB: Record<Market, string> = {
  full_game: "full_game_total",
  "1h": "1H_total",
};

// Hard Rock keys, FL preferred (mirror beatvegas/hardrock.py).
const HR_KEYS = ["hardrockbet_fl", "hardrockbet"];

export type BookLine = { book: string; line: number; isHR: boolean };

export type Verdict = "good" | "fair" | "poor" | "no-hr";

export type LineCheckRow = {
  gameId: number;
  week: number;
  matchup: string;
  hrLine: number | null;
  best: number | null;
  median: number | null;
  delta: number | null; // hrLine - best (<= 0; how far HR sits below the best)
  verdict: Verdict;
  books: BookLine[]; // deduped, sorted by line desc (best first)
};

function median(xs: number[]): number | null {
  if (xs.length === 0) return null;
  const s = [...xs].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

function verdictFor(hr: number | null, best: number | null): Verdict {
  if (hr === null) return "no-hr";
  if (best === null) return "fair";
  if (hr >= best - 0.01) return "good"; // at or above the best total in the market
  if (hr >= best - 0.5) return "fair"; // within half a point
  return "poor"; // shading the total down vs the field
}

export async function getLineCheck(
  season: number,
  market: Market,
): Promise<LineCheckRow[]> {
  const dbMarket = MARKET_DB[market];
  // Latest line per (game, exact book key) for the market.
  const rows = await prisma.$queryRaw<
    {
      game_id: number | bigint;
      book: string | null;
      line: number | null;
      captured_at: string | null;
      week: number | bigint;
      away_team: string;
      home_team: string;
    }[]
  >`
    SELECT DISTINCT ON (o.game_id, o.book)
      o.game_id, o.book, o.line, CAST(o.captured_at AS TEXT) AS captured_at,
      g.week, g.away_team, g.home_team
    FROM odds_snapshots o JOIN games g ON g.id = o.game_id
    WHERE g.season = ${season} AND o.market = ${dbMarket}
    ORDER BY o.game_id, o.book, o.captured_at DESC
  `;

  type Acc = {
    week: number;
    matchup: string;
    // deduped by lowercased book name -> latest line + captured_at
    byBook: Map<string, { line: number; capturedAt: string }>;
  };
  const games = new Map<number, Acc>();

  for (const r of rows) {
    if (r.line === null || !r.book) continue;
    const gid = Number(r.game_id);
    const g =
      games.get(gid) ??
      ({
        week: Number(r.week),
        matchup: `${r.away_team} @ ${r.home_team}`,
        byBook: new Map(),
      } satisfies Acc);
    // Dedupe across book-name casing (Odds API lowercase vs legacy CFBD/DK
    // capitalized) — keep the most recently captured line.
    const key = r.book.toLowerCase();
    const prev = g.byBook.get(key);
    const cap = r.captured_at ?? "";
    if (!prev || cap > prev.capturedAt) {
      g.byBook.set(key, { line: r.line, capturedAt: cap });
    }
    games.set(gid, g);
  }

  const out: LineCheckRow[] = [];
  for (const [gameId, g] of games) {
    const books: BookLine[] = [...g.byBook.entries()].map(([book, v]) => ({
      book,
      line: v.line,
      isHR: HR_KEYS.includes(book),
    }));
    if (books.length === 0) continue;
    books.sort((a, b) => b.line - a.line);

    const lines = books.map((b) => b.line);
    const best = Math.max(...lines);
    const med = median(lines);
    const hr = HR_KEYS.map((k) => g.byBook.get(k)?.line).find(
      (l) => l !== undefined,
    );
    const hrLine = hr ?? null;

    out.push({
      gameId,
      week: g.week,
      matchup: g.matchup,
      hrLine,
      best,
      median: med,
      delta: hrLine === null ? null : Number((hrLine - best).toFixed(2)),
      verdict: verdictFor(hrLine, best),
      books,
    });
  }

  // Show games HR has priced first (actionable), then by week.
  out.sort((a, b) => {
    const ah = a.hrLine === null ? 1 : 0;
    const bh = b.hrLine === null ? 1 : 0;
    return ah - bh || a.week - b.week || a.matchup.localeCompare(b.matchup);
  });
  return out;
}
