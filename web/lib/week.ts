// Which week is "this week"? Predictions can be posted ahead for several
// upcoming weeks (CFBD carries lines for future games), so "max week posted"
// jumps ahead of the games people are actually about to bet. The current week
// is the earliest posted week that still has a game yet to kick off; once every
// posted game has started, it is the latest week that has games.
//
// A game with an unknown kickoff (NULL start_date — e.g. a TBD-time row from a
// stale schedule pull) must not pin the board to its week while other games
// carry real dates: the decision is made from dated games whenever any exist,
// and only falls back to "unknown = upcoming" when no game has a date at all.

export type WeekGame = { week: number; startDate: Date | string | null };

function kickoffMs(g: WeekGame): number | null {
  if (g.startDate === null) return null;
  const t = new Date(g.startDate).getTime();
  return Number.isNaN(t) ? null : t;
}

export function defaultWeek(
  games: WeekGame[],
  now: Date = new Date(),
): number | null {
  if (games.length === 0) return null;
  const dated = games.filter((g) => kickoffMs(g) !== null);
  if (dated.length === 0) {
    // No kickoff known anywhere: treat every game as upcoming.
    return Math.min(...games.map((g) => g.week));
  }
  const upcoming = dated
    .filter((g) => kickoffMs(g)! > now.getTime())
    .map((g) => g.week);
  if (upcoming.length > 0) return Math.min(...upcoming);
  return Math.max(...dated.map((g) => g.week));
}

/** Sorted distinct weeks present. */
export function weeksOf(games: { week: number }[]): number[] {
  return [...new Set(games.map((g) => g.week))].sort((a, b) => a - b);
}
