import { prisma } from "@/lib/prisma";
import type { Record3 } from "@/lib/ledger";

// Post-week review: how the MARKET, the MODEL, and YOU did — split by market
// (full game vs first half) — with win%, units, and CLV, for a chosen week.
//   Market 1H   = results.model_version='market'
//   Market full = results.model_version='market_fg'
//   Model 1H    = results.model_version='gbm_v1' (no full-game model — reference app)
//   You         = graded manual_picks, split by manual_picks.market

export type ReviewLine = {
  entity: "Market" | "Model" | "You";
  market: "Full game" | "First half";
  rec: (Record3 & { n: number }) | null;
};

export type ReviewPick = {
  week: number | null;
  market: string;
  away: string | null;
  home: string | null;
  line: number | null;
  result: string | null; // under/over/push/pending
  units: number | null;
  clv: number | null;
};

export type WeeklyReview = {
  week: number | null;
  weeks: number[];
  lines: ReviewLine[];
  picks: ReviewPick[];
};

const signed = (n: number, dp = 2) => `${n >= 0 ? "+" : ""}${n.toFixed(dp)}`;
const truthy = (v: unknown) => v === true || Number(v) === 1;

function rec(
  wins: number,
  decided: number,
  pushes: number,
  unitsSum: number,
  clvs: number[],
): Record3 & { n: number } {
  return {
    n: decided + pushes,
    record: `${wins}-${decided - wins}${pushes ? `-${pushes}P` : ""}`,
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
  week: number | bigint | null;
};
type PickRow = {
  market: string | null;
  result: string | null;
  units: number | null;
  clv: number | null;
  week: number | bigint | null;
  away_team: string | null;
  home_team: string | null;
  line: number | null;
  graded: number | boolean | null;
};

function fromResults(rows: ResRow[]): (Record3 & { n: number }) | null {
  if (rows.length === 0) return null;
  const wins = rows.filter((r) => truthy(r.under_hit)).length;
  const unitsSum = rows.reduce((a, r) => a + (r.units ?? 0), 0);
  const clvs = rows.filter((r) => r.clv !== null).map((r) => r.clv as number);
  return rec(wins, rows.length, 0, unitsSum, clvs);
}

function fromPicks(rows: PickRow[]): (Record3 & { n: number }) | null {
  if (rows.length === 0) return null;
  const wins = rows.filter((p) => p.result === "under").length;
  const pushes = rows.filter((p) => p.result === "push").length;
  const unitsSum = rows.reduce((a, p) => a + (p.units ?? 0), 0);
  const clvs = rows.filter((p) => p.clv !== null).map((p) => p.clv as number);
  return rec(wins, rows.length - pushes, pushes, unitsSum, clvs);
}

export async function getWeeklyReview(
  season: number,
  week?: number,
): Promise<WeeklyReview> {
  const res = await prisma.$queryRaw<ResRow[]>`
    SELECT r.model_version, r.under_hit, r.units, r.clv, g.week
    FROM results r JOIN games g ON g.id = r.game_id
    WHERE g.season = ${season}
  `;
  const mine = await prisma.$queryRaw<PickRow[]>`
    SELECT market, result, units, clv, week, away_team, home_team, line, graded
    FROM manual_picks WHERE season = ${season}
  `;

  const resWeeks = res.map((r) => Number(r.week));
  const pickWeeks = mine
    .filter((p) => truthy(p.graded))
    .map((p) => Number(p.week));
  const weeks = [...new Set([...resWeeks, ...pickWeeks])]
    .filter((w) => Number.isFinite(w))
    .sort((a, b) => a - b);
  const wk = week && weeks.includes(week) ? week : (weeks[weeks.length - 1] ?? null);

  const r = res.filter((x) => Number(x.week) === wk);
  const isFull = (m: string | null) => m === "full";
  const gradedMine = mine.filter(
    (p) => truthy(p.graded) && Number(p.week) === wk,
  );

  const lines: ReviewLine[] = [
    {
      entity: "Market",
      market: "Full game",
      rec: fromResults(r.filter((x) => x.model_version === "market_fg")),
    },
    {
      entity: "Market",
      market: "First half",
      rec: fromResults(r.filter((x) => x.model_version === "market")),
    },
    {
      entity: "Model",
      market: "First half",
      rec: fromResults(r.filter((x) => x.model_version === "gbm_v1")),
    },
    {
      entity: "You",
      market: "Full game",
      rec: fromPicks(gradedMine.filter((p) => isFull(p.market))),
    },
    {
      entity: "You",
      market: "First half",
      rec: fromPicks(gradedMine.filter((p) => !isFull(p.market))),
    },
  ];

  const picks: ReviewPick[] = mine
    .filter((p) => Number(p.week) === wk)
    .map((p) => ({
      week: p.week === null ? null : Number(p.week),
      market: isFull(p.market) ? "Full game" : "1H",
      away: p.away_team,
      home: p.home_team,
      line: p.line,
      result: truthy(p.graded) ? p.result : "pending",
      units: p.units,
      clv: p.clv,
    }));

  return { week: wk, weeks, lines, picks };
}
