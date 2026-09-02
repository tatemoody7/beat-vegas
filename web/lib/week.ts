// Which week is "this week"? Predictions can be posted ahead for several
// upcoming weeks (CFBD carries lines for future games), so "max week posted"
// jumps ahead of the games people are actually about to bet. The current week
// is the earliest posted week that still has a game yet to kick off; once every
// posted game has started, it is the latest week that has games.

export type WeekGame = { week: number; startDate: Date | string | null };

export function defaultWeek(
  games: WeekGame[],
  now: Date = new Date(),
): number | null {
  if (games.length === 0) return null;
  const upcoming = games
    .filter((g) => {
      if (g.startDate === null) return true; // unknown kickoff: treat as upcoming
      const t = new Date(g.startDate).getTime();
      return Number.isNaN(t) || t > now.getTime();
    })
    .map((g) => g.week);
  if (upcoming.length > 0) return Math.min(...upcoming);
  return Math.max(...games.map((g) => g.week));
}

/** Sorted distinct weeks present. */
export function weeksOf(games: { week: number }[]): number[] {
  return [...new Set(games.map((g) => g.week))].sort((a, b) => a - b);
}
