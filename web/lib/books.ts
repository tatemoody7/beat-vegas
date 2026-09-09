// Friendly sportsbook names for the raw Odds API / CFBD book keys stored in
// odds_snapshots. Shared by Line Check and the Movement chart so a key never
// leaks into the UI as "betonlineag".
export const BOOK_LABELS: Record<string, string> = {
  hardrockbet: "Hard Rock",
  draftkings: "DraftKings",
  fanduel: "FanDuel",
  betmgm: "BetMGM",
  betrivers: "BetRivers",
  bovada: "Bovada",
  betparx: "betPARX",
  ballybet: "Bally Bet",
  betonlineag: "BetOnline",
  lowvig: "LowVig",
  espnbet: "ESPN Bet",
  caesars: "Caesars",
  williamhill_us: "Caesars",
  rebet: "ReBet",
  fanatics: "Fanatics",
  fliff: "Fliff",
  betus: "BetUS",
  mybookieag: "MyBookie",
  betanysports: "BetAnySports",
  consensus: "Consensus",
  kalshi: "Kalshi (exchange)",
  polymarket: "Polymarket (exchange)",
  novig: "Novig (exchange)",
  prophetx: "ProphetX (exchange)",
  betopenly: "BetOpenly (exchange)",
};

// CFTC-regulated exchanges / prediction markets (Odds API region us_ex).
// Legal in Florida, ~zero vig, but no first-half totals — a price-comparison
// source that sharpens the market fair price; never a place we bet.
export const EXCHANGE_KEYS = new Set([
  "kalshi",
  "polymarket",
  "novig",
  "prophetx",
  "betopenly",
]);

export const isExchange = (b: string): boolean =>
  EXCHANGE_KEYS.has(b.toLowerCase());

// CFBD's synthetic cross-book aggregate, stored as a "book" in odds_snapshots.
// It is not a place you can bet and it double-counts the real books, so every
// market read (best / median / fair price) drops it.
export const SYNTHETIC_KEYS = new Set(["consensus"]);
export const isSynthetic = (b: string): boolean =>
  SYNTHETIC_KEYS.has(b.toLowerCase());

// Unknown keys never leak raw: "betonlineag" → "Betonlineag", "some_book" →
// "Some Book". Known keys use the friendly label.
export const titleCase = (key: string): string =>
  key
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((w) => w[0].toUpperCase() + w.slice(1).toLowerCase())
    .join(" ");

export const bookLabel = (b: string): string =>
  BOOK_LABELS[b] ?? BOOK_LABELS[b.toLowerCase()] ?? titleCase(b);
