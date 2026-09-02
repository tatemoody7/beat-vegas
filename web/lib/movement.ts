import { Prisma } from "@prisma/client";
import { prisma } from "@/lib/prisma";

// Port of the "Line movement" tab in beatvegas/dashboard/app.py — per-game 1H
// line history, one series per book over captured_at. Rendered inline on the
// board cards (getMovements for a whole week); there is no standalone page.

export type MovementPoint = { t: string } & Record<string, number | string>;

export type Movement = {
  books: string[];
  points: MovementPoint[]; // pivoted: one row per captured_at, a column per book
  rows: { captured_at: string; book: string; line: number }[]; // ET-formatted, ordered
};

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
export function shortT(s: string): string {
  const m = s.match(/^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})/);
  if (!m) return s;
  const d = new Date(`${m[1]}T${m[2]}:00Z`);
  if (Number.isNaN(d.getTime())) return s;
  const p = Object.fromEntries(
    ET_FMT.formatToParts(d).map((x) => [x.type, x.value]),
  );
  return `${p.month}-${p.day} ${p.hour}:${p.minute}`;
}

type MoveSnap = {
  game_id: number | bigint;
  captured_at: string | null;
  book: string | null;
  line: number | null;
};

function pivot(snaps: MoveSnap[]): Movement {
  const books = new Set<string>();
  const byTime = new Map<string, MovementPoint>();
  const rows: Movement["rows"] = [];
  for (const s of snaps) {
    if (s.line === null || s.captured_at === null) continue;
    const book = (s.book ?? "?").toLowerCase();
    const t = shortT(s.captured_at);
    books.add(book);
    rows.push({ captured_at: t, book, line: s.line });
    const pt = byTime.get(t) ?? { t };
    pt[book] = s.line; // ordered ascending → last write wins (aggfunc="last")
    byTime.set(t, pt);
  }
  return { books: [...books], points: [...byTime.values()], rows };
}

// One query for a whole week's board: game id -> movement (only games with
// more than one snapshot, i.e. something to chart).
export async function getMovements(
  gameIds: number[],
): Promise<Map<number, Movement>> {
  const out = new Map<number, Movement>();
  if (gameIds.length === 0) return out;
  const snaps = await prisma.$queryRaw<MoveSnap[]>`
    SELECT game_id, CAST(captured_at AS TEXT) AS captured_at, book, line
    FROM odds_snapshots
    WHERE game_id IN (${Prisma.join(gameIds)}) AND market = '1H_total'
    ORDER BY game_id, captured_at
  `;
  const byGame = new Map<number, MoveSnap[]>();
  for (const s of snaps) {
    const gid = Number(s.game_id);
    if (!byGame.has(gid)) byGame.set(gid, []);
    byGame.get(gid)!.push(s);
  }
  for (const [gid, rows] of byGame) {
    if (rows.length < 2) continue;
    out.set(gid, pivot(rows));
  }
  return out;
}
