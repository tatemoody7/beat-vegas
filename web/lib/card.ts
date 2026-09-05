import { american, fmt } from "@/lib/format";
import { kickoffET } from "@/lib/homeBoard";
import { prisma } from "@/lib/prisma";

// The Friday bet card. scripts/build_card.py (GitHub Actions: Fri 6:05pm ET,
// retry 7pm, refresh Sat 11am) writes one row per build to `cards`
// (season, week, built_at, payload JSON). The home board shows the latest row
// for the week. The table is NOT in the Prisma schema and may not exist yet on
// a fresh database — every read degrades to "no card" instead of a 500.
//
// Payload contract (exact, from the Python side):
//   {season, week, built_at, model_read, counts:{bet,edge,pass},
//    items:[{game_id, away, home, kick, tier, blocker, hr_line, hr_price,
//            hr_open, market_line, fair_under, ev, bv_line, gap, kill_line,
//            kill_price, action, why:[...], paper_logged}], notes:[...]}
// Items arrive pre-sorted: BET, then EDGE by ev desc, then PASS.

export type CardTier = "BET" | "EDGE" | "PASS";
export type CardBlocker =
  | "no_hr_line"
  | "off_market"
  | "price"
  | "qb_out"
  | "gap"
  | "no_model";

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
};

export type Card = {
  season: number;
  week: number;
  /** When the card was built, UTC ISO; null when the payload did not say. */
  builtAt: string | null;
  modelRead: boolean;
  counts: { bet: number; edge: number; pass: number };
  items: CardItem[];
  notes: string[];
};

// --- parsing ----------------------------------------------------------------

const TIERS: readonly CardTier[] = ["BET", "EDGE", "PASS"];
const BLOCKERS: readonly CardBlocker[] = [
  "no_hr_line",
  "off_market",
  "price",
  "qb_out",
  "gap",
  "no_model",
];

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
  };
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
    bet: items.filter((i) => i.tier === "BET").length,
    edge: items.filter((i) => i.tier === "EDGE").length,
    pass: items.filter((i) => i.tier === "PASS").length,
  };
  const c = isObj(obj.counts) ? obj.counts : {};
  const counts = {
    bet: int(c.bet) ?? derived.bet,
    edge: int(c.edge) ?? derived.edge,
    pass: int(c.pass) ?? derived.pass,
  };

  return {
    season,
    week,
    builtAt: asIso(obj.built_at),
    modelRead: obj.model_read === true || obj.model_read === 1,
    counts,
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
};

export type CardSummary = {
  /** "No bets this week." / "1 bet this week." / "3 bets this week." */
  headline: string;
  hasBets: boolean;
  /** One row per BET, in card order (never more than MAX_CARD_ROWS). */
  bets: CardRow[];
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

function toRow(item: CardItem): CardRow {
  return {
    gameId: item.gameId,
    tier: item.tier,
    matchup: `${item.away} @ ${item.home}`,
    kick: kickoffET(item.kick),
    line: lineLabel(item),
    action: item.action,
    paperLogged: item.paperLogged,
  };
}

/** Pure: everything the card panel draws, worked out once from the card. */
export function summarizeCard(card: Card): CardSummary {
  const bets = card.items
    .filter((i) => i.tier === "BET")
    .slice(0, MAX_CARD_ROWS)
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
