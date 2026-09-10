import { describe, expect, it } from "vitest";
import {
  asIso,
  cardAge,
  cardHealth,
  CARD_STATUS_INPUTS,
  cardStatusDegraded,
  CLOSEST_ROWS,
  killLabel,
  lineLabel,
  MAX_CARD_ROWS,
  parseCard,
  relativeAge,
  summarizeCard,
  type Card,
  type CardItem,
} from "./card";

// --- fixtures ---------------------------------------------------------------

const rawItem = (o: Record<string, unknown> = {}): Record<string, unknown> => ({
  game_id: 401,
  away: "Iowa State",
  home: "Kansas State",
  kick: "2026-09-12T23:30:00Z", // Sat 7:30p ET
  tier: "BET",
  blocker: null,
  hr_line: 24.5,
  hr_price: -110,
  hr_open: 25,
  market_line: 24.5,
  fair_under: -104,
  ev: 0.012,
  bv_line: 22.1,
  gap: 2.4,
  kill_line: 24,
  kill_price: -118,
  action: "Bet the first-half under 24.5 at -110.",
  why: ["gap 2.4 vs Hard Rock", "price at fair"],
  paper_logged: true,
  ...o,
});

const rawCard = (o: Record<string, unknown> = {}): Record<string, unknown> => ({
  season: 2026,
  week: 3,
  built_at: "2026-09-11T22:07:12Z", // Fri 6:07pm ET
  model_read: true,
  counts: { bet: 1, edge: 2, pass: 1, over_cap: 0 },
  items: [
    rawItem(),
    rawItem({
      game_id: 402,
      away: "Kansas",
      home: "Missouri",
      tier: "EDGE",
      blocker: "price",
      hr_price: -118,
      ev: -0.01,
      action: "Wait for -110 or better.",
      paper_logged: false,
    }),
    rawItem({
      game_id: 403,
      away: "Florida",
      home: "LSU",
      tier: "EDGE",
      blocker: "gap",
      ev: 0.004,
      gap: 1.2,
      action: "Wait for 25 or higher.",
      paper_logged: false,
    }),
    rawItem({
      game_id: 404,
      away: "Tulane",
      home: "Memphis",
      tier: "PASS",
      blocker: "no_hr_line",
      hr_line: null,
      hr_price: null,
      ev: null,
      action: "Pass — Hard Rock has no first-half line.",
      paper_logged: false,
    }),
  ],
  notes: ["Hard Rock is holding 6% on first halves this week."],
  ...o,
});

const item = (o: Partial<CardItem> = {}): CardItem => ({
  gameId: 1,
  away: "A",
  home: "B",
  kick: "2026-09-12T23:30:00Z",
  tier: "PASS",
  blocker: null,
  hrLine: 24.5,
  hrPrice: -110,
  hrOpen: null,
  marketLine: null,
  fairUnder: null,
  ev: null,
  bvLine: null,
  gap: null,
  gapBasis: null,
  killLine: null,
  killPrice: null,
  action: "",
  why: [],
  paperLogged: false,
  qualifies: false,
  paperBlocker: null,
  capRank: null,
  overCap: false,
  totalBand: null,
  hookSide: null,
  hrVsMarket: null,
  fairSource: null,
  reason: null,
  degradedInputs: [],
  gateBlocker: null,
  ...o,
});

const card = (o: Partial<Card> = {}): Card => ({
  season: 2026,
  week: 3,
  builtAt: "2026-09-11T22:07:12Z",
  modelRead: true,
  slot: null,
  status: "final",
  degraded: [],
  counts: { bet: 0, edge: 0, pass: 0, overCap: 0, degraded: 0 },
  paper: { qualifying: 0, overCap: 0, cap: 5 },
  items: [],
  notes: [],
  ...o,
});

// --- parseCard --------------------------------------------------------------

describe("parseCard", () => {
  it("parses a full payload from JSON text into camelCase", () => {
    const c = parseCard(JSON.stringify(rawCard()));
    expect(c).not.toBeNull();
    expect(c!.season).toBe(2026);
    expect(c!.week).toBe(3);
    expect(c!.builtAt).toBe("2026-09-11T22:07:12.000Z");
    expect(c!.modelRead).toBe(true);
    expect(c!.counts).toEqual({
      bet: 1,
      edge: 2,
      pass: 1,
      overCap: 0,
      degraded: 0,
    });
    expect(c!.notes).toEqual([
      "Hard Rock is holding 6% on first halves this week.",
    ]);
    expect(c!.items).toHaveLength(4);
    const first = c!.items[0];
    expect(first).toMatchObject({
      gameId: 401,
      away: "Iowa State",
      home: "Kansas State",
      kick: "2026-09-12T23:30:00Z",
      tier: "BET",
      blocker: null,
      hrLine: 24.5,
      hrPrice: -110,
      hrOpen: 25,
      marketLine: 24.5,
      fairUnder: -104,
      ev: 0.012,
      bvLine: 22.1,
      gap: 2.4,
      killLine: 24,
      killPrice: -118,
      action: "Bet the first-half under 24.5 at -110.",
      why: ["gap 2.4 vs Hard Rock", "price at fair"],
      paperLogged: true,
    });
    expect(c!.items[3].hrLine).toBeNull();
    expect(c!.items[3].blocker).toBe("no_hr_line");
  });

  it("accepts an already-parsed object", () => {
    expect(parseCard(rawCard())?.week).toBe(3);
  });

  it("returns null for bad JSON, non-objects and a missing season/week", () => {
    expect(parseCard("{not json")).toBeNull();
    expect(parseCard("")).toBeNull();
    expect(parseCard("[]")).toBeNull();
    expect(parseCard("null")).toBeNull();
    expect(parseCard(null)).toBeNull();
    expect(parseCard(42)).toBeNull();
    expect(parseCard(rawCard({ season: undefined }))).toBeNull();
    expect(parseCard(rawCard({ week: "three" }))).toBeNull();
  });

  it("is null-safe on missing fields and derives counts from the items", () => {
    const c = parseCard({ season: "2026", week: 3 });
    expect(c).toEqual({
      season: 2026,
      week: 3,
      builtAt: null,
      modelRead: false,
      slot: null,
      status: "final",
      degraded: [],
      counts: { bet: 0, edge: 0, pass: 0, overCap: 0, degraded: 0 },
      paper: { qualifying: 0, overCap: 0, cap: 5 },
      items: [],
      notes: [],
    });
    const d = parseCard(rawCard({ counts: "nope", notes: null }));
    expect(d!.counts).toEqual({
      bet: 1,
      edge: 2,
      pass: 1,
      overCap: 0,
      degraded: 0,
    });
    expect(d!.notes).toEqual([]);
    const e = parseCard(rawCard({ counts: { bet: 4 } }));
    expect(e!.counts).toEqual({
      bet: 4,
      edge: 2,
      pass: 1,
      overCap: 0,
      degraded: 0,
    });
  });

  it("drops items with no game id or team and defaults odd fields", () => {
    const c = parseCard(
      rawCard({
        items: [
          rawItem({ game_id: null }),
          rawItem({ away: "" }),
          rawItem({ home: 7 }),
          "junk",
          rawItem({
            game_id: "409",
            tier: "MAYBE",
            blocker: "sweep",
            hr_line: "24.5",
            hr_price: "abc",
            ev: null,
            kick: null,
            action: null,
            why: ["ok", 3, "", null],
            paper_logged: 1,
          }),
        ],
      }),
    );
    expect(c!.items).toHaveLength(1);
    expect(c!.items[0]).toMatchObject({
      gameId: 409,
      tier: "PASS",
      blocker: null,
      hrLine: 24.5,
      hrPrice: null,
      ev: null,
      kick: null,
      action: "",
      why: ["ok"],
      paperLogged: true,
    });
    expect(c!.counts).toEqual({
      bet: 1,
      edge: 2,
      pass: 1,
      overCap: 0,
      degraded: 0,
    }); // payload's own
  });

  it("normalises a naive Postgres timestamp as UTC", () => {
    expect(asIso("2026-09-11 22:07:12.345")).toBe("2026-09-11T22:07:12.345Z");
    expect(asIso("2026-09-11 22:07")).toBe("2026-09-11T22:07:00.000Z");
    expect(asIso(new Date("2026-09-11T22:07:12Z"))).toBe(
      "2026-09-11T22:07:12.000Z",
    );
    expect(asIso("yesterday")).toBeNull();
    expect(asIso(new Date("nope"))).toBeNull();
    expect(asIso(null)).toBeNull();
    expect(parseCard(rawCard({ built_at: "garbage" }))!.builtAt).toBeNull();
  });
});

// --- cardAge ----------------------------------------------------------------

describe("cardAge", () => {
  const built = "2026-09-11T22:07:12Z"; // Fri 6:07pm EDT

  it("formats the ET build time and the age", () => {
    expect(cardAge(built, new Date("2026-09-12T01:10:00Z"))).toBe(
      "built Fri 6:07pm ET · 3h ago",
    );
    expect(cardAge(built, new Date("2026-09-11T22:19:00Z"))).toBe(
      "built Fri 6:07pm ET · 11m ago",
    );
    expect(cardAge(built, new Date("2026-09-11T22:07:30Z"))).toBe(
      "built Fri 6:07pm ET · just now",
    );
    expect(cardAge(built, new Date("2026-09-14T12:00:00Z"))).toBe(
      "built Fri 6:07pm ET · 2d ago",
    );
  });

  it("uses am for a Saturday-morning refresh and handles standard time", () => {
    expect(
      cardAge("2026-09-12T15:02:00Z", new Date("2026-09-12T16:00:00Z")),
    ).toBe("built Sat 11:02am ET · 58m ago");
    // December: EST is UTC-5, so 23:05Z is 6:05pm.
    expect(
      cardAge("2026-12-04T23:05:00Z", new Date("2026-12-05T00:05:00Z")),
    ).toBe("built Fri 6:05pm ET · 1h ago");
  });

  it("accepts a Date and returns null for unknown times", () => {
    expect(
      cardAge(new Date(built), new Date("2026-09-12T01:10:00Z")),
    ).toContain("Fri 6:07pm ET");
    expect(cardAge(null)).toBeNull();
    expect(cardAge("not a time")).toBeNull();
  });

  it("relativeAge never goes negative for a clock skew", () => {
    expect(
      relativeAge(
        new Date("2026-09-11T22:07:12Z"),
        new Date("2026-09-11T22:00:00Z"),
      ),
    ).toBe("just now");
    expect(
      relativeAge(
        new Date("2026-09-10T00:00:00Z"),
        new Date("2026-09-11T23:59:00Z"),
      ),
    ).toBe("47h ago");
    expect(
      relativeAge(
        new Date("2026-09-10T00:00:00Z"),
        new Date("2026-09-12T00:00:00Z"),
      ),
    ).toBe("2d ago");
  });
});

// --- summarizeCard ----------------------------------------------------------

describe("lineLabel", () => {
  it("reads like the board: u24.5 -110", () => {
    expect(lineLabel({ hrLine: 24.5, hrPrice: -110 })).toBe("u24.5 -110");
    expect(lineLabel({ hrLine: 27, hrPrice: 105 })).toBe("u27.0 +105");
    expect(lineLabel({ hrLine: 24.5, hrPrice: null })).toBe("u24.5");
    expect(lineLabel({ hrLine: null, hrPrice: -110 })).toBe(
      "no Hard Rock line",
    );
  });
});

describe("summarizeCard", () => {
  it("with bets: one row per BET in card order, no closest rows, all notes", () => {
    const c = parseCard(rawCard())!;
    const s = summarizeCard(c);
    expect(s.headline).toBe("1 bet this week.");
    expect(s.hasBets).toBe(true);
    expect(s.closest).toEqual([]);
    expect(s.reason).toBeNull();
    expect(s.notes).toEqual(c.notes);
    expect(s.bets).toEqual([
      {
        gameId: 401,
        tier: "BET",
        matchup: "Iowa State @ Kansas State",
        kick: "Sat 7:30p",
        line: "u24.5 -110",
        action: "Bet the first-half under 24.5 at -110.",
        paperLogged: true,
        capRank: null,
        overCap: false,
        paperBlocker: null,
        kill: "below u24.0 or worse than -118",
      },
    ]);
  });

  it("pluralises the headline", () => {
    const s = summarizeCard(
      card({
        items: [
          item({ gameId: 1, tier: "BET" }),
          item({ gameId: 2, tier: "BET" }),
          item({ gameId: 3, tier: "EDGE" }),
        ],
      }),
    );
    expect(s.headline).toBe("2 bets this week.");
    expect(s.bets.map((r) => r.gameId)).toEqual([1, 2]);
  });

  it("no bets: headline, the first note as the reason, top EDGE rows by ev", () => {
    const c = parseCard(
      rawCard({
        items: (rawCard().items as Record<string, unknown>[]).filter(
          (i) => i.tier !== "BET",
        ),
        notes: ["Hard Rock’s hold is too high.", "Two games had no HR line."],
      }),
    )!;
    const s = summarizeCard(c);
    expect(s.headline).toBe("No bets this week.");
    expect(s.hasBets).toBe(false);
    expect(s.bets).toEqual([]);
    expect(s.reason).toBe("Hard Rock’s hold is too high.");
    expect(s.notes).toEqual(["Two games had no HR line."]);
    // EDGE only (the PASS row is left out), best ev first regardless of order.
    expect(s.closest.map((r) => r.gameId)).toEqual([403, 402]);
    expect(s.closest[0]).toMatchObject({
      tier: "EDGE",
      matchup: "Florida @ LSU",
      line: "u24.5 -110",
      action: "Wait for 25 or higher.",
      paperLogged: false,
    });
  });

  it("no bets and no notes: reason is null; unknown ev sorts last", () => {
    const s = summarizeCard(
      card({
        items: [
          item({ gameId: 1, tier: "EDGE", ev: null }),
          item({ gameId: 2, tier: "EDGE", ev: -0.02 }),
          item({ gameId: 3, tier: "EDGE", ev: 0.01 }),
          item({ gameId: 4, tier: "EDGE", ev: 0.03 }),
        ],
      }),
    );
    expect(s.reason).toBeNull();
    expect(s.notes).toEqual([]);
    expect(s.closest).toHaveLength(CLOSEST_ROWS);
    expect(s.closest.map((r) => r.gameId)).toEqual([4, 3, 2]);
  });

  it("caps the bet rows and reads an unknown kickoff / missing line", () => {
    const many = Array.from({ length: 12 }, (_, i) =>
      item({ gameId: i + 1, tier: "BET", kick: null, hrLine: null }),
    );
    const s = summarizeCard(card({ items: many }));
    expect(s.bets).toHaveLength(MAX_CARD_ROWS);
    expect(s.bets[0].kick).toBeNull();
    expect(s.bets[0].line).toBe("no Hard Rock line");
  });
});

// --- paper ledger + weekly cap (2026-09-07) ---------------------------------------

describe("parseCard: paper ledger fields", () => {
  it("reads qualifies / paper_blocker / cap_rank / over_cap / chips and the cap blocker", () => {
    const c = parseCard(
      rawCard({
        paper: { qualifying: 3, over_cap: 1, cap: 5 },
        items: [
          rawItem({
            qualifies: true,
            paper_blocker: null,
            cap_rank: 1,
            over_cap: false,
            total_band: "52–60",
            hook_side: "key+0.5",
          }),
          rawItem({
            game_id: 402,
            blocker: "cap",
            cap_rank: 6,
            over_cap: true,
            qualifies: true,
          }),
          rawItem({
            game_id: 403,
            tier: "EDGE",
            blocker: "price",
            paper_blocker: "price",
            qualifies: true,
          }),
        ],
      }),
    )!;
    expect(c.paper).toEqual({ qualifying: 3, overCap: 1, cap: 5 });
    expect(c.items[0]).toMatchObject({
      qualifies: true,
      paperBlocker: null,
      capRank: 1,
      overCap: false,
      totalBand: "52–60",
      hookSide: "key+0.5",
    });
    expect(c.items[1]).toMatchObject({
      blocker: "cap",
      capRank: 6,
      overCap: true,
      tier: "BET",
    });
    expect(c.items[2]).toMatchObject({
      paperBlocker: "price",
      qualifies: true,
      capRank: null,
    });
  });

  it("reads counts.over_cap, and derives bet (inside the cap) and over_cap from the items when absent", () => {
    const items = [
      rawItem({ cap_rank: 1, over_cap: false }),
      rawItem({ game_id: 402, blocker: "cap", cap_rank: 6, over_cap: true }),
      rawItem({ game_id: 403, tier: "EDGE", blocker: "price" }),
    ];
    const own = parseCard(
      rawCard({ counts: { bet: 1, edge: 1, pass: 0, over_cap: 1 }, items }),
    )!;
    expect(own.counts).toEqual({
      bet: 1,
      edge: 1,
      pass: 0,
      overCap: 1,
      degraded: 0,
    });
    // A payload from before counts.over_cap existed: derive both from the items.
    const derived = parseCard(rawCard({ counts: undefined, items }))!;
    expect(derived.counts).toEqual({
      bet: 1,
      edge: 1,
      pass: 0,
      overCap: 1,
      degraded: 0,
    });
    const partial = parseCard(rawCard({ counts: { bet: 2 }, items }))!;
    expect(partial.counts).toEqual({
      bet: 2,
      edge: 1,
      pass: 0,
      overCap: 1,
      degraded: 0,
    });
  });

  it("derives counts.bet without degraded BETs when the payload lacks counts", () => {
    const items = [
      rawItem({ cap_rank: 1, over_cap: false }),
      rawItem({
        game_id: 402,
        blocker: "degraded",
        degraded_inputs: ["sweep"],
        cap_rank: null,
      }),
      rawItem({ game_id: 403, blocker: "cap", cap_rank: 6, over_cap: true }),
    ];
    const derived = parseCard(rawCard({ counts: undefined, items }))!;
    expect(derived.counts).toEqual({
      bet: 1,
      edge: 0,
      pass: 0,
      overCap: 1,
      degraded: 1,
    });
    // ...and the panel's headline agrees with it.
    expect(summarizeCard(derived).headline).toBe("1 bet this week.");
    expect(summarizeCard(derived).bets.map((r) => r.gameId)).toEqual([401]);
  });

  it("reads fair_source / hr_vs_market and the no_fair_price blocker (PR-6)", () => {
    const c = parseCard(
      rawCard({
        items: [
          rawItem({ fair_source: "exchange", hr_vs_market: 0.5 }),
          rawItem({
            game_id: 402,
            tier: "EDGE",
            blocker: "no_fair_price",
            paper_blocker: "no_fair_price",
            qualifies: true,
            fair_under: null,
            fair_source: null,
            hr_vs_market: null,
            ev: null,
          }),
          rawItem({ game_id: 403, fair_source: "books", hr_vs_market: "-0.5" }),
          rawItem({ game_id: 404, fair_source: "guess", hr_vs_market: "x" }),
        ],
      }),
    )!;
    expect(c.items[0]).toMatchObject({
      fairSource: "exchange",
      hrVsMarket: 0.5,
    });
    expect(c.items[1]).toMatchObject({
      blocker: "no_fair_price",
      paperBlocker: "no_fair_price",
      fairSource: null,
      hrVsMarket: null,
      ev: null,
    });
    expect(c.items[2]).toMatchObject({ fairSource: "books", hrVsMarket: -0.5 });
    // unknown source / garbage number read as null, never leak through
    expect(c.items[3]).toMatchObject({ fairSource: null, hrVsMarket: null });
    // a payload from before the fields existed
    const old = parseCard(rawCard())!;
    expect(old.items[0]).toMatchObject({ fairSource: null, hrVsMarket: null });
  });

  it("derives the paper tallies and defaults when the payload predates them", () => {
    const c = parseCard(rawCard())!; // no paper block, no new item fields
    expect(c.paper).toEqual({ qualifying: 0, overCap: 0, cap: 5 });
    expect(c.items[0]).toMatchObject({
      qualifies: false,
      paperBlocker: null,
      capRank: null,
      overCap: false,
    });
  });
});

describe("killLabel", () => {
  it("reads like the text: below u24 or worse than -118", () => {
    expect(killLabel({ killLine: 24, killPrice: -118 })).toBe(
      "below u24.0 or worse than -118",
    );
    expect(killLabel({ killLine: 24.5, killPrice: null })).toBe("below u24.5");
    expect(killLabel({ killLine: null, killPrice: null })).toBe("");
  });
});

describe("summarizeCard: the weekly cap", () => {
  it("keeps over-cap BETs out of the bet rows and lists them apart, with kill numbers on the bets", () => {
    const c = card({
      items: [
        item({
          gameId: 1,
          tier: "BET",
          capRank: 1,
          gap: 3,
          killLine: 24,
          killPrice: -118,
        }),
        item({ gameId: 2, tier: "BET", capRank: 2, gap: 2 }),
        item({
          gameId: 3,
          tier: "BET",
          capRank: 6,
          gap: 1.8,
          overCap: true,
          blocker: "cap",
          paperLogged: true,
        }),
      ],
    });
    const s = summarizeCard(c);
    expect(s.headline).toBe("2 bets this week.");
    expect(s.bets.map((r) => [r.gameId, r.capRank, r.kill])).toEqual([
      [1, 1, "below u24.0 or worse than -118"],
      [2, 2, ""],
    ]);
    expect(
      s.overCap.map((r) => [r.gameId, r.paperBlocker, r.paperLogged]),
    ).toEqual([[3, "cap", true]]);
    expect(s.degraded).toEqual([]);
  });

  it("keeps degraded BETs out of the bet rows and the headline, listing them apart", () => {
    const c = card({
      items: [
        item({ gameId: 1, tier: "BET", capRank: 1, gap: 3 }),
        item({
          gameId: 2,
          tier: "BET",
          gap: 2.8,
          blocker: "degraded",
          degradedInputs: ["sweep"],
          paperBlocker: "degraded",
          paperLogged: true,
        }),
      ],
    });
    const s = summarizeCard(c);
    expect(s.headline).toBe("1 bet this week.");
    expect(s.bets.map((r) => r.gameId)).toEqual([1]);
    expect(
      s.degraded.map((r) => [r.gameId, r.paperBlocker, r.paperLogged]),
    ).toEqual([[2, "degraded", true]]);
    // Every bet held: no bets this week, and the held rows still show.
    const all = summarizeCard(
      card({
        items: [
          item({ gameId: 2, tier: "BET", blocker: "degraded" }),
          item({ gameId: 3, tier: "EDGE", blocker: "price", ev: 0.01 }),
        ],
      }),
    );
    expect(all.headline).toBe("No bets this week.");
    expect(all.hasBets).toBe(false);
    expect(all.degraded.map((r) => r.gameId)).toEqual([2]);
    expect(all.closest.map((r) => r.gameId)).toEqual([3]);
  });
});

// --- 2026-09 contract: slot / status / degraded / per-item provenance --------

describe("parseCard (2026-09 contract)", () => {
  it("parses slot, status, degraded and the per-item provenance fields", () => {
    const c = parseCard(
      rawCard({
        slot: "sat_am",
        status: "final",
        degraded: [],
        counts: { bet: 1, edge: 2, pass: 1, over_cap: 0, degraded: 0 },
        items: [
          rawItem({
            hr_vs_market: 0.5,
            fair_source: "exchange",
            reason: "model_gap",
            degraded_inputs: [],
          }),
          rawItem({
            game_id: 402,
            tier: "EDGE",
            blocker: "no_fair_price",
            fair_source: "books",
            reason: "price_edge",
          }),
          rawItem({
            game_id: 403,
            tier: "PASS",
            blocker: "degraded",
            degraded_inputs: ["sweep", "pace"],
            gate_blocker: "gap",
          }),
        ],
      }),
    );
    expect(c).not.toBeNull();
    expect(c!.slot).toBe("sat_am");
    expect(c!.status).toBe("final");
    expect(c!.degraded).toEqual([]);
    expect(c!.items[0]).toMatchObject({
      hrVsMarket: 0.5,
      fairSource: "exchange",
      reason: "model_gap",
      degradedInputs: [],
    });
    expect(c!.items[1]).toMatchObject({
      blocker: "no_fair_price",
      fairSource: "books",
      reason: "price_edge",
    });
    expect(c!.items[2]).toMatchObject({
      blocker: "degraded",
      degradedInputs: ["sweep", "pace"],
      gateBlocker: "gap",
    });
    expect(c!.items[0].gateBlocker).toBeNull();
  });

  it("defaults: no slot → null, no status → final, no degraded → []", () => {
    const c = parseCard(rawCard());
    expect(c!.slot).toBeNull();
    expect(c!.status).toBe("final");
    expect(c!.degraded).toEqual([]);
    expect(c!.items[0]).toMatchObject({
      hrVsMarket: null,
      fairSource: null,
      reason: null,
      degradedInputs: [],
      gateBlocker: null,
    });
  });

  it("junk slot/status/fair_source/reason fall back; hr_vs_market must be numeric", () => {
    const c = parseCard(
      rawCard({
        slot: "tuesday",
        status: "wat",
        items: [
          rawItem({
            hr_vs_market: "abc",
            fair_source: "vibes",
            reason: "gut",
            degraded_inputs: ["pace", 3, ""],
          }),
        ],
      }),
    );
    expect(c!.slot).toBeNull();
    expect(c!.status).toBe("final");
    expect(c!.items[0]).toMatchObject({
      hrVsMarket: null,
      fairSource: null,
      reason: null,
      degradedInputs: ["pace"],
    });
    // The legacy slots (weeknight / friday / saturday) are gone: an old row
    // parses to null and the health check treats it like any unknown build.
    expect(parseCard(rawCard({ slot: "friday" }))!.slot).toBeNull();
    expect(parseCard(rawCard({ slot: "weeknight" }))!.slot).toBeNull();
    expect(parseCard(rawCard({ slot: "saturday" }))!.slot).toBeNull();
    // Retired 2026-09-09 along with the daily morning build: a card row
    // written before then must read as a legacy card, not a current one.
    expect(parseCard(rawCard({ slot: "morning" }))!.slot).toBeNull();
    expect(parseCard(rawCard({ slot: "afternoon" }))!.slot).toBeNull();
    expect(parseCard(rawCard({ slot: "fri_pm" }))!.slot).toBe("fri_pm");
    expect(parseCard(rawCard({ slot: "manual" }))!.slot).toBe("manual");
    expect(parseCard(rawCard({ status: "preview" }))!.status).toBe("preview");
  });

  it("a build-wide degraded entry that held a game forces status to degraded and keeps only well-formed entries", () => {
    const c = parseCard(
      rawCard({
        status: "final",
        degraded: [
          { input: "preview", detail: "rotowire_empty", game_ids: [401, "x"] },
          { input: "", detail: "nope" },
          { input: "pace" },
          "junk",
        ],
      }),
    );
    expect(c!.status).toBe("degraded");
    expect(c!.degraded).toEqual([
      { input: "preview", detail: "rotowire_empty", gameIds: [401] },
      { input: "pace", detail: "", gameIds: [] },
    ]);
    // An explicit "degraded" status with an empty list is still honoured.
    expect(parseCard(rawCard({ status: "degraded" }))!.status).toBe("degraded");
  });

  it("a pace-only degraded list does not force the status (owner decision 2026-09-08)", () => {
    // pace is per game and missing on ~5% of games; the game is held, the
    // card's status stays what the builder said.
    const pace = [
      {
        input: "pace",
        detail: "1 model games have no pace read",
        game_ids: [401],
      },
    ];
    const fin = parseCard(rawCard({ status: "final", degraded: pace }));
    expect(fin!.status).toBe("final");
    expect(fin!.degraded).toEqual([
      {
        input: "pace",
        detail: "1 model games have no pace read",
        gameIds: [401],
      },
    ]);
    expect(
      parseCard(rawCard({ status: "preview", degraded: pace }))!.status,
    ).toBe("preview");
    // ...and a sweep truncation that held no card game leaves it alone too.
    const offCard = [
      { input: "sweep", detail: "stopped early (credit_cap)", game_ids: [] },
    ];
    expect(
      parseCard(rawCard({ status: "final", degraded: offCard }))!.status,
    ).toBe("final");
    // A build-wide entry alongside the pace one still flips it.
    expect(
      parseCard(
        rawCard({
          status: "final",
          degraded: [
            ...pace,
            { input: "tempo", detail: "0 rows", game_ids: [401] },
          ],
        }),
      )!.status,
    ).toBe("degraded");
  });

  it("cardStatusDegraded mirrors beatvegas/card.py CARD_STATUS_INPUTS", () => {
    expect(CARD_STATUS_INPUTS).toEqual(["sweep", "preview", "tempo"]);
    expect(cardStatusDegraded([])).toBe(false);
    expect(
      cardStatusDegraded([{ input: "pace", detail: "", gameIds: [1] }]),
    ).toBe(false);
    expect(
      cardStatusDegraded([{ input: "sweep", detail: "", gameIds: [] }]),
    ).toBe(false);
    expect(
      cardStatusDegraded([{ input: "sweep", detail: "", gameIds: [1] }]),
    ).toBe(true);
    expect(
      cardStatusDegraded([{ input: "preview", detail: "", gameIds: [1] }]),
    ).toBe(true);
    expect(
      cardStatusDegraded([{ input: "tempo", detail: "", gameIds: [1] }]),
    ).toBe(true);
  });

  it("counts.bet excludes over-cap BETs when the payload omits counts; overCap/degraded derive too", () => {
    const c = parseCard(
      rawCard({
        counts: undefined,
        items: [
          rawItem({ game_id: 1 }),
          rawItem({ game_id: 2, cap_rank: 6, over_cap: true, blocker: "cap" }),
          rawItem({ game_id: 3, tier: "PASS", blocker: "degraded" }),
        ],
      }),
    );
    expect(c!.counts).toEqual({
      bet: 1,
      edge: 0,
      pass: 1,
      overCap: 1,
      degraded: 1,
    });
    const d = parseCard(
      rawCard({
        counts: { bet: 3, edge: 0, pass: 0, over_cap: 2, degraded: 1 },
      }),
    );
    expect(d!.counts).toEqual({
      bet: 3,
      edge: 0,
      pass: 0,
      overCap: 2,
      degraded: 1,
    });
  });
});

describe("cardHealth", () => {
  // Read AFTER the day's build gate closes: before that, "no card yet today"
  // is just the build not having run yet. Tue/Thu/Fri close at 5:15pm ET,
  // Saturday at 9:15am; Sun/Mon/Wed have no build at all.
  const SAT_10AM = new Date("2026-09-19T14:00:00Z"); // Sat 10:00am ET
  const TUE_6PM = new Date("2026-09-15T22:00:00Z"); // Tue 6:00pm ET

  it("is ok for a card built minutes before it is read", () => {
    const h = cardHealth(
      card({
        slot: "tue_pm",
        status: "final",
        builtAt: "2026-09-15T20:05:00Z",
      }),
      new Date("2026-09-15T20:10:00Z"),
    );
    expect(h.level).toBe("ok");
  });

  it("is ok for today's card read late the same ET day", () => {
    const h = cardHealth(
      card({
        slot: "tue_pm",
        status: "final",
        builtAt: "2026-09-15T20:45:00Z",
      }),
      new Date("2026-09-16T02:30:00Z"), // Tue 10:30pm ET
    );
    expect(h.level).toBe("ok");
  });

  it("warns once a build day's own window has closed with no card", () => {
    const h = cardHealth(
      card({
        slot: "sat_am",
        status: "final",
        builtAt: "2026-09-12T12:10:00Z", // Sat
      }),
      TUE_6PM, // Tuesday, after the 5:15pm close
    );
    expect(h.level).toBe("warn");
    expect(h.title).toBe(
      "This card was built 3d ago. Today's scheduled update has not landed.",
    );
  });

  it("an afternoon card is quiet before 5:15pm ET and warns from 5:15 (EDT)", () => {
    const c = card({
      slot: "sat_am",
      status: "final",
      builtAt: "2026-09-12T12:10:00Z", // Sat 8:10am EDT
    });
    expect(cardHealth(c, new Date("2026-09-15T21:14:00Z")).level).toBe("ok"); // Tue 5:14pm
    expect(cardHealth(c, new Date("2026-09-15T21:15:00Z")).level).toBe("warn"); // Tue 5:15pm
  });

  it("the afternoon gate follows the clock into EST", () => {
    const c = card({
      slot: "sat_am",
      status: "final",
      builtAt: "2026-11-14T13:10:00Z", // Sat 8:10am EST
    });
    expect(cardHealth(c, new Date("2026-11-17T22:14:00Z")).level).toBe("ok"); // Tue 5:14pm EST
    expect(cardHealth(c, new Date("2026-11-17T22:15:00Z")).level).toBe("warn"); // Tue 5:15pm EST
  });

  it("Saturday still warns from 9:15am — the morning the card gets bet", () => {
    const c = card({
      slot: "fri_pm",
      status: "final",
      builtAt: "2026-09-18T20:10:00Z", // Fri 4:10pm EDT
    });
    // Friday evening and Saturday dawn: Friday's card is the current one.
    expect(cardHealth(c, new Date("2026-09-18T23:30:00Z")).level).toBe("ok");
    expect(cardHealth(c, new Date("2026-09-19T13:14:00Z")).level).toBe("ok"); // Sat 9:14am
    const h = cardHealth(c, new Date("2026-09-19T13:15:00Z")); // Sat 9:15am
    expect(h.level).toBe("warn");
    expect(h.title).toBe(
      "This card was built 17h ago. Today's scheduled update has not landed.",
    );
  });

  it("never warns on a day with no scheduled build (Sun, Mon, Wed)", () => {
    const sat = card({
      slot: "sat_am",
      status: "final",
      builtAt: "2026-09-19T12:10:00Z",
    });
    expect(cardHealth(sat, new Date("2026-09-20T16:00:00Z")).level).toBe("ok"); // Sun noon ET
    expect(cardHealth(sat, new Date("2026-09-21T16:00:00Z")).level).toBe("ok"); // Mon noon ET
    // Wednesday is the new one: nothing builds, so Tuesday's card stands all
    // day. A map that forgot Wed would warn from midnight.
    const tue = card({
      slot: "tue_pm",
      status: "final",
      builtAt: "2026-09-15T20:10:00Z",
    });
    expect(cardHealth(tue, new Date("2026-09-16T16:00:00Z")).level).toBe("ok"); // Wed noon ET
    expect(cardHealth(tue, new Date("2026-09-17T03:00:00Z")).level).toBe("ok"); // Wed 11pm ET
  });

  it("warns on a legacy row (no slot/status) once today's window closes", () => {
    const h = cardHealth(card({ builtAt: "2026-09-18T22:00:00Z" }), SAT_10AM);
    expect(h.level).toBe("warn");
    expect(h.title).toBe(
      "This card was built 16h ago. Today's scheduled update has not landed.",
    );
  });

  it("warns on a preview build any day, without naming the slot", () => {
    const h = cardHealth(
      card({
        slot: "sat_am",
        status: "preview",
        builtAt: "2026-09-15T12:07:00Z",
      }),
      TUE_6PM,
    );
    expect(h.level).toBe("warn");
    expect(h.title).toBe(
      "An earlier build. The latest line sweep is not in it yet.",
    );
  });

  it("warns with manual-specific copy for a manual build, even one built today", () => {
    const h = cardHealth(
      card({
        slot: "manual",
        status: "preview",
        builtAt: "2026-09-19T12:07:00Z",
      }),
      SAT_10AM,
    );
    expect(h.level).toBe("warn");
    expect(h.title).toBe(
      "Built by hand Sat 8:07am ET. The scheduled build has not replaced it.",
    );
  });

  it("omits the time when a manual card has no builtAt", () => {
    const h = cardHealth(
      card({ slot: "manual", status: "preview", builtAt: null }),
      SAT_10AM,
    );
    expect(h.title).toBe(
      "Built by hand. The scheduled build has not replaced it.",
    );
  });

  it("warns when a final card has no build time at all", () => {
    const h = cardHealth(
      card({ slot: "sat_am", status: "final", builtAt: null }),
      TUE_6PM,
    );
    expect(h.level).toBe("warn");
    expect(h.title).toBe(
      "This card has no build time. The latest update has not landed.",
    );
  });

  it("names each failed input in words, never the key or the raw detail", () => {
    const h = cardHealth(
      card({
        slot: "fri_pm",
        status: "degraded",
        degraded: [
          { input: "preview", detail: "rotowire_empty", gameIds: [1, 2] },
          {
            input: "sweep",
            detail: "stopped early (credit_cap)",
            gameIds: [1],
          },
        ],
      }),
      SAT_10AM,
    );
    expect(h.level).toBe("warn");
    expect(h.title).toBe("Paper only — some inputs are missing");
    expect(h.details).toEqual([
      "The rules behind these games could not be checked, so nothing here is a real bet today.",
      "the injury and news pull did not finish",
      "the line sweep did not finish",
    ]);
    // No input key, no Python detail string, and never the slot.
    expect(h.title).not.toMatch(/afternoon/);
    expect(h.details.join(" ")).not.toMatch(/rotowire_empty|credit_cap|sweep:/);
  });

  it("does not show the degraded banner for a pace-only morning final", () => {
    // The parser leaves a pace-only card's status at "final"; the held game
    // sits under Held on the panel, not in the banner.
    const c = parseCard(
      rawCard({
        slot: "sat_am",
        status: "final",
        built_at: "2026-09-19T12:45:00Z",
        degraded: [
          {
            input: "pace",
            detail: "1 model games have no pace read",
            game_ids: [401],
          },
        ],
      }),
    );
    expect(c!.status).toBe("final");
    const h = cardHealth(c!, SAT_10AM);
    expect(h.level).toBe("ok");
  });
});

describe("parseCardItem gap_basis", () => {
  it("keeps a known basis and nulls anything else (legacy payloads have no key)", () => {
    const base = rawCard({
      slot: "sat_am",
      status: "final",
      built_at: "2026-09-15T12:05:00Z",
    });
    const item: Record<string, unknown> = {
      game_id: 7,
      away: "A",
      home: "B",
      tier: "EDGE",
    };
    const withBasis = parseCard({
      ...base,
      items: [{ ...item, gap: 2.1, gap_basis: "market" }],
    });
    expect(withBasis!.items[0].gapBasis).toBe("market");
    const legacy = parseCard({ ...base, items: [{ ...item, gap: 2.1 }] });
    expect(legacy!.items[0].gapBasis).toBeNull();
    const junk = parseCard({
      ...base,
      items: [{ ...item, gap: 2.1, gap_basis: "vibes" }],
    });
    expect(junk!.items[0].gapBasis).toBeNull();
  });
});
