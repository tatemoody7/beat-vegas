import { loadResults } from "@/lib/ledger";
import {
  isPaperFirstHalf,
  isRealFirstHalf,
  loadPicks,
  type PickFull,
  isOffPolicy,
} from "@/lib/picks";
import { recordFrom, type Record3 } from "@/lib/record";
import type { PickReason } from "@/lib/verdict";

// Results data: your picks week by week, by the reason each was logged, and by
// the gate that blocked a real bet.
//
// This used to also build a six-row per-week scorecard (Market/Model/You across
// both markets). The scorecard was deleted from /results on 2026-09-10 but the
// computation stayed behind it — six record passes over the season on every
// render, feeding nothing, and duplicating what getLedger already renders.

export type WeekRow = {
  week: number;
  real: Record3 | null;
  paper: Record3 | null;
  /** Real-money 1H picks logged that week (pending included). */
  realBets: number;
  paperBets: number;
};

export type ReasonRow = {
  reason: PickReason | "untagged" | "off_policy";
  real: Record3 | null;
  paper: Record3 | null;
  realBets: number;
  paperBets: number;
};

/** Paper ledger by the gate that blocked a real bet (docs/BETTING_POLICY.md). */
export type BlockerKey =
  | "none"
  | "price"
  | "off_market"
  | "no_fair_price"
  | "qb_out"
  | "cap"
  /** A card input failed on the build (sweep, injury feed, pace, tempo): held, paper only. */
  | "degraded"
  | "untagged";

export type BlockerRow = {
  blocker: BlockerKey;
  paper: Record3 | null;
  paperBets: number;
};

export type WeeklyReview = {
  /** The week shown in the scorecard; null when nothing is graded yet. */
  week: number | null;
  /** Weeks with a graded result or a logged pick. */
  weeks: number[];
  byWeek: WeekRow[];
  byReason: ReasonRow[];
  /** Paper first-half picks by the gate that blocked a real bet. */
  byBlocker: BlockerRow[];
  /** Picks for the selected week (or all, when week is "all"). */
  picks: PickFull[];
};

const graded = (ps: PickFull[]) => ps.filter((p) => p.graded);

/** Pure: week-by-week table over every pick. */
export function weekRows(picks: PickFull[]): WeekRow[] {
  const weeks = [
    ...new Set(picks.map((p) => p.week).filter((w): w is number => w !== null)),
  ].sort((a, b) => a - b);
  return weeks.map((week) => {
    const wk = picks.filter((p) => p.week === week);
    return {
      week,
      real: recordFrom(graded(wk).filter(isRealFirstHalf)),
      paper: recordFrom(graded(wk).filter(isPaperFirstHalf)),
      realBets: wk.filter(isRealFirstHalf).length,
      paperBets: wk.filter(isPaperFirstHalf).length,
    };
  });
}

const REASON_ORDER: ReasonRow["reason"][] = [
  "model_gap",
  "price_edge",
  "manual",
  "untagged",
];

/** Pure: by-reason table; rows with no picks at all are omitted. */
export function reasonRows(picks: PickFull[]): ReasonRow[] {
  const rows: ReasonRow[] = REASON_ORDER.map((reason) => {
    const rs = picks.filter((p) => (p.reason ?? "untagged") === reason);
    return {
      reason,
      real: recordFrom(graded(rs).filter(isRealFirstHalf)),
      paper: recordFrom(graded(rs).filter(isPaperFirstHalf)),
      realBets: rs.filter(isRealFirstHalf).length,
      paperBets: rs.filter(isPaperFirstHalf).length,
    };
  }).filter((r) => r.realBets + r.paperBets > 0);
  // Real money placed against the verdict is its own line, so the overrides
  // can be judged against the system (docs/BETTING_POLICY.md).
  const offs = picks.filter(isOffPolicy);
  if (offs.length) {
    rows.push({
      reason: "off_policy",
      real: recordFrom(graded(offs).filter(isRealFirstHalf)),
      paper: null,
      realBets: offs.filter(isRealFirstHalf).length,
      paperBets: 0,
    });
  }
  return rows;
}

const BLOCKER_ORDER: BlockerKey[] = [
  "none",
  "price",
  "off_market",
  "no_fair_price",
  "qb_out",
  "cap",
  "degraded",
  "untagged",
];

const asBlocker = (v: string | null): BlockerKey =>
  v === "none" ||
  v === "price" ||
  v === "off_market" ||
  v === "no_fair_price" ||
  v === "qb_out" ||
  v === "cap" ||
  v === "degraded"
    ? v
    : "untagged";

/** Pure: the paper ledger by gate — what each gate would have done. Rows with
 *  no picks are omitted. Real picks never enter (they are not tagged). */
export function blockerRows(picks: PickFull[]): BlockerRow[] {
  const paper = picks.filter(isPaperFirstHalf);
  return BLOCKER_ORDER.map((blocker) => {
    const rs = paper.filter((p) => asBlocker(p.blocker) === blocker);
    return {
      blocker,
      paper: recordFrom(graded(rs)),
      paperBets: rs.length,
    };
  }).filter((r) => r.paperBets > 0);
}

export async function getWeeklyReview(
  season: number,
  week?: number | "all",
): Promise<WeeklyReview> {
  const [res, picks] = await Promise.all([
    loadResults(season),
    loadPicks(season),
  ]);

  const resWeeks = res.map((r) => Number(r.week));
  const pickWeeks = picks.map((p) => Number(p.week));
  const weeks = [...new Set([...resWeeks, ...pickWeeks])]
    .filter((w) => Number.isFinite(w))
    .sort((a, b) => a - b);
  const wk =
    week === "all"
      ? null
      : week !== undefined && weeks.includes(week)
        ? week
        : (weeks[weeks.length - 1] ?? null);

  const inWeek = <T extends { week: number | bigint | null }>(rows: T[]) =>
    wk === null ? rows : rows.filter((x) => Number(x.week) === wk);
  const mine = inWeek(picks);

  return {
    week: wk,
    weeks,
    byWeek: weekRows(picks),
    byReason: reasonRows(picks),
    byBlocker: blockerRows(picks),
    picks: mine,
  };
}
