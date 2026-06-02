import { prisma } from "@/lib/prisma";

// Port of the "Research" tab in beatvegas/dashboard/app.py — the edge question
// (realized 1H/full-game ratio) + model_runs over time.

export type EdgeStats = { games: number; mean: number; median: number } | null;

export type ModelRunRow = {
  created_at: string;
  version: string | null;
  train_window: string | null;
  test_window: string | null;
  baseline_under_pct: number | null;
  top_under_pct: number | null;
  top_roi: number | null;
  notes: string | null;
};

function median(xs: number[]): number {
  const s = [...xs].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}

export async function getEdgeStats(): Promise<EdgeStats> {
  const rows = await prisma.$queryRaw<
    { first_half_total: number | bigint; full_game_total: number }[]
  >`
    SELECT first_half_total, full_game_total FROM games
    WHERE first_half_total IS NOT NULL AND full_game_total > 0
  `;
  if (rows.length === 0) return null;
  const ratios = rows.map((r) => Number(r.first_half_total) / r.full_game_total);
  const mean = ratios.reduce((a, b) => a + b, 0) / ratios.length;
  return { games: ratios.length, mean, median: median(ratios) };
}

function metric(js: string | null, key: string): number | null {
  if (!js) return null;
  try {
    const v = JSON.parse(js)[key];
    return typeof v === "number" ? v : null;
  } catch {
    return null;
  }
}

export async function getModelRuns(): Promise<ModelRunRow[]> {
  const runs = await prisma.$queryRaw<
    {
      created_at: string | null;
      version: string | null;
      train_window: string | null;
      test_window: string | null;
      metrics_json: string | null;
      notes: string | null;
    }[]
  >`
    SELECT CAST(created_at AS TEXT) AS created_at, version, train_window,
           test_window, metrics_json, notes
    FROM model_runs ORDER BY created_at
  `;
  return runs.map((r) => ({
    created_at: r.created_at ?? "",
    version: r.version,
    train_window: r.train_window,
    test_window: r.test_window,
    baseline_under_pct: metric(r.metrics_json, "baseline_under_pct"),
    top_under_pct: metric(r.metrics_json, "top_under_pct"),
    top_roi: metric(r.metrics_json, "top_roi"),
    notes: r.notes,
  }));
}
