import { prisma } from "@/lib/prisma";
import type { KickZones } from "@/lib/kickoffClock";

// The loader behind lib/kickoffClock: the kickoff, the venue's zone and the
// visitor's home zone for ONE game. The home venue is the visitor's most-used
// home venue that season, ties to the lowest venue id — the same pick as
// situational.py's modal `home_base`. Kept apart from the pure module so a
// client component can format without pulling prisma into the browser.

type Raw = {
  kickoff: string | null;
  venue_tz: string | null;
  away_home_tz: string | null;
};

/** A `timestamp without time zone` read as text ("2026-09-18 20:12:04.5")
 *  holds UTC: append the Z ourselves. Handing the bare value to a Date is how
 *  you get a 4-5 h shift (lib/boardHealth.ts makes the same move). */
export function isoFromNaive(s: string | null | undefined): string | null {
  if (!s) return null;
  const t = s.trim();
  const d = new Date(
    /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(t)
      ? `${t.replace(" ", "T")}Z`
      : t,
  );
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

const isMissingColumn = (e: unknown): boolean =>
  /column .* does not exist|no such column/i.test(
    String((e as Error)?.message ?? e),
  );

/** The game's kickoff zones, or null when the game is unknown. Before
 *  migrate.yml adds venues.timezone the zones read null (no clock shown). */
export async function getKickZones(gameId: number): Promise<KickZones | null> {
  let rows: Raw[];
  try {
    rows = await prisma.$queryRaw<Raw[]>`
      SELECT g.start_date::text AS kickoff, v.timezone AS venue_tz,
             (SELECT v2.timezone
                FROM games g2 JOIN venues v2 ON v2.id = g2.venue_id
               WHERE g2.season = g.season AND g2.home_team = g.away_team
               GROUP BY g2.venue_id, v2.timezone
               ORDER BY count(*) DESC, g2.venue_id ASC
               LIMIT 1) AS away_home_tz
      FROM games g LEFT JOIN venues v ON v.id = g.venue_id
      WHERE g.id = ${gameId}`;
  } catch (e) {
    if (isMissingColumn(e)) return null;
    throw e;
  }
  if (rows.length === 0) return null;
  const r = rows[0];
  return {
    kickoff: isoFromNaive(r.kickoff),
    venueTz: r.venue_tz,
    awayHomeTz: r.away_home_tz,
  };
}
