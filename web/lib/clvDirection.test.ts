import { expect, test } from "vitest";
import { displayLineValue } from "@/lib/clvDirection";
import { clvSummary, type DqPickRow } from "@/lib/decision-quality";

// Which sign of clv is GOOD, pinned against real week-2 tickets.
//
// manual_picks.clv is closing - bet. Every bet is an UNDER, and a higher number
// is easier to win, so a line that FALLS after the bet leaves us with the better
// ticket. The reporting layer counted clv > 0 as "moved your way" until
// 2026-09-13 and told Tate 0% of his week-2 bets moved his way when in fact
// three did and none moved against him.

const row = (o: Partial<DqPickRow>): DqPickRow => ({
  result: null,
  line: null,
  model_line_at_pick: null,
  opening_line: null,
  closing_line: null,
  clv: null,
  clv_prob: null,
  factors_json_at_pick: null,
  ...o,
});

// Tate's six real 2026 week-2 tickets, exactly as graded.
const WEEK2: DqPickRow[] = [
  row({ line: 27.5, closing_line: 27.5, clv: 0, result: "over" }), // Miss St @ Minn
  row({ line: 31.5, closing_line: 31.5, clv: 0, result: "under" }), // La Tech @ LSU
  row({ line: 26.5, closing_line: 24.5, clv: -2, result: "over" }), // ODU @ VT
  row({ line: 28.5, closing_line: 28.0, clv: -0.5, result: "over" }), // Tenn @ GT
  row({ line: 26.5, closing_line: 26.5, clv: 0, result: "under" }), // Tulsa @ SHSU
  row({ line: 28.5, closing_line: 27.5, clv: -1, result: "under" }), // TTU @ Ore St
];

test("a line that falls after an under bet counts as moving your way", () => {
  const r = clvSummary(WEEK2);
  expect(r.n).toBe(6);
  // Three moved toward the under (clv < 0); three were flat; none moved against.
  expect(r.pctFavourable).toBeCloseTo(50);
});

test("the displayed number is positive when the market came toward us", () => {
  const r = clvSummary(WEEK2);
  // Raw mean is -0.583 (closing - bet); the page shows the gain, not the raw.
  expect(r.avg).toBeCloseTo(-0.583, 2);
  expect(r.avgPointsGained).toBeCloseTo(0.583, 2);
});

test("a line moving AGAINST an under is not counted as favourable", () => {
  // Bet u24.5, closed 26.5: the closing bettor got the easier number, not us.
  const r = clvSummary([row({ clv: 2, result: "under" })]);
  expect(r.pctFavourable).toBe(0);
  expect(r.avgPointsGained).toBeCloseTo(-2);
});

test("no clv anywhere leaves every field null rather than zero", () => {
  const r = clvSummary([row({}), row({})]);
  expect(r.n).toBe(0);
  expect(r.avg).toBeNull();
  expect(r.pctFavourable).toBeNull();
  expect(r.avgPointsGained).toBeNull();
});

test("the picks table shows a fallen line as a positive line value", () => {
  // TTU @ Ore St: bet under 28.5, closed 27.5 — stored −1, shown +1.00.
  expect(displayLineValue(-1)).toBe(1);
  // Tenn @ GT paper pick: bet 25.5, closed 28.5 — moved against, shown −3.00.
  expect(displayLineValue(3)).toBe(-3);
  expect(displayLineValue(0)).toBe(-0);
  expect(displayLineValue(null)).toBeNull();
});
