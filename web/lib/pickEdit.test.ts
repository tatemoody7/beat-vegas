import { describe, expect, it } from "vitest";
import { MAX_EDIT_STAKE, parsePickEdit } from "./pickRules";

// Editing exists because entry mistakes are normal: a price typed from memory,
// a bonus bet that staked more than a flat unit. What must NOT be editable is
// anything that identifies the bet, the bonus flag, a paper pick, or anything
// at all from kickoff (the route enforces paper and kickoff and re-judges a
// changed price; these cover the shape).

describe("parsePickEdit", () => {
  it("takes price, stake and note together", () => {
    const r = parsePickEdit({ price: -125, stake: 2, note: "bonus bet" });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.edit).toEqual({ price: -125, stake: 2, note: "bonus bet" });
  });

  it("refuses the bonus flag: it is set when the ticket is logged", () => {
    // 2026-10-07: flipping it later freed a cap slot and booked a loss as 0.
    for (const isBonus of [true, false]) {
      const r = parsePickEdit({ isBonus });
      expect(r.ok).toBe(false);
      if (!r.ok) expect(r.status).toBe(409);
    }
    expect(parsePickEdit({ price: -110, isBonus: true }).ok).toBe(false);
  });

  it("applies only the fields that are present", () => {
    const r = parsePickEdit({ price: -105 });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.edit).toEqual({ price: -105 });
    expect("stake" in r.edit).toBe(false);
  });

  it("an OMITTED price keeps the stored one; an explicit null is refused", () => {
    // Omitted: the edit does not carry a price at all, so the row keeps its own.
    const kept = parsePickEdit({ stake: 2 });
    expect(kept.ok).toBe(true);
    if (kept.ok) expect("price" in kept.edit).toBe(false);
    // Explicit null (or a blank field): a real ticket never loses its price.
    for (const price of [null, ""]) {
      const r = parsePickEdit({ price });
      expect(r.ok).toBe(false);
      if (!r.ok) expect(r.error).toMatch(/^PRICE MISSING/);
    }
  });

  it("allows clearing the note to null", () => {
    const r = parsePickEdit({ note: null });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.edit.note).toBeNull();
  });

  it("rejects a price that is not American odds", () => {
    // -1.25 or 2.5 is someone typing decimal odds into an American field; the
    // ledger's whole payout maths would be wrong and nothing would complain.
    for (const price of [50, -99, 2.5, 0]) {
      expect(parsePickEdit({ price }).ok).toBe(false);
    }
    for (const price of [-125, 100, -110, 250]) {
      expect(parsePickEdit({ price }).ok).toBe(true);
    }
  });

  it("rejects a stake that is zero, negative or a fat-finger", () => {
    for (const stake of [0, -1, MAX_EDIT_STAKE + 1, "abc"]) {
      expect(parsePickEdit({ stake }).ok).toBe(false);
    }
    expect(parsePickEdit({ stake: MAX_EDIT_STAKE }).ok).toBe(true);
    expect(parsePickEdit({ stake: 2 }).ok).toBe(true);
  });

  it("rejects a non-boolean bonus flag and a non-text note", () => {
    expect(parsePickEdit({ isBonus: "yes" }).ok).toBe(false);
    expect(parsePickEdit({ note: 5 }).ok).toBe(false);
  });

  it("rejects an empty edit rather than silently touching the row", () => {
    expect(parsePickEdit({}).ok).toBe(false);
    expect(parsePickEdit(null).ok).toBe(false);
  });

  it("ignores fields that identify the bet", () => {
    // line/market/gameId are deliberately not editable: they are what the bet
    // WAS. Sending them changes nothing rather than erroring, so a stale client
    // cannot quietly rewrite history.
    const r = parsePickEdit({
      price: -120,
      line: 99,
      market: "full",
      gameId: 7,
    });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.edit).toEqual({ price: -120 });
  });
});
