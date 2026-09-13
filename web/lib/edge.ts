// Edge score + action line for the board redesign. One 0–100 number per game
// so cards sort and read at a glance, one plain-English line saying what to
// do about it, and the "kill" point where the edge is gone.
//
// The score is a RANKING aid layered on lib/verdict.ts — it never overrides
// the verdict. Tier BET is exactly verdict BET (docs/BETTING_POLICY.md); the
// score only decides EDGE vs PASS for the rest, and `blocker` names the first
// policy gate that keeps an EDGE from being a BET. The score is the GAP ALONE
// (50 + SCORE_PER_GAP_PT per point, floored): Hard Rock's price, an off-market
// number and a QB listed out decide whether a game is a bet — they are
// blockers with tags — but never move the number. Pure — no DB — so it is
// unit-tested and easy to tune.

import { evUnder } from "@/lib/devig";
import { american, fmt, round2 } from "@/lib/format";
import { SCORE_BET_MIN, SCORE_WATCH_MIN } from "@/lib/grade";
import {
  BET_GAP_PTS,
  BET_MIN_EV,
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
 * `floor` against `fairUnder`; null if nothing in ±1000 does.
 *
 * DISPLAY ONLY — the money gate compares `ev >= BET_MIN_EV` on the live price
 * directly (verdict.ts, pickRules.checkPolicy). The 5-cent grid cannot express
 * the true break-even, which at a 53.1% fair under is −113.2, and a gate built
 * on the grid manufactures a disagreement band all by itself.
 *
 * The rounding direction is load-bearing and it is why americanSteps walks
 * worst-payout to best: the first rung to clear the floor is always at least as
 * strict as the true break-even, so "needs −110 or better" can never invite a
 * price that loses money. Stating −115 there would be optimistic and wrong.
 *
 * The floor is BET_MIN_EV — the SAME bar verdictFor's BET branch uses — so the
 * kill price is by construction the price at which the verdict flips. It is
 * EV_FLOOR today, NOT zero: see the note in verdict.ts for why `ev` cannot
 * express a true break-even yet. Mirrors beatvegas/card.py::break_even_price.
 */
export function breakEvenPrice(
  fairUnder: number,
  floor: number = BET_MIN_EV,
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
    return `No longer a bet below u${fmt(line)}, or at a worse price than ${american(price)}.`;
  }
  if (line !== null) return `No longer a bet below u${fmt(line)}.`;
  if (price !== null) {
    return `No longer a bet at a worse price than ${american(price)}.`;
  }
  return "No kill numbers without a model number.";
}

export function edgeScore(i: EdgeInput): EdgeResult {
  const verdict = verdictFor(i);
  const hasModel = i.underScore !== null && i.bvLine !== null;
  const bvLine = hasModel ? i.bvLine! : null;

  const offMarket =
    i.hrLine !== null &&
    i.marketLine !== null &&
    i.marketLine - i.hrLine > HR_OFF_MARKET_PTS;
  const pricePos = i.evVerdict === "pos";
  // Display chip only — the price BLOCKER and the BET gate both read BET_MIN_EV.
  const priceNeg = i.evVerdict === "neg";

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
  // Gap only, floored: a gap of exactly BET_GAP_PTS is exactly SCORE_BET_MIN,
  // so green always means the gap rule passed. No-model rows score on context
  // alone and stay under the amber band (CONTEXT_CAP < SCORE_WATCH_MIN).
  const score = hasModel
    ? clamp(Math.floor(50 + SCORE_PER_GAP_PT * (gap ?? 0)), 0, 100)
    : contextScore(i.context);

  // --- Tier + blocker -------------------------------------------------------
  let tier: EdgeTier;
  let blocker: EdgeBlocker | null = null;
  if (verdict.verdict === "BET") {
    tier = "BET";
  } else if (score >= EDGE_SCORE_MIN) {
    tier = "EDGE";
    // Gate order (mirrors beatvegas/card.py): no_hr_line and off_market are
    // market reads on Hard Rock's number; no_fair_price is "cannot judge the
    // price at all" and so precedes "judged it and it is too dear"; qb_out is
    // transient news resolved by kickoff; gap is the residual.
    //
    // The price blocker tests BET_MIN_EV -- the bar the BET gate itself uses --
    // and NOT priceNeg. They are the same today because BET_MIN_EV is EV_FLOOR,
    // but priceNeg is a display chip ("this price is materially bad") while the
    // bar is a policy number meant to be raised by evidence. Reading the chip
    // here would make a raised bar report the blocker as "gap", i.e. blame the
    // model for a price problem.
    if (i.hrLine === null) blocker = "no_hr_line";
    else if (offMarket) blocker = "off_market";
    else if (i.ev === null) blocker = "no_fair_price";
    else if (i.ev < BET_MIN_EV) blocker = "price";
    else if (i.qbOut) blocker = "qb_out";
    else blocker = "gap";
  } else {
    tier = "PASS";
  }

  // --- Action ---------------------------------------------------------------
  // One plain sentence saying what to do, and for anything that is not a bet
  // yet, the number or price that would make it one (spec §13). "Wait" became
  // "Not yet" so the sentence names a condition rather than an instruction.
  let action: string;
  if (tier === "BET") {
    const at = i.hrUnderPrice !== null ? ` at ${american(i.hrUnderPrice)}` : "";
    action = `Bet one unit: first-half under ${fmt(i.hrLine)}${at} on Hard Rock.`;
  } else if (!hasModel) {
    action = pricePos
      ? `Pass: no model number yet. Hard Rock pays about ${fmt((i.ev ?? 0) * 100)}% more than the market on this under, but a price alone is not a bet.`
      : "Pass: no model number yet, and Hard Rock’s price is no better than the market.";
  } else if (blocker === "no_hr_line" || basis === null) {
    if (basis === null) {
      action = `Not yet — no first-half line anywhere. It becomes a bet at under ${fmt(killLine)} or higher.`;
    } else {
      const at =
        killPrice !== null ? `, at ${american(killPrice)} or better` : "";
      action = `Not yet — Hard Rock has no first-half line. It becomes a bet at under ${fmt(killLine)} or higher${at}.`;
    }
  } else if (blocker === "off_market") {
    const diff = round2(i.marketLine! - i.hrLine!);
    action = `Not yet — Hard Rock’s ${fmt(i.hrLine)} is ${fmt(diff)} below the market line of ${fmt(i.marketLine)}. You would be giving up points, and Hard Rock can void a bet that far off the market. Bet it if Hard Rock moves to ${fmt(i.marketLine! - HR_OFF_MARKET_PTS)} or higher.`;
  } else if (blocker === "price") {
    const needs = `${american(killPrice ?? -110)} or better`;
    const hr =
      i.hrUnderPrice !== null ? american(i.hrUnderPrice) : "not posted";
    action = `Not yet — Hard Rock’s price is ${hr}; needs ${needs}.`;
  } else if (blocker === "no_fair_price") {
    if (i.hrUnderPrice === null) {
      action = `Not yet — Hard Rock has not priced its ${fmt(i.hrLine)} under. Paper only until it does.`;
    } else {
      const hr = american(i.hrUnderPrice);
      action = `Not yet — no other book is at ${fmt(i.hrLine)}, so ${hr} cannot be compared. Paper only until one is.`;
    }
  } else if (blocker === "qb_out") {
    action = "Starting QB out — recheck. Our number does not know about it.";
  } else if (tier === "EDGE") {
    // blocker "gap": the amber band — a model row short of the bar.
    action = `Not yet — the line is ${fmt(gap ?? 0)} above our number. It becomes a bet at ${fmt(killLine)} or higher.`;
  } else {
    // PASS on a model row: the line is short of the bar, or below our number.
    const g = gap ?? 0;
    action =
      g > 0
        ? `Pass: the line is ${fmt(g)} above our number. It needs ${fmt(killLine)} or higher.`
        : `Pass: the line is ${fmt(Math.abs(g))} below our number, so this leans over. We only bet unders.`;
  }

  return { score, tier, blocker, action, kill, gap, lineBasis, verdict };
}
