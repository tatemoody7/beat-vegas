import { describe, expect, it } from "vitest";
import type { BoardRow } from "./board";
import type { EdgeResult, EdgeTier } from "./edge";
import {
  assignCapRanks,
  bankrollCurve,
  dayKey,
  edgeContext,
  kickoffET,
  lineState,
  matchesFilters,
  NO_FILTERS,
  parseFilters,
  sortGames,
  strongestRed,
  tierCounts,
  type HomeGame,
} from "./homeBoard";
import type { PickFull } from "./picks";
import type { BoardFactor } from "./score";

// --- fixtures ---------------------------------------------------------------

const row = (o: Partial<BoardRow> = {}): BoardRow => ({
  gameId: 1,
  week: 3,
  startDate: new Date("2025-10-11T23:30:00Z"),
  away: "Iowa State",
  home: "Kansas State",
  underScore: 55,
  underProb: 0.55,
  rank: 1,
  factors: {},
  openLine: 24,
  curLine: 24.5,
  bvLine: 22,
  bvLo: 16,
  bvHi: 28,
  liveGap: 2.5,
  bvAdjust: null,
  bvAdjustReason: null,
  ...o,
});

const edge = (score: number, tier: EdgeTier): EdgeResult =>
  ({
    score,
    tier,
    blocker: null,
    action: "",
    kill: { line: null, price: null, text: "" },
  }) as unknown as EdgeResult;

const game = (o: Partial<HomeGame> = {}): HomeGame =>
  ({
    row: row(),
    check: null,
    edge: edge(70, "EDGE"),
    movement: null,
    preview: null,
    picked: false,
    kickedOff: false,
    kickoff: "Sat 7:30p",
    day: "sat",
    gap: 2.5,
    gapBasis: "market",
    priceLine: "",
    capRank: null,
    overCap: false,
    ...o,
  }) as HomeGame;

const pick = (o: Partial<PickFull>): PickFull =>
  ({
    id: 1,
    gameId: 1,
    week: 3,
    away: "A",
    home: "B",
    market: "1H",
    line: 24,
    stake: 1,
    price: -110,
    note: null,
    modelScore: null,
    modelLine: null,
    result: "under",
    units: 0.91,
    clv: null,
    graded: true,
    isPaper: false,
    verdictAtPick: null,
    reason: null,
    gapAtPick: null,
    evAtPick: null,
    hrLineAtPick: null,
    blocker: null,
    ...o,
  }) as PickFull;

// --- kickoff ----------------------------------------------------------------

describe("kickoffET", () => {
  it("formats an EDT evening kickoff", () => {
    expect(kickoffET(new Date("2025-10-11T23:30:00Z"))).toBe("Sat 7:30p");
  });

  it("formats an EST afternoon kickoff", () => {
    expect(kickoffET(new Date("2025-11-29T18:00:00Z"))).toBe("Sat 1:00p");
  });

  it("formats a morning kickoff with the a suffix", () => {
    expect(kickoffET(new Date("2025-10-11T16:00:00Z"))).toBe("Sat 12:00p");
    expect(kickoffET(new Date("2025-10-11T15:00:00Z"))).toBe("Sat 11:00a");
  });

  it("is null for an unknown or unparseable kickoff", () => {
    expect(kickoffET(null)).toBeNull();
    expect(kickoffET("not a date")).toBeNull();
  });
});

describe("dayKey", () => {
  it("uses the ET day, not the UTC day", () => {
    // 02:00 UTC Sunday = 10:00 PM Saturday in ET.
    expect(dayKey(new Date("2025-10-12T02:00:00Z"))).toBe("sat");
  });

  it("keys the four game days", () => {
    expect(dayKey(new Date("2025-10-09T23:00:00Z"))).toBe("thu");
    expect(dayKey(new Date("2025-10-10T23:00:00Z"))).toBe("fri");
    expect(dayKey(new Date("2025-10-11T23:00:00Z"))).toBe("sat");
    expect(dayKey(new Date("2025-10-12T20:00:00Z"))).toBe("sun");
  });

  it("calls any other day other, and an unknown kickoff null", () => {
    expect(dayKey(new Date("2025-10-07T23:00:00Z"))).toBe("other");
    expect(dayKey(null)).toBeNull();
  });
});

// --- sorting + counts -------------------------------------------------------

describe("sortGames", () => {
  it("sorts by score desc", () => {
    const games = [
      game({ edge: edge(40, "PASS") }),
      game({ edge: edge(90, "BET") }),
      game({ edge: edge(65, "EDGE") }),
    ];
    expect(sortGames(games).map((g) => g.edge.score)).toEqual([90, 65, 40]);
  });

  it("sinks games that have kicked off below every upcoming game", () => {
    const done = game({ edge: edge(95, "EDGE"), kickedOff: true });
    const live = game({ edge: edge(41, "PASS"), kickedOff: false });
    expect(sortGames([done, live]).map((g) => g.edge.score)).toEqual([41, 95]);
  });

  it("breaks a tie on the earlier kickoff, then the away team", () => {
    const late = game({
      row: row({ gameId: 2, startDate: new Date("2025-10-11T23:30:00Z") }),
    });
    const early = game({
      row: row({ gameId: 3, startDate: new Date("2025-10-11T16:00:00Z") }),
    });
    const unknown = game({ row: row({ gameId: 4, startDate: null }) });
    const sorted = sortGames([unknown, late, early]);
    expect(sorted.map((g) => g.row.gameId)).toEqual([3, 2, 4]);
  });

  it("does not mutate the input", () => {
    const games = [
      game({ edge: edge(10, "PASS") }),
      game({ edge: edge(90, "BET") }),
    ];
    sortGames(games);
    expect(games[0].edge.score).toBe(10);
  });
});

describe("tierCounts", () => {
  it("counts each tier", () => {
    const games = [
      game({ edge: edge(90, "BET") }),
      game({ edge: edge(70, "EDGE") }),
      game({ edge: edge(65, "EDGE") }),
      game({ edge: edge(20, "PASS") }),
    ];
    expect(tierCounts(games)).toEqual({ bet: 1, edge: 2, pass: 1 });
  });

  it("is all zeroes on an empty board", () => {
    expect(tierCounts([])).toEqual({ bet: 0, edge: 0, pass: 0 });
  });
});

// --- context extraction -----------------------------------------------------

describe("edgeContext", () => {
  it("is all nulls when the context job has not run", () => {
    expect(edgeContext({})).toEqual({
      combinedSecPlay: null,
      windMph: null,
      dome: null,
      spread: null,
      fhPrior: null,
    });
  });

  it("reads pace, wind, spread and the first-half prior", () => {
    expect(
      edgeContext({
        combined_sec_play: 27.4,
        wx_wind: 12,
        spread: -6.5,
        home_fh_pf: 13.2,
        away_fh_pf: 10.1,
      }),
    ).toEqual({
      combinedSecPlay: 27.4,
      windMph: 12,
      dome: null,
      spread: -6.5,
      fhPrior: 23.3,
    });
  });

  it("takes dome from the boolean or the 0/1 weather flag", () => {
    expect(edgeContext({ dome: true }).dome).toBe(true);
    expect(edgeContext({ wx_dome: 1 }).dome).toBe(true);
    expect(edgeContext({ wx_dome: 0 }).dome).toBe(false);
  });

  it("needs both halves of the prior, and falls back to the scoring names", () => {
    expect(edgeContext({ home_fh_pf: 13 }).fhPrior).toBeNull();
    expect(edgeContext({ fh_home_pf: 12, fh_away_pf: 11 }).fhPrior).toBe(23);
  });
});

describe("strongestRed", () => {
  const fac = (o: Partial<BoardFactor>): BoardFactor =>
    ({
      key: "k",
      label: "l",
      family: "f",
      tier: 1,
      direction: -1,
      hypothesis: false,
      binary: false,
      value: 0,
      color: "red",
      intensity: 0.5,
      lean: -1,
      sentence: "s",
      live: null,
      ...o,
    }) as BoardFactor;

  it("returns the biggest-lean red sentence", () => {
    expect(
      strongestRed([
        fac({ key: "a", lean: -0.4, sentence: "small red." }),
        fac({ key: "b", lean: -2.1, sentence: "big red." }),
        fac({ key: "c", color: "green", lean: 3, sentence: "green." }),
      ]),
    ).toBe("big red.");
  });

  it("ignores unproven factors and returns null with no reds", () => {
    expect(
      strongestRed([fac({ hypothesis: true, sentence: "unproven red." })]),
    ).toBeNull();
    expect(strongestRed(null)).toBeNull();
    expect(strongestRed([])).toBeNull();
  });
});

// --- filters ----------------------------------------------------------------

describe("matchesFilters", () => {
  it("passes everything with no filters", () => {
    expect(matchesFilters(game(), NO_FILTERS)).toBe(true);
  });

  it("filters by day", () => {
    expect(
      matchesFilters(game({ day: "sat" }), { ...NO_FILTERS, days: ["sat"] }),
    ).toBe(true);
    expect(
      matchesFilters(game({ day: "fri" }), { ...NO_FILTERS, days: ["sat"] }),
    ).toBe(false);
    expect(
      matchesFilters(game({ day: null }), { ...NO_FILTERS, days: ["sat"] }),
    ).toBe(false);
  });

  it("filters to Tate's teams on either side", () => {
    const f = { ...NO_FILTERS, myTeams: true };
    expect(matchesFilters(game(), f)).toBe(true); // Kansas State at home
    expect(
      matchesFilters(game({ row: row({ away: "Missouri", home: "Duke" }) }), f),
    ).toBe(true);
    expect(
      matchesFilters(
        game({ row: row({ away: "Duke", home: "Wake Forest" }) }),
        f,
      ),
    ).toBe(false);
  });

  it("filters to games Hard Rock has posted", () => {
    const f = { ...NO_FILTERS, hrOnly: true };
    expect(matchesFilters(game(), f)).toBe(false);
    expect(
      matchesFilters(game({ check: { hrLine: 24.5 } as HomeGame["check"] }), f),
    ).toBe(true);
  });
});

describe("parseFilters", () => {
  it("reads days, mine and hr out of the URL", () => {
    expect(parseFilters({ days: "sat,sun", mine: "1", hr: "1" })).toEqual({
      days: ["sat", "sun"],
      myTeams: true,
      hrOnly: true,
    });
  });

  it("drops junk days, dedupes, and defaults to no filters", () => {
    expect(parseFilters({ days: "SAT, sat ,mon,nope" }).days).toEqual(["sat"]);
    expect(parseFilters({})).toEqual(NO_FILTERS);
    expect(parseFilters({ mine: "0", hr: "yes" })).toEqual(NO_FILTERS);
  });
});

// --- bankroll curve ---------------------------------------------------------

describe("bankrollCurve", () => {
  it("starts at the starting bankroll and compounds settled units by week", () => {
    const curve = bankrollCurve(
      [
        pick({ id: 1, week: 2, units: 0.91 }),
        pick({ id: 2, week: 2, units: -1 }),
        pick({ id: 3, week: 3, units: 0.91 }),
      ],
      100,
      10,
    );
    expect(curve).toEqual([
      { week: 1, units: 0, usd: 100 },
      { week: 2, units: -0.09, usd: 99.1 },
      { week: 3, units: 0.82, usd: 108.2 },
    ]);
  });

  it("ignores pending, paper and full-game picks", () => {
    const curve = bankrollCurve(
      [
        pick({ id: 1, week: 2, units: 5, graded: false }),
        pick({ id: 2, week: 2, units: 5, isPaper: true }),
        pick({ id: 3, week: 2, units: 5, market: "full" }),
        pick({ id: 4, week: 2, units: 1 }),
      ],
      100,
      10,
    );
    expect(curve[curve.length - 1]).toEqual({ week: 2, units: 1, usd: 110 });
  });

  it("is just the starting point with nothing settled", () => {
    expect(bankrollCurve([], 250, 25)).toEqual([
      { week: 0, units: 0, usd: 250 },
    ]);
  });
});

// --- the weekly cap on the board (2026-09-07) ------------------------------------

describe("assignCapRanks", () => {
  const bet = (gameId: number, gap: number, o: Partial<HomeGame> = {}) =>
    game({
      row: row({ gameId, away: `A${gameId}`, home: `H${gameId}` }),
      edge: edge(70 + gap, "BET"),
      gap,
      ...o,
    });

  it("ranks BETs by gap, marks the 6th+ over the cap, leaves non-BETs null", () => {
    const games = [
      bet(1, 2.0),
      bet(2, 3.1),
      bet(3, 2.5),
      bet(4, 1.9),
      bet(5, 2.2),
      bet(6, 2.1),
      game({ row: row({ gameId: 7 }), edge: edge(64, "EDGE"), gap: 1.4 }),
    ];
    const out = assignCapRanks(games, new Set(), 5);
    const ranks = Object.fromEntries(out.map((g) => [g.row.gameId, g.capRank]));
    expect(ranks).toEqual({ 1: 5, 2: 1, 3: 2, 4: 6, 5: 3, 6: 4, 7: null });
    expect(out.filter((g) => g.overCap).map((g) => g.row.gameId)).toEqual([4]);
    expect(out.map((g) => g.row.gameId)).toEqual([1, 2, 3, 4, 5, 6, 7]); // order kept
  });

  it("a game already bet keeps its slot ahead of a bigger new gap", () => {
    const games = [
      bet(1, 3.0),
      bet(2, 2.9),
      bet(3, 2.8),
      bet(4, 2.7),
      bet(5, 2.6),
      bet(6, 1.8),
    ];
    const out = assignCapRanks(games, new Set([6]), 5);
    const by = Object.fromEntries(out.map((g) => [g.row.gameId, g]));
    expect(by[6].capRank).toBe(1);
    expect(by[6].overCap).toBe(false);
    expect(by[5].capRank).toBe(6);
    expect(by[5].overCap).toBe(true);
  });

  it("kicked-off games are out of the ranking", () => {
    const out = assignCapRanks(
      [bet(1, 3.0, { kickedOff: true }), bet(2, 2.0)],
      new Set(),
      5,
    );
    expect(out.map((g) => g.capRank)).toEqual([null, 1]);
  });
});

// --- lineState ----------------------------------------------------------------

describe("lineState", () => {
  it("has a model whenever the row carries a score and our number, whatever line it was scored on", () => {
    const r = row({ factors: { line_kind: "derived_fg" }, curLine: 24.5 });
    expect(lineState(r, null)).toEqual({ hasModel: true, derived: false });
  });

  it("is derived only when neither Hard Rock nor the market has posted a first-half line", () => {
    const r = row({ curLine: null });
    expect(lineState(r, null).derived).toBe(true);
    expect(lineState(r, { hrLine: 24.5 }).derived).toBe(false);
    expect(lineState(row({ curLine: 24 }), null).derived).toBe(false);
  });

  it("has no model without a score or our number", () => {
    expect(lineState(row({ underScore: null }), null).hasModel).toBe(false);
    expect(lineState(row({ bvLine: null }), null).hasModel).toBe(false);
  });
});
