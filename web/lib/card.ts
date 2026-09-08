import { american, fmt } from "@/lib/format";
import { kickoffET } from "@/lib/homeBoard";
import { prisma } from "@/lib/prisma";
import { REASONS, WEEKLY_BET_CAP, type PickReason } from "@/lib/verdict";

// The bet card. scripts/build_card.py (GitHub Actions: weeknight and Friday
// preview builds, then the Saturday-morning FINAL ~8:45am ET) writes one row
// per build to `cards` (season, week, built_at, payload JSON). The home board
// shows the latest row for the week. The table is NOT in the Prisma schema and
// may not exist yet on a fresh database — every read degrades to "no card"
// instead of a 500.
//
// Payload contract (exact, from the Python side):
//   {season, week, built_at, model_read, slot, status,
//    degraded:[{input, detail, game_ids?}],
//    counts:{bet,edge,pass,over_cap,degraded},
//    paper:{qualifying, over_cap, cap},
//    items:[{game_id, away, home, kick, tier, blocker, hr_line, hr_price,
//            hr_open, market_line, fair_under, fair_source, hr_vs_market, ev,
//            bv_line, gap, kill_line, kill_price, action, why:[...], paper_logged,
//            qualifies, paper_blocker, cap_rank, over_cap,
//            full_game_total, spread, total_band, hook_side, key_dist,
//            hr_vs_market, fair_source, degraded_inputs, reason}],
//    notes:[...]}
// slot/status/degraded and the per-item provenance fields arrived 2026-09;
// older rows lack them and parse to null / "final" / [] so nothing breaks.
// counts.bet excludes over-cap and degraded BETs (the bettable count).
// Items arrive pre-sorted: BET, then EDGE, then PASS — each tier by gap desc
// (the cap-5 rule the real-close backtest measured ranks by gap). The 6th+
// BET by gap keeps tier BET but carries blocker "cap" and over_cap: every
// gate passed, the weekly cap (docs/BETTING_POLICY.md) makes it paper only.
// counts.bet is the bettable BETs (inside the cap, no failed input);
// counts.over_cap and counts.degraded tally the rest.

export type CardTier = "BET" | "EDGE" | "PASS";
export type CardBlocker =
  | "no_hr_line"
  | "off_market"
  | "price"
  | "no_fair_price"
  | "qb_out"
  | "gap"
  | "no_model"
  | "cap"
  /** No fair price to judge Hard Rock's against (no exchange/books at the number). */
  | "no_fair_price"
  /** An input the gate needs failed on this build (see Card.degraded). */
  | "degraded";
/** Which build wrote the card: weeknight/Friday previews, the Saturday final, or a manual run. */
export type CardSlot = "weeknight" | "friday" | "saturday" | "manual";
/** final = bet off it; preview = an earlier build; degraded = an input failed. */
export type CardStatus = "final" | "preview" | "degraded";
export type DegradedInput = {
  input: string;
  detail: string;
  /** Games the failure touched; [] when it was build-wide. */
  gameIds: number[];
};
/** Where the fair price came from: a no-vig exchange, or the books' consensus. */
export type FairSource = "exchange" | "books";

export type CardItem = {
  gameId: number;
  away: string;
  home: string;
  /** Kickoff as a UTC ISO string; null when unknown. */
  kick: string | null;
  tier: CardTier;
  blocker: CardBlocker | null;
  hrLine: number | null;
  hrPrice: number | null;
  hrOpen: number | null;
  marketLine: number | null;
  fairUnder: number | null;
  ev: number | null;
  bvLine: number | null;
  gap: number | null;
  killLine: number | null;
  killPrice: number | null;
  action: string;
  why: string[];
  paperLogged: boolean;
  /** Hard Rock's 1H line sits BET_GAP_PTS+ above ours (any tier): on the paper ledger. */
  qualifies: boolean;
  /** The gate that blocked a real bet on a qualifying game (null = it was a BET). */
  paperBlocker: string | null;
  /** 1-based rank among the week's BETs by gap; null on non-BETs. */
  capRank: number | null;
  /** BET beyond the weekly cap: every gate passed, paper only. */
  overCap: boolean;
  /** Display chips (never gates): full-game total band and hook position. */
  totalBand: string | null;
  hookSide: string | null;
  /** Hard Rock's 1H line minus the market's (+ = Hard Rock is higher, better for an under). */
  hrVsMarket: number | null;
  fairSource: FairSource | null;
  /** The reason a pick off this item would log (model_gap / price_edge / manual). */
  reason: PickReason | null;
  /** Inputs that failed for this game on this build. */
  degradedInputs: string[];
};

export type Card = {
  season: number;
  week: number;
  /** When the card was built, UTC ISO; null when the payload did not say. */
  builtAt: string | null;
  modelRead: boolean;
  slot: CardSlot | null;
  status: CardStatus;
  degraded: DegradedInput[];
  /** bet = bettable BETs (inside the cap, no failed input); overCap = BETs beyond it; degraded = items blocked by a failed input. */
  counts: {
    bet: number;
    edge: number;
    pass: number;
    overCap: number;
    degraded: number;
  };
  /** Paper ledger tallies: qualifying games, BETs over the cap, the cap. */
  paper: { qualifying: number; overCap: number; cap: number };
  items: CardItem[];
  notes: string[];
};

// --- parsing ----------------------------------------------------------------

const TIERS: readonly CardTier[] = ["BET", "EDGE", "PASS"];
const BLOCKERS: readonly CardBlocker[] = [
  "no_hr_line",
  "off_market",
  "price",
  "no_fair_price",
  "qb_out",
  "gap",
  "no_model",
  "cap",
  "no_fair_price",
  "degraded",
];
const SLOTS: readonly CardSlot[] = [
  "weeknight",
  "friday",
  "saturday",
  "manual",
];
const STATUSES: readonly CardStatus[] = ["final", "preview", "degraded"];
const FAIR_SOURCES: readonly FairSource[] = ["exchange", "books"];

const num = (v: unknown): number | null => {
  if (v === null || v === undefined || v === "" || typeof v === "boolean") {
    return null;
  }
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};
const int = (v: unknown): number | null => {
  const n = num(v);
  return n === null ? null : Math.trunc(n);
};
const str = (v: unknown): string | null =>
  typeof v === "string" && v.trim() !== "" ? v : null;
const strList = (v: unknown): string[] =>
  Array.isArray(v)
    ? v.filter((s): s is string => typeof s === "string" && s.trim() !== "")
    : [];
const isObj = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null && !Array.isArray(v);

function parseItem(raw: unknown): CardItem | null {
  if (!isObj(raw)) return null;
  const gameId = int(raw.game_id);
  const away = str(raw.away);
  const home = str(raw.home);
  if (gameId === null || away === null || home === null) return null;
  const tier = TIERS.includes(raw.tier as CardTier)
    ? (raw.tier as CardTier)
    : "PASS";
  const blocker = BLOCKERS.includes(raw.blocker as CardBlocker)
    ? (raw.blocker as CardBlocker)
    : null;
  return {
    gameId,
    away,
    home,
    kick: str(raw.kick),
    tier,
    blocker,
    hrLine: num(raw.hr_line),
    hrPrice: int(raw.hr_price),
    hrOpen: num(raw.hr_open),
    marketLine: num(raw.market_line),
    fairUnder: num(raw.fair_under),
    ev: num(raw.ev),
    bvLine: num(raw.bv_line),
    gap: num(raw.gap),
    killLine: num(raw.kill_line),
    killPrice: int(raw.kill_price),
    action: str(raw.action) ?? "",
    why: strList(raw.why),
    paperLogged: raw.paper_logged === true || raw.paper_logged === 1,
    qualifies: raw.qualifies === true || raw.qualifies === 1,
    paperBlocker: str(raw.paper_blocker),
    capRank: int(raw.cap_rank),
    overCap: raw.over_cap === true || raw.over_cap === 1,
    totalBand: str(raw.total_band),
    hookSide: str(raw.hook_side),
    hrVsMarket: num(raw.hr_vs_market),
    fairSource: FAIR_SOURCES.includes(raw.fair_source as FairSource)
      ? (raw.fair_source as FairSource)
      : null,
    reason: REASONS.includes(raw.reason as PickReason)
      ? (raw.reason as PickReason)
      : null,
    degradedInputs: strList(raw.degraded_inputs),
  };
}

function parseDegraded(raw: unknown): DegradedInput | null {
  if (!isObj(raw)) return null;
  const input = str(raw.input);
  if (input === null) return null;
  const gameIds = Array.isArray(raw.game_ids)
    ? raw.game_ids.map(int).filter((n): n is number => n !== null)
    : [];
  return { input, detail: str(raw.detail) ?? "", gameIds };
}

/**
 * Pure, defensive parse of a card payload (JSON text or an already-parsed
 * object). Null when the payload is not JSON, not an object, or has no usable
 * season/week. Items that lack a game id or a team are dropped; every other
 * field is null-safe. Counts are re-derived from the items when the payload's
 * own counts are missing or malformed, so the panel can never disagree with
 * the rows it shows.
 */
export function parseCard(raw: unknown): Card | null {
  let obj: unknown = raw;
  if (typeof raw === "string") {
    try {
      obj = JSON.parse(raw);
    } catch {
      return null;
    }
  }
  if (!isObj(obj)) return null;
  const season = int(obj.season);
  const week = int(obj.week);
  if (season === null || week === null) return null;

  const items = Array.isArray(obj.items)
    ? obj.items.map(parseItem).filter((i): i is CardItem => i !== null)
    : [];
  const derived = {
    bet: items.filter(
      (i) => i.tier === "BET" && !i.overCap && i.blocker !== "degraded",
    ).length,
    edge: items.filter((i) => i.tier === "EDGE").length,
    pass: items.filter((i) => i.tier === "PASS").length,
    overCap: items.filter((i) => i.overCap).length,
    degraded: items.filter((i) => i.blocker === "degraded").length,
  };
  const c = isObj(obj.counts) ? obj.counts : {};
  const counts = {
    bet: int(c.bet) ?? derived.bet,
    edge: int(c.edge) ?? derived.edge,
    pass: int(c.pass) ?? derived.pass,
    overCap: int(c.over_cap) ?? derived.overCap,
    degraded: int(c.degraded) ?? derived.degraded,
  };
  const degraded = Array.isArray(obj.degraded)
    ? obj.degraded
        .map(parseDegraded)
        .filter((d): d is DegradedInput => d !== null)
    : [];
  const slot = SLOTS.includes(obj.slot as CardSlot)
    ? (obj.slot as CardSlot)
    : null;
  // A failed input always shows as degraded, whatever the builder said.
  const status: CardStatus =
    degraded.length > 0
      ? "degraded"
      : STATUSES.includes(obj.status as CardStatus)
        ? (obj.status as CardStatus)
        : "final";
  const pp = isObj(obj.paper) ? obj.paper : {};
  const paper = {
    qualifying: int(pp.qualifying) ?? items.filter((i) => i.qualifies).length,
    overCap: int(pp.over_cap) ?? items.filter((i) => i.overCap).length,
    cap: int(pp.cap) ?? WEEKLY_BET_CAP,
  };

  return {
    season,
    week,
    builtAt: asIso(obj.built_at),
    modelRead: obj.model_read === true || obj.model_read === 1,
    slot,
    status,
    degraded,
    counts,
    paper,
    items,
    notes: strList(obj.notes),
  };
}

/** Normalise a timestamp (Date, ISO string, or a naive Postgres text
 *  "2026-09-04 22:07:12" which the Python side writes in UTC) to UTC ISO. */
export function asIso(v: unknown): string | null {
  if (v instanceof Date) {
    return Number.isNaN(v.getTime()) ? null : v.toISOString();
  }
  const s = str(v);
  if (s === null) return null;
  let t = s.trim();
  // Naive "YYYY-MM-DD HH:MM:SS[.fff]" carries no zone: treat as UTC.
  if (/^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(t)) {
    t = `${t.replace(" ", "T")}Z`;
  }
  const d = new Date(t);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

// --- age ----------------------------------------------------------------------

const ET = "America/New_York";

/** "Fri 6:07pm" in ET. */
function builtET(d: Date): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: ET,
    weekday: "short",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  }).formatToParts(d);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  const ampm = get("dayPeriod").toLowerCase().startsWith("p") ? "pm" : "am";
  return `${get("weekday")} ${get("hour")}:${get("minute")}${ampm}`;
}

/** "just now" / "12m ago" / "3h ago" / "2d ago". */
export function relativeAge(then: Date, now: Date): string {
  const ms = Math.max(0, now.getTime() - then.getTime());
  const m = Math.floor(ms / 60_000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 48) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

/**
 * "built Fri 6:07pm ET · 3h ago" — when the card was built, in the reader's
 * betting timezone, plus how stale it is. Null when the time is unknown.
 */
export function cardAge(
  builtAt: string | Date | null,
  now: Date = new Date(),
): string | null {
  const iso = asIso(builtAt);
  if (iso === null) return null;
  const d = new Date(iso);
  return `built ${builtET(d)} ET · ${relativeAge(d, now)}`;
}

// --- health (is this the card to bet off?) ---------------------------------------

/** A card older than this, read on a Saturday, means the final never landed. */
export const STALE_CARD_HOURS = 6;

/** Weekday in ET ("Sat"). */
function weekdayET(d: Date): string {
  return new Intl.DateTimeFormat("en-US", { timeZone: ET, weekday: "short" })
    .format(d)
    .slice(0, 3);
}

export type CardHealth = {
  level: "ok" | "warn";
  title: string;
  details: string[];
};

/**
 * Pure: whether the card on screen is the one to bet off. In order: a
 * degraded build warns and lists the failed inputs; on a Saturday (ET) a
 * preview build, or one built for another slot, warns that the final has not
 * replaced it; on a Saturday a legacy row (no slot/status) older than
 * STALE_CARD_HOURS warns the same way. Anything else is ok — a Friday preview
 * read on Friday is exactly what it should be.
 */
export function cardHealth(card: Card, now: Date): CardHealth {
  if (card.status === "degraded") {
    return {
      level: "warn",
      title: `Degraded card · ${card.slot ?? "unknown slot"}`,
      details: card.degraded.map((d) =>
        d.detail === "" ? d.input : `${d.input}: ${d.detail}`,
      ),
    };
  }
  const saturday = weekdayET(now) === "Sat";
  if (
    saturday &&
    (card.status === "preview" ||
      (card.slot !== null && card.slot !== "saturday"))
  ) {
    if (card.slot === "manual") {
      const when =
        card.builtAt === null
          ? ""
          : ` built ${builtET(new Date(card.builtAt))} ET`;
      return {
        level: "warn",
        title: `Manual card${when} — re-run with slot=saturday for a final`,
        details: [],
      };
    }
    return {
      level: "warn",
      title: `Preview card (${card.slot ?? "preview"}) — the Saturday final builds 8:05–8:45am ET`,
      details: [],
    };
  }
  const isSaturdayFinal = card.slot === "saturday" && card.status === "final";
  if (saturday && !isSaturdayFinal && card.builtAt !== null) {
    const built = new Date(card.builtAt);
    const ageMs = now.getTime() - built.getTime();
    if (ageMs > STALE_CARD_HOURS * 3_600_000) {
      return {
        level: "warn",
        title: `Card is ${relativeAge(built, now)} — the Saturday final has not landed`,
        details: [],
      };
    }
  }
  return { level: "ok", title: "", details: [] };
}

// --- summary (what the panel shows) --------------------------------------------

/** Rows the panel is allowed to draw at most. */
export const MAX_CARD_ROWS = 8;
/** EDGE items shown as "closest to a bet" on a no-bet week. */
export const CLOSEST_ROWS = 3;

export type CardRow = {
  gameId: number;
  tier: CardTier;
  /** "Away @ Home" */
  matchup: string;
  /** "Sat 7:30p" ET, or null when the kickoff is unknown. */
  kick: string | null;
  /** "u24.5 -110", "u24.5" when the price is unknown, or "no Hard Rock line". */
  line: string;
  action: string;
  paperLogged: boolean;
  /** Rank among the week's BETs by gap (1 = biggest gap); null on non-BETs. */
  capRank: number | null;
  overCap: boolean;
  /** Which gate blocked a real bet on a qualifying game (null = none). */
  paperBlocker: string | null;
  /** "below u24.5 or worse than -120" — the numbers that kill the bet; "" when unknown. */
  kill: string;
};

export type CardSummary = {
  /** "No bets this week." / "1 bet this week." / "3 bets this week." */
  headline: string;
  hasBets: boolean;
  /** One row per bettable BET (inside the weekly cap, no failed input), in card order (never more than MAX_CARD_ROWS). */
  bets: CardRow[];
  /** BETs beyond the weekly cap: every gate passed, paper only. */
  overCap: CardRow[];
  /** BETs held because an input failed on this build (blocker "degraded"): paper only, no cap slot. */
  degraded: CardRow[];
  /** On a no-bet week: up to CLOSEST_ROWS EDGE items, best ev first. */
  closest: CardRow[];
  /** On a no-bet week: the first note, shown right under the headline. */
  reason: string | null;
  /** The remaining notes. */
  notes: string[];
};

/** "u24.5 -110" — the Hard Rock first-half line and under price on an item. */
export function lineLabel(item: Pick<CardItem, "hrLine" | "hrPrice">): string {
  if (item.hrLine === null) return "no Hard Rock line";
  return `u${fmt(item.hrLine)}${item.hrPrice === null ? "" : ` ${american(item.hrPrice)}`}`;
}

/** "below u24.5 or worse than -120" — what would kill the bet; "" when unknown. */
export function killLabel(
  item: Pick<CardItem, "killLine" | "killPrice">,
): string {
  const parts: string[] = [];
  if (item.killLine !== null) parts.push(`below u${fmt(item.killLine)}`);
  if (item.killPrice !== null)
    parts.push(`worse than ${american(item.killPrice)}`);
  return parts.join(" or ");
}

function toRow(item: CardItem): CardRow {
  return {
    gameId: item.gameId,
    tier: item.tier,
    matchup: `${item.away} @ ${item.home}`,
    kick: kickoffET(item.kick),
    line: lineLabel(item),
    action: item.action,
    paperLogged: item.paperLogged,
    capRank: item.capRank,
    overCap: item.overCap,
    paperBlocker: item.overCap ? "cap" : item.paperBlocker,
    kill: killLabel(item),
  };
}

/** Pure: everything the card panel draws, worked out once from the card. */
export function summarizeCard(card: Card): CardSummary {
  const bets = card.items
    .filter((i) => i.tier === "BET" && !i.overCap && i.blocker !== "degraded")
    .slice(0, MAX_CARD_ROWS)
    .map(toRow);
  const overCap = card.items
    .filter((i) => i.tier === "BET" && i.overCap)
    .map(toRow);
  const degraded = card.items
    .filter((i) => i.tier === "BET" && i.blocker === "degraded")
    .map(toRow);
  const hasBets = bets.length > 0;
  const closest = hasBets
    ? []
    : card.items
        .filter((i) => i.tier === "EDGE")
        .sort(
          (a, b) =>
            (b.ev ?? Number.NEGATIVE_INFINITY) -
            (a.ev ?? Number.NEGATIVE_INFINITY),
        )
        .slice(0, CLOSEST_ROWS)
        .map(toRow);
  const reason = hasBets ? null : (card.notes[0] ?? null);
  return {
    headline: hasBets
      ? `${bets.length} bet${bets.length === 1 ? "" : "s"} this week.`
      : "No bets this week.",
    hasBets,
    bets,
    overCap,
    degraded,
    closest,
    reason,
    notes: reason === null ? card.notes : card.notes.slice(1),
  };
}

// --- reads ------------------------------------------------------------------------

type CardRowRaw = { payload: string | null; built_at: Date | string | null };

/**
 * The most recent card for a season and week — or, with no week, the most
 * recent card of the season (the caller checks `card.week` against the board's
 * week). Null when there is no row, the table does not exist yet, or the
 * payload does not parse.
 */
export async function getLatestCard(
  season: number,
  week?: number,
): Promise<Card | null> {
  let rows: CardRowRaw[];
  try {
    rows =
      week === undefined
        ? await prisma.$queryRaw<CardRowRaw[]>`
            SELECT payload, built_at FROM cards
            WHERE season = ${season}
            ORDER BY built_at DESC LIMIT 1
          `
        : await prisma.$queryRaw<CardRowRaw[]>`
            SELECT payload, built_at FROM cards
            WHERE season = ${season} AND week = ${week}
            ORDER BY built_at DESC LIMIT 1
          `;
  } catch (e) {
    console.warn("cards unavailable:", (e as Error)?.message ?? e);
    return null;
  }
  const row = rows[0];
  if (!row) return null;
  const card = parseCard(row.payload);
  if (card === null) return null;
  return { ...card, builtAt: card.builtAt ?? asIso(row.built_at) };
}
