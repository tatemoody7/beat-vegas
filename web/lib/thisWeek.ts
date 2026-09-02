import { getBoard, type BoardRow } from "@/lib/board";
import { getLineCheck, type LineCheckRow } from "@/lib/lineCheck";
import { getPicks, isRealFirstHalf, type PickFull } from "@/lib/picks";
import { getPreviewByGame, type PreviewGame } from "@/lib/preview";
import type { Record3 } from "@/lib/record";
import { verdictFor, WEEKLY_BET_CAP, type VerdictResult } from "@/lib/verdict";
import { defaultWeek, weeksOf } from "@/lib/week";

// "This Week" data layer: composes the board, the Hard Rock price check, the
// injury/news preview and the pick ledger into one verdict per game plus a
// bankroll strip. Reads only.

export type ThisWeekGame = {
  row: BoardRow;
  check: LineCheckRow | null;
  verdict: VerdictResult;
  /** Injuries + news for the game (unofficial), when the preview job has run. */
  preview: PreviewGame | null;
  /** A real-money 1H pick already logged on this game this season. */
  picked: boolean;
  /** Kickoff has passed (no more bets). */
  kickedOff: boolean;
};

export type Bankroll = {
  startUsd: number;
  unitUsd: number;
  /** Signed units from graded real-money 1H picks this season. */
  realUnits: number;
  currentUsd: number;
  /** Real-money 1H picks logged for the displayed week (pending or graded). */
  weekBets: number;
  cap: number;
  real: Record3 | null;
  paper: Record3 | null;
};

export type ThisWeek = {
  season: number;
  week: number | null;
  /** Weeks that have games on the board (for the week selector). */
  weeks: number[];
  /** Every row is a derived reference line — the model has no read this week. */
  noModel: boolean;
  games: ThisWeekGame[];
  counts: { bet: number; watch: number; pass: number };
  bankroll: Bankroll;
};

// Bankroll policy (docs/BETTING_POLICY.md): fixed dollar unit, flat staking.
// Env-driven so a top-up is a Vercel setting, not a deploy.
function envNum(name: string, fallback: number): number {
  const v = Number(process.env[name]);
  return Number.isFinite(v) && v > 0 ? v : fallback;
}

export async function getThisWeek(
  season: number,
  requestedWeek?: number,
  now: Date = new Date(),
): Promise<ThisWeek> {
  const [board, checks, { picks, record, paperRecord }] = await Promise.all([
    getBoard(season),
    getLineCheck(season, "1h"),
    getPicks(season),
  ]);

  // Default to the week you are about to bet (earliest week with a game still
  // to kick off — lib/week.ts); ?week= lets Tate review a past one.
  const weeks = weeksOf(board);
  const week =
    requestedWeek !== undefined && weeks.includes(requestedWeek)
      ? requestedWeek
      : defaultWeek(board, now);
  const rows = board.filter((b) => b.week === week);
  const previews =
    week === null
      ? new Map<number, PreviewGame>()
      : await getPreviewByGame(season, week);
  const checkById = new Map(checks.map((c) => [c.gameId, c]));
  const noModel =
    rows.length > 0 &&
    rows.every(
      (r) => r.factors.line_kind === "derived_fg" || r.underScore === null,
    );

  // Only real-money FIRST-HALF picks count toward the record, the bankroll and
  // the weekly cap (full game is context, paper is tracked apart).
  const real1H = picks.filter(isRealFirstHalf);
  const pickedGames = new Set(real1H.map((p) => p.gameId));
  const pickedKey = new Set(real1H.map((p) => `${p.away}@${p.home}`));

  const games: ThisWeekGame[] = rows.map((row) => {
    const check = checkById.get(row.gameId) ?? null;
    const verdict = verdictFor({
      away: row.away,
      home: row.home,
      derived: row.factors.line_kind === "derived_fg",
      underScore: row.underScore,
      bvLine: row.bvLine,
      liveLine: row.curLine,
      fallbackLine: row.factors.line ?? null,
      gap: row.liveGap,
      z: row.liveGapZ,
      hrLine: check?.hrLine ?? null,
      hrUnderPrice: check?.hrUnderPrice ?? null,
      ev: check?.ev ?? null,
      evVerdict: check?.evVerdict ?? "na",
      fhShare: row.factors.fh_share ?? null,
      qbOut: Boolean(row.factors.qb_out_home || row.factors.qb_out_away),
      qbOutDetail: row.factors.qb_out_detail ?? null,
      bvAdjust: row.bvAdjust,
      bvAdjustReason: row.bvAdjustReason,
      factorBoard: row.factors.factor_board,
    });
    const start = row.startDate ? new Date(row.startDate).getTime() : NaN;
    return {
      row,
      check,
      verdict,
      preview: previews.get(row.gameId) ?? null,
      picked:
        pickedGames.has(row.gameId) || pickedKey.has(`${row.away}@${row.home}`),
      kickedOff: Number.isFinite(start) && start <= now.getTime(),
    };
  });

  const order = { BET: 0, WATCH: 1, PASS: 2 } as const;
  games.sort(
    (a, b) =>
      order[a.verdict.verdict] - order[b.verdict.verdict] ||
      b.verdict.strength - a.verdict.strength ||
      a.row.away.localeCompare(b.row.away),
  );

  const counts = {
    bet: games.filter((g) => g.verdict.verdict === "BET").length,
    watch: games.filter((g) => g.verdict.verdict === "WATCH").length,
    pass: games.filter((g) => g.verdict.verdict === "PASS").length,
  };

  const startUsd = envNum("BANKROLL_USD", 100);
  const unitUsd = envNum("UNIT_USD", 10);
  const realUnits = real1H
    .filter((p: PickFull) => p.graded)
    .reduce((a, p) => a + (p.units ?? 0), 0);
  const bankroll: Bankroll = {
    startUsd,
    unitUsd,
    realUnits,
    currentUsd: Math.round((startUsd + realUnits * unitUsd) * 100) / 100,
    weekBets: real1H.filter((p) => p.week === week).length,
    cap: WEEKLY_BET_CAP,
    real: record,
    paper: paperRecord,
  };

  return { season, week, weeks, noModel, games, counts, bankroll };
}
