import { expect, test } from "vitest";
import { beatMyModel, type DqPickRow } from "@/lib/decision-quality";

const row = (o: Partial<DqPickRow>): DqPickRow => ({
  result: null, line: null, model_line_at_pick: null, opening_line: null,
  closing_line: null, clv: null, factors_json_at_pick: null, ...o,
});

test("beatMyModel splits on edge sign and computes hit% excluding pushes", () => {
  const picks: DqPickRow[] = [
    // edge = line - model_line. Positive edge = model agreed.
    row({ line: 26, model_line_at_pick: 24, result: "under" }), // +2, win
    row({ line: 26, model_line_at_pick: 24, result: "over" }),  // +2, loss
    row({ line: 25, model_line_at_pick: 25, result: "push" }),  // 0 -> against bucket (edge<=0), push excluded
    row({ line: 23, model_line_at_pick: 25, result: "under" }), // -2, against, win
  ];
  const r = beatMyModel(picks);
  // agreed: edge > 0 => rows 1 & 2 (n=2); 1 under win, 1 over loss, no push.
  expect(r.agreed).toEqual({ n: 2, wins: 1, decided: 2, hitPct: 50 });
  // against: edge <= 0 => row 3 (push, edge==0) + row 4 (-2, under win) = n 2;
  // push excluded from decided, so 1 decided / 1 win.
  expect(r.against).toEqual({ n: 2, wins: 1, decided: 1, hitPct: 100 });
});

import { clvSummary } from "@/lib/decision-quality";

test("clvSummary: avg, positive share, and hit% by clv sign", () => {
  const picks: DqPickRow[] = [
    row({ clv: 1.0, result: "under" }),  // +clv win
    row({ clv: 0.5, result: "over" }),   // +clv loss
    row({ clv: -1.0, result: "under" }), // -clv win
    row({ clv: null, result: "under" }), // ignored for clv stats
  ];
  const r = clvSummary(picks);
  expect(r.n).toBe(3);                       // non-null clv only
  expect(r.avg).toBeCloseTo((1.0 + 0.5 - 1.0) / 3);
  expect(r.pctPositive).toBeCloseTo((100 * 2) / 3);
  expect(r.posClvHitPct).toBe(50);          // 2 decided +clv, 1 win
  expect(r.negClvHitPct).toBe(100);         // 1 decided -clv, 1 win
});

import { timingSummary } from "@/lib/decision-quality";

test("timingSummary: share at/better than open, share beating close", () => {
  // For an UNDER bettor a HIGHER line taken is better.
  const picks: DqPickRow[] = [
    row({ line: 26, opening_line: 25, closing_line: 25.5 }), // >= open, > close
    row({ line: 24, opening_line: 25, closing_line: 24.5 }), // < open, < close
    row({ line: 25, opening_line: 25, closing_line: 25 }),   // == open (counts), == close (not beating)
    row({ line: 27, opening_line: null, closing_line: 26 }), // no open; > close
  ];
  const r = timingSummary(picks);
  expect(r.nOpen).toBe(3);                  // rows with opening_line
  expect(r.pctAtOrBetterThanOpen).toBeCloseTo((100 * 2) / 3); // rows 1 and 3
  expect(r.nClose).toBe(4);
  expect(r.pctBeatingClose).toBeCloseTo((100 * 2) / 4);       // rows 1 and 4
});

import { perFactorAttribution } from "@/lib/decision-quality";

const board = (greens: string[]) =>
  JSON.stringify({
    factor_board: greens.map((key) => ({
      key, label: key, family: "x", tier: 1, direction: 1, hypothesis: false,
      binary: false, value: 1, color: "green", intensity: 0.5, lean: 1,
      sentence: "", live: null,
    })),
  });

test("perFactorAttribution: your hit% per green factor vs ledger rate", () => {
  const picks: DqPickRow[] = [
    row({ result: "under", factors_json_at_pick: board(["pace_estimate"]) }),
    row({ result: "over", factors_json_at_pick: board(["pace_estimate"]) }),
    row({ result: "under", factors_json_at_pick: board(["pace_estimate"]) }),
    row({ result: "push", factors_json_at_pick: board([]) }),
  ];
  const ledger = { pace_estimate: { mean: 0.6, n: 100 } };
  const rows = perFactorAttribution(picks, ledger);
  expect(rows).toHaveLength(1);
  const f = rows[0];
  expect(f.key).toBe("pace_estimate");
  expect(f.n).toBe(3);
  expect(f.decided).toBe(3);          // no pushes among the 3 with this factor green
  expect(f.yourHitPct).toBeCloseTo((100 * 2) / 3);
  expect(f.ledgerHitPct).toBe(60);
  // your 66.7% > ledger 60% => you use it well
  expect(f.weight).toBe("under");
});

test("beatMyModel excludes picks with no model line (null edge)", () => {
  const picks: DqPickRow[] = [
    row({ line: 26, model_line_at_pick: 24, result: "under" }), // +2 agreed, win
    row({ line: 22, model_line_at_pick: 25, result: "under" }), // -3 against, win
    row({ line: 24, model_line_at_pick: null, result: "over" }), // null edge -> EXCLUDED
    row({ line: null, model_line_at_pick: 25, result: "under" }), // null edge -> EXCLUDED
  ];
  const r = beatMyModel(picks);
  expect(r.agreed).toEqual({ n: 1, wins: 1, decided: 1, hitPct: 100 });
  expect(r.against).toEqual({ n: 1, wins: 1, decided: 1, hitPct: 100 });
});
