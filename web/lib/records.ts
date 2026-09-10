import { unstable_cache } from "next/cache";
import { MODEL_VERSION } from "@/lib/model";
import { prisma } from "@/lib/prisma";

// Our own season records (plan Phase 1): one row per game, model-aligned —
// game meta + market line + our number (bv_line/gap) + the real 1H result and
// under/over outcome. Surfaced as an in-app grid + CSV export in Research. The
// full feature-frame export + immutable snapshots arrive with Phase 0's
// GameRecord; this is the decision-level record buildable from existing tables.

export type RecordRow = {
  season: number;
  week: number;
  away: string;
  home: string;
  fullGameTotal: number | null;
  spread: number | null;
  line: number | null; // the 1H line used at scoring
  bvLine: number | null; // our market-blind number
  bvGap: number | null; // line - bvLine (under direction)
  bvGapZ: number | null; // gap in residual sigmas
  underScore: number | null;
  rank: number | null;
  firstHalfTotal: number | null; // real 1H result
  outcome: "under" | "over" | "push" | null;
};

const num = (v: number | bigint | null | undefined): number | null =>
  v === null || v === undefined ? null : Number(v);

/** Exported for its test: this is what the CSV's last column means. */
export function outcome(
  fh: number | null,
  line: number | null,
): RecordRow["outcome"] {
  if (fh === null || line === null) return null;
  if (fh < line) return "under";
  if (fh > line) return "over";
  return "push";
}

export async function getRecordSeasons(): Promise<number[]> {
  // Seasons with content THIS GRID can show: a played game or a model row
  // (the grid's own JOIN below). Display-only derived_lines predictions must
  // NOT qualify — 8 June reference lines made prod default to 888 all-NULL
  // 2026 rows.
  const rows = await prisma.$queryRaw<{ season: number | bigint }[]>`
    SELECT DISTINCT g.season FROM games g
    WHERE g.first_half_total IS NOT NULL
       OR EXISTS (SELECT 1 FROM predictions p
                  WHERE p.game_id = g.id AND p.model_version = ${MODEL_VERSION})
    ORDER BY g.season DESC
  `;
  return rows.map((r) => Number(r.season));
}

async function getSeasonRecordsUncached(season: number): Promise<RecordRow[]> {
  const rows = await prisma.$queryRaw<
    {
      season: number | bigint;
      week: number | bigint;
      away_team: string;
      home_team: string;
      full_game_total: number | null;
      spread: number | null;
      first_half_total: number | bigint | null;
      line_used: number | null;
      bv_line: number | null;
      bv_gap: number | null;
      bv_sigma: number | null;
      under_score: number | bigint | null;
      rank: number | bigint | null;
    }[]
  >`
    SELECT g.season, g.week, g.away_team, g.home_team, g.full_game_total, g.spread,
           g.first_half_total, p.line_used, p.bv_line, p.bv_gap, p.bv_sigma,
           p.under_score, p.rank
    FROM games g
    LEFT JOIN predictions p
      ON p.game_id = g.id AND p.model_version = ${MODEL_VERSION}
    WHERE g.season = ${season}
    ORDER BY g.week, p.rank NULLS LAST, g.id
  `;
  return rows.map((r) => {
    const line = num(r.line_used);
    const fh = num(r.first_half_total);
    const bvGap = num(r.bv_gap);
    const bvSigma = num(r.bv_sigma);
    return {
      season: Number(r.season),
      week: Number(r.week),
      away: r.away_team,
      home: r.home_team,
      fullGameTotal: num(r.full_game_total),
      spread: num(r.spread),
      line,
      bvLine: num(r.bv_line),
      bvGap,
      bvGapZ:
        bvGap !== null && bvSigma
          ? Math.round((bvGap / bvSigma) * 100) / 100
          : null,
      underScore: num(r.under_score),
      rank: num(r.rank),
      firstHalfTotal: fh,
      outcome: outcome(fh, line),
    };
  });
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
  { key: "line", header: "line_1h" },
  { key: "bvLine", header: "bv_line" },
  { key: "bvGap", header: "bv_gap" },
  { key: "bvGapZ", header: "bv_gap_z" },
  { key: "underScore", header: "under_score" },
  { key: "rank", header: "rank" },
  { key: "firstHalfTotal", header: "first_half_total_actual" },
  { key: "outcome", header: "outcome" },
];

function csvCell(v: unknown): string {
  if (v === null || v === undefined) return "";
  const s = String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function recordsToCsv(rows: RecordRow[]): string {
  const head = CSV_COLUMNS.map((c) => c.header).join(",");
  const body = rows
    .map((r) => CSV_COLUMNS.map((c) => csvCell(r[c.key])).join(","))
    .join("\n");
  return `${head}\n${body}\n`;
}
