import multiplier from "../../data/multiplier.json";
import fbsTeams from "../../data/fbs_teams.json";

// Mirror of beatvegas/etl/proxy_line.py::fh_share + etl/fbs.py. The proxy
// first-half line (used only where no real 1H line exists) is a STEP share of
// the full-game total: a flat base below the blowout spread cut, a higher share
// at or above it (favorites score relatively more early). Both artifacts are
// git-tracked so the web reads the exact numbers the Python lane fitted.

type StepCoeffs = {
  kind: string;
  base: number;
  blowout: number;
  cut: number;
};

const COEFFS = multiplier as StepCoeffs;
const SHARE_CLAMP: [number, number] = [0.48, 0.56];
const DEFAULT_SHARE = 0.52;

export const PROXY_BASE_SHARE =
  COEFFS.kind === "step" ? COEFFS.base : DEFAULT_SHARE;
export const PROXY_BLOWOUT_SHARE =
  COEFFS.kind === "step" ? COEFFS.blowout : DEFAULT_SHARE;
export const PROXY_BLOWOUT_CUT = COEFFS.kind === "step" ? COEFFS.cut : Infinity;

const clamp = (x: number) =>
  Math.min(Math.max(x, SHARE_CLAMP[0]), SHARE_CLAMP[1]);

/** Expected first-half share of the full-game total for a given spread. */
export function fhShare(spread: number | null | undefined): number {
  if (COEFFS.kind !== "step") return DEFAULT_SHARE;
  const noSpread =
    spread === null || spread === undefined || !Number.isFinite(spread);
  const share =
    !noSpread && Math.abs(spread as number) >= COEFFS.cut
      ? COEFFS.blowout
      : COEFFS.base;
  return clamp(share);
}

const roundHalf = (x: number) => Math.round(x * 2) / 2;

/** The synthetic 1H line we grade against, rounded to the half point. */
export function proxyTotal(
  fullGameTotal: number,
  spread: number | null | undefined,
): number {
  return roundHalf(fullGameTotal * fhShare(spread));
}

/** "49.8% of the total (53.8% for 21+ point spreads)" — for prose. */
export function proxyShareText(): string {
  const p = (x: number) => `${(100 * x).toFixed(1)}%`;
  if (COEFFS.kind !== "step")
    return `${p(DEFAULT_SHARE)} of the full-game total`;
  return `${p(COEFFS.base)} of the full-game total (${p(COEFFS.blowout)} when the spread is ${COEFFS.cut}+ points)`;
}

// --- FBS membership ---------------------------------------------------------
const FBS = fbsTeams as Record<string, string[]>;
const fbsSets = new Map<number, Set<string>>();
for (const [season, schools] of Object.entries(FBS)) {
  fbsSets.set(Number(season), new Set(schools));
}

/** Seasons the snapshot covers. */
export const FBS_SEASONS = [...fbsSets.keys()].sort((a, b) => a - b);

/** True when both teams were FBS in that season. Unknown season → false (never guess). */
export function isFbsGame(
  season: number,
  home: string | null,
  away: string | null,
): boolean {
  const set = fbsSets.get(season);
  if (!set || !home || !away) return false;
  return set.has(home) && set.has(away);
}

export const hasFbsSeason = (season: number): boolean => fbsSets.has(season);
