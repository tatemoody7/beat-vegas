import type { LedgerRow } from "@/lib/betLedger";
import { withBetOpening } from "@/lib/edge";
import type { HomeGame } from "@/lib/homeBoard";
import type { RecordRow } from "@/lib/records";

// The research season (docs/ROADMAP_2026.md, Tate 2026-10-07): every strategy
// runs on paper, and a visitor sees a game's rating only once the game has
// kicked off — results after the close, never a pre-kickoff signal someone
// could mistake for a recommendation. Since roadmap v1.4 (2026-10-08) the
// owner also bets first-half unders with real money, recorded separately; a
// visitor still never reads bet wording ("Bet one unit" becomes "Paper signal").
// The signed-in owner sees everything, as before. Every public surface that carries a rating, our
// number, a gap or a paper pick passes through one of the three gates below,
// server-side, before anything is rendered or serialised.

/** The site-wide banner (Tate's wording, 2026-10-08, roadmap v1.4). */
export const RESEARCH_BANNER =
  "2026 is a research season. Every strategy runs on paper and is judged against the closing line; the owner also bets first-half unders with real money, recorded separately. Ratings publish at kickoff.";

/** What a visitor reads in place of the action line before kickoff. */
export const HIDDEN_ACTION = "Rating publishes at kickoff.";

/** True when this viewer must not see this game's signal yet. */
export function hidesSignal(kickedOff: boolean, authed: boolean): boolean {
  return !authed && !kickedOff;
}

/** A kickoff (UTC ISO string or epoch ms) has passed at `now`. An unknown
 *  kickoff has NOT passed: the gate fails closed. A string without a zone is
 *  read as UTC — timestamps are naive UTC everywhere in this project. */
export function kickoffPassed(
  kickoff: string | number | null | undefined,
  now: Date,
): boolean {
  if (kickoff === null || kickoff === undefined) return false;
  const ms =
    typeof kickoff === "number"
      ? kickoff
      : Date.parse(
          /[zZ]|[+-]\d\d:?\d\d$/.test(kickoff)
            ? kickoff
            : `${kickoff.replace(" ", "T")}Z`,
        );
  return Number.isFinite(ms) && ms <= now.getTime();
}

/** The board and the game page: a pre-kickoff game, for a visitor, keeps its
 *  matchup, kickoff, lines, form and news, and loses everything that says what
 *  to bet — rating, rank, cap slot, our number, the gap, the kill line, the
 *  factor read and the "bet logged" chip. */
export function gateGame(g: HomeGame, authed: boolean): HomeGame {
  if (!hidesSignal(g.kickedOff, authed)) {
    // A visitor after kickoff sees the rating, never bet wording: the
    // owner's real bets are his, recorded separately (roadmap v1.4).
    if (authed) return g;
    return {
      ...g,
      edge: { ...g.edge, action: withBetOpening(g.edge.action, false) },
    };
  }
  return {
    ...g,
    signalHidden: true,
    picked: false,
    gap: null,
    boardRank: null,
    capRank: null,
    overCap: false,
    row: {
      ...g.row,
      bvLine: null,
      factors: { ...g.row.factors, factor_board: [] },
    },
    edge: {
      ...g.edge,
      // The board sorts a day by score then gap (homeBoard.sortGames): zeroing
      // both makes a hidden day sort by kickoff and name, so the ORDER of the
      // rows cannot rank the games either.
      score: 0,
      action: HIDDEN_ACTION,
      kill: { line: null, price: null, text: "" },
      gap: null,
    },
  };
}

/** /records and its CSV: our number, the gap, its z and the rank stay blank
 *  until the game kicks off. The market line and the result are public. The
 *  rows arrive ordered by week then model rank, so a blanked row also loses
 *  its place: within its week it follows the kicked-off rows, ordered by
 *  kickoff and then the away team, and the order cannot rank the games. */
export function gateRecords(
  rows: RecordRow[],
  authed: boolean,
  now: Date,
): RecordRow[] {
  if (authed) return rows;
  const tagged = rows.map((r, i) => {
    const open = !kickoffPassed(r.kickoffMs, now);
    const row = open
      ? { ...r, bvLine: null, bvGap: null, bvGapZ: null, rank: null }
      : r;
    return { row, i, open };
  });
  const kick = (r: RecordRow) => r.kickoffMs ?? Number.POSITIVE_INFINITY;
  tagged.sort(
    (a, b) =>
      a.row.week - b.row.week ||
      Number(a.open) - Number(b.open) ||
      (a.open
        ? kick(a.row) - kick(b.row) || a.row.away.localeCompare(b.row.away)
        : a.i - b.i),
  );
  return tagged.map((t) => t.row);
}

/** The bet ledger on Results and its CSV: a row exists to say what was bet,
 *  so a row whose game has not kicked off is withheld entirely from a visitor
 *  (paper or real). Every row after kickoff stays public, losses included. */
export function gateLedger(
  rows: LedgerRow[],
  authed: boolean,
  now: Date,
): LedgerRow[] {
  if (authed) return rows;
  return rows.filter((r) => kickoffPassed(r.kickoff, now));
}
