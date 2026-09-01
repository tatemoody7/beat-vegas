import { prisma } from "@/lib/prisma";

// Port of the 3-way Ledger in beatvegas/dashboard/app.py (market vs model vs you).
// Market = under vs real closing line (results.model_version='market');
// Model = the model's leans (results.model_version='gbm_v1');
// You = graded manual_picks.

export type Record3 = {
  record: string; // e.g. "6-6" or "2-3" or "5-4-1P"
  hit: string; // "50.0%" or "—"
  units: string; // signed, "+0.91" / "-0.55"
  clv: string; // signed mean, or "—"
};

export type PickRow = {
  week: number | null;
  away: string | null;
  home: string | null;
  line: number | null;
  price: number | null;
  result: string | null; // under / over / push / pending
  units: number | null;
  clv: number | null;
  graded: boolean;
  isPaper: boolean;
};

export type Ledger = {
  market: Record3 | null;
  model: Record3 | null;
  you: Record3 | null; // real-money picks only
  paper: Record3 | null; // paper picks (stake 0) — never merged into "you"
  picks: PickRow[];
};

const signed = (n: number, dp = 2) => `${n >= 0 ? "+" : ""}${n.toFixed(dp)}`;
const truthy = (v: unknown) => v === true || Number(v) === 1;

// app.py::_record — wins/decided/pushes, hit%, summed units, mean non-null CLV.
function record(
  wins: number,
  decided: number,
  pushes: number,
  unitsSum: number,
  clvs: number[],
): Record3 {
  const losses = decided - wins;
  return {
    record: `${wins}-${losses}${pushes ? `-${pushes}P` : ""}`,
    hit: decided ? `${((100 * wins) / decided).toFixed(1)}%` : "—",
    units: signed(unitsSum),
    clv: clvs.length
      ? signed(clvs.reduce((a, b) => a + b, 0) / clvs.length)
      : "—",
  };
}

type ResRow = {
  model_version: string | null;
  under_hit: number | boolean | null;
  units: number | null;
  clv: number | null;
  actual_first_half_total: number | null;
  line_used: number | null;
};
type RawPick = {
  graded: number | boolean | null;
  result: string | null;
  units: number | null;
  clv: number | null;
  week: number | bigint | null;
  line: number | null;
  price: number | bigint | null;
  away_team: string | null;
  home_team: string | null;
  is_paper: number | boolean | null;
};

// results store under_hit as a bool, so a push looks like a loss there —
// recover it from actual == line so pushes don't deflate the under%.
function fromResults(rows: ResRow[]): Record3 | null {
  const isPush = (r: ResRow) =>
    r.actual_first_half_total !== null &&
    r.line_used !== null &&
    Number(r.actual_first_half_total) === Number(r.line_used);
  // under_hit NULL means the row was never graded — it must not count as a
  // loss (pushes are the exception: they're recovered from actual == line).
  const usable = rows.filter((r) => r.under_hit !== null || isPush(r));
  if (usable.length === 0) return null;
  const pushes = usable.filter(isPush).length;
  const wins = usable.filter((r) => truthy(r.under_hit)).length;
  const unitsSum = usable.reduce((a, r) => a + (r.units ?? 0), 0);
  const clvs = usable.filter((r) => r.clv !== null).map((r) => r.clv as number);
  return record(wins, usable.length - pushes, pushes, unitsSum, clvs);
}

export async function getLedger(season: number): Promise<Ledger> {
  const res = await prisma.$queryRaw<ResRow[]>`
    SELECT r.model_version, r.under_hit, r.units, r.clv,
           r.actual_first_half_total, r.line_used
    FROM results r JOIN games g ON g.id = r.game_id
    WHERE g.season = ${season}
  `;
  const mine = await prisma.$queryRaw<RawPick[]>`
    SELECT graded, result, units, clv, week, line, price, away_team, home_team,
           is_paper
    FROM manual_picks WHERE season = ${season}
  `;

  const market = fromResults(res.filter((r) => r.model_version === "market"));
  const model = fromResults(res.filter((r) => r.model_version === "gbm_v1"));

  const fromPicks = (rows: RawPick[]): Record3 | null => {
    if (rows.length === 0) return null;
    const wins = rows.filter((p) => p.result === "under").length;
    const pushes = rows.filter((p) => p.result === "push").length;
    const unitsSum = rows.reduce((a, p) => a + (p.units ?? 0), 0);
    const clvs = rows.filter((p) => p.clv !== null).map((p) => p.clv as number);
    return record(wins, rows.length - pushes, pushes, unitsSum, clvs);
  };
  const graded = mine.filter((p) => truthy(p.graded));
  const you = fromPicks(graded.filter((p) => !truthy(p.is_paper)));
  const paper = fromPicks(graded.filter((p) => truthy(p.is_paper)));

  const picks: PickRow[] = mine.map((p) => ({
    week: p.week === null ? null : Number(p.week),
    away: p.away_team,
    home: p.home_team,
    line: p.line,
    price: p.price === null ? null : Number(p.price),
    result: truthy(p.graded) ? p.result : "pending",
    units: p.units,
    clv: p.clv,
    graded: truthy(p.graded),
    isPaper: truthy(p.is_paper),
  }));
  // pending first, then by week
  picks.sort(
    (a, b) =>
      Number(a.graded) - Number(b.graded) || (a.week ?? 0) - (b.week ?? 0),
  );

  return { market, model, you, paper, picks };
}
