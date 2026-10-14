import { describe, expect, it } from "vitest";
import type { ArmPosition } from "./armPositions";
import {
  HYPOTHESES,
  PROTOCOL,
  cardFor,
  cardsFor,
  llrShare,
  statusOf,
} from "./research";

const meta = HYPOTHESES[0];
const pos = (over: Partial<ArmPosition>): ArmPosition => ({
  hypothesis: "H-ARM-1HU",
  standard: "sprt",
  read_date: "2026-10-19",
  run_id: "1",
  state: "running",
  label: "IN FORWARD TEST",
  logged: 12,
  readings: 9,
  weeks: 1,
  excluded: 3,
  pending: 0,
  needed: 30,
  llr: 0.4,
  mean_ev: -0.012,
  ev_lo: -0.05,
  ev_hi: 0.03,
  next_read: "2026-10-26",
  readAt: new Date("2026-10-19T12:05:00Z"),
  freshness: "current",
  sufficient: false,
  ...over,
});

describe("research cards", () => {
  it("shows every registered hypothesis in slot order, never ranked", () => {
    expect(HYPOTHESES.map((h) => h.id)).toEqual([
      "H-ARM-1HU",
      "H-ARM-1HO",
      "H-ARM-FGU",
      "H-ARM-WX1H",
      "H-ARM-WXFG",
      "H-ARM-HT1H",
      "H-PRICE-HR",
    ]);
    const cards = cardsFor(new Map());
    expect(cards).toHaveLength(7);
    expect(cards.every((c) => c.status === "not yet read")).toBe(true);
  });
  it("hides the EV until ten readings and never before", () => {
    expect(cardFor(meta, pos({ readings: 9 })).ev).toBeNull();
    expect(cardFor(meta, pos({ readings: 10 })).ev).toEqual({
      mean: -0.012,
      lo: -0.05,
      hi: 0.03,
    });
  });
  it("names the status from the protocol state, with collecting before the decision window", () => {
    expect(statusOf(meta, undefined)).toBe("not yet read");
    expect(statusOf(meta, pos({}))).toBe("collecting");
    expect(statusOf(meta, pos({ readings: 30, sufficient: true }))).toBe(
      "reading",
    );
    expect(statusOf(meta, pos({ state: "promote" }))).toBe("promoted");
    expect(statusOf(meta, pos({ state: "stop" }))).toBe("stopped");
    expect(statusOf(meta, pos({ state: "timeout" }))).toBe("timed out");
    const pricing = HYPOTHESES[6];
    expect(
      statusOf(pricing, pos({ standard: "pricing", state: "insufficient" })),
    ).toBe("collecting");
    expect(
      statusOf(pricing, pos({ standard: "pricing", state: "weakening" })),
    ).toBe("weakening");
  });
  it("places the LLR between the two boundaries and caps the progress at 100%", () => {
    expect(llrShare(PROTOCOL.STOP_LLR)).toBe(0);
    expect(llrShare(PROTOCOL.PROMOTE_LLR)).toBe(1);
    expect(llrShare(0)).toBeCloseTo(0.24, 2);
    const c = cardFor(meta, pos({ readings: 45, needed: 30 }));
    expect(c.progressPct).toBe(100);
    expect(cardFor(meta, pos({ readings: 0, llr: 0 })).llrPct).toBeNull(); // nothing read yet
  });
  it("carries the read date, run id, next read and the outdated flag", () => {
    const c = cardFor(
      meta,
      pos({ freshness: "outdated", run_id: "38590000001" }),
    );
    expect(c.outdated).toBe(true);
    expect(c.runId).toBe("38590000001");
    expect(c.nextRead).toBe("2026-10-26");
    expect(c.readAt?.toISOString()).toBe("2026-10-19T12:05:00.000Z");
  });
});
