// Friendly sportsbook names for the raw Odds API / CFBD book keys stored in
// odds_snapshots. Shared by Line Check and the Movement chart so a key never
// leaks into the UI as "betonlineag".
export const BOOK_LABELS: Record<string, string> = {
  hardrockbet: "Hard Rock",
  hardrockbet_fl: "Hard Rock (FL)",
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
  fliff: "Fliff",
  betus: "BetUS",
  mybookieag: "MyBookie",
  betanysports: "BetAnySports",
  consensus: "Consensus",
};

export const bookLabel = (b: string): string =>
  BOOK_LABELS[b] ?? BOOK_LABELS[b.toLowerCase()] ?? b;
