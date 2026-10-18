import { prisma } from "@/lib/prisma";

// The stored arm positions (`arm_positions`, 2026-10-14, programme step 10):
// one row per registered hypothesis per Monday read, written only by the
// Monday workflow (beatvegas/positions.py). The site reads the NEWEST row per
// hypothesis and never recomputes a position: the Monday read and the final
// read (2026-11-30) read the same row, so none of the three can disagree. Timestamps come
// back as text and are read as UTC (lib/et.ts convention).

export const ARM_STANDARDS = ["sprt", "pricing", "exploratory"] as const;
export type ArmStandard = (typeof ARM_STANDARDS)[number];

/** A Monday read older than this reads "outdated" (beatvegas/positions.py). */
export const OUTDATED_AFTER_DAYS = 8;

export type ArmPositionRow = {
  hypothesis: string;
  standard: ArmStandard;
  read_date: string;
  read_at: string; // naive UTC text
  run_id: string | null;
  state: string | null;
  label: string | null;
  logged: number | null;
  readings: number | null;
  weeks: number | null;
  excluded: number | null;
  pending: number | null;
  needed: number | null;
  llr: number | null;
  mean_ev: number | null;
  ev_lo: number | null;
  ev_hi: number | null;
  next_read: string | null;
};

export type ArmPosition = Omit<ArmPositionRow, "read_at"> & {
  readAt: Date;
  freshness: "current" | "outdated";
  sufficient: boolean; // readings >= needed
};

export function utcFrom(s: string): Date {
  return new Date(
    /[zZ]|[+-]\d\d:?\d\d$/.test(s) ? s : `${s.replace(" ", "T")}Z`,
  );
}

export function freshnessOf(readAt: Date, now: Date): "current" | "outdated" {
  return now.getTime() - readAt.getTime() > OUTDATED_AFTER_DAYS * 86_400_000
    ? "outdated"
    : "current";
}

/** Pure: the newest row per hypothesis, shaped for the page. */
export function newestByHypothesis(
  rows: ArmPositionRow[],
  now: Date,
): Map<string, ArmPosition> {
  const out = new Map<string, ArmPosition>();
  for (const r of rows) {
    const readAt = utcFrom(r.read_at);
    const prev = out.get(r.hypothesis);
    if (prev && prev.readAt.getTime() >= readAt.getTime()) continue;
    const { read_at: _ra, ...rest } = r;
    void _ra;
    out.set(r.hypothesis, {
      ...rest,
      readAt,
      freshness: freshnessOf(readAt, now),
      sufficient: (r.readings ?? 0) >= (r.needed ?? Number.POSITIVE_INFINITY),
    });
  }
  return out;
}

const isMissingTable = (e: unknown): boolean =>
  typeof e === "object" &&
  e !== null &&
  String((e as { message?: string }).message ?? "").includes("does not exist");

/** The newest position per hypothesis; an empty map when the table is not there yet. */
export async function getArmPositions(
  now: Date = new Date(),
): Promise<Map<string, ArmPosition>> {
  try {
    const rows = await prisma.$queryRaw<ArmPositionRow[]>`
      SELECT DISTINCT ON (hypothesis)
             hypothesis, standard, read_date, CAST(read_at AS TEXT) AS read_at, run_id,
             state, label, logged, readings, weeks, excluded, pending, needed,
             llr, mean_ev, ev_lo, ev_hi, next_read
      FROM arm_positions
      ORDER BY hypothesis, read_at DESC, id DESC`;
    return newestByHypothesis(rows, now);
  } catch (e) {
    if (isMissingTable(e)) return new Map();
    throw e;
  }
}

/** The newest row's payload for one hypothesis, parsed; null with no row or no
 *  payload. The exploratory card reads its comparison from it (the Monday
 *  workflow wrote it; nothing here recomputes it). */
export async function getPositionPayload(
  hypothesis: string,
): Promise<Record<string, unknown> | null> {
  try {
    const rows = await prisma.$queryRaw<{ payload_json: string | null }[]>`
      SELECT payload_json FROM arm_positions
      WHERE hypothesis = ${hypothesis}
      ORDER BY read_at DESC, id DESC
      LIMIT 1`;
    const raw = rows[0]?.payload_json;
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    return parsed !== null && typeof parsed === "object"
      ? (parsed as Record<string, unknown>)
      : null;
  } catch (e) {
    if (isMissingTable(e)) return null;
    throw e;
  }
}
