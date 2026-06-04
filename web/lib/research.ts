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

// --- Gap vs CLV: do our biggest BV-vs-Vegas gaps earn positive closing-line
// value? The verdict on the whole "make our own number" method. Gap is in the
// under direction (bet line − BV line); CLV is reused from results (positive =
// the under closed at a softer number).
export type GapBucket = {
  label: string;
  n: number;
  meanGap: number | null;
  meanClv: number | null;
  meanUnits: number | null;
  underPct: number | null;
};

const GAP_BUCKETS: { label: string; lo: number; hi: number }[] = [
  { label: "<0", lo: -Infinity, hi: 0 },
  { label: "0–1", lo: 0, hi: 1 },
  { label: "1–2", lo: 1, hi: 2 },
  { label: "2–3", lo: 2, hi: 3 },
  { label: "3+", lo: 3, hi: Infinity },
];

const avg = (xs: number[]): number | null =>
  xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null;
const r2 = (v: number | null): number | null =>
  v === null ? null : Math.round(v * 100) / 100;

// resultLedger = which graded ledger supplies the bet line + CLV. We use the
// 'market' ledger (consensus open as bet line, close − open as CLV) because the
// question is whether the LINE moves toward our BV number by close — pure market
// movement, independent of the model's own entry timing. predVersion supplies
// the BV line.
export async function getGapClvBuckets(
  resultLedger = "market",
  predVersion = "gbm_v1",
): Promise<GapBucket[]> {
  const rows = await prisma.$queryRaw<
    {
      gap: number | null;
      clv: number | null;
      units: number | null;
      under_hit: boolean | number | null;
    }[]
  >`
    SELECT (r.line_used - p.bv_line) AS gap, r.clv, r.units, r.under_hit
    FROM results r
    JOIN predictions p ON p.game_id = r.game_id
    WHERE r.model_version = ${resultLedger}
      AND p.model_version = ${predVersion}
      AND r.clv IS NOT NULL
      AND p.bv_line IS NOT NULL
      AND r.line_used IS NOT NULL
  `;
  return GAP_BUCKETS.map((b) => {
    const inB = rows.filter(
      (x) => x.gap !== null && x.gap >= b.lo && x.gap < b.hi,
    );
    const gaps = inB.map((x) => Number(x.gap));
    const clvs = inB.filter((x) => x.clv !== null).map((x) => Number(x.clv));
    const units = inB
      .filter((x) => x.units !== null)
      .map((x) => Number(x.units));
    const hits = inB.filter((x) => x.under_hit !== null);
    const underPct = hits.length
      ? hits.filter((x) => Number(x.under_hit) === 1 || x.under_hit === true)
          .length / hits.length
      : null;
    return {
      label: b.label,
      n: inB.length,
      meanGap: r2(avg(gaps)),
      meanClv: r2(avg(clvs)),
      meanUnits: r2(avg(units)),
      underPct: underPct === null ? null : Math.round(underPct * 1000) / 10,
    };
  });
}

// --- BV-line calibration audit: the per-segment OOF residual table emitted by
// scripts/retrain.py into the latest model_runs row (metrics_json.bv_residual).
export type BvCalibration = {
  n: number;
  overall: number | null;
  segments: { label: string; n: number; meanResidual: number | null }[];
} | null;

export async function getBvCalibration(): Promise<BvCalibration> {
  const rows = await prisma.$queryRaw<{ metrics_json: string | null }[]>`
    SELECT metrics_json FROM model_runs
    WHERE metrics_json IS NOT NULL
    ORDER BY created_at DESC LIMIT 5
  `;
  for (const row of rows) {
    if (!row.metrics_json) continue;
    let bv: Record<string, unknown> | undefined;
    try {
      bv = (JSON.parse(row.metrics_json) as Record<string, unknown>)
        .bv_residual as Record<string, unknown> | undefined;
    } catch {
      continue;
    }
    if (!bv || typeof bv !== "object") continue;
    const segments: {
      label: string;
      n: number;
      meanResidual: number | null;
    }[] = [];
    const pushGroup = (group: unknown) => {
      if (!group || typeof group !== "object") return;
      for (const [k, v] of Object.entries(group as Record<string, unknown>)) {
        const seg = v as { n?: number; mean_residual?: number | null };
        if (seg && typeof seg === "object" && "mean_residual" in seg) {
          segments.push({
            label: k,
            n: Number(seg.n ?? 0),
            meanResidual:
              seg.mean_residual === null || seg.mean_residual === undefined
                ? null
                : Number(seg.mean_residual),
          });
        }
      }
    };
    pushGroup(bv.by_era);
    pushGroup(bv.by_tempo);
    pushGroup(bv.by_dome);
    return {
      n: Number(bv.n ?? 0),
      overall:
        bv.overall_mean_residual === null ||
        bv.overall_mean_residual === undefined
          ? null
          : Number(bv.overall_mean_residual),
      segments,
    };
  }
  return null;
}

export async function getEdgeStats(): Promise<EdgeStats> {
  const rows = await prisma.$queryRaw<
    { first_half_total: number | bigint; full_game_total: number }[]
  >`
    SELECT first_half_total, full_game_total FROM games
    WHERE first_half_total IS NOT NULL AND full_game_total > 0
  `;
  if (rows.length === 0) return null;
  const ratios = rows.map(
    (r) => Number(r.first_half_total) / r.full_game_total,
  );
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
