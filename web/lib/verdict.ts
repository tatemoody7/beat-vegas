// Plain-English verdict per game for the "This Week" page: BET / WATCH / PASS,
// a confidence read, and 2–3 sentences saying WHY. Pure — no DB — so the rules
// are unit-tested and easy to tune.
//
// Gates come from the VALIDATED selection rule, not from sigma. The backtest
// (scripts/validate_engine.py → beatvegas/backtest/bv_engine.py) ranks each
// season's games by bv_gap; the top 20% is the selection band. In Neon the
// season 80th-percentile gap is 1.2–1.8 pts and the 90th is 2.2–3.0 pts
// (2023–25), so BET_GAP_PTS ≈ the top-20% cutoff and STRONG_GAP_PTS ≈ the
// top-10%. Against a FAIR estimated line (step share, FBS-only) that band shows
// no confirmed edge — so the gap is a ranking rule, and only real-line
// closing-line value this season can prove an edge. bv_sigma (~11.9 pts) is
// the per-GAME outcome noise — a gap can never clear it, so it is context
// ("any single game is near a coin flip"), not a gate.
//
// The gap that gates a BET is HARD ROCK'S number minus ours — Hard Rock is the
// only book bettable from Florida, so a consensus gap that Hard Rock does not
// match is not an edge you can take. MODEL_BET_THRESHOLD mirrors score.py.
// Betting policy (docs/BETTING_POLICY.md): 1H unders only, ≤ WEEKLY_BET_CAP
// bets a week, flat 1 unit each. Zero bets is a valid week.

import type { BoardFactor } from "@/lib/score";
import type { EvVerdict } from "@/lib/lineCheck";
import { american, fmt, round2, signed } from "@/lib/format";

export const BET_GAP_PTS = 1.75;
export const STRONG_GAP_PTS = 3.0;
export const WATCH_GAP_PTS = 1.0;
export const MODEL_BET_THRESHOLD = 53; // model ledger only; not a verdict input since 2026-09-06
export const WEEKLY_BET_CAP = 5;
// Hard Rock more than this far BELOW the market total = off-market number
// (mirrors lib/lineCheck.ts "poor"): never a BET.
export const HR_OFF_MARKET_PTS = 0.5;
// Price gate: Hard Rock's under may be at most this much worse (per $1) than the
// market's no-vig fair price. -0.05 lets standard -110 juice on a balanced market
// through and rejects -115 or worse unless the market itself leans under.
export const EV_FLOOR = -0.05;
/** EV_FLOOR as a positive whole percent for prose ("up to 5% worse than fair"). */
export const EV_FLOOR_PCT = Math.abs(EV_FLOOR * 100);
// weekly_update.py --min-games: the model needs this many FBS-vs-FBS games
// played by both teams this season (0 since 2026-09-08: every game gets a
// number off last season's priors; rows with under 2 games are tagged "early
// season" on the board).
export const MIN_GAMES_FOR_MODEL = 0;

export type Verdict = "BET" | "WATCH" | "PASS";
export type Confidence = "high" | "medium" | "low" | "none";
/** Why a pick was made — stored on manual_picks.reason (shared with pick.py). */
export type PickReason = "model_gap" | "price_edge" | "manual";
export const REASONS: readonly PickReason[] = [
  "model_gap",
  "price_edge",
  "manual",
];

export type VerdictInput = {
  away: string;
  home: string;
  underScore: number | null;
  bvLine: number | null;
  /** Live consensus current 1H line, if any book has posted one. */
  liveLine: number | null;
  /** Fallback line baked in at scoring time (derived / proxy). */
  fallbackLine: number | null;
  /** Consensus gap (liveLine − bvLine), or the gap stored at scoring time. */
  gap: number | null;
  /** Hard Rock price check (lib/lineCheck.ts). */
  hrLine: number | null;
  hrUnderPrice: number | null;
  ev: number | null;
  evVerdict: EvVerdict;
  /** First-half share used for a derived reference line (factors.fh_share). */
  fhShare: number | null;
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
  /** Hard Rock's line minus our number (the gap you can actually bet); null without both. */
  hrGap: number | null;
  /** Pick reason this verdict would log (model_gap / price_edge / manual). */
  reason: PickReason;
  /** Sort key: higher = stronger case. */
  strength: number;
};

/** model read + Hard Rock gap in the band → model_gap; price-only → price_edge; else manual. */
export function deriveReason(
  hasModel: boolean,
  hrGap: number | null,
  priceEdgeOnly: boolean,
): PickReason {
  if (hasModel && hrGap !== null && hrGap >= BET_GAP_PTS) return "model_gap";
  if (priceEdgeOnly) return "price_edge";
  return "manual";
}

export function priceSentence(i: VerdictInput): string {
  if (i.hrLine === null) {
    return "Hard Rock has not posted a first-half line yet.";
  }
  const at =
    i.hrUnderPrice === null
      ? `under ${fmt(i.hrLine)}`
      : `under ${fmt(i.hrLine)} at ${american(i.hrUnderPrice)}`;
  if (i.ev === null) {
    // Two different causes, and the headline already branches on them: blaming
    // the other books when Hard Rock itself posted no price contradicts it (and
    // is simply wrong — the books may all be priced). Mirrors card.py.
    return i.hrUnderPrice === null
      ? `Hard Rock has the under at ${fmt(i.hrLine)} but no price on it yet, so there is nothing to compare.`
      : `Hard Rock has the under at ${fmt(i.hrLine)}. Not enough other books are at that number to compare the price.`;
  }
  const pctTxt = fmt(Math.abs(i.ev) * 100);
  // "Fair price" is defined in the sentence rather than in a parenthetical the
  // reader has to decode (spec §14a).
  switch (i.evVerdict) {
    case "pos":
      return `Hard Rock’s ${at} pays about ${pctTxt}% more than the fair price. Fair price = the other books and the exchanges with the vig taken out.`;
    case "neg":
      return `Hard Rock’s ${at} pays about ${pctTxt}% less than the fair price. You would be paying extra vig.`;
    default:
      return `Hard Rock’s ${at} is priced about the same as the rest of the market.`;
  }
}

// What a gap of this size means. The band is a RANKING rule the backtest
// validated; it is not a proven win rate.
function sizeSentence(gap: number): string {
  if (gap >= STRONG_GAP_PTS) {
    return " Gaps this big are the top ~10% of a season — the strongest end of the band the backtest validated for ranking games. Against a fair estimated line the backtest found no confirmed edge, so only real-line closing-line value this season can prove one; still close to a coin flip on any single game.";
  }
  if (gap >= BET_GAP_PTS) {
    return " That puts it in the top ~20% of gaps — the selection band the backtest validated for ranking games, not a proven win rate. Against a fair estimated line the backtest found no confirmed edge; only closing-line value against real lines this season can prove one, and any single game is still close to a coin flip.";
  }
  if (gap >= WATCH_GAP_PTS) {
    return " That is a small lean — below the gap size that qualifies as bettable.";
  }
  return "";
}

function gapSentence(i: VerdictInput, hrGap: number | null): string {
  const line = i.liveLine ?? i.fallbackLine;
  if (i.underScore === null || i.bvLine === null) {
    const share =
      i.fhShare !== null && Number.isFinite(i.fhShare)
        ? `${fmt(i.fhShare * 100)}% of it`
        : "about half of it";
    const ref =
      line !== null
        ? `The ${fmt(line)} shown is a reference first-half number worked out from the full-game total (${share}; the share is higher when one side is a heavy favorite), not a prediction.`
        : "No first-half line has been posted yet.";
    return `No model read yet. ${ref}`;
  }
  // Prefer the number you can actually bet.
  if (hrGap !== null && i.hrLine !== null) {
    const dir =
      hrGap > 0
        ? "above our number, which leans under"
        : hrGap < 0
          ? "below our number, which leans over"
          : "right on our number";
    const market =
      i.liveLine !== null && Math.abs(i.liveLine - i.hrLine) >= 0.05
        ? ` (the market consensus is ${fmt(i.liveLine)}).`
        : ".";
    return `Hard Rock has the first half at ${fmt(i.hrLine)}; our number is ${fmt(i.bvLine)}${market} Hard Rock’s line is ${fmt(Math.abs(hrGap))} points ${dir}.${sizeSentence(hrGap)}`;
  }
  if (i.gap === null || line === null) {
    return `Our number for the first half is ${fmt(i.bvLine)}, but no Vegas line has been captured to compare it to.`;
  }
  const src =
    i.liveLine !== null
      ? "The market has (Hard Rock has not posted)"
      : "The estimated line is";
  const dir =
    i.gap > 0
      ? "above our number, which leans under"
      : i.gap < 0
        ? "below our number, which leans over"
        : "right on our number";
  return `${src} the first half at ${fmt(line)}; our number is ${fmt(i.bvLine)}. The line is ${fmt(Math.abs(i.gap))} points ${dir}.${sizeSentence(i.gap)}`;
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
    // board.py already words most sentences "<fact> — helps the under."; strip
    // that tail so we never render "— helps the under — helps the under."
    const s = f.sentence
      .trim()
      .replace(/[.]+$/, "")
      .replace(
        /\s+[—–-]+\s+(helps|hurts|works against|is neutral for)\b[^—–]*$/i,
        "",
      )
      .trim();
    return `${s} — ${tail}`;
  });
}

export function verdictFor(i: VerdictInput): VerdictResult {
  const hasModel = i.underScore !== null && i.bvLine !== null;
  const consensusGap = i.gap ?? 0;
  const hrGap =
    hasModel && i.hrLine !== null && i.bvLine !== null
      ? round2(i.hrLine - i.bvLine)
      : null;
  const pricePos = i.evVerdict === "pos";
  const priceNeg = i.evVerdict === "neg";

  const flags: string[] = [];
  if (i.qbOut) {
    flags.push(
      `QB OUT (live Rotowire, unofficial): ${i.qbOutDetail ?? "a starting quarterback is listed out"}. The model’s number does not know this — re-check before betting.`,
    );
  }
  if (i.bvAdjust !== null && i.bvAdjust !== 0) {
    flags.push(
      `Our number includes a manual ${signed(i.bvAdjust, 1)} adjustment${i.bvAdjustReason ? ` (${i.bvAdjustReason})` : ""}.`,
    );
  }

  const why = [
    gapSentence(i, hrGap),
    priceSentence(i),
    ...driverSentences(i.factorBoard),
  ].slice(0, 4);

  const out = (
    verdict: Verdict,
    confidence: Confidence,
    headline: string,
    priceEdgeOnly: boolean,
    strength: number,
  ): VerdictResult => ({
    verdict,
    confidence,
    headline,
    why,
    flags,
    priceEdgeOnly,
    hrGap,
    reason: deriveReason(hasModel, hrGap, priceEdgeOnly),
    strength,
  });

  // --- No model (the week has not been scored yet) ---------------------------
  // A price alone is never a bet, so this is a PASS either way (edge.ts tiers
  // these rows PASS and the Log-pick prefill stores this verdict). The
  // priceEdgeOnly flag + headline survive so the reason still logs price_edge.
  if (!hasModel) {
    if (pricePos) {
      return out(
        "PASS",
        "low",
        "Price edge only — Hard Rock is paying better than the market on this under, but there is no model read behind it.",
        true,
        10 + (i.ev ?? 0) * 100,
      );
    }
    return out(
      "PASS",
      "none",
      "No model read and no price edge — nothing to act on.",
      false,
      0,
    );
  }

  // --- Model rows -----------------------------------------------------------
  // Hard Rock posting a number well BELOW the market is not a gift: an under
  // at a lower total is a worse bet than the same under at the market's number
  // (lib/lineCheck.ts calls this "poor"), and Hard Rock's house rules can void
  // bets on lines that differ materially from the general market. Never BET
  // into it — WATCH until Hard Rock's number is back within half a point.
  if (
    hrGap !== null &&
    hrGap >= BET_GAP_PTS &&
    i.liveLine !== null &&
    i.liveLine - i.hrLine! > HR_OFF_MARKET_PTS
  ) {
    const below = round2(i.liveLine - i.hrLine!);
    return out(
      "WATCH",
      "medium",
      `Our number clears the bar, but Hard Rock’s total is ${fmt(below)} points below the market’s — you’d be giving up points, and an off-market number risks a void. Wait for Hard Rock to move toward ${fmt(i.liveLine)}.`,
      false,
      55 + hrGap * 10,
    );
  }
  // A starting QB listed out: the number does not know it. Never BET into it;
  // WATCH until the news settles and the line has had a chance to react.
  if (hrGap !== null && hrGap >= BET_GAP_PTS && i.qbOut) {
    return out(
      "WATCH",
      "medium",
      "Our number clears the bar, but a starting quarterback is listed out and the model does not know it — re-check the number after the news settles.",
      false,
      58 + hrGap * 10,
    );
  }
  // BET needs Hard Rock's own number in the band at a JUDGEABLE price no worse
  // than EV_FLOOR against the market's fair price (standard juice passes). No
  // fair price (no book or exchange at Hard Rock's number, or Hard Rock itself
  // unpriced) is not a pass: it is paper only (card.py blocker no_fair_price).
  if (hrGap !== null && hrGap >= BET_GAP_PTS && !priceNeg && i.ev !== null) {
    // Confidence is the gap alone. The classifier's under_score used to gate
    // "high" (needed >= MODEL_BET_THRESHOLD); the 2026-09-06 post-mortem found
    // every score band hits the same rate against a fair line, so it no longer
    // enters the label. It stays a display chip.
    const confidence: Confidence = hrGap >= STRONG_GAP_PTS ? "high" : "medium";
    return out(
      "BET",
      confidence,
      pricePos
        ? "Model edge in the bettable range at Hard Rock’s number AND a good Hard Rock price — the strongest kind of spot."
        : "Model edge in the bettable range at Hard Rock’s number, at a fair price.",
      false,
      100 + hrGap * 10 + (i.ev ?? 0) * 100,
    );
  }
  if (hrGap !== null && hrGap >= BET_GAP_PTS && priceNeg) {
    return out(
      "WATCH",
      "medium",
      "Model edge in the bettable range, but Hard Rock’s price is worse than the market — wait for a better number or pass.",
      false,
      60 + hrGap * 10,
    );
  }
  if (hrGap !== null && hrGap >= BET_GAP_PTS && i.ev === null) {
    return out(
      "WATCH",
      "medium",
      i.hrUnderPrice === null
        ? "Model edge in range, but Hard Rock hasn’t priced its under yet — the price can’t be judged. Paper only."
        : "Model edge in range, but no other book or exchange is priced at Hard Rock’s number — the price can’t be judged. Paper only.",
      false,
      59 + hrGap * 10,
    );
  }
  if (i.hrLine === null && consensusGap >= BET_GAP_PTS) {
    return out(
      "WATCH",
      "low",
      i.liveLine !== null
        ? "Hard Rock has not posted a first-half line yet — the market’s number clears our bar, but you can only bet Hard Rock. Re-check once it posts."
        : "Model edge vs an ESTIMATED line — Hard Rock has not posted a first-half line yet and no other book has either. Re-check once a real line is up.",
      false,
      50 + consensusGap * 10,
    );
  }
  if (hrGap !== null && i.liveLine !== null && consensusGap >= BET_GAP_PTS) {
    const below = round2(i.liveLine - i.hrLine!);
    return out(
      "WATCH",
      "low",
      `The market’s number clears our bar but Hard Rock’s is ${fmt(below)} points lower — no edge at Hard Rock’s line.`,
      false,
      40 + hrGap * 10,
    );
  }
  const effGap = hrGap ?? consensusGap;
  if (effGap >= WATCH_GAP_PTS || pricePos) {
    return out(
      "WATCH",
      "low",
      pricePos
        ? "Small model lean plus a good Hard Rock price — worth a look, not a strong case."
        : "Small model lean — below the gap size that qualifies as bettable.",
      false,
      30 + effGap * 10 + (i.ev ?? 0) * 100,
    );
  }
  return out(
    "PASS",
    "none",
    effGap > 0
      ? "The line is near our number — no edge."
      : "The line sits below our number — this leans over, and we only bet unders.",
    false,
    effGap,
  );
}
