// The /api/health body (2026-10-14, programme step 3). Kept out of the route
// file because a Next route module may export only its handlers. Since
// 2026-10-18 (the site is a read-only record, D17) there is one body for
// everyone: the pause switch left it (nothing on the site reads `rule_paused`
// any more) and the owner-only projection went with the cookie.

export type JobHealth = {
  verdict: string | null;
  at: string | null;
  note: string | null;
};
export type HealthBody = {
  ok: true;
  lastFullGameCapture: string | null;
  resultsStale: boolean;
  buildMissed: boolean;
  lastBuiltAt?: string | null;
  resultsBehindHours: number;
  unscoredPlayedGames: number;
  lastGradedAt?: string | null;
  fullGameSnapshotsLast24h: number;
  fullGameGamesLast24h: number;
  gauges: {
    cfbdCallsRemaining: number | null;
    oddsCreditsRemaining: number | null;
    lastCloseCaptureAt: string | null;
    lastCloseCaptureEvents: number | null;
    lastGradeCompletedAt: string | null;
    closeCoveragePct: number | null;
    closeCoverage: string | null;
    lastDispatch: Record<string, string | null>;
    health: Record<string, JobHealth>;
  };
  warnings: string[];
};
