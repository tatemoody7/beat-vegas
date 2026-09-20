import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createPick,
  isDuplicatePick,
  isPaperFirstHalf,
  isRealFirstHalf,
  type PickFull,
} from "./picks";

// createPick writes through raw SQL; capture the tagged template it sends.
const executeRaw = vi.fn();
const queryRaw = vi.fn();
const findUnique = vi.fn();
vi.mock("@/lib/prisma", () => ({
  prisma: {
    games: { findUnique: (...a: unknown[]) => findUnique(...a) },
    $queryRaw: (...a: unknown[]) => queryRaw(...a),
    $executeRaw: (...a: unknown[]) => executeRaw(...a),
  },
}));
import { recordFrom } from "./record";

const pick = (o: Partial<PickFull>): PickFull => ({
  id: 1,
  gameId: 1,
  week: 3,
  away: "A",
  home: "B",
  market: "1H",
  line: 24.5,
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
  isBonus: false,
  verdictAtPick: null,
  reason: null,
  gapAtPick: null,
  evAtPick: null,
  hrLineAtPick: null,
  blocker: null,
  ...o,
});

describe("the real record counts first-half real-money picks only", () => {
  const picks = [
    pick({ id: 1 }), // real 1H win
    pick({ id: 2, market: "full", isPaper: true, units: -1 }), // paper full: out of both
    pick({ id: 3, isPaper: true, units: 0.91 }), // paper 1H
    pick({ id: 4, market: "full", units: 0.91 }), // legacy real full: excluded
  ];
  it("filters", () => {
    expect(picks.filter(isRealFirstHalf).map((p) => p.id)).toEqual([1]);
    expect(picks.filter(isPaperFirstHalf).map((p) => p.id)).toEqual([3]);
  });
  it("records", () => {
    expect(recordFrom(picks.filter(isRealFirstHalf))).toMatchObject({
      record: "1-0",
      units: "+0.91",
      roi: "+91.0%",
    });
    expect(recordFrom(picks.filter(isPaperFirstHalf))).toMatchObject({
      record: "1-0",
      units: "+0.91",
    });
  });
});

// The uq_manual_pick_per_ledger backstop only reaches the user as a 409 if this
// classifier recognises the driver's message. Get it wrong and a double-click
// becomes a bare 500 on the one screen where money is logged -- so pin the
// exact strings Postgres and the SQLite dev/test path actually produce.
describe("a unique-constraint violation is read as a duplicate, not a crash", () => {
  it("recognises Postgres", () => {
    expect(
      isDuplicatePick(
        new Error(
          'duplicate key value violates unique constraint "uq_manual_pick_per_ledger"',
        ),
      ),
    ).toBe(true);
  });

  it("recognises SQLite (local dev and the sim DB)", () => {
    expect(
      isDuplicatePick(
        new Error(
          "UNIQUE constraint failed: index 'uq_manual_pick_per_ledger'",
        ),
      ),
    ).toBe(true);
  });

  it("does not swallow an unrelated failure as a duplicate", () => {
    // These must reach the 503 branch, not be reported as "already logged".
    expect(isDuplicatePick(new Error("connection terminated"))).toBe(false);
    expect(isDuplicatePick(new Error('column "is_bonus" does not exist'))).toBe(
      false,
    );
    expect(isDuplicatePick(undefined)).toBe(false);
  });
});

describe("createPick writes the book and the price's provenance", () => {
  beforeEach(() => {
    executeRaw.mockReset();
    queryRaw.mockReset().mockResolvedValue([]);
    findUnique.mockReset().mockResolvedValue({
      season: 2026,
      week: 3,
      home_team: "H",
      away_team: "A",
    });
  });
  const sent = () => {
    const [strings, ...values] = executeRaw.mock.calls[0] as [
      TemplateStringsArray,
      ...unknown[],
    ];
    return { sql: strings.join("?"), values };
  };

  it("stores a priced ticket as Hard Rock's with provenance 'logged'", async () => {
    await createPick({ gameId: 7, line: 26.5, price: -115 });
    const { sql, values } = sent();
    expect(sql).toMatch(/INSERT INTO manual_picks/);
    expect(sql).toMatch(/\bbook, price_provenance\b/);
    expect(values).toContain("hardrockbet");
    expect(values).toContain("logged");
    expect(values).toContain(-115);
  });

  it("stores a priceless paper pick as NULL with provenance 'unknown' — never -110", async () => {
    await createPick({ gameId: 7, line: 26.5, isPaper: true });
    const { values } = sent();
    expect(values).toContain("unknown");
    expect(values).toContain(null);
    expect(values).not.toContain(-110);
  });
});
