import type { LedgerRow } from "@/lib/betLedger";
import { withBetOpening } from "@/lib/edge";
import type { HomeGame } from "@/lib/homeBoard";
import type { RecordRow } from "@/lib/records";

// The research season (docs/ROADMAP_2026.md): every strategy runs on paper.
// Since roadmap v1.7 (Tate, 2026-10-10) a visitor sees the board and the game
// page as the owner does, ratings before kickoff included; the owner's real
// bets stay his (v1.4), so a visitor never reads bet wording ("Bet one unit"
// becomes "Paper signal") and never sees his "bet logged" chip before kickoff.
// The bet ledger, /records and both CSVs still withhold a game until it kicks
// off. The signed-in owner sees everything. Every public surface that carries
// a rating, our number, a gap or a paper pick passes through one of the three
// gates below, server-side, before anything is rendered or serialised.

/** The site-wide banner (Tate's wording, 2026-10-08, roadmap v1.4; "Florida,
 *  21+" from docs/LEGAL_MEMO_2026-10.md, roadmap v1.7; the ledger named a
 *  personal stake, roadmap v2.0, 2026-10-11). */
export const RESEARCH_BANNER =
  "2026 is a research season. Every strategy runs on paper and is judged against the closing line. The owner also bets first-half unders with real money as a personal stake, recorded separately and never evidence for any strategy. Florida, 21+.";

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

/** The board and the game page: a visitor sees the owner's board — rating,
 *  rank, our number, the gap, the kill line and the factor read, before kickoff
 *  too (roadmap v1.7) — in paper wording, never bet wording: the owner's real
 *  bets are his, recorded separately (v1.4). Before kickoff his "bet logged"
 *  chip stays his as well, as the bet ledger withholds the ticket until then
 *  (`gateLedger`). */
export function gateGame(g: HomeGame, authed: boolean): HomeGame {
  if (authed) return g;
  // The weekly cap is the owner's real-money rule (v1.4): its slot number,
  // its "past the cap" chip and the "real money needs N games" clause reveal
  // which games his stake will take, so a visitor never sees them (2026-10-14,
  // programme step 2). The rating, rank, our number and the gap stay.
  const paper = {
    ...g,
    edge: {
      ...g.edge,
      action: withoutRealMoney(withBetOpening(g.edge.action, false)),
    },
  };
  // After kickoff the ledger shows the ticket anyway, so the slot can show too.
  return g.kickedOff
    ? paper
    : { ...paper, picked: false, capRank: null, overCap: false };
}

/** The early-season sentence names the real-money threshold; for a visitor it
 *  names the rating's instead. Every other sentence passes through unchanged. */
export function withoutRealMoney(action: string): string {
  return action.replace(/; real money needs (\d+)\./, "; a rating needs $1.");
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
      ? { ...r, bvLine: null, hrGap: null, consGap: null, rank: null }
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
