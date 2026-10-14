// The /api/health body and its public projection (2026-10-14, programme step 3).
// Kept out of the route file so the projection can be unit-tested: a Next route
// module may export only its handlers.

export type JobHealth = {
  verdict: string | null;
  at: string | null;
  note: string | null;
};
export type HealthBody = {
  ok: true;
  rulePaused: boolean;
  rulePauseReadable: boolean;
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

/** What a visitor reads: the body without the owner's operational detail —
 *  no pause switch, no API budgets, no per-job run note, and each warning cut
 *  before its "Run:" link. Keys are removed, never nulled, so a reader cannot
 *  mistake "hidden" for "off". */
export function publicBody(full: HealthBody) {
  const {
    rulePaused: _p,
    rulePauseReadable: _r,
    gauges: { cfbdCallsRemaining: _c, oddsCreditsRemaining: _o, ...gauges },
    ...rest
  } = full;
  void _p;
  void _r;
  void _c;
  void _o;
  return {
    ...rest,
    gauges: {
      ...gauges,
      health: Object.fromEntries(
        Object.entries(gauges.health).map(([id, h]) => [
          id,
          { verdict: h.verdict, at: h.at },
        ]),
      ),
    },
    warnings: full.warnings.map((w) => w.replace(/ Run: \S+$/, "")),
  };
}
