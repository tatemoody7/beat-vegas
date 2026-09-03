import { Prisma } from "@prisma/client";
import { median } from "@/lib/format";
import { prisma } from "@/lib/prisma";

// Per-game line history for the board cards (getMovements for a whole week;
// there is no standalone page). Two markets per game:
//   * first half (1H_total) — the market we bet: a per-book series for the
//     chart plus open → current per book and by consensus;
//   * full game (full_game_total) — context only: consensus open → current
//     total and spread, plus the per-book series.
// The 1H `books` / `points` / `rows` shape is unchanged (MovementChart reads it).

export type MovementPoint = { t: string } & Record<string, number | string>;

/** One book's first and latest capture of a market. */
export type BookMove = {
  book: string;
  open: number;
  cur: number;
  /** Spread at the first / latest capture (full-game rows only; null when absent). */
  openSpread: number | null;
  curSpread: number | null;
  /** Number of captures. */
  n: number;
};

export type MarketMovement = {
  /** Consensus (median across books) of each book's first capture. */
  open: number | null;
  /** Consensus of each book's latest capture. */
  cur: number | null;
  spreadOpen: number | null;
  spreadCur: number | null;
  books: BookMove[];
  /** Pivoted per-book series (one row per capture time) for a chart. */
  series: { books: string[]; points: MovementPoint[] };
};

export type Movement = {
  // --- first half (unchanged shape, read by MovementChart) -----------------
  books: string[];
  points: MovementPoint[]; // pivoted: one row per captured_at, a column per book
  rows: { captured_at: string; book: string; line: number }[]; // ET-formatted, ordered
  /** First-half open → current summary; null when no 1H line was captured. */
  firstHalf: MarketMovement | null;
  /** Full-game total + spread movement; null when none captured. */
  fullGame: MarketMovement | null;
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

export type MoveSnap = {
  game_id: number | bigint;
  captured_at: string | null;
  book: string | null;
  line: number | null;
  spread?: number | null;
  market?: string | null;
};

function pivot(snaps: MoveSnap[]): Pick<Movement, "books" | "points" | "rows"> {
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

/**
 * Open → current per book and by consensus for one market's snapshots
 * (ascending by captured_at). Pure; the CFBD synthetic "consensus" row is
 * dropped so it cannot double-count the real books. Null when nothing usable.
 */
export function summarizeMarket(snaps: MoveSnap[]): MarketMovement | null {
  const byBook = new Map<string, MoveSnap[]>();
  for (const s of snaps) {
    if (s.line === null || s.line === undefined) continue;
    const book = (s.book ?? "?").toLowerCase();
    if (book === "consensus") continue;
    if (!byBook.has(book)) byBook.set(book, []);
    byBook.get(book)!.push(s);
  }
  if (byBook.size === 0) return null;
  const books: BookMove[] = [];
  for (const [book, caps] of byBook) {
    caps.sort((a, b) =>
      (a.captured_at ?? "").localeCompare(b.captured_at ?? ""),
    );
    const first = caps[0];
    const last = caps[caps.length - 1];
    books.push({
      book,
      open: Number(first.line),
      cur: Number(last.line),
      openSpread: first.spread ?? null,
      curSpread: last.spread ?? null,
      n: caps.length,
    });
  }
  books.sort((a, b) => b.cur - a.cur || a.book.localeCompare(b.book));
  const spreads = (pick: (b: BookMove) => number | null) =>
    books.map(pick).filter((v): v is number => v !== null);
  const kept = snaps.filter(
    (s) => (s.book ?? "?").toLowerCase() !== "consensus",
  );
  const piv = pivot(kept);
  return {
    open: median(books.map((b) => b.open)),
    cur: median(books.map((b) => b.cur)),
    spreadOpen: median(spreads((b) => b.openSpread)),
    spreadCur: median(spreads((b) => b.curSpread)),
    books,
    series: { books: piv.books, points: piv.points },
  };
}

/** Pure: build one game's Movement from its 1H and full-game snapshots. */
export function buildMovement(
  firstHalf: MoveSnap[],
  fullGame: MoveSnap[],
): Movement {
  return {
    ...pivot(firstHalf),
    firstHalf: summarizeMarket(firstHalf),
    fullGame: summarizeMarket(fullGame),
  };
}

// One query for a whole week's board: game id -> movement, for every game with
// at least one first-half or full-game snapshot.
export async function getMovements(
  gameIds: number[],
): Promise<Map<number, Movement>> {
  const out = new Map<number, Movement>();
  if (gameIds.length === 0) return out;
  const snaps = await prisma.$queryRaw<MoveSnap[]>`
    SELECT game_id, CAST(captured_at AS TEXT) AS captured_at, book, line,
           spread, market
    FROM odds_snapshots
    WHERE game_id IN (${Prisma.join(gameIds)})
      AND market IN ('1H_total', 'full_game_total')
    ORDER BY game_id, captured_at
  `;
  const byGame = new Map<number, { fh: MoveSnap[]; fg: MoveSnap[] }>();
  for (const s of snaps) {
    const gid = Number(s.game_id);
    if (!byGame.has(gid)) byGame.set(gid, { fh: [], fg: [] });
    const g = byGame.get(gid)!;
    if (s.market === "full_game_total") g.fg.push(s);
    else g.fh.push(s);
  }
  for (const [gid, g] of byGame) {
    if (g.fh.length === 0 && g.fg.length === 0) continue;
    out.set(gid, buildMovement(g.fh, g.fg));
  }
  return out;
}
