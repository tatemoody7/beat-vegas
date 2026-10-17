import { unstable_cache } from "next/cache";
import { csvCell } from "@/lib/format";
import { MARKET_LEDGER_1H, MODEL_VERSION, SITE_MIN_SEASON } from "@/lib/model";
import { trustedFirstHalf } from "@/lib/grade";
import { recordFrom, type Record3 } from "@/lib/record";

export { trustedFirstHalf };
import { prisma } from "@/lib/prisma";

// Our own season records (plan Phase 1): one row per game, model-aligned —
// game meta + our number + the real 1H result, graded two ways and never mixed
// (fact-check audit 2026-10-17): Hard Rock Records on Hard Rock's own line and
// price at the last scheduled card, and Market Research on the consensus close. Surfaced as an in-app grid + CSV export in Research. The
// full feature-frame export + immutable snapshots arrive with Phase 0's
// GameRecord; this is the decision-level record buildable from existing tables.

export type RecordRow = {
  season: number;
  week: number;
  away: string;
  home: string;
  /** Games.id; the join key, not a CSV column. */
  gameId: number;
  fullGameTotal: number | null;
  spread: number | null;
  bvLine: number | null; // our market-blind number
  rank: number | null;
  /** The real first half, only when the grader would trust it (a 0-0 half
   *  needs its proof, `ZERO_PROVEN_SOURCES`); null otherwise. */
  firstHalfTotal: number | null;
  // --- Hard Rock Records (fact-check audit 2026-10-17, Tate: decision time =
  // the last SCHEDULED card built before kickoff). Hard Rock's MAIN first-half
  // line and under price as that card froze them. Null = no verified Hard Rock
  // line: the game is out of every Hard Rock figure, never given a substitute.
  hrLine: number | null;
  hrPrice: number | null;
  /** hrLine minus our number; positive leans under. */
  hrGap: number | null;
  hrOutcome: "under" | "over" | "push" | null;
  /** One unit on the under at hrPrice: +win, -1 loss, 0 push. */
  hrUnits: number | null;
  // --- Market Research: the judge's consensus close (results market row,
  // beatvegas.consensus.market_close). A benchmark, never a bet: no price.
  consLine: number | null;
  consGap: number | null;
  consOutcome: "under" | "over" | "push" | null;
  /** Our number was produced AFTER kickoff (a retro re-score, e.g. 2026 week 1):
   *  accuracy only, never a decision the board could have acted on. Null when
   *  either timestamp is missing. */
  scoredAfterKickoff: boolean | null;
  /** Kickoff as epoch ms (survives the cache's JSON round trip); null when
   *  unknown. Read by `lib/signalGate.gateRecords`; not a CSV column. */
  kickoffMs: number | null;
};

/** Exported for its test: one unit on the under at an American price. */
export function underUnits(
  result: RecordRow["hrOutcome"],
  price: number | null,
): number | null {
  if (result === null || price === null || price === 0) return null;
  if (result === "push") return 0;
  if (result === "over") return -1;
  return price > 0 ? price / 100 : 100 / Math.abs(price);
}

const round2 = (v: number) => Math.round(v * 100) / 100;

const num = (v: number | bigint | null | undefined): number | null =>
  v === null || v === undefined ? null : Number(v);

/** Exported for its test: this is what the CSV's last column means. */
export function outcome(
  fh: number | null,
  line: number | null,
): RecordRow["hrOutcome"] {
  if (fh === null || line === null) return null;
  if (fh < line) return "under";
  if (fh > line) return "over";
  return "push";
}

/** Exported for its test. True when the prediction was created after the game
 *  kicked off (a retro re-score); null when either side is unknown. */
export function scoredAfter(
  createdAt: Date | string | null | undefined,
  startDate: Date | string | null | undefined,
): boolean | null {
  if (createdAt == null || startDate == null) return null;
  const c = new Date(createdAt).getTime();
  const k = new Date(startDate).getTime();
  if (Number.isNaN(c) || Number.isNaN(k)) return null;
  return c > k;
}

/** Exported for its test. Epoch ms of a kickoff, or null when unknown. */
export function kickoffMs(
  startDate: Date | string | null | undefined,
): number | null {
  if (startDate == null) return null;
  // A naive string is UTC (never hand one to Date without a zone).
  const k =
    typeof startDate === "string" && !/[zZ]|[+-]\d\d:?\d\d$/.test(startDate)
      ? Date.parse(`${startDate.replace(" ", "T")}Z`)
      : new Date(startDate).getTime();
  return Number.isNaN(k) ? null : k;
}

/** The week the records grid opens on: the LATEST week with a graded game.
 *  The season's schedule is present to week 15 from day one, so "the last
 *  week present" opened on one pending Navy @ Army row in September (Tate
 *  2026-09-16). Null when nothing has been graded; the page then falls back to
 *  the last week. */
export function defaultWeek(
  rows: Pick<RecordRow, "week" | "firstHalfTotal">[],
): number | null {
  let best: number | null = null;
  for (const r of rows) {
    if (r.firstHalfTotal !== null && (best === null || r.week > best))
      best = r.week;
  }
  return best;
}

export async function getRecordSeasons(): Promise<number[]> {
  // Seasons with content THIS GRID can show: a played game or a model row
  // (the grid's own JOIN below). Display-only derived_lines predictions must
  // NOT qualify — 8 June reference lines made prod default to 888 all-NULL
  // 2026 rows.
  const rows = await prisma.$queryRaw<{ season: number | bigint }[]>`
    SELECT DISTINCT g.season FROM games g
    WHERE g.season >= ${SITE_MIN_SEASON}
      AND (g.first_half_total IS NOT NULL
           OR EXISTS (SELECT 1 FROM predictions p
                      WHERE p.game_id = g.id AND p.model_version = ${MODEL_VERSION}))
    ORDER BY g.season DESC
  `;
  return rows.map((r) => Number(r.season));
}

export type HrQuote = { line: number; price: number };

/** Hard Rock's main line and under price as the last SCHEDULED card built
 *  before each game's kickoff froze them (card.py `hr_line` / `hr_price` are
 *  the main line, never an alternate rung). Only cards carry Hard Rock, so a
 *  season before the first card has none. */
export async function hardRockAtLastCard(
  season: number,
  week?: number,
): Promise<Map<number, HrQuote>> {
  const rows = await prisma.$queryRaw<
    { gid: number | bigint; hr_line: number | null; hr_price: number | null }[]
  >`
    SELECT DISTINCT ON ((i->>'game_id')::int)
           (i->>'game_id')::int AS gid,
           (i->>'hr_line')::float AS hr_line,
           (i->>'hr_price')::int AS hr_price
    FROM cards c
    CROSS JOIN LATERAL jsonb_array_elements(c.payload::jsonb -> 'items') i
    JOIN games g ON g.id = (i->>'game_id')::int
    WHERE c.season = ${season}
      AND (${week ?? null}::int IS NULL OR c.week = ${week ?? null}::int)
      AND COALESCE(c.payload::jsonb ->> 'slot', '') <> 'manual'
      AND c.built_at < g.start_date
      AND i->>'hr_line' IS NOT NULL AND i->>'hr_price' IS NOT NULL
    ORDER BY (i->>'game_id')::int, c.built_at DESC
  `;
  const out = new Map<number, HrQuote>();
  for (const r of rows) {
    if (r.hr_line === null || r.hr_price === null) continue;
    out.set(Number(r.gid), { line: Number(r.hr_line), price: Number(r.hr_price) });
  }
  return out;
}

async function getSeasonRecordsUncached(season: number): Promise<RecordRow[]> {
  const [rows, hr] = await Promise.all([
    prisma.$queryRaw<
      {
        id: number | bigint;
        season: number | bigint;
        week: number | bigint;
        away_team: string;
        home_team: string;
        full_game_total: number | null;
        spread: number | null;
        first_half_total: number | bigint | null;
        first_half_source: string | null;
        home_points: number | bigint | null;
        away_points: number | bigint | null;
        bv_line: number | null;
        rank: number | bigint | null;
        created_at: Date | string | null;
        start_date: Date | string | null;
        cons_line: number | null;
      }[]
    >`
      SELECT g.id, g.season, g.week, g.away_team, g.home_team, g.full_game_total,
             g.spread, g.first_half_total, g.first_half_source, g.home_points,
             g.away_points, p.bv_line, p.rank, p.created_at, g.start_date,
             r.closing_line AS cons_line
      FROM games g
      LEFT JOIN predictions p
        ON p.game_id = g.id AND p.model_version = ${MODEL_VERSION}
      LEFT JOIN results r
        ON r.game_id = g.id AND r.model_version = ${MARKET_LEDGER_1H}
      WHERE g.season = ${season}
      ORDER BY g.week, p.rank NULLS LAST, g.id
    `,
    hardRockAtLastCard(season),
  ]);
  return rows.map((r) => {
    const gameId = Number(r.id);
    const fh = trustedFirstHalf(
      num(r.first_half_total),
      num(r.home_points),
      num(r.away_points),
      r.first_half_source,
    );
    const bvLine = num(r.bv_line);
    const q = hr.get(gameId) ?? null;
    const hrOutcome = outcome(fh, q?.line ?? null);
    const consLine = num(r.cons_line);
    const gap = (line: number | null) =>
      line !== null && bvLine !== null ? round2(line - bvLine) : null;
    return {
      season: Number(r.season),
      week: Number(r.week),
      away: r.away_team,
      home: r.home_team,
      gameId,
      fullGameTotal: num(r.full_game_total),
      spread: num(r.spread),
      bvLine,
      rank: num(r.rank),
      firstHalfTotal: fh,
      hrLine: q?.line ?? null,
      hrPrice: q?.price ?? null,
      hrGap: gap(q?.line ?? null),
      hrOutcome,
      hrUnits: underUnits(hrOutcome, q?.price ?? null),
      consLine,
      consGap: gap(consLine),
      consOutcome: outcome(fh, consLine),
      scoredAfterKickoff: scoredAfter(r.created_at, r.start_date),
      kickoffMs: kickoffMs(r.start_date),
    };
  });
}

export type ViewTotals = {
  /** Played, rated games with the view's line, and those without one. */
  graded: number;
  missing: number;
  record: Record3 | null;
};

/** The season line above each view. Hard Rock: units at Hard Rock's price.
 *  Market Research: the record only -- no one can bet the consensus. */
export function viewTotals(rows: RecordRow[], view: "hr" | "market"): ViewTotals {
  const played = rows.filter((r) => r.firstHalfTotal !== null && r.bvLine !== null);
  const outcomeOf = (r: RecordRow) => (view === "hr" ? r.hrOutcome : r.consOutcome);
  const graded = played.filter((r) => outcomeOf(r) !== null);
  return {
    graded: graded.length,
    missing: played.length - graded.length,
    record: recordFrom(
      graded.map((r) => ({
        result: outcomeOf(r),
        units: view === "hr" ? r.hrUnits : null,
        clv: null,
        stake: view === "hr" ? 1 : 0,
      })),
    ),
  };
}

// History view — slow-changing (updates at most weekly), so cache the DB scan.
export const getSeasonRecords = unstable_cache(
  getSeasonRecordsUncached,
  ["season-records"],
  { revalidate: 3600 },
);

const CSV_COLUMNS: { key: keyof RecordRow; header: string }[] = [
  { key: "season", header: "season" },
  { key: "week", header: "week" },
  { key: "away", header: "away" },
  { key: "home", header: "home" },
  { key: "fullGameTotal", header: "full_game_total" },
  { key: "spread", header: "spread" },
  { key: "bvLine", header: "bv_line" },
  // under_score left the CSV on 2026-10-04 with the classifier (docs/CLASSIFIER_RETIREMENT.md);
  // the scoring-time line (line_1h, bv_gap, outcome) left it on 2026-10-17: it
  // was a derived or proxy number no book posted (fact-check audit).
  { key: "rank", header: "rank" },
  { key: "hrLine", header: "hr_line_last_card" },
  { key: "hrPrice", header: "hr_price_last_card" },
  { key: "hrGap", header: "hr_gap" },
  { key: "hrOutcome", header: "hr_result" },
  { key: "hrUnits", header: "hr_units" },
  { key: "consLine", header: "consensus_close" },
  { key: "consGap", header: "consensus_gap" },
  { key: "consOutcome", header: "consensus_result" },
  { key: "firstHalfTotal", header: "first_half_total_actual" },
  { key: "scoredAfterKickoff", header: "scored_after_kickoff" },
];

export function recordsToCsv(rows: RecordRow[]): string {
  const head = CSV_COLUMNS.map((c) => c.header).join(",");
  const body = rows
    .map((r) => CSV_COLUMNS.map((c) => csvCell(r[c.key])).join(","))
    .join("\n");
  return `${head}\n${body}\n`;
}
