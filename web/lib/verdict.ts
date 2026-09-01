// Plain-English verdict per game for the "This Week" page: BET / WATCH / PASS,
// a confidence read, and 2–3 sentences saying WHY. Pure — no DB — so the rules
// are unit-tested and easy to tune.
//
// Thresholds mirror beatvegas/model/score.py — keep the two in sync:
//   OPPORTUNITY_Z (score.py line 33) marks a gap worth watching;
//   BET_Z is the "clears the BV line's own noise" bar from docs/BV_LINE.md that
//   OpportunityCard already uses to call a gap a "clear signal".
// Betting policy (docs/BETTING_POLICY.md): 1H unders only, ≤ WEEKLY_BET_CAP
// bets a week, flat 1 unit each. Zero bets is a valid week.

import type { BoardFactor } from "@/lib/score";
import type { EvVerdict } from "@/lib/lineCheck";

export const OPPORTUNITY_Z = 0.5;
export const BET_Z = 1.0;
export const MODEL_BET_THRESHOLD = 53;
export const WEEKLY_BET_CAP = 5;
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
  const noise =
    i.z === null
      ? ""
      : Math.abs(i.z) >= BET_Z
        ? ` — that’s ${fmt(Math.abs(i.z))}× our margin of error, a clear signal.`
        : ` — that’s only ${fmt(Math.abs(i.z))}× our margin of error, inside the noise.`;
  return `${src} the first half at ${fmt(line)}; our number is ${fmt(i.bvLine)}. The line is ${fmt(Math.abs(i.gap))} points ${dir}${noise}`;
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
  const gapUnder = (i.gap ?? 0) > 0;
  const z = i.z ?? 0;
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
  const clear = gapUnder && z >= BET_Z && i.liveLine !== null;
  if (clear && !priceNeg) {
    const confidence: Confidence =
      z >= 1.5 &&
      (pricePos || i.evVerdict === "fair") &&
      i.underScore! >= MODEL_BET_THRESHOLD
        ? "high"
        : "medium";
    return {
      verdict: "BET",
      confidence,
      headline: pricePos
        ? "Clear model edge AND a good Hard Rock price — the strongest kind of spot."
        : "Clear model edge at a fair price.",
      why,
      flags,
      priceEdgeOnly: false,
      strength: 100 + z * 10 + (i.ev ?? 0) * 100,
    };
  }
  if (clear && priceNeg) {
    return {
      verdict: "WATCH",
      confidence: "medium",
      headline:
        "Clear model edge, but Hard Rock’s price is worse than the market — wait for a better number or pass.",
      why,
      flags,
      priceEdgeOnly: false,
      strength: 60 + z * 10,
    };
  }
  if ((gapUnder && z >= OPPORTUNITY_Z) || pricePos) {
    return {
      verdict: "WATCH",
      confidence: "low",
      headline: pricePos
        ? "Small model lean plus a good Hard Rock price — worth a look, not a strong case."
        : "Small model lean — the gap is inside our margin of error.",
      why,
      flags,
      priceEdgeOnly: false,
      strength: 30 + z * 10 + (i.ev ?? 0) * 100,
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
    strength: z,
  };
}

export const CONFIDENCE_LABEL: Record<Confidence, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
  none: "No read",
};
