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

/** Each arm's clock start, naive UTC (protocol.ARMS_START / WX_ARMS_START /
 *  HT_ARM_START; pinned by tests/test_research_parity.py). A paper pick placed
 *  before its arm's start is development evidence and never a reading. */
export const ARM_STARTS: Record<string, string> = {
  "H-ARM-1HU": "2026-10-13T20:51:39.533351",
  "H-ARM-1HO": "2026-10-13T20:51:39.533351",
  "H-ARM-FGU": "2026-10-13T20:51:39.533351",
  "H-ARM-WX1H": "2026-10-10T00:00:00",
  "H-ARM-WXFG": "2026-10-10T00:00:00",
  "H-ARM-HT1H": "2026-10-10T00:00:00",
};

/** The final read of the 2026 season (protocol.FINAL_READ_DATE; roadmap v2.6,
 *  Tate 2026-10-18; pinned by tests/test_research_parity.py): the Monday after
 *  the last captured slate (Sat 2026-11-28). Every arm is read for the last time
 *  that day and a still-running one times out. It replaced the 2027-01-25 read. */
export const FINAL_READ_DATE = "2026-11-30";

/** The 1H-unders arm reads the paper picks the card logs; true when this pick
 *  was placed at or after its clock start. */
export function isForward(arm: string, placedAtIso: string | null): boolean {
  const start = ARM_STARTS[arm];
  if (!start || placedAtIso === null) return false;
  const t = Date.parse(
    /[zZ]|[+-]\d\d:?\d\d$/.test(placedAtIso)
      ? placedAtIso
      : `${placedAtIso.replace(" ", "T")}Z`,
  );
  return t >= Date.parse(`${start.slice(0, 23)}Z`);
}

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

// --- Exploratory collectors (no error budget, no sequential test) -------------

export type ExploratoryMeta = {
  id: string;
  name: string;
  rule: string;
  decides: string;
};

/** H-ARM-EVP (Tate's option A, 2026-10-14; beatvegas/evp_paper.py). Not one of
 *  the registered arms: it never takes a slot in the error budget, and nothing
 *  is adopted from it; the final read (FINAL_READ_DATE, 2026-11-30) decides
 *  whether a 2027 test is registered. */
export const EXPLORATORY: readonly ExploratoryMeta[] = [
  {
    id: "H-ARM-EVP",
    name: "Value at Hard Rock’s price",
    rule: "The first-half under when its estimated value at Hard Rock’s price is +2% or more: the market’s vig-free line moved a fifth of the way toward our number.",
    decides:
      "Exploratory: no error budget and no decision this season. The final read on Nov 30, 2026 decides whether it becomes a registered test.",
  },
];

type Summary = {
  n: number;
  mean_ev: number | null;
  ev_lo: number | null;
  ev_hi: number | null;
};

export type ExploratoryCard = {
  meta: ExploratoryMeta;
  status: "not yet read" | "collecting";
  logged: number;
  readings: number;
  weeks: number;
  excluded: number;
  pending: number;
  ev: { mean: number; lo: number | null; hi: number | null } | null;
  /** The gap rule (H-ARM-1HU) over exactly the same weeks, from the same row. */
  gap: {
    readings: number;
    excluded: number;
    ev: { mean: number; lo: number | null; hi: number | null } | null;
  } | null;
  both: number;
  evpOnly: number;
  gapOnly: number;
  readAt: Date | null;
  runId: string | null;
  nextRead: string | null;
  outdated: boolean;
};

const num = (v: unknown): number | null =>
  typeof v === "number" && Number.isFinite(v) ? v : null;

/** An EV only from EV_INTERVAL_MIN_READINGS readings (the same honest rule as the arms). */
function evOf(s: Summary | null) {
  if (s === null || s.mean_ev === null) return null;
  if (s.n < PROTOCOL.EV_INTERVAL_MIN_READINGS) return null;
  return { mean: s.mean_ev, lo: s.ev_lo, hi: s.ev_hi };
}

function summaryOf(v: unknown): (Summary & { excluded: number }) | null {
  if (v === null || typeof v !== "object") return null;
  const o = v as Record<string, unknown>;
  return {
    n: num(o.n) ?? 0,
    mean_ev: num(o.mean_ev),
    ev_lo: num(o.ev_lo),
    ev_hi: num(o.ev_hi),
    excluded: num(o.excluded) ?? 0,
  };
}

/** Pure: the exploratory card from its newest stored row and that row's payload. */
export function exploratoryCardFor(
  meta: ExploratoryMeta,
  pos: ArmPosition | undefined,
  payload: Record<string, unknown> | null,
): ExploratoryCard {
  const readings = pos?.readings ?? 0;
  const cmp =
    payload && typeof payload.comparison === "object" && payload.comparison
      ? (payload.comparison as Record<string, unknown>)
      : null;
  const gap = summaryOf(cmp?.gap_rule ?? null);
  return {
    meta,
    status: pos ? "collecting" : "not yet read",
    logged: pos?.logged ?? 0,
    readings,
    weeks: pos?.weeks ?? 0,
    excluded: pos?.excluded ?? 0,
    pending: pos?.pending ?? 0,
    ev: pos
      ? evOf({
          n: readings,
          mean_ev: pos.mean_ev,
          ev_lo: pos.ev_lo,
          ev_hi: pos.ev_hi,
        })
      : null,
    gap:
      gap === null
        ? null
        : { readings: gap.n, excluded: gap.excluded, ev: evOf(gap) },
    both: num(cmp?.both) ?? 0,
    evpOnly: num(cmp?.evp_only) ?? 0,
    gapOnly: num(cmp?.gap_only) ?? 0,
    readAt: pos?.readAt ?? null,
    runId: pos?.run_id ?? null,
    nextRead: pos?.next_read ?? null,
    outdated: pos?.freshness === "outdated",
  };
}
