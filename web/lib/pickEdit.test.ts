import { describe, expect, it } from "vitest";
import { MAX_EDIT_STAKE, parsePickEdit } from "./pickRules";

// Editing exists because entry mistakes are normal: a price typed from memory,
// a bonus bet that staked more than a flat unit. What must NOT be editable is
// anything that identifies the bet, or anything at all once it is graded (the
// route enforces the graded rule; these cover the shape).

describe("parsePickEdit", () => {
  it("takes price, stake, note and the bonus flag together", () => {
    const r = parsePickEdit({
      price: -125,
      stake: 2,
      note: "bonus bet",
      isBonus: true,
    });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.edit).toEqual({
      price: -125,
      stake: 2,
      note: "bonus bet",
      isBonus: true,
    });
  });

  it("applies only the fields that are present", () => {
    const r = parsePickEdit({ price: -105 });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.edit).toEqual({ price: -105 });
    expect("stake" in r.edit).toBe(false);
  });

  it("allows clearing the price and the note to null", () => {
    const r = parsePickEdit({ price: null, note: null });
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.edit.price).toBeNull();
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
