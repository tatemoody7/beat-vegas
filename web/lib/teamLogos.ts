import teamLogos from "@/data/team_logos.json";

// Which teams have a vendored logo mark, and where it lives.
//
// The marks are real files under web/public/logos/<cfbd id>.png, put there by
// scripts/fetch_team_logos.py (CFBD /teams -> the logos-dark artwork, which is
// the dark-background variant the navy canvas needs). They are vendored rather
// than hotlinked so a CDN outage cannot blank the board and so `npm run dev`
// works offline.
//
// team_logos.json is the index of what actually landed: an id absent from it has
// no file, and TeamLogo renders NOTHING for it rather than a broken image or a
// placeholder. FCS/NAIA opponents are the usual case.
//
// Unlike data/fbs_teams.json and data/multiplier.json this file has no repo-root
// twin, so it is deliberately not in FILES in lib/dataMirror.test.ts — the PNGs
// it indexes are web assets and nothing in beatvegas/ reads it.

const INDEX: Record<string, string> = teamLogos;

/** Public path to a team's mark, or null when we have no artwork for it. */
export function logoSrc(teamId: number | null | undefined): string | null {
  if (teamId === null || teamId === undefined) return null;
  return INDEX[String(teamId)] === undefined ? null : `/logos/${teamId}.png`;
}

/** The school name behind an id, for tests and debugging. */
export function logoSchool(teamId: number | null | undefined): string | null {
  if (teamId === null || teamId === undefined) return null;
  return INDEX[String(teamId)] ?? null;
}
