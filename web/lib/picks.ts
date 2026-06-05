import { prisma } from "@/lib/prisma";
import { getBoard } from "@/lib/board";
import type { Record3 } from "@/lib/ledger";

// Writable My Picks: the current scored slate to bet on, the user's logged picks
// (with the model snapshot frozen at log time), and a running "You" record.

export type SlateOption = {
  gameId: number;
  week: number;
  away: string;
  home: string;
  underScore: number | null;
  curLine: number | null; // consensus current; falls back to model line
  modelLine: number | null;
};

export type PickFull = {
  id: number;
  week: number | null;
  away: string | null;
  home: string | null;
  market: string; // '1H' | 'full'
  line: number | null;
  stake: number | null;
  price: number | null;
  note: string | null;
  modelScore: number | null;
  modelLine: number | null;
  result: string | null; // under/over/push or "pending"
  units: number | null;
  clv: number | null;
  graded: boolean;
};

// Current week's scored games (max week present in the season's predictions).
export async function getSlate(season: number): Promise<SlateOption[]> {
  const board = await getBoard(season);
  if (board.length === 0) return [];
  const maxWeek = Math.max(...board.map((b) => b.week));
  return board
    .filter((b) => b.week === maxWeek)
    .map((b) => ({
      gameId: b.gameId,
      week: b.week,
      away: b.away,
      home: b.home,
      underScore: b.underScore,
      curLine: b.curLine ?? b.factors.line ?? null,
      modelLine: b.factors.line ?? null,
    }));
}

const signed = (n: number, dp = 2) => `${n >= 0 ? "+" : ""}${n.toFixed(dp)}`;
const truthy = (v: unknown) => v === true || Number(v) === 1;

type RawPick = {
  id: number | bigint;
  week: number | bigint | null;
  away_team: string | null;
  home_team: string | null;
  market: string | null;
  line: number | null;
  stake: number | null;
  price: number | bigint | null;
  note: string | null;
  model_score_at_pick: number | bigint | null;
  model_line_at_pick: number | null;
  result: string | null;
  units: number | null;
  clv: number | null;
  graded: number | boolean | null;
};

export async function getPicks(
  season: number,
): Promise<{ picks: PickFull[]; record: Record3 | null }> {
  const rows = await prisma.$queryRaw<RawPick[]>`
    SELECT id, week, away_team, home_team, market, line, stake, price, note,
           model_score_at_pick, model_line_at_pick, result, units, clv, graded
    FROM manual_picks WHERE season = ${season}
  `;

  const picks: PickFull[] = rows.map((r) => ({
    id: Number(r.id),
    week: r.week === null ? null : Number(r.week),
    away: r.away_team,
    home: r.home_team,
    market: r.market === "full" ? "full" : "1H", // null (legacy) -> 1H
    line: r.line,
    stake: r.stake,
    price: r.price === null ? null : Number(r.price),
    note: r.note,
    modelScore:
      r.model_score_at_pick === null ? null : Number(r.model_score_at_pick),
    modelLine: r.model_line_at_pick,
    result: truthy(r.graded) ? r.result : "pending",
    units: r.units,
    clv: r.clv,
    graded: truthy(r.graded),
  }));
  // pending first, then newest (highest id) first within each group
  picks.sort((a, b) => Number(a.graded) - Number(b.graded) || b.id - a.id);

  // Running "You" record over graded picks (mirrors ledger _record).
  const graded = picks.filter((p) => p.graded);
  let record: Record3 | null = null;
  if (graded.length) {
    const wins = graded.filter((p) => p.result === "under").length;
    const pushes = graded.filter((p) => p.result === "push").length;
    const decided = graded.length - pushes;
    const unitsSum = graded.reduce((a, p) => a + (p.units ?? 0), 0);
    const clvs = graded
      .filter((p) => p.clv !== null)
      .map((p) => p.clv as number);
    record = {
      record: `${wins}-${decided - wins}${pushes ? `-${pushes}P` : ""}`,
      hit: decided ? `${((100 * wins) / decided).toFixed(1)}%` : "—",
      units: signed(unitsSum),
      clv: clvs.length
        ? signed(clvs.reduce((a, b) => a + b, 0) / clvs.length)
        : "—",
    };
  }
  return { picks, record };
}

export type CreatePickInput = {
  gameId: number;
  market?: "1H" | "full"; // default 1H
  line: number;
  stake?: number;
  price?: number;
  note?: string;
};

// Insert a ManualPick, freezing the model's current score+line onto it.
export async function createPick(input: CreatePickInput): Promise<void> {
  const game = await prisma.games.findUnique({
    where: { id: input.gameId },
    select: { season: true, week: true, home_team: true, away_team: true },
  });
  if (!game) throw new Error("game not found");

  const market = input.market === "full" ? "full" : "1H";

  // The model (predictions) is 1H-only — only freeze its read onto a 1H pick.
  // Full-game picks store NULL model fields (the model is a reference, not a pick).
  const pred =
    market === "1H"
      ? await prisma.$queryRaw<
          {
            under_score: number | bigint | null;
            line_used: number | null;
            factors_json: string | null;
          }[]
        >`
    SELECT under_score, line_used, factors_json FROM predictions
    WHERE game_id = ${input.gameId} ORDER BY created_at DESC LIMIT 1
  `
      : [];
  const modelScore =
    pred[0]?.under_score == null ? null : Number(pred[0].under_score);
  const modelLine = pred[0]?.line_used ?? null;
  const factorsAtPick = pred[0]?.factors_json ?? null;

  const stake = input.stake ?? 1.0;
  const price = input.price ?? -110;
  const note = input.note ?? null;
  const placedAt = new Date().toISOString();

  // Postgres is strict: cast the ISO string to a timestamp and use a real
  // boolean for `graded` (SQLite tolerated a text date + integer 0; Neon/PG won't).
  await prisma.$executeRaw`
    INSERT INTO manual_picks
      (game_id, season, week, home_team, away_team, side, market, line, price,
       stake, placed_at, note, model_score_at_pick, model_line_at_pick,
       factors_json_at_pick, graded)
    VALUES
      (${input.gameId}, ${game.season}, ${game.week}, ${game.home_team},
       ${game.away_team}, 'under', ${market}, ${input.line}, ${price}, ${stake},
       ${placedAt}::timestamp, ${note}, ${modelScore}, ${modelLine},
       ${factorsAtPick}, false)
  `;
}

// Returns false if the pick is already graded (immutable) or missing.
export async function deletePick(id: number): Promise<boolean> {
  const rows = await prisma.$queryRaw<{ graded: number | boolean | null }[]>`
    SELECT graded FROM manual_picks WHERE id = ${id}
  `;
  if (rows.length === 0 || truthy(rows[0].graded)) return false;
  await prisma.$executeRaw`DELETE FROM manual_picks WHERE id = ${id}`;
  return true;
}
