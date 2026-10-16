import { prisma } from "@/lib/prisma";
import { utcFrom } from "@/lib/armPositions";

// The Board's top-10 analysis (H-1H-SHORTLIST; Tate 2026-10-15, reshaped
// 2026-10-16): the frozen read of every game a scheduled card rated, written
// once per card by scripts/publish_shortlist.py into `shortlist_entries`. The
// site shows an entry on the game page of the Board's #1-#10 and never
// re-prices or relabels it. Every number is an estimate, worded as one.

export const LABEL_POTENTIAL = "Potential positive market value";
export const LABEL_FAIR = "Fair price";
export const LABEL_EXPENSIVE = "Expensive";
export const LABEL_INSUFFICIENT = "Insufficient pricing data";

export type ShortlistStat = {
  key: string;
  words: string;
  value: number | null;
  pct: number | null;
  scoring: "less" | "more" | null;
  verdict: string;
};

export type ShortlistPrice = {
  hr_line: number;
  hr_under: number;
  hr_over: number | null;
  hr_quote_at: string | null;
  hr_confirmed_at?: string;
  hr_age_h?: number;
  breakeven: number;
  hr_hold: number | null;
  ref_books?: string[];
  best_other_under?: number | null;
  ev_point?: number;
  ev_table_low?: number;
  range_low?: number;
  range_high?: number;
  ref_line?: number;
  fair_under?: number | null;
  status: string;
};

export type ShortlistQuote = { line: number; under: number; at: string } | null;

export type ShortlistEntry = {
  game_id: number;
  matchup: string;
  kick: string;
  rank: number;
  why_rank: string;
  label: string;
  price: ShortlistPrice;
  model: {
    bv_line: number | null;
    market_line: number | null;
    gap: number | null;
  };
  first_hr: ShortlistQuote;
  latest_hr: ShortlistQuote;
  analysis: {
    stats: ShortlistStat[];
    situational: {
      min_rest_days: number | null;
      either_off_bye: number | null;
      either_short_week: number | null;
      away_travel_km: number | null;
      kick_local_hour: number | null;
    };
    est_1h_possessions: number | null;
    weather: {
      dome: boolean;
      wind_mph?: number | null;
      gust_mph?: number | null;
      temperature_f?: number | null;
      precipitation_mm?: number | null;
      fetched_at?: string | null;
      scoring?: "less" | "more" | null;
      verdict?: string;
    } | null;
    qb: { out: boolean; detail: string };
  };
};

export type Shortlist = {
  cardId: number;
  slot: string;
  publishedAt: Date;
  cardBuilt: Date | null;
  pool: number;
  sha256: string;
  entries: ShortlistEntry[];
  /** A newer scheduled card for the same week has no publication yet (a
   *  missed publish, adjustment 2): the page says so instead of hiding it. */
  newerCardMissing: boolean;
};

type Row = {
  card_id: number;
  slot: string;
  published_at: string;
  card_built: string | null;
  pool_size: number | null;
  publication_sha256: string;
  payload_json: string;
  newest_card: number | null;
};

/** Pure: stored rows (one publication) -> the page's shape. */
export function shortlistFrom(rows: Row[]): Shortlist | null {
  if (rows.length === 0) return null;
  const r0 = rows[0];
  const entries = rows
    .map((r) => JSON.parse(r.payload_json) as ShortlistEntry)
    .sort((a, b) => a.rank - b.rank);
  return {
    cardId: r0.card_id,
    slot: r0.slot,
    publishedAt: utcFrom(r0.published_at),
    cardBuilt: r0.card_built ? utcFrom(r0.card_built) : null,
    pool: r0.pool_size ?? entries.length,
    sha256: r0.publication_sha256,
    entries,
    newerCardMissing: r0.newest_card !== null && r0.newest_card > r0.card_id,
  };
}

const isMissingTable = (e: unknown): boolean =>
  typeof e === "object" &&
  e !== null &&
  String((e as { message?: string }).message ?? "").includes("does not exist");

/** The newest publication for a season and week; null when there is none (or
 *  the table is not there yet). Never throws for a missing table, so the Board
 *  renders unchanged without it (adjustment 2). */
export async function getShortlist(
  season: number,
  week: number,
): Promise<Shortlist | null> {
  try {
    const rows = await prisma.$queryRaw<Row[]>`
      WITH pub AS (
        SELECT max(card_id) AS card_id FROM shortlist_entries
        WHERE season = ${season} AND week = ${week}
      ),
      newest AS (
        SELECT max(id) AS id FROM cards
        WHERE season = ${season} AND week = ${week}
          AND payload::jsonb->>'slot' IN ('tue_pm', 'thu_pm', 'fri_pm', 'sat_am')
      )
      SELECT e.card_id, e.slot, CAST(e.published_at AS TEXT) AS published_at,
             e.card_built, e.pool_size, e.publication_sha256, e.payload_json,
             (SELECT id FROM newest) AS newest_card
      FROM shortlist_entries e
      WHERE e.card_id = (SELECT card_id FROM pub)
      ORDER BY e.rank`;
    return shortlistFrom(rows);
  } catch (e) {
    if (isMissingTable(e)) return null;
    throw e;
  }
}

// --- words --------------------------------------------------------------------

export const pctText = (x: number | null | undefined, dp = 1): string =>
  x === null || x === undefined
    ? "—"
    : `${x > 0 ? "+" : ""}${(100 * x).toFixed(dp)}%`;

/** "estimated EV +1.8% (rough range 0.0% to +3.9%)"; never a bare EV. */
export function evText(p: ShortlistPrice): string {
  if (p.ev_point === undefined) return "no estimate (incomplete pricing)";
  const range =
    p.range_low !== undefined && p.range_high !== undefined
      ? ` (rough range ${pctText(p.range_low)} to ${pctText(p.range_high)})`
      : "";
  return `estimated EV ${pctText(p.ev_point)}${range}`;
}

/** Ordinal percentile, "11th percentile". */
export function ordinal(n: number): string {
  const v = n % 100;
  const suf =
    v >= 11 && v <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" }[n % 10] ?? "th");
  return `${n}${suf}`;
}

export function scoringText(s: "less" | "more" | null | undefined): string {
  if (s === "less") return "points to less scoring";
  if (s === "more") return "points to more scoring";
  return "middle third";
}

/** The screen's verdict in words: no factor has been shown to beat the line. */
export function verdictText(v: string | undefined): string {
  if (v === "null") return "not shown to beat the line";
  if (v === "preliminary") return "a preliminary association, untested forward";
  if (v === "candidate") return "a candidate, awaiting a forward test";
  return "not screened";
}
