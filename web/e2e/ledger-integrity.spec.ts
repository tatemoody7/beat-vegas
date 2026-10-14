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

/** Mark one game's Hard Rock 1H quotes as SEEN 10 minutes ago (as a close
 *  poll that found the number unchanged would), run `fn`, and put every
 *  last_seen_at back. The fixture's quotes land 72 h and 24 h ago, which the
 *  6-hour live rule (M2) refuses as PRICE STALE. */
async function withHrSeenNow(
  gameId: number,
  fn: () => Promise<void>,
): Promise<void> {
  const saved = await query<{ id: number; last_seen_at: string | null }>(
    `SELECT id, last_seen_at::text AS last_seen_at FROM odds_snapshots
     WHERE game_id = $1 AND LOWER(book) = 'hardrockbet' AND market = '1H_total'`,
    [gameId],
  );
  await query(
    `UPDATE odds_snapshots
     SET last_seen_at = (now() AT TIME ZONE 'utc') - interval '10 minutes'
     WHERE game_id = $1 AND LOWER(book) = 'hardrockbet' AND market = '1H_total'`,
    [gameId],
  );
  try {
    await fn();
  } finally {
    for (const r of saved) {
      await query(
        "UPDATE odds_snapshots SET last_seen_at = $2::timestamp WHERE id = $1",
        [r.id, r.last_seen_at],
      );
    }
  }
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
      await withHrSeenNow(BET_ONE, async () => {
        const res = await request.patch(`/api/picks/${before.id}`, {
          data: { price: -400 },
        });
        expect(res.status()).toBe(409);
        expect((await res.json()).error).toMatch(/worse than the kill price/);
      });
      expect(await pickOn(BET_ONE, false)).toEqual(before);
    } finally {
      await query(
        "UPDATE manual_picks SET bet_at = $2::timestamp WHERE id = $1",
        [before.id, savedBetAt],
      );
    }
  });
});

// Backdated logs (M1B, 2026-10-07): a ticket written more than 30 minutes
// before it is logged is judged as of its bet time -- the card in force then
// must have rated it BET, and Hard Rock's price must have been seen within
// 6 h before the bet. The fixture's card is built 10 min ago and its Hard
// Rock snapshots land 72 h and 24 h ago, so two specs move the card back 30 h
// (and put it back in `finally`).
const BET_TWO = 900002; // BET #2, nothing logged on it

const hoursAgoIso = (h: number) =>
  new Date(Date.now() - h * 3_600_000).toISOString();

async function withCardBuilt30hAgo(fn: () => Promise<void>): Promise<void> {
  const cards = await query<{ id: number; built_at: string }>(
    "SELECT id, built_at::text AS built_at FROM cards",
  );
  await query(
    "UPDATE cards SET built_at = (now() AT TIME ZONE 'utc') - interval '30 hours'",
  );
  try {
    await fn();
  } finally {
    for (const c of cards) {
      await query("UPDATE cards SET built_at = $2::timestamp WHERE id = $1", [
        c.id,
        c.built_at,
      ]);
    }
  }
}

test.describe("backdated logs", () => {
  test("a late log of a game no card in force rated BET is refused", async ({
    request,
  }) => {
    // The only card was built 10 min ago: at a bet time 1 h back, none existed.
    const res = await request.post("/api/picks", {
      data: { gameId: BET_TWO, line: 53.5, price: -110, betAt: hoursAgoIso(1) },
    });
    expect(res.status()).toBe(409);
    expect((await res.json()).error).toMatch(/^NOT A BET THEN/);
    expect(
      await query("SELECT id FROM manual_picks WHERE game_id = $1", [BET_TWO]),
    ).toHaveLength(0);
  });

  test("a late log whose Hard Rock price was over 6 h old at bet time is refused", async ({
    request,
  }) => {
    await withCardBuilt30hAgo(async () => {
      // Card in force: yes (30 h back). Newest Hard Rock quote before a bet
      // 1 h ago: the one captured 24 h ago -- 23 h old at the bet.
      const res = await request.post("/api/picks", {
        data: {
          gameId: BET_TWO,
          line: 53.5,
          price: -110,
          betAt: hoursAgoIso(1),
        },
      });
      expect(res.status()).toBe(409);
      const { error } = await res.json();
      expect(error).toMatch(/^PRICE UNAVAILABLE/);
      expect(error).toMatch(/more than 6 hours old/);
    });
    expect(
      await query("SELECT id FROM manual_picks WHERE game_id = $1", [BET_TWO]),
    ).toHaveLength(0);
  });

  test("a late log checked against the card and a fresh price at bet time is recorded", async ({
    request,
  }) => {
    await withCardBuilt30hAgo(async () => {
      // Bet 23 h ago: the card (30 h) was in force and the 24 h-old quote was
      // 1 h old. It is recorded as the BET it was; then removed again. The
      // request says the Board showed Watch: the reply names the disagreement
      // and the stored verdict stays the server's (B2a, 2026-10-14).
      const res = await request.post("/api/picks", {
        data: {
          gameId: BET_TWO,
          line: 53.5,
          price: -110,
          betAt: hoursAgoIso(23),
          verdict: "WATCH",
        },
      });
      expect(res.status(), await res.text()).toBe(201);
      const body = await res.json();
      expect(body.verdict).toBe("BET");
      expect(body.boardVerdict).toBe("WATCH");
      expect(body.disagreement).toMatch(
        /^Logged\. The Board showed Watch, but the server rated this Bet/,
      );
      const rows = await query<{ id: number; verdict_at_pick: string }>(
        "SELECT id, verdict_at_pick FROM manual_picks WHERE game_id = $1",
        [BET_TWO],
      );
      expect(rows).toHaveLength(1);
      expect(rows[0].verdict_at_pick).toBe("BET");
      const del = await request.delete(`/api/picks/${rows[0].id}`);
      expect(del.status()).toBe(200);
    });
    expect(
      await query("SELECT id FROM manual_picks WHERE game_id = $1", [BET_TWO]),
    ).toHaveLength(0);
  });
});

// Live freshness (M2, 2026-10-07): a live real ticket needs Hard Rock's price
// SEEN in the last 6 h, and "Refresh price" polls one game. The refresh
// specs never reach GitHub: each is refused before the dispatch (the e2e
// server's GITHUB_DISPATCH_TOKEN is a placeholder).
test.describe("live freshness and Refresh price", () => {
  test("a live log on a price last seen 24 h ago is refused as PRICE STALE", async ({
    request,
  }) => {
    const res = await request.post("/api/picks", {
      data: { gameId: BET_TWO, line: 53.5, price: -110 },
    });
    expect(res.status()).toBe(409);
    expect((await res.json()).error).toMatch(/^PRICE STALE/);
    expect(
      await query("SELECT id FROM manual_picks WHERE game_id = $1", [BET_TWO]),
    ).toHaveLength(0);
  });

  test("the log form offers Refresh price on PRICE STALE", async ({ page }) => {
    await page.goto(`/game/${BET_TWO}`);
    await page.getByRole("button", { name: "Log this bet" }).click();
    await page.getByRole("button", { name: /^Log bet/ }).click();
    const form = page.locator("form.bv-card");
    await expect(form.getByRole("alert")).toContainText("PRICE STALE");
    await expect(
      form.getByRole("button", { name: "Refresh price" }),
    ).toBeVisible();
  });

  test("Refresh price refuses a fresh price, a kicked-off game and an unknown one", async ({
    request,
  }) => {
    await withHrSeenNow(BET_TWO, async () => {
      const fresh = await request.post("/api/price-refresh", {
        data: { gameId: BET_TWO },
      });
      expect(fresh.status()).toBe(409);
      expect((await fresh.json()).error).toMatch(/nothing to refresh/);
    });
    const played = await request.post("/api/price-refresh", {
      data: { gameId: 900012 },
    });
    expect(played.status()).toBe(409);
    expect((await played.json()).error).toMatch(/kicked off/);
    const unknown = await request.post("/api/price-refresh", {
      data: { gameId: 123 },
    });
    expect(unknown.status()).toBe(404);
    const junk = await request.post("/api/price-refresh", {
      data: { gameId: "1;drop" },
    });
    expect(junk.status()).toBe(400);
  });

  test("a second Refresh inside the cooldown is refused before any dispatch", async ({
    request,
  }) => {
    const key = `price_refresh_${BET_TWO}`;
    await query(
      `INSERT INTO app_settings (key, value, note, updated_at)
       VALUES ($1, 'e2e', 'requested', (now() AT TIME ZONE 'utc') - interval '2 minutes')
       ON CONFLICT (key) DO UPDATE SET updated_at = EXCLUDED.updated_at`,
      [key],
    );
    try {
      const res = await request.post("/api/price-refresh", {
        data: { gameId: BET_TWO },
      });
      expect(res.status()).toBe(429);
      expect((await res.json()).error).toMatch(/last 10 minutes/);
    } finally {
      await query("DELETE FROM app_settings WHERE key = $1", [key]);
    }
  });
});
