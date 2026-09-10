import { describe, expect, it } from "vitest";
import {
  blockReason,
  buildBetSlip,
  effectiveBlock,
  killBlocks,
  liveLinesFrom,
  loggedLabel,
  MOVED_PTS,
  timeToKick,
  type LiveLine,
} from "./betSlip";
import type { Card, CardItem } from "./card";

const NOW = new Date("2026-09-19T12:50:00Z"); // Sat 8:50am ET

const item = (o: Partial<CardItem> = {}): CardItem => ({
  gameId: 1,
  away: "Kansas",
  home: "Missouri",
  kick: "2026-09-19T19:30:00Z", // Sat 3:30p ET
  tier: "BET",
  blocker: null,
  hrLine: 24.5,
  hrPrice: -110,
  hrOpen: null,
  marketLine: 24.5,
  fairUnder: 0.52,
  ev: -0.004,
  bvLine: 22.4,
  gap: 2.1,
  gapBasis: null,
  killLine: 24.5,
  killPrice: -120,
  action: "Bet now: 1H under 24.5 at -110 on Hard Rock.",
  why: [],
  paperLogged: true,
  qualifies: true,
  paperBlocker: null,
  capRank: 1,
  overCap: false,
  totalBand: "52–60",
  hookSide: "key+0.5",
  hrVsMarket: null,
  fairSource: null,
  reason: null,
  degradedInputs: [],
  gateBlocker: null,
  ...o,
});

const card = (items: CardItem[]): Card => ({
  season: 2026,
  week: 3,
  builtAt: "2026-09-19T12:45:00Z",
  modelRead: true,
  slot: "sat_am",
  status: "final",
  degraded: [],
  counts: {
    bet: items.filter((i) => i.tier === "BET" && !i.overCap).length,
    edge: 0,
    pass: 0,
    overCap: items.filter((i) => i.overCap).length,
    degraded: 0,
  },
  paper: { qualifying: 0, overCap: 0, cap: 5 },
  items,
  notes: [],
});

describe("buildBetSlip", () => {
  it("does not spend a cap slot on a bonus bet", () => {
    // POST /api/picks and build_card.py both exclude bonus bets from the cap
    // (they risk none of the roll). The slip has to agree, or it says a slot
    // is gone when the server would still take the bet.
    const s = buildBetSlip(
      null,
      [
        {
          gameId: 9,
          away: "A",
          home: "B",
          line: 24,
          price: -110,
          isBonus: false,
        },
        {
          gameId: 8,
          away: "C",
          home: "D",
          line: 27,
          price: -105,
          isBonus: true,
        },
      ],
      5,
      NOW,
    );
    expect(s.used).toBe(1);
  });

  it("is empty without a card, but still reports the cap usage", () => {
    const s = buildBetSlip(
      null,
      [
        {
          gameId: 9,
          away: "A",
          home: "B",
          line: 24,
          price: -110,
          isBonus: false,
        },
      ],
      5,
      NOW,
    );
    expect(s.rows).toEqual([]);
    expect(s.used).toBe(1);
    expect(s.cap).toBe(5);
  });

  it("lists BETs by cap rank with line, price, kill numbers and a status per row", () => {
    const c = card([
      item({
        gameId: 3,
        away: "Iowa",
        home: "Nebraska",
        capRank: 6,
        overCap: true,
        blocker: "cap",
        gap: 1.8,
      }),
      item({ gameId: 1 }),
      item({
        gameId: 2,
        away: "Toledo",
        home: "Akron",
        capRank: 2,
        gap: 2.0,
        kick: "2026-09-19T16:00:00Z",
      }),
      item({ gameId: 4, tier: "EDGE", blocker: "price", capRank: null }),
      item({
        gameId: 5,
        away: "LSU",
        home: "Florida",
        capRank: 3,
        gap: 1.9,
        kick: "2026-09-19T12:00:00Z",
      }),
    ]);
    const picks = [
      {
        gameId: 2,
        away: "Toledo",
        home: "Akron",
        line: 24,
        price: -115,
        isBonus: false,
      },
    ];
    const s = buildBetSlip(c, picks, 5, NOW);
    expect(s.rows.map((r) => [r.gameId, r.capRank, r.status])).toEqual([
      [1, 1, "open"],
      [2, 2, "logged"],
      [5, 3, "kicked_off"],
      [3, 6, "over_cap"],
    ]);
    const r = s.rows[0];
    expect(r.matchup).toBe("Kansas @ Missouri");
    expect(r.kick).toBe("Sat 3:30p");
    expect(r.line).toBe("u24.5 -110");
    expect(r.kill).toBe("below u24.5 or worse than -120");
    expect(r.gap).toBe(2.1);
    expect(s.rows[1]).toMatchObject({ loggedLine: 24, loggedPrice: -115 });
    expect(s.used).toBe(1);
    expect(s.builtAt).toBe("2026-09-19T12:45:00Z");
  });

  it("carries a NULL logged price through (pick logged before Hard Rock priced it)", () => {
    const c = card([item({ gameId: 1 })]);
    const s = buildBetSlip(
      c,
      [
        {
          gameId: 1,
          away: "Kansas",
          home: "Missouri",
          line: 24.5,
          price: null,
          isBonus: false,
        },
      ],
      5,
      NOW,
    );
    expect(s.rows[0]).toMatchObject({
      status: "logged",
      loggedLine: 24.5,
      loggedPrice: null,
    });
    expect(loggedLabel(s.rows[0].loggedLine, s.rows[0].loggedPrice)).toBe(
      "logged u24.5",
    );
  });

  it("matches a logged pick by team names when the game id is missing", () => {
    const c = card([item({ gameId: 1 })]);
    const s = buildBetSlip(
      c,
      [
        {
          gameId: null,
          away: "Kansas",
          home: "Missouri",
          line: 24.5,
          price: -110,
          isBonus: false,
        },
      ],
      5,
      NOW,
    );
    expect(s.rows[0].status).toBe("logged");
  });
});

describe("loggedLabel", () => {
  it("shows the line and price, the line alone when unpriced, or just 'logged'", () => {
    expect(loggedLabel(24, -115)).toBe("logged u24 -115");
    expect(loggedLabel(24.5, 100)).toBe("logged u24.5 +100");
    expect(loggedLabel(24.5, null)).toBe("logged u24.5");
    expect(loggedLabel(null, -110)).toBe("logged");
  });
});

// --- 2026-09: live Hard Rock line, kill blocks, kickoff clock ------------------

const live = (entries: [number, LiveLine][] = []): Map<number, LiveLine> =>
  new Map(entries);

describe("liveLinesFrom", () => {
  it("maps each board game's Hard Rock 1H line + under price by game id", () => {
    const m = liveLinesFrom([
      { row: { gameId: 1 }, check: { hrLine: 25, hrUnderPrice: -112 } },
      { row: { gameId: 2 }, check: { hrLine: null, hrUnderPrice: null } },
      { row: { gameId: 3 }, check: null },
    ]);
    expect(m.get(1)).toEqual({ hrLine: 25, hrPrice: -112 });
    expect(m.get(2)).toEqual({ hrLine: null, hrPrice: null });
    expect(m.has(3)).toBe(false);
  });
});

describe("killBlocks", () => {
  it("flags a line below the kill line first, then a worse price", () => {
    expect(killBlocks(24, -110, 24.5, -120)).toBe("kill_line");
    expect(killBlocks(24, -130, 24.5, -120)).toBe("kill_line");
    expect(killBlocks(24.5, -125, 24.5, -120)).toBe("kill_price");
    expect(killBlocks(24.5, -120, 24.5, -120)).toBeNull();
    expect(killBlocks(25, 105, 24.5, -110)).toBeNull();
  });
  it("cannot block on a missing side", () => {
    expect(killBlocks(null, -125, 24.5, -120)).toBe("kill_price");
    expect(killBlocks(24, null, 24.5, -120)).toBe("kill_line");
    expect(killBlocks(null, null, 24.5, -120)).toBeNull();
    expect(killBlocks(20, -150, null, null)).toBeNull();
  });
});

describe("blockReason", () => {
  it("names Hard Rock's live number when the block is live-sourced", () => {
    expect(
      blockReason("kill_line", true, { liveLine: 24, killLine: 24.5 }),
    ).toBe("Hard Rock is now at u24.0, below the kill line of u24.5.");
    expect(
      blockReason("kill_price", true, { livePrice: -125, killPrice: -115 }),
    ).toBe("Hard Rock is now -125, worse than the kill price of -115.");
  });

  it("names the entered value when the block comes from what was typed", () => {
    expect(blockReason("kill_line", false, { line: 24, killLine: 24.5 })).toBe(
      "u24.0 is below the kill line of u24.5 — not the bet we rated.",
    );
    expect(
      blockReason("kill_price", false, { price: -125, killPrice: -115 }),
    ).toBe("-125 is worse than the kill price of -115 — not the bet we rated.");
  });

  it("reads the same for degraded/cap regardless of source", () => {
    expect(blockReason("degraded", true)).toBe(
      "An input is missing, so this is paper only.",
    );
    expect(blockReason("degraded", false)).toBe(
      "An input is missing, so this is paper only.",
    );
    expect(blockReason("cap", false)).toMatch(/already logged this week/);
  });
});

describe("effectiveBlock", () => {
  const row = {
    blockedBy: "kill_line" as const,
    killLine: 24.5,
    killPrice: -120,
    liveLine: 24,
    livePrice: -110,
  };

  it("re-checks a kill block against the ENTERED values, not the stale live snapshot", () => {
    // Live line (24) sits below the kill line (24.5) — row.blockedBy says so —
    // but the user has typed in the kill line itself: not blocked.
    expect(effectiveBlock(row, 24.5, -110)).toEqual({
      block: null,
      isLive: false,
    });
  });

  it("blocks with live wording when the entered values still match the live number", () => {
    expect(effectiveBlock(row, 24, -110)).toEqual({
      block: "kill_line",
      isLive: true,
    });
  });

  it("degraded is a hard block regardless of what's entered", () => {
    const degraded = { ...row, blockedBy: "degraded" as const };
    expect(effectiveBlock(degraded, 30, -110).block).toBe("degraded");
    expect(effectiveBlock(degraded, 24.5, -110).block).toBe("degraded");
  });

  it("cap is a hard block regardless of what's entered", () => {
    const capped = { ...row, blockedBy: "cap" as const };
    expect(effectiveBlock(capped, 30, -110).block).toBe("cap");
  });

  it("blocks on the entered values even without a live-sourced blockedBy", () => {
    const clean = { ...row, blockedBy: null };
    expect(effectiveBlock(clean, 20, -110)).toEqual({
      block: "kill_line",
      isLive: false,
    });
    expect(effectiveBlock(clean, 24.5, -110)).toEqual({
      block: null,
      isLive: false,
    });
  });
});

describe("timeToKick", () => {
  it("counts down in hours and minutes, then minutes, then kicked off", () => {
    expect(timeToKick("2026-09-19T16:00:00Z", NOW)).toBe("kicks in 3h 10m");
    expect(timeToKick("2026-09-19T15:50:00Z", NOW)).toBe("kicks in 3h");
    expect(timeToKick("2026-09-19T13:15:00Z", NOW)).toBe("kicks in 25m");
    expect(timeToKick("2026-09-19T12:50:00Z", NOW)).toBe("kicked off");
    expect(timeToKick("2026-09-19T12:00:00Z", NOW)).toBe("kicked off");
  });
  it("is null without a usable kickoff", () => {
    expect(timeToKick(null, NOW)).toBeNull();
    expect(timeToKick("soon", NOW)).toBeNull();
  });
});

describe("buildBetSlip with live lines", () => {
  const kills = { killLine: 24.5, killPrice: -120 };

  it("shows the live Hard Rock number when the board has one, else the card's", () => {
    const c = card([
      item({ gameId: 1, ...kills }),
      item({ gameId: 2, away: "Toledo", home: "Akron", capRank: 2, ...kills }),
      item({ gameId: 3, away: "LSU", home: "Florida", capRank: 3, ...kills }),
    ]);
    const s = buildBetSlip(
      c,
      [],
      5,
      NOW,
      live([
        [1, { hrLine: 25, hrPrice: -112 }],
        [3, { hrLine: null, hrPrice: null }],
      ]),
    );
    expect(s.rows[0]).toMatchObject({
      hrLine: 24.5,
      hrPrice: -110,
      liveLine: 25,
      livePrice: -112,
      moved: true,
    });
    expect(s.rows[1]).toMatchObject({
      liveLine: 24.5,
      livePrice: -110,
      moved: false,
    });
    expect(s.rows[2]).toMatchObject({
      liveLine: 24.5,
      livePrice: -110,
      moved: false,
    });
    expect(s.cardStatus).toBe("final");
  });

  it("moved is |live − card| ≥ MOVED_PTS on the line only", () => {
    expect(MOVED_PTS).toBe(0.5);
    const c = card([item({ gameId: 1 })]);
    const at = (hrLine: number | null) =>
      buildBetSlip(c, [], 5, NOW, live([[1, { hrLine, hrPrice: -125 }]]))
        .rows[0].moved;
    expect(at(25)).toBe(true);
    expect(at(24)).toBe(true);
    expect(at(24.9)).toBe(false);
    expect(at(null)).toBe(false);
    expect(
      buildBetSlip(
        card([item({ gameId: 1, hrLine: null })]),
        [],
        5,
        NOW,
        live([[1, { hrLine: 25, hrPrice: -110 }]]),
      ).rows[0].moved,
    ).toBe(false);
  });

  it("blockedBy: degraded beats a kill, kill_line beats kill_price, cap last", () => {
    const c = card([
      item({
        gameId: 1,
        ...kills,
        blocker: "degraded",
        degradedInputs: ["injuries"],
      }),
      item({ gameId: 2, away: "T", home: "A", capRank: 2, ...kills }),
      item({ gameId: 3, away: "L", home: "F", capRank: 3, ...kills }),
      item({ gameId: 4, away: "X", home: "Y", capRank: 4, ...kills }),
    ]);
    const l = live([
      [1, { hrLine: 23, hrPrice: -130 }],
      [2, { hrLine: 24, hrPrice: -130 }],
      [3, { hrLine: 24.5, hrPrice: -125 }],
    ]);
    expect(buildBetSlip(c, [], 5, NOW, l).rows.map((r) => r.blockedBy)).toEqual(
      ["degraded", "kill_line", "kill_price", null],
    );
    // Cap: used >= cap blocks every still-open row that nothing else blocks.
    const capped = buildBetSlip(
      c,
      [
        {
          gameId: 91,
          away: "a",
          home: "b",
          line: 24,
          price: -110,
          isBonus: false,
        },
        {
          gameId: 92,
          away: "c",
          home: "d",
          line: 24,
          price: -110,
          isBonus: false,
        },
      ],
      2,
      NOW,
      l,
    );
    expect(capped.rows.map((r) => r.blockedBy)).toEqual([
      "degraded",
      "kill_line",
      "kill_price",
      "cap",
    ]);
    // A per-item degraded input blocks even without the blocker flag.
    expect(
      buildBetSlip(
        card([item({ gameId: 1, degradedInputs: ["odds"] })]),
        [],
        5,
        NOW,
      ).rows[0].blockedBy,
    ).toBe("degraded");
  });

  it("cap does not block rows that are already logged or kicked off", () => {
    const c = card([
      item({ gameId: 1 }),
      item({
        gameId: 2,
        away: "T",
        home: "A",
        capRank: 2,
        kick: "2026-09-19T12:00:00Z",
      }),
    ]);
    const s = buildBetSlip(
      c,
      [
        {
          gameId: 1,
          away: "Kansas",
          home: "Missouri",
          line: 24.5,
          price: -110,
          isBonus: false,
        },
      ],
      1,
      NOW,
    );
    expect(s.rows.map((r) => [r.status, r.blockedBy])).toEqual([
      ["logged", null],
      ["kicked_off", null],
    ]);
  });

  it("carries kicksIn, reason (model_gap fallback), hrVsMarket and fairSource", () => {
    const c = card([
      item({ gameId: 1, kick: "2026-09-19T16:00:00Z" }),
      item({
        gameId: 2,
        away: "T",
        home: "A",
        capRank: 2,
        kick: null,
        reason: "price_edge",
        hrVsMarket: 0.5,
        fairSource: "exchange",
      }),
    ]);
    const s = buildBetSlip(c, [], 5, NOW);
    expect(s.rows[0]).toMatchObject({
      kicksIn: "kicks in 3h 10m",
      kickMinutes: 190,
      reason: "model_gap",
      hrVsMarket: null,
      fairSource: null,
    });
    expect(s.rows[1]).toMatchObject({
      kicksIn: null,
      kickMinutes: null,
      reason: "price_edge",
      hrVsMarket: 0.5,
      fairSource: "exchange",
    });
  });

  it("reports the card status, null without a card", () => {
    expect(buildBetSlip(null, [], 5, NOW).cardStatus).toBeNull();
    const c = { ...card([item()]), status: "degraded" as const };
    expect(buildBetSlip(c, [], 5, NOW).cardStatus).toBe("degraded");
  });
});
