import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  HR_RUNG_DISTANCE_PTS,
  HR_RUNG_MIN_BOOKS,
  HR_RUNG_PRICE,
  isCentredQuote,
  isHrRung,
  SKEW_REJECT_PRICE,
} from "@/lib/devig";
import { summarizeMarket, type MoveSnap } from "@/lib/movement";

// Mirrors tests/test_price_skew_filter.py. A book's MAIN total prices both sides
// near -110; a rung of the alternate ladder moves the line several points and
// goes lopsided to compensate. Measured live 2026-09-12 on Tulsa @ Sam Houston,
// 29 minutes before kickoff: eight books at 26.5 around -120/-110, Hard Rock at
// 20.5 (-275/+220), BetMGM at 21.5 (-250/+185).

describe("isCentredQuote", () => {
  it("keeps a normal quote", () => {
    expect(isCentredQuote(-110, -110)).toBe(true);
    expect(isCentredQuote(-150, 125)).toBe(true); // worst centred quote observed
  });

  it("rejects the rungs we actually saw", () => {
    expect(isCentredQuote(-275, 220)).toBe(false); // Hard Rock
    expect(isCentredQuote(-250, 185)).toBe(false); // BetMGM
    expect(isCentredQuote(-375, 260)).toBe(false); // BetMGM, ODU @ Virginia Tech
  });

  it("sits between them", () => {
    expect(isCentredQuote(SKEW_REJECT_PRICE, 130)).toBe(true);
    expect(isCentredQuote(SKEW_REJECT_PRICE - 1, 130)).toBe(false);
  });

  it("keeps a quote it cannot judge", () => {
    expect(isCentredQuote(null, null)).toBe(true);
    expect(isCentredQuote(-110, undefined)).toBe(true);
  });
});

const snap = (
  book: string,
  line: number,
  over: number | null,
  under: number | null,
  t: string,
): MoveSnap => ({
  game_id: 1,
  captured_at: t,
  book,
  line,
  over_price: over,
  under_price: under,
  market: "1H_total",
});

describe("summarizeMarket", () => {
  it("a late rung does not move the market line", () => {
    const m = summarizeMarket([
      snap("draftkings", 26.5, -125, 105, "2026-09-10T12:00:00"),
      snap("fanduel", 26.5, -122, 100, "2026-09-10T12:00:00"),
      snap("hardrockbet", 26.5, -120, -105, "2026-09-10T12:00:00"),
      snap("draftkings", 26.5, -125, 105, "2026-09-12T22:31:00"),
      snap("fanduel", 26.5, -122, 100, "2026-09-12T22:31:00"),
      snap("hardrockbet", 20.5, -275, 220, "2026-09-12T22:31:00"),
    ]);
    expect(m?.open).toBe(26.5);
    expect(m?.cur).toBe(26.5);
  });

  it("a book still contributes its last centred quote", () => {
    const m = summarizeMarket([
      snap("hardrockbet", 27.5, -110, -110, "2026-09-09T12:00:00"),
      snap("hardrockbet", 26.5, -115, -105, "2026-09-11T12:00:00"),
      snap("hardrockbet", 20.5, -275, 220, "2026-09-12T22:31:00"),
    ]);
    expect(m?.open).toBe(27.5);
    expect(m?.cur).toBe(26.5);
  });

  it("a genuine two-point disagreement at normal juice survives", () => {
    const m = summarizeMarket([
      snap("draftkings", 28.5, -110, -110, "2026-09-11T12:00:00"),
      snap("fanduel", 28.5, -110, -110, "2026-09-11T12:00:00"),
      snap("bovada", 26.5, -115, -105, "2026-09-11T12:00:00"),
    ]);
    expect(m?.cur).toBe(28.5);
    expect(m?.books.length).toBe(3);
  });
});

// The same vectors beatvegas/devig.py::is_hr_rung is pinned to
// (tests/test_price_skew_filter.py), so the card and the site cannot drift.
describe("isHrRung (Hard Rock alternate lines, 2026-09-25)", () => {
  it("matches the golden vectors shared with the Python side", () => {
    const v = JSON.parse(
      readFileSync(
        path.resolve(__dirname, "../../tests/fixtures/hr_rung_vectors.json"),
        "utf8",
      ),
    ) as {
      price: number;
      distance: number;
      min_books: number;
      cases: {
        name: string;
        over: number | null;
        under: number | null;
        line: number;
        others: (number | null)[];
        rung: boolean;
      }[];
    };
    expect(v.price).toBe(HR_RUNG_PRICE);
    expect(v.distance).toBe(HR_RUNG_DISTANCE_PTS);
    expect(v.min_books).toBe(HR_RUNG_MIN_BOOKS);
    for (const c of v.cases) {
      expect(isHrRung(c.over, c.under, c.line, c.others), c.name).toBe(c.rung);
    }
  });
});
