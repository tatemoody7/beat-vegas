import { prisma } from "@/lib/prisma";
import { getBoard } from "@/lib/board";
import { recordFrom, type Record3 } from "@/lib/record";
import { defaultWeek } from "@/lib/week";
import type { PickReason, Verdict } from "@/lib/verdict";
import { DEFAULT_STAKE, PAPER_STAKE } from "@/lib/pickRules";

// My Picks data layer: the current slate (for API validation), the user's
// logged picks with the model + verdict snapshot frozen at log time, and the
// running records. ONE picks query (loadPicks) feeds the ledger, the weekly
// review and the bankroll strip so they can never disagree.

export type SlateOption = {
  gameId: number;
  week: number;
  away: string;
  home: string;
};

export type PickFull = {
  id: number;
  gameId: number | null;
  week: number | null;
  away: string | null;
  home: string | null;
  market: "1H" | "full";
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
  isPaper: boolean; // tracked with nothing at risk
  // Decision snapshot (null on picks logged before the tracking columns existed).
  verdictAtPick: Verdict | null;
  reason: PickReason | null;
  gapAtPick: number | null;
  evAtPick: number | null;
  hrLineAtPick: number | null;
  /** Paper ledger: the gate that blocked a real bet (none | price | off_market | qb_out | cap); null on real picks. */
  blocker: string | null;
};

/** A real-money 1H pick on the week, as the bet slip needs it. */
export type WeekPick = {
  gameId: number | null;
  away: string | null;
  home: string | null;
  line: number | null;
  price: number | null;
};

// Games on the current week (the week you are about to bet — see lib/week.ts).
export async function getSlate(season: number): Promise<SlateOption[]> {
  const board = await getBoard(season);
  const week = defaultWeek(board);
  return board
    .filter((b) => b.week === week)
    .map((b) => ({
      gameId: b.gameId,
      week: b.week,
      away: b.away,
      home: b.home,
    }));
}

const truthy = (v: unknown) => v === true || Number(v) === 1;
const num = (v: number | bigint | null | undefined): number | null =>
  v === null || v === undefined ? null : Number(v);

type RawPick = {
  id: number | bigint;
  game_id: number | bigint | null;
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
  is_paper: number | boolean | null;
  verdict_at_pick?: string | null;
  reason?: string | null;
  gap_at_pick?: number | null;
  ev_at_pick?: number | null;
  hr_line_at_pick?: number | null;
  blocker?: string | null;
};

const isMissingColumn = (e: unknown): boolean =>
  /column .* does not exist|no such column/i.test(
    String((e as Error)?.message ?? e),
  );

// The tracking columns arrive with the Python lane's migration; until it has
// run on a database, fall back to the legacy column list (snapshot fields null)
// and say so in the server log rather than 500 the whole Results page.
async function selectPicks(season: number): Promise<RawPick[]> {
  try {
    return await prisma.$queryRaw<RawPick[]>`
      SELECT id, game_id, week, away_team, home_team, market, line, stake, price,
             note, model_score_at_pick, model_line_at_pick, result, units, clv,
             graded, is_paper, verdict_at_pick, reason, gap_at_pick, ev_at_pick,
             hr_line_at_pick, blocker
      FROM manual_picks WHERE season = ${season}
    `;
  } catch (e) {
    if (!isMissingColumn(e)) throw e;
  }
  // `blocker` (2026-09-07) arrives with the Python lane's migration; keep the
  // rest of the snapshot when only it is missing.
  try {
    return await prisma.$queryRaw<RawPick[]>`
      SELECT id, game_id, week, away_team, home_team, market, line, stake, price,
             note, model_score_at_pick, model_line_at_pick, result, units, clv,
             graded, is_paper, verdict_at_pick, reason, gap_at_pick, ev_at_pick,
             hr_line_at_pick
      FROM manual_picks WHERE season = ${season}
    `;
  } catch (e) {
    if (!isMissingColumn(e)) throw e;
    console.warn("manual_picks tracking columns missing — run the migration");
    return prisma.$queryRaw<RawPick[]>`
      SELECT id, game_id, week, away_team, home_team, market, line, stake, price,
             note, model_score_at_pick, model_line_at_pick, result, units, clv,
             graded, is_paper
      FROM manual_picks WHERE season = ${season}
    `;
  }
}

const asVerdict = (v: string | null | undefined): Verdict | null =>
  v === "BET" || v === "WATCH" || v === "PASS" ? v : null;
const asReason = (v: string | null | undefined): PickReason | null =>
  v === "model_gap" || v === "price_edge" || v === "manual" ? v : null;

/** Every pick for the season, pending first then newest first. */
export async function loadPicks(season: number): Promise<PickFull[]> {
  const rows = await selectPicks(season);
  const picks: PickFull[] = rows.map((r) => ({
    id: Number(r.id),
    gameId: num(r.game_id),
    week: num(r.week),
    away: r.away_team,
    home: r.home_team,
    market: r.market === "full" ? "full" : "1H", // null (legacy) -> 1H
    line: r.line,
    stake: r.stake,
    price: num(r.price),
    note: r.note,
    modelScore: num(r.model_score_at_pick),
    modelLine: r.model_line_at_pick,
    result: truthy(r.graded) ? r.result : "pending",
    units: r.units,
    clv: r.clv,
    graded: truthy(r.graded),
    isPaper: truthy(r.is_paper),
    verdictAtPick: asVerdict(r.verdict_at_pick),
    reason: asReason(r.reason),
    gapAtPick: r.gap_at_pick ?? null,
    evAtPick: r.ev_at_pick ?? null,
    hrLineAtPick: r.hr_line_at_pick ?? null,
    blocker: r.blocker ?? null,
  }));
  picks.sort((a, b) => Number(a.graded) - Number(b.graded) || b.id - a.id);
  return picks;
}

/** Real-money picks that count: first-half only (the only market we bet). */
export const isRealFirstHalf = (p: PickFull): boolean =>
  !p.isPaper && p.market === "1H";
export const isPaperFirstHalf = (p: PickFull): boolean =>
  p.isPaper && p.market === "1H";
/** Real money placed where the site graded WATCH/PASS (or a legacy pick with no
 *  frozen verdict is NOT off-policy — we cannot know). Flagged on Results. */
export const isOffPolicy = (p: PickFull): boolean =>
  !p.isPaper && p.verdictAtPick !== null && p.verdictAtPick !== "BET";

export type PickRecords = {
  picks: PickFull[];
  /** Real-money first-half picks only. */
  record: Record3 | null;
  /** Paper first-half picks, kept apart so they never flatter the real ledger. */
  paperRecord: Record3 | null;
};

export async function getPicks(season: number): Promise<PickRecords> {
  const picks = await loadPicks(season);
  const graded = picks.filter((p) => p.graded);
  return {
    picks,
    record: recordFrom(graded.filter(isRealFirstHalf)),
    paperRecord: recordFrom(graded.filter(isPaperFirstHalf)),
  };
}

export type CreatePickInput = {
  gameId: number;
  market?: "1H" | "full"; // default 1H
  line: number;
  stake?: number;
  price?: number;
  note?: string;
  isPaper?: boolean;
  verdict?: Verdict;
  reason?: PickReason;
  gap?: number | null;
  ev?: number | null;
  hrLine?: number | null;
};

export type CreatePickResult = {
  /** False when the tracking columns are missing and the pick was stored without its snapshot. */
  tracked: boolean;
};

// Insert a ManualPick, freezing the model's current score+line and the This
// Week verdict onto it.
export async function createPick(
  input: CreatePickInput,
): Promise<CreatePickResult> {
  const game = await prisma.games.findUnique({
    where: { id: input.gameId },
    select: { season: true, week: true, home_team: true, away_team: true },
  });
  if (!game) throw new Error("game not found");

  const market = input.market === "full" ? "full" : "1H";

  // The model (predictions) is 1H-only — only freeze its read onto a 1H pick.
  // Prefer the MODEL row over the display-only derived_lines row (the same
  // rule as board.ts: post_derived_lines writes seconds after scoring, so
  // "newest" alone picked the reference row). model_line_at_pick is OUR
  // NUMBER (bv_line) — the value Results compares your line against — with
  // the scoring line as a fallback for legacy rows that have no bv_line.
  const pred =
    market === "1H"
      ? await prisma.$queryRaw<
          {
            under_score: number | bigint | null;
            bv_line: number | null;
            line_used: number | null;
            factors_json: string | null;
          }[]
        >`
    SELECT under_score, bv_line, line_used, factors_json FROM predictions
    WHERE game_id = ${input.gameId}
    ORDER BY (model_version = 'derived_lines') ASC, created_at DESC
    LIMIT 1
  `
      : [];
  const modelScore =
    pred[0]?.under_score == null ? null : Number(pred[0].under_score);
  const modelLine = pred[0]?.bv_line ?? pred[0]?.line_used ?? null;
  const factorsAtPick = pred[0]?.factors_json ?? null;

  const isPaper = input.isPaper === true;
  // Flat 1 unit for real AND paper (paper record reads in units; is_paper keeps
  // it out of the bankroll). The client's stake is never trusted.
  const stake = isPaper ? PAPER_STAKE : DEFAULT_STAKE;
  const price = input.price ?? -110;
  const note = input.note ?? null;
  const placedAt = new Date().toISOString();
  const verdict = input.verdict ?? null;
  const reason = input.reason ?? null;
  const gap = input.gap ?? null;
  const ev = input.ev ?? null;
  const hrLine = input.hrLine ?? null;

  // Postgres is strict: cast the ISO string to a timestamp and use real
  // booleans (SQLite tolerated a text date + integer 0; Neon/PG won't).
  try {
    await prisma.$executeRaw`
      INSERT INTO manual_picks
        (game_id, season, week, home_team, away_team, side, market, line, price,
         stake, is_paper, placed_at, note, model_score_at_pick, model_line_at_pick,
         factors_json_at_pick, graded, verdict_at_pick, reason, gap_at_pick,
         ev_at_pick, hr_line_at_pick)
      VALUES
        (${input.gameId}, ${game.season}, ${game.week}, ${game.home_team},
         ${game.away_team}, 'under', ${market}, ${input.line}, ${price}, ${stake},
         ${isPaper}, ${placedAt}::timestamp, ${note}, ${modelScore}, ${modelLine},
         ${factorsAtPick}, false, ${verdict}, ${reason}, ${gap}, ${ev}, ${hrLine})
    `;
    return { tracked: true };
  } catch (e) {
    if (!isMissingColumn(e)) throw e;
    console.warn(
      "manual_picks tracking columns missing — pick stored without snapshot",
    );
    await prisma.$executeRaw`
      INSERT INTO manual_picks
        (game_id, season, week, home_team, away_team, side, market, line, price,
         stake, is_paper, placed_at, note, model_score_at_pick, model_line_at_pick,
         factors_json_at_pick, graded)
      VALUES
        (${input.gameId}, ${game.season}, ${game.week}, ${game.home_team},
         ${game.away_team}, 'under', ${market}, ${input.line}, ${price}, ${stake},
         ${isPaper}, ${placedAt}::timestamp, ${note}, ${modelScore}, ${modelLine},
         ${factorsAtPick}, false)
    `;
    return { tracked: false };
  }
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
