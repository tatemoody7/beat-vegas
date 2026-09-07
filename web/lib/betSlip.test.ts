import { describe, expect, it } from "vitest";
import { buildBetSlip, loggedLabel } from "./betSlip";
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
  ...o,
});

const card = (items: CardItem[]): Card => ({
  season: 2026,
  week: 3,
  builtAt: "2026-09-19T12:45:00Z",
  modelRead: true,
  slot: "saturday",
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
  it("is empty without a card, but still reports the cap usage", () => {
    const s = buildBetSlip(
      null,
      [{ gameId: 9, away: "A", home: "B", line: 24, price: -110 }],
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
      { gameId: 2, away: "Toledo", home: "Akron", line: 24, price: -115 },
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
