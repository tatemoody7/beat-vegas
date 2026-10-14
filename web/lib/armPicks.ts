import { prisma } from "@/lib/prisma";
import { ARM_STARTS, HYPOTHESES } from "@/lib/research";

// The registered arms' FORWARD paper picks (2026-10-14, programme step 13):
// every graded pick placed at or after its arm's clock start, with the judge's
// reading (`ev_cons`) or the reason there is none (`cons_excluded`). The same
// selection `scripts/protocol_position.py::arm_rows` makes -- H-ARM-1HU from
// the paper `manual_picks` (1H, under), the other five from `challenger_picks`
// by arm tag -- so the rows here are the rows the Monday read averages. Only
// graded rows: a graded pick's game has kicked off, so nothing here reveals a
// pick before kickoff. Development rows (before the start) are never listed.

export type ArmPick = {
  arm: string;
  id: number;
  week: number | null;
  away: string | null;
  home: string | null;
  market: string;
  side: string;
  line: number | null;
  price: number | null;
  result: string | null;
  units: number | null;
  evCons: number | null;
  consExcluded: string | null;
  placedAt: string; // naive UTC text
};

type Raw = {
  arm: string;
  id: number;
  week: number | null;
  away: string | null;
  home: string | null;
  market: string;
  side: string;
  line: number | null;
  price: number | null;
  result: string | null;
  units: number | null;
  ev_cons: number | null;
  cons_excluded: string | null;
  placed_at: string;
};

const CHALLENGER_ARMS = HYPOTHESES.filter(
  (h) => h.standard === "sprt" && h.id !== "H-ARM-1HU",
).map((h) => h.id);

/** Pure: keep a row only at or after its own arm's start, group by arm in slot order. */
export function groupForward(rows: ArmPick[]): Map<string, ArmPick[]> {
  const out = new Map<string, ArmPick[]>();
  for (const h of HYPOTHESES) if (h.standard === "sprt") out.set(h.id, []);
  for (const r of rows) {
    const start = ARM_STARTS[r.arm];
    if (!start || !out.has(r.arm)) continue;
    const t = Date.parse(`${r.placedAt.replace(" ", "T").slice(0, 23)}Z`);
    if (!(t >= Date.parse(`${start.slice(0, 23)}Z`))) continue;
    out.get(r.arm)!.push(r);
  }
  for (const list of out.values())
    list.sort((a, b) => b.placedAt.localeCompare(a.placedAt) || b.id - a.id);
  return out;
}

const isMissingTable = (e: unknown): boolean =>
  String((e as { message?: string })?.message ?? "").includes("does not exist");

export async function getArmPicks(
  season: number,
): Promise<Map<string, ArmPick[]>> {
  const earliest = Object.values(ARM_STARTS).sort()[0];
  try {
    const raw = await prisma.$queryRaw<Raw[]>`
      SELECT 'H-ARM-1HU' AS arm, mp.id, mp.week, mp.away_team AS away, mp.home_team AS home,
             mp.market, mp.side, mp.line, mp.price, mp.result, mp.units,
             mp.ev_cons, mp.cons_excluded, CAST(mp.placed_at AS TEXT) AS placed_at
      FROM manual_picks mp
      WHERE mp.season = ${season} AND mp.is_paper IS TRUE AND mp.market = '1H'
        AND mp.side = 'under' AND mp.graded IS TRUE
        AND mp.placed_at >= ${earliest}::timestamp
      UNION ALL
      SELECT cp.arm, cp.id, cp.week, cp.away_team, cp.home_team, cp.market, cp.side,
             cp.line, cp.price, cp.result, cp.units, cp.ev_cons, cp.cons_excluded,
             CAST(cp.placed_at AS TEXT)
      FROM challenger_picks cp
      WHERE cp.season = ${season} AND cp.arm = ANY(${CHALLENGER_ARMS})
        AND cp.graded IS TRUE AND cp.placed_at >= ${earliest}::timestamp`;
    return groupForward(
      raw.map((r) => ({
        arm: r.arm,
        id: Number(r.id),
        week: r.week,
        away: r.away,
        home: r.home,
        market: r.market,
        side: r.side,
        line: r.line,
        price: r.price,
        result: r.result,
        units: r.units,
        evCons: r.ev_cons,
        consExcluded: r.cons_excluded,
        placedAt: r.placed_at,
      })),
    );
  } catch (e) {
    if (isMissingTable(e)) return groupForward([]);
    throw e;
  }
}

export type PricingOpportunity = {
  market: string;
  week: number | null;
  game: string;
  captured_at: string;
  hrs_to_kick: number | null;
  hr_line: number | null;
  ref_line: number | null;
  side: string;
  price: number | null;
  ev_ref: number | null;
  ev_ref_lower: number | null;
  ev_close: number | null;
  market_moved: string | null;
  tier: number | null;
  fl_check: string | null;
  result: string | null;
};

/** Pure: the forward opportunities the newest pricing row carries (older rows
 *  stored the verdict alone: no list). */
export function opportunitiesFrom(
  payload: string | null,
): PricingOpportunity[] {
  if (!payload) return [];
  try {
    const p = JSON.parse(payload) as { opportunities?: PricingOpportunity[] };
    return Array.isArray(p.opportunities) ? p.opportunities : [];
  } catch {
    return [];
  }
}

export async function getPricingOpportunities(): Promise<PricingOpportunity[]> {
  try {
    const rows = await prisma.$queryRaw<{ payload_json: string | null }[]>`
      SELECT payload_json FROM arm_positions
      WHERE hypothesis = 'H-PRICE-HR'
      ORDER BY read_at DESC, id DESC LIMIT 1`;
    return opportunitiesFrom(rows[0]?.payload_json ?? null);
  } catch (e) {
    if (isMissingTable(e)) return [];
    throw e;
  }
}
