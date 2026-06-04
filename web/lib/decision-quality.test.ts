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
