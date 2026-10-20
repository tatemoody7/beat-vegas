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
  MIN_GAMES_FOR_REAL_MONEY,
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
  /** The feed's newest Hard Rock quote is an alternate line; hrLine is the last main line (display only). */
  | "hr_alt_line"
  | "off_market"
  | "price"
  | "no_fair_price"
  | "qb_out"
  /** A team on this row has fewer than MIN_GAMES_FOR_REAL_MONEY games this season: paper only. */
  | "early_season"
  /** Board alignment B3 (2026-10-14): a failed input on the scheduled build touched this game; paper only. */
  | "held"
  /** Board alignment B4: no scheduled card has read this game's line and injury report yet. */
  | "not_on_card"
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

/** The line the gap is measured against, as the row sentence names it. Hard
 *  Rock's number stays "the line" (it is the one you can bet); the market's and
 *  the reference line are named, so a row that shows "no line yet" never then
 *  says "the line is 0.2 above our number". */
export function basisNoun(basis: LineBasis | null): string {
  if (basis === "market") return "the market line";
  if (basis === "reference") return "our reference line";
  return "the line";
}

export function edgeScore(i: EdgeInput): EdgeResult {
  const verdict = verdictFor(i);
  const hasModel = i.bvLine !== null;
  const bvLine = hasModel ? i.bvLine! : null;

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
  // What the gap is measured against, in words (mirrors card.py::_basis_noun).
  const noun = basisNoun(lineBasis);

  // H-PCT: the kill line and the score scale stretch with this slate's bar.
  const bar = i.bar ?? BET_GAP_PTS;
  const killLine = bvLine !== null ? roundHalfUp(bvLine + bar) : null;
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
    ? clamp(Math.floor(50 + ((SCORE_BET_MIN - 50) / bar) * (gap ?? 0)), 0, 100)
    : contextScore(i.context);

  // --- Tier + blocker -------------------------------------------------------
  let tier: EdgeTier;
  let blocker: EdgeBlocker | null = null;
  if (verdict.verdict === "BET") {
    tier = "BET";
  } else if (score >= EDGE_SCORE_MIN) {
    tier = "EDGE";
    // Gate order (mirrors beatvegas/card.py): no_hr_line is the market read on
    // Hard Rock's number (off_market was retired 2026-10-07); no_fair_price is "cannot judge the
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
    else if (i.hrLive === false) blocker = "hr_alt_line";
    else if (i.ev === null) blocker = "no_fair_price";
    else if (i.ev < BET_MIN_EV) blocker = "price";
    else if (i.qbOut) blocker = "qb_out";
    else if (
      i.minGamesPlayed !== null &&
      i.minGamesPlayed < MIN_GAMES_FOR_REAL_MONEY
    )
      blocker = "early_season";
    else blocker = "gap";
  } else {
    tier = "PASS";
  }

  // --- Action ---------------------------------------------------------------
  // A BET's sentence opens with PAPER_ACTION, for everyone: the "Bet one unit"
  // opening of roadmap v1.4 left with real money on 2026-10-18 (D2).
  // One plain sentence saying what to do, and for anything that is not a bet
  // yet, the number or price that would make it one (spec §13). The sentence
  // names a research condition, never an instruction to a bettor ("Not yet —"
  // became "Not a paper signal yet:", 2026-10-20, final-2026 plan D4 build 5).
  let action: string;
  if (tier === "BET") {
    const at = i.hrUnderPrice !== null ? ` at ${american(i.hrUnderPrice)}` : "";
    action = `${PAPER_ACTION} first-half under ${fmt(i.hrLine)}${at} on Hard Rock.`;
  } else if (!hasModel) {
    action = pricePos
      ? `Pass: no model number yet. Hard Rock pays about ${fmt((i.ev ?? 0) * 100)}% more than the market on this under, but a price alone is not a signal.`
      : "Pass: no model number yet, and Hard Rock’s price is no better than the market.";
  } else if (blocker === "no_hr_line" || basis === null) {
    if (basis === null) {
      action = `Not a paper signal yet: no first-half line anywhere. It becomes a paper signal at under ${fmt(killLine)} or higher.`;
    } else {
      const at =
        killPrice !== null ? `, at ${american(killPrice)} or better` : "";
      action = `Not a paper signal yet: Hard Rock has no first-half line. It becomes a paper signal at under ${fmt(killLine)} or higher${at}.`;
    }
  } else if (blocker === "hr_alt_line") {
    action = `Not a paper signal yet: Hard Rock’s feed is showing an alternate line, not its main number. The last main line on file is under ${fmt(i.hrLine)}.`;
  } else if (blocker === "price") {
    const needs = `${american(killPrice ?? -110)} or better`;
    const hr =
      i.hrUnderPrice !== null ? american(i.hrUnderPrice) : "not posted";
    action = `Not a paper signal yet: Hard Rock’s under price is ${hr}; the rule needs ${needs}.`;
  } else if (blocker === "no_fair_price") {
    if (i.hrUnderPrice === null) {
      action = `Not a paper signal yet: Hard Rock has not priced its ${fmt(i.hrLine)} under. Paper only until it does.`;
    } else {
      const hr = american(i.hrUnderPrice);
      action = `Not a paper signal yet: no other book is at ${fmt(i.hrLine)}, so ${hr} cannot be compared. Paper only until one is.`;
    }
  } else if (blocker === "qb_out") {
    action =
      "Not a paper signal yet: a starting QB is out, and our number does not know about it.";
  } else if (blocker === "early_season") {
    const at = i.hrUnderPrice !== null ? ` at ${american(i.hrUnderPrice)}` : "";
    const n = i.minGamesPlayed ?? 0;
    action = `Paper only — ${n} game${n === 1 ? "" : "s"} played this season; real money needs ${MIN_GAMES_FOR_REAL_MONEY}. Everything else clears: first-half under ${fmt(i.hrLine)}${at} on Hard Rock.`;
  } else if (tier === "EDGE") {
    // blocker "gap": the amber band — a model row short of the bar.
    action = `Not a paper signal yet: ${noun} is ${fmt(gap ?? 0)} above our number. It becomes a paper signal at ${fmt(killLine)} or higher.`;
  } else {
    // PASS on a model row: the line is short of the bar, on our number, or
    // below it. The noun names the basis: a row that reads "no line yet" and
    // then "the line is 0.2 above" contradicted itself (site review 2026-09-28).
    const g = gap ?? 0;
    action =
      g > 0
        ? `Pass: ${noun} is ${fmt(g)} above our number. It needs ${fmt(killLine)} or higher.`
        : Math.abs(g) < 0.05
          ? `Pass: ${noun} sits on our number. No signal.`
          : `Pass: ${noun} is ${fmt(Math.abs(g))} below our number, so this leans over. We only rate unders.`;
  }

  return { score, tier, blocker, action, kill, gap, lineBasis, verdict };
}

/**
 * The Board's short form of a Pass (website plan 2026-10-15, Q4): every Pass
 * game stays on the Board with its rank, but says its reason in a few words;
 * "we only rate unders" is said once above the Pass rows instead of on each.
 * The full sentence (`action`) stays on the game page and in card.py. Null for
 * anything that is not a Pass.
 */
export function passShort(r: EdgeResult): string | null {
  if (r.tier !== "PASS") return null;
  if (r.gap === null) return "Pass · no model number yet";
  if (Math.abs(r.gap) < 0.05) return "Pass · on our number";
  if (r.gap < 0) return `Pass · leans over ${fmt(Math.abs(r.gap))}`;
  return r.kill.line !== null
    ? `Pass · short of the bar (needs ${fmt(r.kill.line)})`
    : "Pass · short of the bar";
}

/**
 * The opening of a BET's action sentence. Since 2026-10-18 (final-2026 plan,
 * D2) there is only the paper one: "Bet one unit:" and the swap that applied it
 * inside the real-money cap (roadmap v1.4) left with real money. Mirrored by
 * beatvegas/card.py (PAPER_ACTION).
 */
export const PAPER_ACTION = "Paper signal:";
