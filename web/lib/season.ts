// Shared season resolution for every season-scoped view, so the board, picks,
// ledger, line study and records always agree on the default AND say so out
// loud when they fall back to an older season (early-season 2026 has no data
// yet — silently showing 2025 is indistinguishable from a live board).

/** CFB season N runs Aug N → early Jan N+1; June+ counts as the upcoming season
 *  (mirrors beatvegas/season.py::current_season). */
export function currentCfbSeason(now: Date = new Date()): number {
  return now.getUTCMonth() + 1 >= 6
    ? now.getUTCFullYear()
    : now.getUTCFullYear() - 1;
}

export type ResolvedSeason = {
  season: number;
  /** Set when the view silently fell back from the current CFB season to an
   *  older one (no data yet) — render a notice so stale ≠ live. Null when the
   *  user explicitly picked a season or the default IS current. */
  fallbackFrom: number | null;
};

export function resolveSeason(
  seasons: number[],
  requested?: string,
  now: Date = new Date(),
): ResolvedSeason {
  const req = requested ? Number(requested) : NaN;
  if (Number.isFinite(req) && seasons.includes(req)) {
    return { season: req, fallbackFrom: null };
  }
  const current = currentCfbSeason(now);
  const season = seasons[0] ?? current;
  return { season, fallbackFrom: season < current ? current : null };
}
