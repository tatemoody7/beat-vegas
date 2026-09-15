import { describe, expect, it } from "vitest";
import { buildMovement, summarizeMarket, type MoveSnap } from "./movement";

const snap = (o: Partial<MoveSnap>): MoveSnap => ({
  game_id: 1,
  captured_at: "2025-10-08 12:00:00",
  book: "draftkings",
  line: 24.5,
  ...o,
});

describe("summarizeMarket (open -> current per book and by consensus)", () => {
  it("takes each book's first and last capture and the median across books", () => {
    const m = summarizeMarket([
      snap({
        book: "draftkings",
        line: 24,
        captured_at: "2025-10-08 12:00:00",
      }),
      snap({
        book: "hardrockbet",
        line: 25,
        captured_at: "2025-10-08 12:00:00",
      }),
      snap({
        book: "draftkings",
        line: 23.5,
        captured_at: "2025-10-10 12:00:00",
      }),
      snap({
        book: "hardrockbet",
        line: 24.5,
        captured_at: "2025-10-10 12:00:00",
      }),
    ])!;
    expect(m.open).toBe(24.5); // median of 24 and 25
    expect(m.cur).toBe(24); // median of 23.5 and 24.5
    expect(m.books.map((b) => [b.book, b.open, b.cur, b.n])).toEqual([
      ["hardrockbet", 25, 24.5, 2],
      ["draftkings", 24, 23.5, 2],
    ]);
  });

  it("drops the synthetic consensus row and null lines", () => {
    const m = summarizeMarket([
      snap({ book: "Consensus", line: 99 }),
      snap({ book: "draftkings", line: null }),
      snap({
        book: "draftkings",
        line: 24,
        captured_at: "2025-10-09 12:00:00",
      }),
    ])!;
    expect(m.books.map((b) => b.book)).toEqual(["draftkings"]);
    expect(m.cur).toBe(24);
  });

  it("carries the full-game spread open -> current", () => {
    const m = summarizeMarket([
      snap({ line: 52.5, spread: -7, captured_at: "2025-10-08 12:00:00" }),
      snap({ line: 51.5, spread: -9.5, captured_at: "2025-10-10 12:00:00" }),
    ])!;
    expect([m.spreadOpen, m.spreadCur]).toEqual([-7, -9.5]);
  });

  it("is null with nothing usable", () => {
    expect(summarizeMarket([])).toBeNull();
    expect(summarizeMarket([snap({ book: "consensus" })])).toBeNull();
  });
});

describe("buildMovement", () => {
  it("summarizes both markets", () => {
    const m = buildMovement(
      [
        snap({
          book: "draftkings",
          line: 24,
          captured_at: "2025-10-08 12:00:00",
        }),
        snap({
          book: "draftkings",
          line: 23.5,
          captured_at: "2025-10-10 12:00:00",
        }),
      ],
      [snap({ line: 52.5, spread: -7, market: "full_game_total" })],
    );
    expect(m.firstHalf?.books.map((b) => b.book)).toEqual(["draftkings"]);
    expect(m.firstHalf?.open).toBe(24);
    expect(m.firstHalf?.cur).toBe(23.5);
    expect(m.fullGame?.cur).toBe(52.5);
    expect(m.fullGame?.spreadCur).toBe(-7);
  });

  it("reports no first half when only the full game was captured", () => {
    const m = buildMovement([], [snap({ line: 52.5 })]);
    expect(m.firstHalf).toBeNull();
    expect(m.fullGame?.open).toBe(52.5);
  });
});
