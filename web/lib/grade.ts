// The grade: one coloured 0–100 score per game, and one colour language for
// everything graded on the site. Pure — no DB — so it is unit-tested and the
// thresholds live in exactly one place.
//
//   score >= SCORE_BET_MIN   -> "bet"   (green)   the gap rule passed
//   score >= SCORE_WATCH_MIN -> "watch" (amber)   worth watching
//   else                     -> "pass"  (red)     nothing to act on
//
// A settled game is coloured by its RESULT, not its score: won = green,
// lost = red, push = grey (lib/grade.ts settledOf). Cyan is never a grade.

export type Grade = "bet" | "watch" | "pass";
export type Settled = "won" | "lost" | "push";
export type GradeColor = "good" | "warn" | "bad" | "push";

/** Score at and above which a game is a bet. The score is the gap alone, so
 *  a gap of exactly BET_GAP_PTS lands here (lib/edge.ts SCORE_PER_GAP_PT). */
export const SCORE_BET_MIN = 70;
/** Score at and above which a game is worth watching. */
export const SCORE_WATCH_MIN = 55;

export function gradeOf(score: number | null): Grade | null {
  if (score === null || !Number.isFinite(score)) return null;
  if (score >= SCORE_BET_MIN) return "bet";
  if (score >= SCORE_WATCH_MIN) return "watch";
  return "pass";
}

/** How the first-half under settled at `line`; null until both are known. */
export function settledOf(
  actualFirstHalf: number | null,
  line: number | null,
): Settled | null {
  if (actualFirstHalf === null || line === null) return null;
  if (!Number.isFinite(actualFirstHalf) || !Number.isFinite(line)) return null;
  if (actualFirstHalf < line) return "won";
  if (actualFirstHalf > line) return "lost";
  return "push";
}

const GRADE_COLOR: Record<Grade, GradeColor> = {
  bet: "good",
  watch: "warn",
  pass: "bad",
};

const SETTLED_COLOR: Record<Settled, GradeColor> = {
  won: "good",
  lost: "bad",
  push: "push",
};

/** The colour token a badge should carry: the result once settled, else the grade. */
export function gradeColor(
  score: number | null,
  settled: Settled | null = null,
): GradeColor {
  if (settled !== null) return SETTLED_COLOR[settled];
  const g = gradeOf(score);
  return g === null ? "push" : GRADE_COLOR[g];
}

/** The verdict tier as edgeScore names it (lib/edge.ts EdgeTier). */
export type VerdictTier = "BET" | "EDGE" | "PASS";

const TIER_COLOR: Record<VerdictTier, GradeColor> = {
  BET: "good",
  EDGE: "warn",
  PASS: "bad",
};

/** Plain words for the verdict colour (website plan 2026-10-15, Q3 + adjustment
 *  4): green is the week's RULE being met, never a proven edge. */
export const TIER_WORD: Record<VerdictTier, string> = {
  BET: "meets this week's rule",
  EDGE: "not yet",
  PASS: "pass",
};

/** The colour of a pre-kickoff badge: the verdict, not the score band (Q3,
 *  2026-10-15). The board and the game page read this one helper, so a game
 *  can no longer be green on the board and amber on its page. */
export function tierColor(tier: VerdictTier): GradeColor {
  return TIER_COLOR[tier];
}

/**
 * The colour of a pre-kickoff rank badge: the verdict only (audit 2026-10-17,
 * Tate, reversing 2026-10-16's green #1-#10). Green is a paper signal — a game
 * meeting this week's rule — never a proven bet; amber is "not yet", red a
 * pass. The rank stays on the badge. The Board and the game page read this one
 * helper.
 */
export function badgeColor(
  tier: VerdictTier,
  _boardRank: number | null = null,
): GradeColor {
  return tierColor(tier);
}

/** The badge's words for a screen reader: the verdict. */
export function badgeWord(
  tier: VerdictTier,
  _boardRank: number | null = null,
): string {
  return TIER_WORD[tier];
}

/** The word beside the number: "won" / "lost" / "push" once settled, else the
 *  grade. Both enums already read as plain lower-case words, so the key is the word. */
export function gradeWord(
  score: number | null,
  settled: Settled | null = null,
): string {
  if (settled !== null) return settled;
  return gradeOf(score) ?? "no score";
}
