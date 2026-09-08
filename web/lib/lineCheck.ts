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

// Books excluded from the BOOK median fair price ON TOP of the ones every
// market read already drops. beatvegas/card.py FAIR_PRICE_EXCLUDED is the full
// list — Hard Rock (the book being judged), this sweepstakes book, the
// synthetic aggregate and the exchanges (they enter through the exchange-first
// path instead) — and the first, third and fourth are filtered by HR_KEYS,
// isSynthetic and isExchange below, so only the sweepstakes book is left here.
// tests/test_gate_parity.py asserts the two agree.
export const FAIR_PRICE_EXCLUDED_EXTRA = new Set(["fliff"]);
// A book is "comparable" to Hard Rock's number within this many points
// (card.py FAIR_PRICE_LINE_WINDOW / FAIR_PRICE_WIDE_WINDOW).
export const FAIR_PRICE_LINE_WINDOW = 0.5;
export const FAIR_PRICE_WIDE_WINDOW = 1.5;
// An exchange quote enters only when it is genuinely ~0-hold and still live
// (card.py EXCHANGE_MAX_HOLD / EXCHANGE_MAX_AGE_H): one wide illiquid two-way
// de-vigs to a fair under near 0.71 and a delisted quote stays "latest" forever.
export const EXCHANGE_MAX_HOLD = 0.02;
export const EXCHANGE_MAX_AGE_H = 24.0;

export type FairSource = "exchange" | "books";
export type FairObs = {
  line: number;
  overPrice: number | null;
  underPrice: number | null;
  /** Snapshot time; used only to age out stale exchange quotes. */
  capturedAt?: string | null;
};

const fairUnderOf = (o: FairObs): number | null =>
  o.overPrice === null || o.underPrice === null
    ? null
    : devigTwoWay(o.overPrice, o.underPrice).fairUnder;

const timeOf = (t: string | null | undefined): number | null => {
  if (!t) return null;
  const ms = Date.parse(t);
  return Number.isNaN(ms) ? null : ms;
};

/**
 * (points BELOW Hard Rock's line, points ABOVE it) a book may sit and still
 * price Hard Rock's number — mirrors card.py fair_price_window. Half a point
 * both ways, widened below to FAIR_PRICE_WIDE_WINDOW when Hard Rock is posting
 * ABOVE the market: that is the best case for an under and the case where no
 * book is within half a point by construction, so the price would be unjudgeable
 * and the game silently paper. A book at a LOWER total is a conservative
 * reference for an under (its fair under-probability is higher, so the price bar
 * it sets is harder) — clearing the gate against it cannot manufacture a bet a
 * like-for-like price would have blocked.
 */
export function fairPriceWindow(hrVsMarket: number | null): {
  below: number;
  above: number;
} {
  return {
    below:
      hrVsMarket !== null && hrVsMarket > 0
        ? FAIR_PRICE_WIDE_WINDOW
        : FAIR_PRICE_LINE_WINDOW,
    above: FAIR_PRICE_LINE_WINDOW,
  };
}

/**
 * The market's no-vig fair P(under) at Hard Rock's number — EXCHANGE-FIRST
 * (mirrors beatvegas/card.py market_read): the median of the tight, fresh
 * exchanges quoting Hard Rock's EXACT line, else the median over comparable
 * books (fairPriceWindow; Hard Rock, fliff, the synthetic aggregate and the
 * exchanges excluded), else null — the price cannot be judged.
 *
 * `now` is the instant the read is "as of" (epoch ms or a parseable string);
 * without one the newest snapshot in `byBook` stands in.
 */
export function marketFairUnderAt(
  hrLine: number | null,
  byBook: Map<string, FairObs>,
  now?: number | string | Date | null,
): { fairUnder: number | null; source: FairSource | null } {
  if (hrLine === null) return { fairUnder: null, source: null };
  // Hard Rock vs the OTHER books' median, which decides how far below Hard
  // Rock's line a book may sit (card.py hr_vs_market -> fair_price_window).
  const otherLines: number[] = [];
  for (const [key, o] of byBook) {
    const k = key.toLowerCase();
    if (HR_KEYS.includes(k) || isSynthetic(k)) continue;
    otherLines.push(o.line);
  }
  const others = median(otherLines);
  const { below, above } = fairPriceWindow(
    others === null ? null : hrLine - others,
  );
  const caps = [...byBook.values()]
    .map((o) => timeOf(o.capturedAt))
    .filter((t): t is number => t !== null);
  let refMs: number | null;
  if (now instanceof Date) refMs = now.getTime();
  else if (typeof now === "number") refMs = now;
  else refMs = timeOf(now) ?? (caps.length ? Math.max(...caps) : null);

  const exchange: number[] = [];
  const books: number[] = [];
  for (const [key, o] of byBook) {
    const k = key.toLowerCase();
    if (
      HR_KEYS.includes(k) ||
      isSynthetic(k) ||
      FAIR_PRICE_EXCLUDED_EXTRA.has(k) ||
      o.overPrice === null ||
      o.underPrice === null
    ) {
      continue;
    }
    const d = devigTwoWay(o.overPrice, o.underPrice);
    if (isExchange(k)) {
      // Same market only: exact line equality (a half point off is another total).
      if (Math.abs(o.line - hrLine) >= 1e-9) continue;
      // Tight enough to be a fair price, recent enough to be a live one. An
      // unknown capture time is not evidence of staleness — keep the quote.
      if (d.hold > EXCHANGE_MAX_HOLD) continue;
      const cap = timeOf(o.capturedAt);
      if (
        cap !== null &&
        refMs !== null &&
        refMs - cap > EXCHANGE_MAX_AGE_H * 3600_000
      ) {
        continue;
      }
      exchange.push(d.fairUnder);
    } else if (o.line - hrLine <= above && hrLine - o.line <= below) {
      books.push(d.fairUnder);
    }
  }
  // MEDIAN, so one odd quote among three or more cannot drag the fair price
  // (for one or two quotes the median IS the mean).
  const ex = median(exchange);
  if (ex !== null) return { fairUnder: ex, source: "exchange" };
  const med = median(books);
  return { fairUnder: med, source: med === null ? null : "books" };
}

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
      -- pre-kickoff only: a poll that ran after kickoff captures an in-game
      -- number (e.g. u31.5 -275 at halftime) that must never read as the line
      AND (g.start_date IS NULL OR o.captured_at <= g.start_date)
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
    // under at Hard Rock's number: tight, fresh exchanges at the exact line
    // first, else the comparable books (fairPriceWindow) — the same read as the
    // card (beatvegas/card.py), so the site and the card never disagree on EV.
    // No `now`: this page renders whole seasons, so each game's own newest
    // snapshot is the instant its exchange quotes are aged against.
    const hrUnderPrice = hrObs?.underPrice ?? null;
    const marketFairUnder = marketFairUnderAt(hrLine, g.byBook).fairUnder;
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
