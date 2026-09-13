import { prisma } from "@/lib/prisma";

// Is the results pipeline actually running?
//
// On 2026-09-12/13 grade.yml failed four runs straight and nothing said so: the
// only failure channel is GitHub's failed-run email. Week 2 sat with finals for
// 14 of 303 games and 0 of 31 picks graded for two days while the board looked
// completely normal. The board is where Tate looks, so the board is where the
// alarm belongs.
//
// The tell is a game THE MODEL RATED that kicked off long enough ago to be over
// and still has no final score. The rated set is exactly the board: a
// game_records row is written when the week is scored, before kickoff.
//
// "A game a book priced" was the first cut and it was too loose -- books price
// FCS-vs-FCS games, ESPN's FBS feed does not cover them and nothing here reads
// them, so 15 of those sat unscored after the 2026-09-13 backfill and would
// have kept the banner lit forever. A banner that is always on is a banner
// nobody reads.

// A game is done ~4h after kickoff and grade.yml runs twice a day (6:30am and
// noon ET). 18h means at least one grading window came and went.
export const STALE_AFTER_HOURS = 18;

export type GradeHealth = {
  lastGradedAt: Date | null;
  /** Priced games that kicked off over STALE_AFTER_HOURS ago with no score. */
  unscored: number;
  /** Kickoff of the oldest of those — how far behind we actually are. */
  oldestUnscoredKick: Date | null;
};

export type Staleness =
  | { stale: false }
  | {
      stale: true;
      unscored: number;
      behindHours: number;
      lastGradedAt: Date | null;
    };

/** Pure: turn the counts into the thing the banner renders. */
export function staleness(h: GradeHealth, now: Date = new Date()): Staleness {
  if (h.unscored <= 0 || !h.oldestUnscoredKick) return { stale: false };
  const behindHours = Math.floor(
    (now.getTime() - h.oldestUnscoredKick.getTime()) / 3_600_000,
  );
  return {
    stale: true,
    unscored: h.unscored,
    behindHours,
    lastGradedAt: h.lastGradedAt,
  };
}

// These columns are `timestamp without time zone` holding UTC. Read them as
// text and append the Z ourselves, the same way lib/movement.ts::shortT does —
// handing a naive timestamp straight to a Date is how you get a 4-5h shift.
const utc = (s: string | null): Date | null => {
  if (!s) return null;
  const d = new Date(`${s}Z`);
  return Number.isNaN(d.getTime()) ? null : d;
};

export async function getGradeHealth(season: number): Promise<GradeHealth> {
  const rows = await prisma.$queryRaw<
    {
      last_graded: string | null;
      unscored: bigint;
      oldest_kick: string | null;
    }[]
  >`
    SELECT (SELECT to_char(MAX(graded_at), 'YYYY-MM-DD"T"HH24:MI:SS')
              FROM game_records) AS last_graded,
           COUNT(*) AS unscored,
           to_char(MIN(g.start_date), 'YYYY-MM-DD"T"HH24:MI:SS') AS oldest_kick
      FROM games g
     WHERE g.season = ${season}
       AND g.home_points IS NULL
       AND EXISTS (SELECT 1 FROM game_records gr WHERE gr.game_id = g.id)
       AND g.start_date < (NOW() AT TIME ZONE 'utc')
             - (${STALE_AFTER_HOURS} * INTERVAL '1 hour')`;
  const r = rows[0];
  return {
    lastGradedAt: utc(r?.last_graded ?? null),
    unscored: Number(r?.unscored ?? 0),
    oldestUnscoredKick: utc(r?.oldest_kick ?? null),
  };
}
