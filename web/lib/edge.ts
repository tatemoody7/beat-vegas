// Edge score + action line for the board redesign. One 0–100 number per game
// so cards sort and read at a glance, one plain-English line saying what to
// do about it, and the "kill" point where the edge is gone.
//
// The score is a RANKING aid layered on lib/verdict.ts — it never overrides
// the verdict. Tier BET is exactly verdict BET (docs/BETTING_POLICY.md); the
// score only decides EDGE vs PASS for the rest, and `blocker` names the first
// policy gate that keeps an EDGE from being a BET. Pure — no DB — so it is
// unit-tested and easy to tune.

import { evUnder } from "@/lib/devig";
import { american, fmt, round2 } from "@/lib/format";
import { SCORE_BET_MIN, SCORE_WATCH_MIN } from "@/lib/grade";
import {
  BET_GAP_PTS,
  HR_OFF_MARKET_PTS,
  verdictFor,
  type VerdictInput,
  type VerdictResult,
  EV_FLOOR,
} from "@/lib/verdict";

/** Context leans used when the model has no read (from factors_json). */
export type EdgeContext = {
  combinedSecPlay: number | null;
  windMph: number | null;
  dome: boolean | null;
  spread: number | null;
  fhPrior: number | null;
};

export type EdgeInput = VerdictInput & {
  /** Consensus (median) current 1H line across books, if any. */
  marketLine: number | null;
  /** Best (highest) book 1H line. */
  bestLine: number | null;
  /** Market fair P(under) at Hard Rock's number, if computable. */
  marketFairUnder: number | null;
  /** Context leans for no-model rows. */
  context: EdgeContext;
};

export type EdgeTier = "BET" | "EDGE" | "PASS";
/** Which line the gap (and so the score) is measured against. */
export type LineBasis = "hardrock" | "market" | "reference";
/** Why an EDGE is not a BET — the first failing policy gate, in gate order. */
export type EdgeBlocker =
  | "no_hr_line"
  | "off_market"
  | "price"
  | "no_fair_price"
  | "qb_out"
  | "gap";

export type EdgeResult = {
  /** 0..100 integer. */
  score: number;
  tier: EdgeTier;
  /** Set only on tier EDGE. */
  blocker: EdgeBlocker | null;
  /** One plain-English line: what to do. */
  action: string;
  /** Where the edge is gone. */
  kill: { line: number | null; price: number | null; text: string };
  /** The line minus our number, against `lineBasis`; null without a model. */
  gap: number | null;
  /** Which line is on screen for this game (Hard Rock, else market, else reference). */
  lineBasis: LineBasis | null;
  /** From verdictFor, unchanged. */
  verdict: VerdictResult;
};

/** Worst EV (per $1) still treated as a fair price — mirrors lineCheck "neg". */
export const FAIR_EV_FLOOR = EV_FLOOR; // single source: verdict.ts
/** Points of score per point of gap: a gap of BET_GAP_PTS lands on SCORE_BET_MIN. */
export const SCORE_PER_GAP_PT = (SCORE_BET_MIN - 50) / BET_GAP_PTS;
/** The EDGE ("watch") tier starts where the amber band starts. */
export const EDGE_SCORE_MIN = SCORE_WATCH_MIN;
export const CONTEXT_BASE = 40;
export const CONTEXT_CAP = 49;
export const PRICE_ONLY_CAP = 55;
const PRICE_BONUS_CAP = 8;
const OFF_MARKET_PENALTY = 10;
const QB_OUT_PENALTY = 5;

const clamp = (n: number, lo: number, hi: number): number =>
  Math.min(hi, Math.max(lo, n));

/** Round UP to the next half point (23.55 → 24, 23.1 → 23.5, 23.5 → 23.5). */
export function roundHalfUp(x: number): number {
  return Math.ceil(x * 2 - 1e-9) / 2;
}

// American prices in 5-cent steps from worst payout to best; -100 is +100.
function* americanSteps(): Generator<number> {
  for (let p = -1000; p <= 1000; p += 5) {
    if (p === -100 || (p > -100 && p < 100)) continue;
    yield p;
  }
}

/**
 * The worst American price (5-cent steps) at which the under still clears
 * `FAIR_EV_FLOOR` against `fairUnder`; null if nothing in ±1000 does.
 */
export function breakEvenPrice(
  fairUnder: number,
  floor: number = FAIR_EV_FLOOR,
): number | null {
  for (const p of americanSteps()) {
    if (evUnder(fairUnder, p) >= floor) return p;
  }
  return null;
}

/** Context-only score for rows without a model read (40 ± leans, cap 49). */
export function contextScore(c: EdgeContext): number {
  let s = CONTEXT_BASE;
  const pace = c.combinedSecPlay;
  if (pace !== null) {
    if (pace >= 29) s += 6;
    else if (pace >= 27.5) s += 4;
  }
  if (c.windMph !== null) {
    if (c.windMph >= 15) s += 3;
    else if (c.windMph >= 10) s += 2;
  }
  if (c.dome === true) s -= 2;
  if (c.spread !== null) {
    const a = Math.abs(c.spread);
    if (a <= 7) s += 2;
    else if (a <= 14) s += 1;
    else if (a > 21) s -= 3;
  }
  if (c.fhPrior !== null) {
    if (c.fhPrior <= 15) s += 3;
    else if (c.fhPrior <= 17) s += 1;
    else if (c.fhPrior >= 24) s -= 2;
  }
  return Math.min(CONTEXT_CAP, s);
}

function killText(line: number | null, price: number | null): string {
  if (line !== null && price !== null) {
    return `Not worth it below u${fmt(line)} or worse than ${american(price)}.`;
  }
  if (line !== null) return `Not worth it below u${fmt(line)}.`;
  if (price !== null) return `Not worth it worse than ${american(price)}.`;
  return "No kill point without a model read.";
}

export function edgeScore(i: EdgeInput): EdgeResult {
  const verdict = verdictFor(i);
  const hasModel = !i.derived && i.underScore !== null && i.bvLine !== null;
  const bvLine = hasModel ? i.bvLine! : null;

  const offMarket =
    i.hrLine !== null &&
    i.marketLine !== null &&
    i.marketLine - i.hrLine > HR_OFF_MARKET_PTS;
  const pricePos = i.evVerdict === "pos";
  const priceNeg = i.evVerdict === "neg";
  const priceBonus =
    i.hrUnderPrice !== null && i.ev !== null
      ? clamp(Math.round(i.ev * 100), -PRICE_BONUS_CAP, PRICE_BONUS_CAP)
      : 0;

  // Gap basis: the number you can bet, else the market, else the reference.
  const basis = i.hrLine ?? i.marketLine ?? i.fallbackLine;
  const lineBasis: LineBasis | null =
    i.hrLine !== null
      ? "hardrock"
      : i.marketLine !== null
        ? "market"
        : i.fallbackLine !== null
          ? "reference"
          : null;
  const gap = bvLine !== null && basis !== null ? round2(basis - bvLine) : null;

  const killLine = bvLine !== null ? roundHalfUp(bvLine + BET_GAP_PTS) : null;
  const killPrice =
    i.marketFairUnder !== null ? breakEvenPrice(i.marketFairUnder) : null;
  const kill = {
    line: killLine,
    price: killPrice,
    text: killText(killLine, killPrice),
  };

  // --- Score --------------------------------------------------------------
  let score: number;
  if (hasModel) {
    score = clamp(Math.round(50 + SCORE_PER_GAP_PT * (gap ?? 0)), 0, 100);
    score += priceBonus;
    if (offMarket) score -= OFF_MARKET_PENALTY;
    if (i.qbOut) score -= QB_OUT_PENALTY;
    score = clamp(score, 0, 100);
  } else {
    score = contextScore(i.context);
    if (pricePos) {
      score = Math.min(PRICE_ONLY_CAP, score + Math.max(1, priceBonus));
    }
  }

  // --- Tier + blocker -------------------------------------------------------
  let tier: EdgeTier;
  let blocker: EdgeBlocker | null = null;
  if (verdict.verdict === "BET") {
    tier = "BET";
  } else if (score >= EDGE_SCORE_MIN || (!hasModel && pricePos)) {
    tier = "EDGE";
    // Gate order (mirrors beatvegas/card.py): no_hr_line, off_market and price
    // are market reads on Hard Rock's number; no_fair_price is the price
    // gate's "cannot judge" branch, so it follows price; qb_out is transient
    // news resolved by kickoff; gap is the residual.
    if (i.hrLine === null) blocker = "no_hr_line";
    else if (offMarket) blocker = "off_market";
    else if (priceNeg) blocker = "price";
    else if (i.ev === null) blocker = "no_fair_price";
    else if (i.qbOut) blocker = "qb_out";
    else blocker = "gap";
  } else {
    tier = "PASS";
  }

  // --- Action ---------------------------------------------------------------
  let action: string;
  if (tier === "BET") {
    const at = i.hrUnderPrice !== null ? ` at ${american(i.hrUnderPrice)}` : "";
    action = `Bet now: 1H under ${fmt(i.hrLine)}${at} on Hard Rock.`;
  } else if (!hasModel) {
    action = pricePos
      ? `Price only: Hard Rock pays ${fmt((i.ev ?? 0) * 100)}% better than the market on this under. No model behind it.`
      : "Pass: no model read this week and no price edge at Hard Rock.";
  } else if (blocker === "no_hr_line" || basis === null) {
    const lead =
      basis === null ? "No line captured yet." : "No Hard Rock line yet.";
    action = `${lead} A bet at under ${fmt(killLine)} or higher, -110 or better.`;
  } else if (blocker === "off_market") {
    const diff = round2(i.marketLine! - i.hrLine!);
    action = `Wait: Hard Rock’s ${fmt(i.hrLine)} is ${fmt(diff)} below the market’s ${fmt(i.marketLine)} — giving up points and a void risk. Bet if it moves to ${fmt(i.marketLine! - 0.5)} or higher.`;
  } else if (blocker === "price") {
    const needs =
      killPrice !== null
        ? `${american(killPrice)} or better`
        : "a fair price (-110 or better)";
    const hr = i.hrUnderPrice !== null ? american(i.hrUnderPrice) : "unpriced";
    action = `Wait: Hard Rock is ${hr}; needs ${needs}.`;
  } else if (blocker === "no_fair_price") {
    if (i.hrUnderPrice === null) {
      action = `Wait: Hard Rock hasn’t priced its ${fmt(i.hrLine)} under yet — nothing to judge. Paper only until Hard Rock posts a price.`;
    } else {
      const hr = american(i.hrUnderPrice);
      action = `Wait: Hard Rock’s ${hr} can’t be judged — no other book or exchange is priced at ${fmt(i.hrLine)}. Paper only until a comparable price appears.`;
    }
  } else if (blocker === "qb_out") {
    action =
      "Wait: a starting QB is listed out — re-check the number after the news settles.";
  } else {
    // blocker "gap" (EDGE) or PASS on a model row: the line is short of the bar.
    const g = gap ?? 0;
    action =
      g > 0
        ? `Pass: the line is only ${fmt(g)} above our number; needs ${fmt(killLine)} or higher.`
        : `Pass: the line is ${fmt(Math.abs(g))} below our number (leans over); needs ${fmt(killLine)} or higher.`;
  }

  return { score, tier, blocker, action, kill, gap, lineBasis, verdict };
}
