// The fixture, typed for the specs. week.mjs / expected.mjs are plain JS so
// seed.mjs can run under `node`; TypeScript infers little from them, so the
// shapes the specs read are declared here once and the modules are cast to
// them. lib/e2eFixture.test.ts is what checks the VALUES against the site's
// own rules; this file only names their types.

import {
  buildWeek as buildWeekJs,
  etParts as etPartsJs,
} from "../fixture/week.mjs";
import {
  buildExpected as buildExpectedJs,
  CRON_JOBS as CRON_JOBS_JS,
} from "../fixture/expected.mjs";

export type HrCapture = {
  capturedAt: Date;
  line: number;
  over: number;
  under: number;
};

export type FixtureGame = {
  id: number;
  away: string;
  home: string;
  kick: Date;
  week: number;
  season: number;
  bv: number;
  underScore: number;
  hr: HrCapture[] | null;
  books: Record<string, [number, number, number]>;
  fg: { total: number; spread: number };
  ref: number;
  played: {
    homePts: number;
    awayPts: number;
    homeFh: number;
    awayFh: number;
  } | null;
  awayTeamId: number;
  homeTeamId: number;
  gamesPlayed: { home: number; away: number };
  scoredAt: Date;
  scenario: string;
};

export type FixtureWeek = {
  now: Date;
  season: number;
  week: number;
  prevWeek: number;
  games: FixtureGame[];
  teams: { id: number; school: string; conference: string }[];
};

export type Edge = {
  score: number;
  tier: "BET" | "EDGE" | "PASS";
  blocker: string | null;
  action: string;
  gap: number | null;
  lineBasis: "hardrock" | "market" | "reference" | null;
  killLine: number;
  killPrice: number | null;
  verdict: "BET" | "WATCH" | "PASS";
  reason: "model_gap" | "price_edge" | "manual";
  hrGap: number | null;
  inBand: boolean;
  priceLine: string;
  input: {
    hrLine: number | null;
    hrUnderPrice: number | null;
    ev: number | null;
    marketLine: number | null;
    fallbackLine: number | null;
    marketFairUnder: number | null;
  };
};

export type LineCheck = {
  hrLine: number | null;
  hrUnderPrice: number | null;
  hrCentred: boolean;
  /** False when the newest Hard Rock quote is an alternate line (expected.mjs::hrPickFor). */
  hrLive: boolean;
  /** Capture instant of the Hard Rock quote shown. */
  hrAsOf: Date | null;
  best: number;
  median: number | null;
  ev: number | null;
  books: string[];
} | null;

export type ExpectedRow = {
  game: FixtureGame;
  check: LineCheck;
  cons: { open: number | null; cur: number | null };
  edge: Edge;
  kickedOff: boolean;
  picked: boolean;
  capRank: number | null;
  overCap: boolean;
  boardRank: number | null;
};

export type ExpectedPick = {
  id: number;
  game: FixtureGame;
  week: number;
  line: number;
  price: number;
  isPaper: boolean;
  verdict: "BET" | "WATCH" | "PASS";
  reason: "model_gap" | "price_edge" | "manual";
  gap: number;
  graded: boolean;
  result?: "under" | "over" | "push";
  units?: number;
  clv?: number;
  blocker: string | null;
  scenario: string;
};

export type Expected = {
  bar: number;
  slate: { bar: number; n: number; share: number; basis: string };
  counts: { bet: number; edge: number; pass: number };
  clearing: number;
  barLine: string;
  rows: ExpectedRow[];
  rankOrder: number[];
  playedIds: number[];
  betIds: number[];
  answer: {
    bets: {
      gameId: number;
      matchup: string;
      numbers: string;
      picked: boolean;
    }[];
    open: number;
    closest: {
      gameId: number;
      matchup: string;
      numbers: string;
      needs: string;
    }[];
    used: number;
    cap: number;
    headline: string;
    slotsLine: string;
  };
  card: {
    slot: string;
    counts: {
      bet: number;
      edge: number;
      pass: number;
      over_cap: number;
      degraded: number;
    };
    slate: { bar: number; n: number };
    items: { game_id: number; tier: string; blocker: string | null }[];
  };
  builtAt: Date;
  picks: ExpectedPick[];
  pickedIds: Set<number>;
  paperLogged: Set<number>;
  ledger: {
    real: { record: string; units: string; n: number };
    paper: { record: string; units: string; n: number; hit: string };
    realBets: number;
    paperPicks: number;
    clvDisplayed: string[];
    avgPointsGained: string;
    pctFavourable: string;
    startUsd: number;
    unitUsd: number;
    bankrollUsd: number;
  };
  lastDispatch: Record<string, Date>;
  health: Record<string, { verdict: "ok"; at: Date; note: string }>;
};

export const buildWeek = buildWeekJs as unknown as (now?: Date) => FixtureWeek;
export const buildExpected = buildExpectedJs as unknown as (
  week: FixtureWeek,
) => Expected;
export const etParts = etPartsJs as unknown as (d: Date) => {
  weekday: string;
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
};
export const CRON_JOBS = CRON_JOBS_JS as unknown as Record<string, unknown>;

/** The week and its expectations, built once per spec file at import time. */
export function fixture(now: Date = new Date()) {
  const week = buildWeek(now);
  const expected = buildExpected(week);
  const thisWeek = week.games.filter((g) => g.week === week.week);
  return {
    week,
    expected,
    thisWeek,
    byId: new Map(week.games.map((g) => [g.id, g])),
    rowById: new Map(expected.rows.map((r) => [r.game.id, r])),
  };
}
