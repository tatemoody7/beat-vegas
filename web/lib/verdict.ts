// Plain-English verdict per game for the "This Week" page: BET / WATCH / PASS,
// a confidence read, and 2–3 sentences saying WHY. Pure — no DB — so the rules
// are unit-tested and easy to tune.
//
// Gates come from the VALIDATED selection rule, not from sigma. The backtest
// (scripts/validate_engine.py → beatvegas/backtest/bv_engine.py) bets the top
// 20% of each season's games by bv_gap and grades 54.0% under / +3.0% ROI
// OOS. In Neon the season 80th-percentile gap is 1.2–1.8 pts and the 90th is
// 2.2–3.0 pts (2023–25), so BET_GAP_PTS ≈ the top-20% cutoff and
// STRONG_GAP_PTS ≈ the top-10%. bv_sigma (~11.9 pts) is the per-GAME outcome
// noise — a gap can never clear it, so it is context ("any single game is
// near a coin flip"), not a gate. MODEL_BET_THRESHOLD mirrors score.py.
// Betting policy (docs/BETTING_POLICY.md): 1H unders only, ≤ WEEKLY_BET_CAP
// bets a week, flat 1 unit each. Zero bets is a valid week.

import type { BoardFactor } from "@/lib/score";
import type { EvVerdict } from "@/lib/lineCheck";

export const BET_GAP_PTS = 1.75;
export const STRONG_GAP_PTS = 3.0;
export const WATCH_GAP_PTS = 1.0;
export const MODEL_BET_THRESHOLD = 53;
export const WEEKLY_BET_CAP = 5;
// What the validated rule earned OOS — quoted, never promised.
export const BACKTEST_UNDER_PCT = 54.0;
// weekly_update.py --min-games: the model needs this many games played by both
// teams, so weeks 1–2 have no model read at all.
export const MIN_GAMES_FOR_MODEL = 2;

export type Verdict = "BET" | "WATCH" | "PASS";
export type Confidence = "high" | "medium" | "low" | "none";

export type VerdictInput = {
  away: string;
  home: string;
  /** Display-only derived line (line_kind === "derived_fg"): no model read. */
  derived: boolean;
  underScore: number | null;
  bvLine: number | null;
  /** Live consensus current 1H line, if any book has posted one. */
  liveLine: number | null;
  /** Fallback line baked in at scoring time (derived / proxy). */
  fallbackLine: number | null;
  gap: number | null;
  z: number | null;
  /** Hard Rock price check (lib/lineCheck.ts). */
  hrLine: number | null;
  hrUnderPrice: number | null;
  ev: number | null;
  evVerdict: EvVerdict;
  qbOut: boolean;
  qbOutDetail: string | null;
  bvAdjust: number | null;
  bvAdjustReason: string | null;
  factorBoard: BoardFactor[] | null | undefined;
};

export type VerdictResult = {
  verdict: Verdict;
  confidence: Confidence;
  /** One line: the reason in a nutshell. */
  headline: string;
  /** 2–3 plain sentences: gap, price, drivers. */
  why: string[];
  /** Things the number does not know about (QB out, manual nudge). */
  flags: string[];
  /** True when the only edge is Hard Rock's price, with no model behind it. */
  priceEdgeOnly: boolean;
  /** Sort key: higher = stronger case. */
  strength: number;
};

const fmt = (n: number, dp = 1) => n.toFixed(dp);
const signed = (n: number, dp = 1) => `${n > 0 ? "+" : ""}${n.toFixed(dp)}`;
const american = (p: number) => (p > 0 ? `+${p}` : `${p}`);

function priceSentence(i: VerdictInput): string {
  if (i.hrLine === null) {
    return "Hard Rock hasn’t posted a first-half line for this game yet.";
  }
  const at =
    i.hrUnderPrice === null
      ? `under ${fmt(i.hrLine)}`
      : `under ${fmt(i.hrLine)} at ${american(i.hrUnderPrice)}`;
  if (i.ev === null) {
    return `Hard Rock has ${at}; not enough other books at that number to judge the price.`;
  }
  const pct = fmt(Math.abs(i.ev) * 100);
  switch (i.evVerdict) {
    case "pos":
      return `Hard Rock’s ${at} pays about ${pct}% better than the market’s fair price — a good price.`;
    case "neg":
      return `Hard Rock’s ${at} pays about ${pct}% worse than the market’s fair price — you’d be paying extra vig.`;
    default:
      return `Hard Rock’s ${at} is priced about the same as the rest of the market — a fair price, no extra edge.`;
  }
}

function gapSentence(i: VerdictInput): string {
  const line = i.liveLine ?? i.fallbackLine;
  if (i.derived || i.underScore === null || i.bvLine === null) {
    const ref =
      line !== null
        ? `The ${fmt(line)} shown is a reference first-half number worked out from the full-game total (about 52% of it), not a prediction.`
        : "No first-half line has been posted yet.";
    return `No model read yet — the model needs both teams to have played ${MIN_GAMES_FOR_MODEL} games this season. ${ref}`;
  }
  if (i.gap === null || line === null) {
    return `Our number for the first half is ${fmt(i.bvLine)}, but no Vegas line has been captured to compare it to.`;
  }
  const src = i.liveLine !== null ? "Vegas has" : "The estimated line is";
  const dir =
    i.gap > 0
      ? "above our number, which leans under"
      : i.gap < 0
        ? "below our number, which leans over"
        : "right on our number";
  const size =
    i.gap >= STRONG_GAP_PTS
      ? ` Gaps this big are the top ~10% of a season — historically the strongest under spots, about ${fmt(BACKTEST_UNDER_PCT)}% under; still close to a coin flip on any single game.`
      : i.gap >= BET_GAP_PTS
        ? ` That puts it in the top ~20% of gaps — the group that went under about ${fmt(BACKTEST_UNDER_PCT)}% of the time in the backtest. A small edge, so any single game is still close to a coin flip.`
        : i.gap >= WATCH_GAP_PTS
          ? " That is a small lean — below the gap size the backtest says is worth betting."
          : "";
  return `${src} the first half at ${fmt(line)}; our number is ${fmt(i.bvLine)}. The line is ${fmt(Math.abs(i.gap))} points ${dir}.${size}`;
}

// The 1–2 strongest real (non-hypothesis, tier 1–2) drivers on the factor
// board, worded as the board already words them.
function driverSentences(board: BoardFactor[] | null | undefined): string[] {
  const usable = (board ?? []).filter(
    (f) =>
      !f.hypothesis &&
      f.tier <= 2 &&
      (f.color === "green" || f.color === "red") &&
      f.sentence,
  );
  usable.sort((a, b) => Math.abs(b.lean) - Math.abs(a.lean));
  return usable.slice(0, 2).map((f) => {
    const tail =
      f.color === "green" ? "helps the under." : "works against the under.";
    const s = f.sentence.trim().replace(/[.]+$/, "");
    return `${s} — ${tail}`;
  });
}

export function verdictFor(i: VerdictInput): VerdictResult {
  const hasModel = !i.derived && i.underScore !== null && i.bvLine !== null;
  const gap = i.gap ?? 0;
  const gapUnder = gap > 0;
  const pricePos = i.evVerdict === "pos";
  const priceNeg = i.evVerdict === "neg";

  const flags: string[] = [];
  if (i.qbOut) {
    flags.push(
      `QB OUT (live ESPN, unofficial): ${i.qbOutDetail ?? "a starting quarterback is listed out"}. The model’s number does not know this — re-check before betting.`,
    );
  }
  if (i.bvAdjust !== null && i.bvAdjust !== 0) {
    flags.push(
      `Our number includes a manual ${signed(i.bvAdjust)} adjustment${i.bvAdjustReason ? ` (${i.bvAdjustReason})` : ""}.`,
    );
  }

  const why = [
    gapSentence(i),
    priceSentence(i),
    ...driverSentences(i.factorBoard),
  ].slice(0, 4);

  // --- No model (weeks 1–2, or a derived reference row) ---------------------
  if (!hasModel) {
    if (pricePos) {
      return {
        verdict: "WATCH",
        confidence: "low",
        headline:
          "Price edge only — Hard Rock is paying better than the market on this under, but there is no model read behind it.",
        why,
        flags,
        priceEdgeOnly: true,
        strength: 10 + (i.ev ?? 0) * 100,
      };
    }
    return {
      verdict: "PASS",
      confidence: "none",
      headline: "No model read and no price edge — nothing to act on.",
      why,
      flags,
      priceEdgeOnly: false,
      strength: 0,
    };
  }

  // --- Model rows -----------------------------------------------------------
  const clear = gap >= BET_GAP_PTS && i.liveLine !== null;
  if (clear && !priceNeg) {
    const confidence: Confidence =
      gap >= STRONG_GAP_PTS && i.underScore! >= MODEL_BET_THRESHOLD
        ? "high"
        : "medium";
    return {
      verdict: "BET",
      confidence,
      headline: pricePos
        ? "Model edge in the bettable range AND a good Hard Rock price — the strongest kind of spot."
        : "Model edge in the bettable range at a fair price.",
      why,
      flags,
      priceEdgeOnly: false,
      strength: 100 + gap * 10 + (i.ev ?? 0) * 100,
    };
  }
  if (clear && priceNeg) {
    return {
      verdict: "WATCH",
      confidence: "medium",
      headline:
        "Model edge in the bettable range, but Hard Rock’s price is worse than the market — wait for a better number or pass.",
      why,
      flags,
      priceEdgeOnly: false,
      strength: 60 + gap * 10,
    };
  }
  if (gap >= BET_GAP_PTS && i.liveLine === null) {
    return {
      verdict: "WATCH",
      confidence: "low",
      headline:
        "Model edge vs an ESTIMATED line — no book has posted a first-half total yet. Re-check once a real line is up.",
      why,
      flags,
      priceEdgeOnly: false,
      strength: 50 + gap * 10,
    };
  }
  if (gap >= WATCH_GAP_PTS || pricePos) {
    return {
      verdict: "WATCH",
      confidence: "low",
      headline: pricePos
        ? "Small model lean plus a good Hard Rock price — worth a look, not a strong case."
        : "Small model lean — below the gap size the backtest says is worth betting.",
      why,
      flags,
      priceEdgeOnly: false,
      strength: 30 + gap * 10 + (i.ev ?? 0) * 100,
    };
  }
  return {
    verdict: "PASS",
    confidence: "none",
    headline: gapUnder
      ? "The line is near our number — no edge."
      : "The line sits below our number — this leans over, and we only bet unders.",
    why,
    flags,
    priceEdgeOnly: false,
    strength: gap,
  };
}

export const CONFIDENCE_LABEL: Record<Confidence, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
  none: "No read",
};
