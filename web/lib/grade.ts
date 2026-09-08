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

/** Score at and above which a game is a bet. Set so a gap of exactly
 *  BET_GAP_PTS at a fair price lands here (lib/edge.ts scoreForGap). */
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

export const GRADE_WORD: Record<Grade, string> = {
  bet: "bet",
  watch: "watch",
  pass: "pass",
};

export const SETTLED_WORD: Record<Settled, string> = {
  won: "won",
  lost: "lost",
  push: "push",
};

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

/** The word beside the number: "won" / "lost" / "push" once settled, else the grade. */
export function gradeWord(
  score: number | null,
  settled: Settled | null = null,
): string {
  if (settled !== null) return SETTLED_WORD[settled];
  const g = gradeOf(score);
  return g === null ? "no score" : GRADE_WORD[g];
}
