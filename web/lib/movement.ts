import { prisma } from "@/lib/prisma";

// Port of the "Line movement" tab in beatvegas/dashboard/app.py — per-game 1H
// line history, one series per book over captured_at.

export type MovementGame = {
  id: number;
  week: number;
  matchup: string;
  snaps: number;
};

export type MovementPoint = { t: string } & Record<string, number | string>;

export type Movement = {
  books: string[];
  points: MovementPoint[]; // pivoted: one row per captured_at, a column per book
  rows: { captured_at: string; book: string; line: number }[]; // raw, ordered
};

// Games with >1 snapshot for the season, labeled + sorted by week (app.py:180-186).
export async function getMovementGames(
  season: number,
): Promise<MovementGame[]> {
  const rows = await prisma.$queryRaw<
    {
      id: number | bigint;
      week: number | bigint;
      matchup: string;
      snaps: number | bigint;
    }[]
  >`
    SELECT g.id, g.week, g.away_team || ' @ ' || g.home_team AS matchup,
           COUNT(*) AS snaps
    FROM games g JOIN odds_snapshots o ON o.game_id = g.id
    WHERE g.season = ${season} AND o.market = '1H_total'
    GROUP BY g.id HAVING COUNT(*) > 1 ORDER BY g.week
  `;
  return rows.map((r) => ({
    id: Number(r.id),
    week: Number(r.week),
    matchup: r.matchup,
    snaps: Number(r.snaps),
  }));
}

// "2025-10-13 12:00:00.000000" (stored naive UTC) -> "10-13 08:00" in ET.
// Without the conversion every point on the movement chart reads 4-5h late
// for the Florida user actually timing these moves.
const ET_FMT = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/New_York",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});
function shortT(s: string): string {
  const m = s.match(/^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})/);
  if (!m) return s;
  const d = new Date(`${m[1]}T${m[2]}:00Z`);
  if (Number.isNaN(d.getTime())) return s;
  const p = Object.fromEntries(
    ET_FMT.formatToParts(d).map((x) => [x.type, x.value]),
  );
  return `${p.month}-${p.day} ${p.hour}:${p.minute}`;
}

export async function getMovement(gameId: number): Promise<Movement> {
  const snaps = await prisma.$queryRaw<
    { captured_at: string | null; book: string | null; line: number | null }[]
  >`
    SELECT CAST(captured_at AS TEXT) AS captured_at, book, line
    FROM odds_snapshots
    WHERE game_id = ${gameId} AND market = '1H_total'
    ORDER BY captured_at
  `;

  const books = new Set<string>();
  const byTime = new Map<string, MovementPoint>();
  const rows: Movement["rows"] = [];

  for (const s of snaps) {
    if (s.line === null || s.captured_at === null) continue;
    const book = s.book ?? "?";
    const t = shortT(s.captured_at);
    books.add(book);
    rows.push({ captured_at: s.captured_at, book, line: s.line });
    const pt = byTime.get(t) ?? { t };
    pt[book] = s.line; // ordered ascending → last write wins (aggfunc="last")
    byTime.set(t, pt);
  }

  return {
    books: [...books],
    points: [...byTime.values()],
    rows,
  };
}
