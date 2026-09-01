import { getBoard, type BoardRow } from "@/lib/board";
import { getLineCheck, type LineCheckRow } from "@/lib/lineCheck";
import { getPicks, type PickFull } from "@/lib/picks";
import type { Record3 } from "@/lib/ledger";
import { verdictFor, WEEKLY_BET_CAP, type VerdictResult } from "@/lib/verdict";

// "This Week" data layer: composes the board, the Hard Rock price check and
// the pick ledger into one verdict per game plus a bankroll strip. Reads only.

export type ThisWeekGame = {
  row: BoardRow;
  check: LineCheckRow | null;
  verdict: VerdictResult;
  /** A real-money pick already logged on this game/1H this season. */
  picked: boolean;
};

export type Bankroll = {
  startUsd: number;
  unitUsd: number;
  /** Signed units from graded real-money picks this season. */
  realUnits: number;
  currentUsd: number;
  /** Real-money picks logged for the displayed week (pending or graded). */
  weekBets: number;
  cap: number;
  real: Record3 | null;
  paper: Record3 | null;
};

export type ThisWeek = {
  season: number;
  week: number | null;
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
): Promise<ThisWeek> {
  const [board, checks, { picks, record, paperRecord }] = await Promise.all([
    getBoard(season),
    getLineCheck(season, "1h"),
    getPicks(season),
  ]);

  // Default to the latest scored week; ?week= lets Tate review a past one.
  const weeks = new Set(board.map((b) => b.week));
  const week =
    requestedWeek !== undefined && weeks.has(requestedWeek)
      ? requestedWeek
      : board.length
        ? Math.max(...board.map((b) => b.week))
        : null;
  const rows = board.filter((b) => b.week === week);
  const checkById = new Map(checks.map((c) => [c.gameId, c]));
  const noModel =
    rows.length > 0 &&
    rows.every(
      (r) => r.factors.line_kind === "derived_fg" || r.underScore === null,
    );

  const realPicks = picks.filter((p) => !p.isPaper);
  // PickFull carries team names, not game ids — match on the matchup.
  const pickedKey = new Set(
    realPicks
      .filter((p) => p.market === "1H")
      .map((p) => `${p.away}@${p.home}`),
  );

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
      qbOut: Boolean(row.factors.qb_out_home || row.factors.qb_out_away),
      qbOutDetail: row.factors.qb_out_detail ?? null,
      bvAdjust: row.bvAdjust,
      bvAdjustReason: row.bvAdjustReason,
      factorBoard: row.factors.factor_board,
    });
    return {
      row,
      check,
      verdict,
      picked: pickedKey.has(`${row.away}@${row.home}`),
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
  const realUnits = realPicks
    .filter((p: PickFull) => p.graded)
    .reduce((a, p) => a + (p.units ?? 0), 0);
  const bankroll: Bankroll = {
    startUsd,
    unitUsd,
    realUnits,
    currentUsd: Math.round((startUsd + realUnits * unitUsd) * 100) / 100,
    weekBets: realPicks.filter((p) => p.week === week).length,
    cap: WEEKLY_BET_CAP,
    real: record,
    paper: paperRecord,
  };

  return { season, week, noModel, games, counts, bankroll };
}
