// Every enum the site shows a reader, translated ONCE into plain English.
// No component renders a raw enum value: it goes through a map here, and
// `labelOf` never echoes an unknown key back to the screen.
//
// Vocabulary (docs/superpowers/specs/2026-09-08-site-copy.md): score · gap ·
// our number · Hard Rock's line · the market line · our reference line ·
// line value · Watch (never "EDGE" on screen) · kill line / kill price ·
// paper pick · weekly cap.

import { american, fmt } from "@/lib/format";
import type { EdgeBlocker, EdgeTier } from "@/lib/edge";
import type { LineBasis } from "@/lib/edge";
import type { CardBlocker } from "@/lib/card";
import type { SlipBlock } from "@/lib/betSlip";
import type { PickReason, Verdict } from "@/lib/verdict";
import { BET_GAP_PTS, STRONG_GAP_PTS, WEEKLY_BET_CAP } from "@/lib/verdict";

/** Look a key up; an unknown key gets the fallback, never itself. */
export function labelOf<K extends string>(
  map: Readonly<Record<K, string>>,
  key: string | null | undefined,
  fallback: string,
): string {
  if (key === null || key === undefined) return fallback;
  return (map as Readonly<Record<string, string>>)[key] ?? fallback;
}

// --- tiers --------------------------------------------------------------------

/** The small word beside the score. EDGE is "Watch" everywhere on screen. */
export const TIER_TEXT: Record<EdgeTier, string> = {
  BET: "Bet",
  EDGE: "Watch",
  PASS: "Pass",
};

/** The verdict frozen onto a logged pick. */
export const VERDICT_TEXT: Record<Verdict, string> = {
  BET: "Bet",
  WATCH: "Watch",
  PASS: "Pass",
};

/** manual_picks.market. */
export const MARKET_TEXT: Record<string, string> = {
  "1H": "First half",
  full: "Full game",
};

// --- blockers (why a strong game is not a bet right now) ---------------------

export type AnyBlocker = EdgeBlocker | CardBlocker;

/** Table-cell form. */
export const BLOCKER_SHORT: Record<AnyBlocker, string> = {
  no_hr_line: "Waiting on Hard Rock's line",
  off_market: "Hard Rock's line is below the market",
  price: "Price too short",
  no_fair_price: "Price can't be compared",
  qb_out: "Starting QB out",
  gap: "Gap too small",
  no_model: "No model number",
  cap: "Past the weekly cap",
  degraded: "An input failed",
};

/** Results "what blocked it" rows (includes the two non-blocker ledger keys). */
export const GATE_TEXT: Record<AnyBlocker | "none" | "untagged", string> = {
  none: "Bet — nothing blocked it",
  no_hr_line: "Hard Rock had no first-half line",
  off_market: "Hard Rock's line was below the market",
  price: "Hard Rock's price was too short",
  no_fair_price: "Hard Rock's price could not be compared",
  qb_out: "A starting QB was out",
  gap: "The gap was too small",
  no_model: "No model number yet",
  cap: `Past the ${WEEKLY_BET_CAP}-bet week`,
  degraded: "An input failed that morning",
  untagged: "Logged before we tracked this",
};

export type BlockerContext = {
  hrLine?: number | null;
  hrPrice?: number | null;
  marketLine?: number | null;
  killLine?: number | null;
  killPrice?: number | null;
};

/**
 * The plain tag on a card whose score is strong but which is not a bet right
 * now. Carries the numbers the reader needs, so nothing lives in a tooltip.
 */
export function blockerTag(
  blocker: AnyBlocker | null,
  ctx: BlockerContext = {},
): string | null {
  if (blocker === null) return null;
  switch (blocker) {
    case "no_hr_line":
      return "Not yet — Hard Rock has no first-half line";
    case "off_market": {
      const diff =
        ctx.marketLine != null && ctx.hrLine != null
          ? ` ${fmt(ctx.marketLine - ctx.hrLine)}`
          : "";
      return `Not yet — Hard Rock's line is${diff} below the market line`;
    }
    case "price": {
      const hr = ctx.hrPrice != null ? american(ctx.hrPrice) : "too short";
      const needs =
        ctx.killPrice != null
          ? `${american(ctx.killPrice)} or better`
          : "a better price";
      return `Not yet — Hard Rock's price is ${hr}; needs ${needs}`;
    }
    case "no_fair_price":
      return "Not yet — no other book is at that number, so the price can't be compared";
    case "qb_out":
      return "Starting QB out — recheck";
    case "gap":
      return ctx.killLine != null
        ? `Not yet — the line needs to reach ${fmt(ctx.killLine)}`
        : "Not yet — the gap is too small";
    case "no_model":
      return "No model number yet — the week has not been scored";
    case "cap":
      return `Past the ${WEEKLY_BET_CAP}-bet week — paper only`;
    case "degraded":
      return "Paper only — an input is missing";
  }
}

// --- bet slip -----------------------------------------------------------------

export type SlipBlockContext = {
  line?: number | null;
  price?: number | null;
  killLine?: number | null;
  killPrice?: number | null;
  liveLine?: number | null;
  livePrice?: number | null;
};

/** Why the slip will not log this bet — typed-value form and live-line form. */
export function slipBlockText(
  block: SlipBlock,
  live: boolean,
  ctx: SlipBlockContext = {},
): string {
  const kl = ctx.killLine != null ? `u${fmt(ctx.killLine)}` : "the kill line";
  const kp = ctx.killPrice != null ? american(ctx.killPrice) : "the kill price";
  switch (block) {
    case "degraded":
      return "An input is missing, so this is paper only.";
    case "cap":
      return `${WEEKLY_BET_CAP} real-money bets are already logged this week.`;
    case "kill_line":
      if (live) {
        const now =
          ctx.liveLine != null ? `u${fmt(ctx.liveLine)}` : "a lower total";
        return `Hard Rock is now at ${now}, below the kill line of ${kl}.`;
      }
      return ctx.line != null
        ? `u${fmt(ctx.line)} is below the kill line of ${kl} — not the bet we rated.`
        : `That total is below the kill line of ${kl} — not the bet we rated.`;
    case "kill_price":
      if (live) {
        const now =
          ctx.livePrice != null ? american(ctx.livePrice) : "a worse price";
        return `Hard Rock is now ${now}, worse than the kill price of ${kp}.`;
      }
      return ctx.price != null
        ? `${american(ctx.price)} is worse than the kill price of ${kp} — not the bet we rated.`
        : `That price is worse than the kill price of ${kp} — not the bet we rated.`;
  }
}

// --- pick reasons -------------------------------------------------------------

export type ReasonKey = PickReason | "untagged" | "off_policy";

export const REASON_TEXT: Record<ReasonKey, { long: string; short: string }> = {
  model_gap: {
    long: `Model gap — Hard Rock ${BET_GAP_PTS}+ above our number`,
    short: "model gap",
  },
  price_edge: { long: "Price only — no model number", short: "price only" },
  manual: { long: "Your own call", short: "your call" },
  untagged: { long: "Logged before we tracked this", short: "untagged" },
  off_policy: { long: "Real money on a Watch or Pass", short: "off the rules" },
};

// --- degraded card inputs -----------------------------------------------------

// Mirrors beatvegas/card.py DEGRADED_INPUT_TEXT — see the reasoning there for
// why "morning" is gone and why `pace` no longer claims a failure.
export const CARD_INPUT_TEXT: Record<string, string> = {
  sweep: "the line sweep did not finish",
  preview: "the injury and news pull did not finish",
  tempo: "the pace numbers did not load",
  pace: "these teams have only played FCS opponents, so there is no season-to-date pace on them yet",
};
export const CARD_INPUT_FALLBACK = "an input did not load";

// --- line basis ---------------------------------------------------------------

/** "vs Hard Rock's line" / "vs the market line (DraftKings, FanDuel)" / ... */
export function basisPhrase(
  basis: LineBasis | null,
  books: readonly string[] = [],
): string {
  switch (basis) {
    case "hardrock":
      return "vs Hard Rock's line";
    case "market":
      return books.length > 0
        ? `vs the market line (${books.join(", ")})`
        : "vs the market line";
    case "reference":
      return "vs our reference line (from the full-game total)";
    default:
      return "";
  }
}

// --- line study sources --------------------------------------------------------

export const LINE_SOURCE_TEXT: Record<string, string> = {
  real_open: "a book's open",
  proxy: "our estimate",
};

// --- post-mortem --------------------------------------------------------------

export const RULE_TEXT: Record<string, string> = {
  cap5: `Followed the rules (at most ${WEEKLY_BET_CAP} a week, gap ${BET_GAP_PTS}+)`,
  gap175: `Every gap ${BET_GAP_PTS}+`,
  gap300: `Every gap ${STRONG_GAP_PTS}+`,
  top20: "Top 20% by gap each season",
  all: "Every game (blanket under)",
  bet: "Rated Bet",
  price_read: "Hard Rock paid at least fair",
  all_hr: "Every Hard Rock line",
  qualifying: `Gap ${BET_GAP_PTS}+ at Hard Rock, whatever blocked it`,
};

export const PROXY_TEXT: Record<string, string> = {
  real: "the real closing line",
  fg: "the full-game closing line",
  step: "an estimated line",
  hr: "Hard Rock's line",
  hr_close: "Hard Rock's closing line",
  market: "the market line when we rated it",
  market_close: "the market's closing line",
};

export const SEVERITY_TEXT: Record<string, string> = {
  change: "change",
  watch: "watch",
  ok: "holds up",
};

/** Settled outcome words for tables. */
export const RESULT_TEXT: Record<string, string> = {
  under: "Under",
  over: "Over",
  push: "Push",
};
export const RESULT_PENDING = "Pending";
/** A played game whose first half no book ever priced: shown for the score, not the record. */
export const RESULT_NO_LINE = "No line";

/** Outcome colours (never cyan): under/won green, over/lost red, push grey. */
export const RESULT_COLOR: Record<string, string> = {
  under: "var(--good)",
  over: "var(--bad)",
  push: "var(--push)",
};

/** Punctuation- and case-insensitive form, so a comparison is not defeated by a
 *  curly apostrophe or a trailing full stop. */
function loose(s: string): string {
  return s
    .toLowerCase()
    .replace(/[‘’′']/g, "'")
    .replace(/[^a-z0-9'+-]+/g, " ")
    .trim();
}

/**
 * The blocker tag, but only when it says something the action line does not.
 * `blockerTag` and `edge.action` are built from the same blocker, so on most
 * Watch games they render the identical sentence twice — the tag is meant to be
 * a summary beside a different message, not an echo of it.
 */
export function distinctTag(
  tag: string | null,
  action: string | null,
): string | null {
  if (tag === null) return null;
  const t = loose(tag);
  if (t === "") return null;
  return action !== null && loose(action).includes(t) ? null : tag;
}
