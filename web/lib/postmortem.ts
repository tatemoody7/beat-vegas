import { prisma } from "@/lib/prisma";
import { recordFromCounts, type Record3 } from "@/lib/record";
import { signed } from "@/lib/format";

// Post-mortem: every rated game vs its outcome, computed by
// scripts/post_mortem.py (Monday, after grading) into postmortem_runs /
// postmortem_buckets. One live run per scope:
//   hist_2023_25 — the stored walk-forward ratings regraded at the flat 0.52
//                  proxy they were built on ('flat') and at the fair step proxy
//                  ('step'); segments fbs_only | all.
//   live_<season> — the season's cards graded at Hard Rock's number ('hr'),
//                  the consensus at build ('market') and the close ('market_close').
// The tables are not in the Prisma schema; read them raw and degrade to null.

export type PmBucket = {
  scope: string;
  segment: string;
  proxy_kind: string;
  selection: string;
  dimension: string;
  bucket: string;
  bucket_order: number;
  n: number;
  unders: number;
  overs: number;
  pushes: number;
  under_pct: number | null;
  units: number;
  roi: number | null;
  ci_lo: number | null;
  ci_hi: number | null;
  p_beat: number | null;
};

export type PmFlag = {
  code: string;
  severity: "change" | "watch" | "ok" | string;
  text: string;
  evidence: Record<string, unknown>;
};

export type PmNotes = {
  flags?: PmFlag[];
  caveats?: string[];
  n_bets?: number;
  n_graded?: number;
  n_items?: number;
  derived_line?: {
    n?: number;
    mae?: number | null;
    bias?: number | null;
    hr_mae?: number | null;
    market_mae?: number | null;
    share?: number | null;
  };
  price_read_counts?: Record<
    string,
    { under?: number; over?: number; push?: number }
  >;
  [k: string]: unknown;
};

export type PmRun = {
  scope: string;
  run_id: string;
  computed_at: string;
  n_games: number;
  notes: PmNotes | null;
};

export type PostMortem = { runs: PmRun[]; buckets: PmBucket[] };

export const HIST_SCOPE = "hist_2023_25";

export const RULE_LABEL: Record<string, string> = {
  cap5: "Followed the system (≤5 a week by gap, gap ≥ 1.75)",
  gap175: "Every gap ≥ 1.75",
  gap300: "Every gap ≥ 3.0 (strong)",
  top20: "Top 20% by gap, per season",
  score53: "Every score ≥ 53",
  both: "Gap ≥ 1.75 and score ≥ 53",
  all: "Every rated game (blanket under)",
  bet: "Card BET tier",
  price_read: "Price read (Hard Rock pays at least fair)",
  all_hr: "Every Hard Rock number (blanket under)",
};

export const PROXY_LABEL: Record<string, string> = {
  real: "real closing line",
  step: "fair line",
  flat: "old 0.52 line",
  hr: "Hard Rock's number",
  market: "consensus at build",
  market_close: "consensus close",
};

type RawRun = {
  scope: string;
  run_id: string | null;
  computed_at: Date | string;
  n_games: number | bigint | null;
  notes_json: string | null;
};

type RawBucket = Omit<
  PmBucket,
  "n" | "unders" | "overs" | "pushes" | "bucket_order"
> & {
  n: number | bigint | null;
  unders: number | bigint | null;
  overs: number | bigint | null;
  pushes: number | bigint | null;
  bucket_order: number | bigint | null;
};

const num = (v: unknown): number =>
  v === null || v === undefined ? 0 : Number(v);
const numOrNull = (v: unknown): number | null =>
  v === null || v === undefined ? null : Number(v);

/** Both post-mortem tables; null when they do not exist yet (Monday fills them). */
export async function loadPostMortem(): Promise<PostMortem | null> {
  try {
    const runs = await prisma.$queryRaw<RawRun[]>`
      SELECT scope, run_id, computed_at, n_games, notes_json
      FROM postmortem_runs ORDER BY scope
    `;
    if (runs.length === 0) return null;
    const buckets = await prisma.$queryRaw<RawBucket[]>`
      SELECT scope, segment, proxy_kind, selection, dimension, bucket, bucket_order,
             n, unders, overs, pushes, under_pct, units, roi, ci_lo, ci_hi, p_beat
      FROM postmortem_buckets
      WHERE dimension <> 'wl_contrast'
    `;
    return {
      runs: runs.map((r) => {
        let notes: PmNotes | null = null;
        try {
          notes = r.notes_json ? (JSON.parse(r.notes_json) as PmNotes) : null;
        } catch {
          notes = null;
        }
        return {
          scope: r.scope,
          run_id: r.run_id ?? "",
          computed_at:
            r.computed_at instanceof Date
              ? r.computed_at.toISOString()
              : String(r.computed_at),
          n_games: num(r.n_games),
          notes,
        };
      }),
      buckets: buckets.map((b) => ({
        scope: b.scope,
        segment: b.segment,
        proxy_kind: b.proxy_kind,
        selection: b.selection,
        dimension: b.dimension,
        bucket: b.bucket,
        bucket_order: num(b.bucket_order),
        n: num(b.n),
        unders: num(b.unders),
        overs: num(b.overs),
        pushes: num(b.pushes),
        under_pct: numOrNull(b.under_pct),
        units: num(b.units),
        roi: numOrNull(b.roi),
        ci_lo: numOrNull(b.ci_lo),
        ci_hi: numOrNull(b.ci_hi),
        p_beat: numOrNull(b.p_beat),
      })),
    };
  } catch (e) {
    console.warn("postmortem tables unavailable:", (e as Error)?.message ?? e);
    return null;
  }
}

// ---------------------------------------------------------------- pure selectors

const pick = (
  buckets: PmBucket[],
  scope: string,
  segment: string,
  proxy: string,
  selection: string,
  dimension: string,
): PmBucket[] =>
  buckets.filter(
    (b) =>
      b.scope === scope &&
      b.segment === segment &&
      b.proxy_kind === proxy &&
      b.selection === selection &&
      b.dimension === dimension,
  );

/** The headline record (dimension 'all') for one scope/segment/proxy/rule. */
export function headline(
  buckets: PmBucket[],
  scope: string,
  segment: string,
  proxy: string,
  selection: string,
): Record3 | null {
  const b = pick(buckets, scope, segment, proxy, selection, "all")[0];
  if (!b) return null;
  return recordFromCounts(b.unders, b.overs, b.pushes, b.units);
}

export type BandRow = {
  bucket: string;
  n: number;
  record: string;
  hit: string;
  ci: string;
  pBeat: string;
  units: string;
  roi: string;
  /** small: n < 30 (no rate shown), medium: n < 100 (no ROI), full otherwise. */
  size: "small" | "medium" | "full";
};

const pctText = (v: number | null): string =>
  v === null ? "—" : `${(100 * v).toFixed(1)}%`;

/** One dimension's buckets in display order, formatted for a table. */
export function bandTable(
  buckets: PmBucket[],
  scope: string,
  segment: string,
  proxy: string,
  dimension: string,
  selection = "all",
): BandRow[] {
  return pick(buckets, scope, segment, proxy, selection, dimension)
    .slice()
    .sort(
      (a, b) =>
        a.bucket_order - b.bucket_order || a.bucket.localeCompare(b.bucket),
    )
    .map((b) => {
      const size: BandRow["size"] =
        b.n < 30 ? "small" : b.n < 100 ? "medium" : "full";
      return {
        bucket: b.bucket,
        n: b.n,
        record: `${b.unders}-${b.overs}${b.pushes ? `-${b.pushes}P` : ""}`,
        hit: pctText(b.under_pct),
        ci:
          b.ci_lo === null || b.ci_hi === null
            ? "—"
            : `${(100 * b.ci_lo).toFixed(1)}–${(100 * b.ci_hi).toFixed(1)}%`,
        pBeat: b.p_beat === null ? "—" : b.p_beat.toFixed(2),
        units: signed(b.units),
        roi:
          b.roi === null || size !== "full"
            ? "—"
            : `${signed(100 * b.roi, 1)}%`,
        size,
      };
    });
}

/** The change flags a run wrote, in the order the script emitted them. */
export function flagsFrom(run: PmRun | undefined | null): PmFlag[] {
  return run?.notes?.flags ?? [];
}

export type LiveNotes = {
  nBets: number;
  nGraded: number;
  nItems: number;
  derivedMae: number | null;
  hrMae: number | null;
  marketMae: number | null;
  share: number | null;
  priceReads: { band: string; under: number; over: number; push: number }[];
};

const BAND_ORDER = ["neg", "fair", "pos"];

/** The live-scope diagnostics with safe defaults. */
export function liveNotesFrom(run: PmRun | undefined | null): LiveNotes {
  const n = run?.notes ?? {};
  const d = n.derived_line ?? {};
  const counts = n.price_read_counts ?? {};
  return {
    nBets: num(n.n_bets),
    nGraded: num(n.n_graded),
    nItems: num(n.n_items),
    derivedMae: numOrNull(d.mae),
    hrMae: numOrNull(d.hr_mae),
    marketMae: numOrNull(d.market_mae),
    share: numOrNull(d.share),
    priceReads: Object.entries(counts)
      .sort(([a], [b]) => BAND_ORDER.indexOf(a) - BAND_ORDER.indexOf(b))
      .map(([band, c]) => ({
        band,
        under: num(c.under),
        over: num(c.over),
        push: num(c.push),
      })),
  };
}

/** The live scope present in the data (`live_2026`), if any. */
export function liveScopeOf(runs: PmRun[]): string | null {
  const live = runs
    .map((r) => r.scope)
    .filter((s) => s.startsWith("live_"))
    .sort();
  return live.length ? live[live.length - 1] : null;
}
