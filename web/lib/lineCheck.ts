import { EV_FLOOR } from "@/lib/verdict";
import { isExchange, isSynthetic } from "@/lib/books";
import { devigTwoWay, evUnder } from "@/lib/devig";
import { median } from "@/lib/format";
import { prisma } from "@/lib/prisma";

// "Line Check" — is Hard Rock giving Tate a good number vs the rest of the market?
// He can only bet Hard Rock (Florida), so this is a quality/CLV check, not price
// shopping. For an UNDER, a HIGHER total at HR is better. The line verdict is HR
// vs the BEST (highest) total available; the EV verdict (devig) asks whether HR's
// under PRICE clears the market's no-vig fair-under at a comparable number.

export type Market = "full_game" | "1h";

const MARKET_DB: Record<Market, string> = {
  full_game: "full_game_total",
  "1h": "1H_total",
};

// Hard Rock's live Odds API key (mirror beatvegas/hardrock.py). The docs'
// `hardrockbet_fl` never appears in the feed, so it is not listed.
const HR_KEYS = ["hardrockbet"];

export type BookLine = {
  book: string;
  line: number;
  isHR: boolean;
  isExchange: boolean; // no-vig CFTC exchange (comparison only, never bet)
  underPrice: number | null;
  fairUnder: number | null; // no-vig fair under prob from this book's two sides
};

export type Verdict = "good" | "fair" | "poor" | "no-hr";
// EV verdict: HR's under price vs the market no-vig fair-under at HR's number.
export type EvVerdict = "pos" | "fair" | "neg" | "na";

export type LineCheckRow = {
  gameId: number;
  week: number;
  matchup: string;
  hrLine: number | null;
  best: number | null;
  median: number | null;
  delta: number | null; // hrLine - best (<= 0; how far HR sits below the best)
  verdict: Verdict;
  // Devig / EV layer:
  hrUnderPrice: number | null;
  marketFairUnder: number | null; // consensus no-vig fair-under at HR's line
  ev: number | null; // per-$1 EV of HR's under vs marketFairUnder
  evVerdict: EvVerdict;
  books: BookLine[]; // deduped, sorted by line desc (best first)
};

function verdictFor(hr: number | null, best: number | null): Verdict {
  if (hr === null) return "no-hr";
  if (best === null) return "fair";
  if (hr >= best - 0.01) return "good"; // at or above the best total in the market
  if (hr >= best - 0.5) return "fair"; // within half a point
  return "poor"; // shading the total down vs the field
}

export function evVerdictFor(ev: number | null): EvVerdict {
  if (ev === null) return "na";
  if (ev > 0.005) return "pos"; // HR's under clears the market's fair price
  if (ev < EV_FLOOR) return "neg"; // worse than standard juice vs the fair price
  return "fair";
}

export async function getLineCheck(
  season: number,
  market: Market,
): Promise<LineCheckRow[]> {
  const dbMarket = MARKET_DB[market];
  // Latest line per (game, case-folded book key) for the market. The CFBD
  // synthetic "consensus" aggregate is not a book anyone can bet and would
  // double-count the real ones, so it never enters the market read.
  const rows = await prisma.$queryRaw<
    {
      game_id: number | bigint;
      book: string | null;
      line: number | null;
      over_price: number | bigint | null;
      under_price: number | bigint | null;
      captured_at: string | null;
      week: number | bigint;
      away_team: string;
      home_team: string;
    }[]
  >`
    SELECT DISTINCT ON (o.game_id, LOWER(o.book))
      o.game_id, LOWER(o.book) AS book, o.line, o.over_price, o.under_price,
      CAST(o.captured_at AS TEXT) AS captured_at,
      g.week, g.away_team, g.home_team
    FROM odds_snapshots o JOIN games g ON g.id = o.game_id
    WHERE g.season = ${season} AND o.market = ${dbMarket}
      AND LOWER(COALESCE(o.book, '')) <> 'consensus'
    ORDER BY o.game_id, LOWER(o.book), o.captured_at DESC
  `;

  type BookObs = {
    line: number;
    overPrice: number | null;
    underPrice: number | null;
    capturedAt: string;
  };
  type Acc = {
    week: number;
    matchup: string;
    // deduped by lowercased book name -> latest observation
    byBook: Map<string, BookObs>;
  };
  const games = new Map<number, Acc>();

  for (const r of rows) {
    if (r.line === null || !r.book || isSynthetic(r.book)) continue;
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
      g.byBook.set(key, {
        line: r.line,
        overPrice: r.over_price === null ? null : Number(r.over_price),
        underPrice: r.under_price === null ? null : Number(r.under_price),
        capturedAt: cap,
      });
    }
    games.set(gid, g);
  }

  const out: LineCheckRow[] = [];
  for (const [gameId, g] of games) {
    const fairUnderOf = (o: BookObs): number | null =>
      o.overPrice === null || o.underPrice === null
        ? null
        : devigTwoWay(o.overPrice, o.underPrice).fairUnder;

    const books: BookLine[] = [...g.byBook.entries()].map(([book, v]) => ({
      book,
      line: v.line,
      isHR: HR_KEYS.includes(book),
      isExchange: isExchange(book),
      underPrice: v.underPrice,
      fairUnder: fairUnderOf(v),
    }));
    if (books.length === 0) continue;
    books.sort((a, b) => b.line - a.line);

    const lines = books.map((b) => b.line);
    const best = Math.max(...lines);
    const med = median(lines);
    const hrObs = HR_KEYS.map((k) => g.byBook.get(k)).find(
      (o) => o !== undefined,
    );
    const hrLine = hrObs?.line ?? null;

    // Devig / EV layer. Compare HR's under price to the market's no-vig fair
    // under at a COMPARABLE number (other books within half a point of HR's
    // line) — keeps it apples-to-apples rather than mixing different totals.
    const hrUnderPrice = hrObs?.underPrice ?? null;
    const comparable =
      hrLine === null
        ? []
        : [...g.byBook.entries()]
            .filter(([k]) => !HR_KEYS.includes(k))
            .map(([, o]) => o)
            .filter((o) => Math.abs(o.line - hrLine) <= 0.5)
            .map(fairUnderOf)
            .filter((f): f is number => f !== null);
    const marketFairUnder = median(comparable);
    const ev =
      marketFairUnder !== null && hrUnderPrice !== null
        ? evUnder(marketFairUnder, hrUnderPrice)
        : null;

    out.push({
      gameId,
      week: g.week,
      matchup: g.matchup,
      hrLine,
      best,
      median: med,
      delta: hrLine === null ? null : Number((hrLine - best).toFixed(2)),
      verdict: verdictFor(hrLine, best),
      hrUnderPrice,
      marketFairUnder,
      ev,
      evVerdict: evVerdictFor(ev),
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
