import type { ArmPosition } from "@/lib/armPositions";

// The Research page's one source for what each registered hypothesis IS
// (name, rule, which standard judges it) and the protocol's numbers. The
// numbers are pinned to beatvegas/protocol.py and beatvegas/pricing.py by
// tests/test_research_parity.py, so the copy cannot drift from the test that
// actually decides an arm. Positions themselves come from arm_positions
// (lib/armPositions.ts); nothing here computes one.

export const PROTOCOL = {
  NEEDED_READINGS: 30, // protocol.MIN_OBS: no decision before this many
  MIN_WEEKS: 3, // protocol.MIN_WEEKS
  MAX_READINGS: 200, // protocol.MAX_OBS: timeout
  PROMOTE_LLR: 5.075, // protocol.UPPER, ln(0.8/0.005)
  STOP_LLR: -1.604, // protocol.LOWER, ln(0.2/0.995)
  TARGET_EV: 0.03, // protocol H1: +3% EV against the close
  PRICING_NEEDED: 40, // pricing.VERDICT_MIN_OPPS
  EV_INTERVAL_MIN_READINGS: 10, // the site shows an EV only from here (honest-leaderboard rule)
} as const;

export type Standard = "sprt" | "pricing";

export type HypothesisMeta = {
  id: string;
  name: string;
  rule: string;
  standard: Standard;
  slot: number | null;
};

/** The registered hypotheses the page shows, in ledger-slot order, then the pricing study. */
export const HYPOTHESES: readonly HypothesisMeta[] = [
  {
    id: "H-ARM-1HU",
    name: "First-half unders",
    rule: "The under on Hard Rock’s first-half total when our number sits far enough below it to clear the week’s bar.",
    standard: "sprt",
    slot: 1,
  },
  {
    id: "H-ARM-1HO",
    name: "First-half overs",
    rule: "The over on the bottom fifth of the slate, where our number sits above Hard Rock’s line.",
    standard: "sprt",
    slot: 2,
  },
  {
    id: "H-ARM-FGU",
    name: "Full-game unders",
    rule: "The under on Hard Rock’s full-game total when the full-game model clears its own bar.",
    standard: "sprt",
    slot: 3,
  },
  {
    id: "H-ARM-WX1H",
    name: "Wind, first-half unders",
    rule: "The first-half under at any outdoor game whose kickoff-hour wind is forecast at 10 mph or more.",
    standard: "sprt",
    slot: 6,
  },
  {
    id: "H-ARM-WXFG",
    name: "Wind, full-game unders",
    rule: "The same 10 mph wind rule on the full-game total.",
    standard: "sprt",
    slot: 7,
  },
  {
    id: "H-ARM-HT1H",
    name: "High totals, first-half unders",
    rule: "The first-half under when the books’ consensus full-game total is 60 or more.",
    standard: "sprt",
    slot: 8,
  },
  {
    id: "H-PRICE-HR",
    name: "Hard Rock’s prices",
    rule: "Is Hard Rock’s price ever better than the vig-free market reference for the same wager, and does the market then move toward it?",
    standard: "pricing",
    slot: null,
  },
];

export type CardStatus =
  | "not yet read"
  | "collecting"
  | "reading"
  | "promoted"
  | "stopped"
  | "timed out"
  | "paused"
  | "strengthening"
  | "weakening"
  | "inconclusive";

export type HypothesisCard = {
  meta: HypothesisMeta;
  status: CardStatus;
  needed: number;
  readings: number;
  progressPct: number; // readings / needed, capped at 100
  weeks: number | null;
  excluded: number;
  pending: number;
  logged: number;
  /** The judge's mean EV with its interval, only once there are enough readings. */
  ev: { mean: number; lo: number | null; hi: number | null } | null;
  /** The SPRT position as a share of the way from STOP (0) to PROMOTE (1). */
  llrPct: number | null;
  llr: number | null;
  readAt: Date | null;
  runId: string | null;
  nextRead: string | null;
  outdated: boolean;
  sufficient: boolean;
};

export function statusOf(
  meta: HypothesisMeta,
  pos: ArmPosition | undefined,
): CardStatus {
  if (!pos) return "not yet read";
  const s = (pos.state ?? "").toLowerCase();
  if (meta.standard === "pricing") {
    if (s === "insufficient" || s === "") return "collecting";
    if (s === "strengthening" || s === "weakening" || s === "inconclusive")
      return s;
    return "collecting";
  }
  if (s === "promote") return "promoted";
  if (s === "stop") return "stopped";
  if (s === "timeout") return "timed out";
  if (s === "paused") return "paused";
  return pos.sufficient ? "reading" : "collecting";
}

export function llrShare(llr: number): number {
  const span = PROTOCOL.PROMOTE_LLR - PROTOCOL.STOP_LLR;
  const v = (llr - PROTOCOL.STOP_LLR) / span;
  return Math.min(1, Math.max(0, v));
}

export function cardFor(
  meta: HypothesisMeta,
  pos: ArmPosition | undefined,
): HypothesisCard {
  const needed =
    pos?.needed ??
    (meta.standard === "pricing"
      ? PROTOCOL.PRICING_NEEDED
      : PROTOCOL.NEEDED_READINGS);
  const readings = pos?.readings ?? 0;
  const enoughForEv =
    pos !== undefined &&
    pos.mean_ev !== null &&
    readings >= PROTOCOL.EV_INTERVAL_MIN_READINGS;
  return {
    meta,
    status: statusOf(meta, pos),
    needed,
    readings,
    progressPct: Math.min(100, Math.round((100 * readings) / needed)),
    weeks: pos?.weeks ?? null,
    excluded: pos?.excluded ?? 0,
    pending: pos?.pending ?? 0,
    logged: pos?.logged ?? 0,
    ev: enoughForEv
      ? { mean: pos.mean_ev as number, lo: pos.ev_lo, hi: pos.ev_hi }
      : null,
    llrPct:
      meta.standard === "sprt" &&
      pos?.llr !== null &&
      pos?.llr !== undefined &&
      readings > 0
        ? llrShare(pos.llr)
        : null,
    llr: pos?.llr ?? null,
    readAt: pos?.readAt ?? null,
    runId: pos?.run_id ?? null,
    nextRead: pos?.next_read ?? null,
    outdated: pos?.freshness === "outdated",
    sufficient: pos?.sufficient ?? false,
  };
}

/** The cards in slot order; no rank, no sort by result (honest-leaderboard rule). */
export function cardsFor(
  positions: Map<string, ArmPosition>,
): HypothesisCard[] {
  return HYPOTHESES.map((m) => cardFor(m, positions.get(m.id)));
}

export const pct = (v: number) =>
  `${v >= 0 ? "+" : ""}${(100 * v).toFixed(1)}%`;
