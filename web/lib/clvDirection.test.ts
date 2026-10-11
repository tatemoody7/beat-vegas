import { expect, test } from "vitest";
import { displayLineValue } from "@/lib/clvDirection";

// Which sign of clv is GOOD, pinned against real week-2 tickets.
//
// manual_picks.clv is closing - bet. Every bet is an UNDER, and a higher number
// is easier to win, so a line that FALLS after the bet leaves us with the better
// ticket. The reporting layer counted clv > 0 as "moved your way" until
// 2026-09-13 and told Tate 0% of his week-2 bets moved his way when in fact
// three did and none moved against him.

// Tate's six real 2026 week-2 tickets, exactly as graded: stored clv per ticket.
const WEEK2_CLV = [
  0, // Miss St @ Minn, u27.5 closed 27.5
  0, // La Tech @ LSU, u31.5 closed 31.5
  -2, // ODU @ VT, u26.5 closed 24.5
  -0.5, // Tenn @ GT, u28.5 closed 28.0
  0, // Tulsa @ SHSU, u26.5 closed 26.5
  -1, // TTU @ Ore St, u28.5 closed 27.5
];

test("a line that falls after an under bet counts as moving your way", () => {
  const shown = WEEK2_CLV.map((c) => displayLineValue(c) as number);
  // Three moved toward the under (stored clv < 0, shown > 0); three were
  // flat; none moved against.
  expect(shown.filter((v) => v > 0)).toHaveLength(3);
  expect(shown.filter((v) => v < 0)).toHaveLength(0);
});

test("the displayed number is positive when the market came toward us", () => {
  const raw = WEEK2_CLV.reduce((a, b) => a + b, 0) / WEEK2_CLV.length;
  const gained =
    WEEK2_CLV.map((c) => displayLineValue(c) as number).reduce(
      (a, b) => a + b,
      0,
    ) / WEEK2_CLV.length;
  // Raw mean is -0.583 (closing - bet); the page shows the gain, not the raw.
  expect(raw).toBeCloseTo(-0.583, 2);
  expect(gained).toBeCloseTo(0.583, 2);
});

test("a line moving AGAINST an under is not counted as favourable", () => {
  // Bet u24.5, closed 26.5: the closing bettor got the easier number, not us.
  expect(displayLineValue(2)).toBe(-2);
});

test("the picks table shows a fallen line as a positive line value", () => {
  // TTU @ Ore St: bet under 28.5, closed 27.5 — stored −1, shown +1.00.
  expect(displayLineValue(-1)).toBe(1);
  // Tenn @ GT paper pick: bet 25.5, closed 28.5 — moved against, shown −3.00.
  expect(displayLineValue(3)).toBe(-3);
  expect(displayLineValue(0)).toBe(-0);
  expect(displayLineValue(null)).toBeNull();
});
