import { isCentredQuote } from "@/lib/devig";
import { Prisma } from "@prisma/client";
import { median } from "@/lib/format";
import { prisma } from "@/lib/prisma";

// Per-game line history for the game page (getMovements for a whole week;
// there is no standalone page). Two markets per game:
//   * first half (1H_total) — the market we bet: open → current per book and
//     by consensus (the BookTable on /game/[id]);
//   * full game (full_game_total) — context only: consensus open → current
//     total and spread.
// The per-book time-series chart that used to sit under the table is gone
// (Tate, 2026-09-13: it "looks like scribbles"); the per-book list is the
// movement read, and it stays.

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
};

export type Movement = {
  /** First-half open → current summary; null when no 1H line was captured. */
  firstHalf: MarketMovement | null;
  /** Full-game total + spread movement; null when none captured. */
  fullGame: MarketMovement | null;
};

export type MoveSnap = {
  game_id: number | bigint;
  captured_at: string | null;
  book: string | null;
  line: number | null;
  over_price?: number | null;
  under_price?: number | null;
  spread?: number | null;
  market?: string | null;
};

/**
 * Open → current per book and by consensus for one market's snapshots
 * (ascending by captured_at). Pure; the CFBD synthetic "consensus" row is
 * dropped so it cannot double-count the real books. Null when nothing usable.
 */
export function summarizeMarket(snaps: MoveSnap[]): MarketMovement | null {
  const byBook = new Map<string, MoveSnap[]>();
  for (const s of snaps) {
    if (s.line === null || s.line === undefined) continue;
    // Drop off-centre rungs so the market open/cur is the real market. The
    // per-book table below still shows every book its own quote.
    if (!isCentredQuote(s.over_price, s.under_price)) continue;
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
  return {
    open: median(books.map((b) => b.open)),
    cur: median(books.map((b) => b.cur)),
    spreadOpen: median(spreads((b) => b.openSpread)),
    spreadCur: median(spreads((b) => b.curSpread)),
    books,
  };
}

/** Pure: build one game's Movement from its 1H and full-game snapshots. */
export function buildMovement(
  firstHalf: MoveSnap[],
  fullGame: MoveSnap[],
): Movement {
  return {
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
           over_price, under_price, spread, market
    FROM odds_snapshots o
    WHERE o.game_id IN (${Prisma.join(gameIds)})
      AND o.market IN ('1H_total', 'full_game_total')
      -- pre-kickoff only: in-game captures are not line movement
      AND o.captured_at <= COALESCE(
        (SELECT g.start_date FROM games g WHERE g.id = o.game_id), o.captured_at)
    ORDER BY o.game_id, o.captured_at
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
