import { expect, test } from "@playwright/test";
import { query } from "./helpers/db";

// The ledger's write rules (2026-10-07, M1A), exercised against the fixture
// database through the real routes. Every check here is a REFUSAL and then a
// read-back that the row did not change, so the suite's other specs (which
// count the seeded ledger) see the same rows whichever project runs first.
// The one spec that has to move a row (the price re-check) puts it back in
// `finally`.
//
//   - paper is build-only: POST refuses isPaper; PATCH/DELETE refuse a paper row
//   - a real ticket keeps its price (explicit null refused) and its bonus flag
//   - a changed price is re-judged by the same evaluator a new ticket goes
//     through (web/lib/ticketPolicy.ts)

const BET_ONE = 900001; // BET #1: a real, pending ticket on it (fixture pick 3)
const PRICE_BLOCKED = 900003; // a pending build paper pick (blocker price)

type Row = {
  id: number;
  price: number | null;
  stake: number;
  is_bonus: boolean | null;
  note: string | null;
};

async function pickOn(gameId: number, isPaper: boolean): Promise<Row> {
  const rows = await query<Row>(
    `SELECT id, price, stake, is_bonus, note FROM manual_picks
     WHERE game_id = $1 AND COALESCE(is_paper, false) = $2`,
    [gameId, isPaper],
  );
  expect(
    rows,
    `one ${isPaper ? "paper" : "real"} pick on ${gameId}`,
  ).toHaveLength(1);
  return rows[0];
}

test.describe("the ledger's write rules", () => {
  test("a hand-logged paper pick is refused: paper is the build's", async ({
    request,
  }) => {
    const res = await request.post("/api/picks", {
      data: { gameId: 900002, line: 53.5, price: -110, isPaper: true },
    });
    expect(res.status()).toBe(400);
    expect((await res.json()).error).toMatch(/^PAPER IS BUILD-ONLY/);
    const rows = await query(
      "SELECT id FROM manual_picks WHERE game_id = 900002",
    );
    expect(rows).toHaveLength(0);
  });

  test("a build paper pick cannot be edited or deleted", async ({
    request,
  }) => {
    const before = await pickOn(PRICE_BLOCKED, true);
    const patch = await request.patch(`/api/picks/${before.id}`, {
      data: { price: -110, stake: 3 },
    });
    expect(patch.status()).toBe(409);
    expect((await patch.json()).error).toMatch(/^PAPER IS FROZEN/);
    const del = await request.delete(`/api/picks/${before.id}`);
    expect(del.status()).toBe(409);
    expect((await del.json()).error).toMatch(/^PAPER IS FROZEN/);
    expect(await pickOn(PRICE_BLOCKED, true)).toEqual(before);
  });

  test("a real ticket keeps its price and its bonus flag", async ({
    request,
  }) => {
    const before = await pickOn(BET_ONE, false);
    const cleared = await request.patch(`/api/picks/${before.id}`, {
      data: { price: null },
    });
    expect(cleared.status()).toBe(400);
    expect((await cleared.json()).error).toMatch(/^PRICE MISSING/);
    const bonus = await request.patch(`/api/picks/${before.id}`, {
      data: { isBonus: true },
    });
    expect(bonus.status()).toBe(409);
    expect((await bonus.json()).error).toMatch(/bonus flag/);
    expect(await pickOn(BET_ONE, false)).toEqual(before);
  });

  test("a changed price is re-judged against the kill price", async ({
    request,
  }) => {
    // Make the ticket one written just now, so it is judged by the LIVE read
    // (the fixture writes it 20 h back, before the card existed -- the
    // backdated path is M1B's), then try to edit it to a price no fair under
    // clears. Put bet_at back whatever happens.
    const before = await pickOn(BET_ONE, false);
    const [{ bet_at: savedBetAt }] = await query<{ bet_at: string | null }>(
      "SELECT bet_at::text AS bet_at FROM manual_picks WHERE id = $1",
      [before.id],
    );
    await query(
      `UPDATE manual_picks
       SET bet_at = (now() AT TIME ZONE 'utc') - interval '5 minutes'
       WHERE id = $1`,
      [before.id],
    );
    try {
      const res = await request.patch(`/api/picks/${before.id}`, {
        data: { price: -400 },
      });
      expect(res.status()).toBe(409);
      expect((await res.json()).error).toMatch(/worse than the kill price/);
      expect(await pickOn(BET_ONE, false)).toEqual(before);
    } finally {
      await query(
        "UPDATE manual_picks SET bet_at = $2::timestamp WHERE id = $1",
        [before.id, savedBetAt],
      );
    }
  });
});
