import { describe, expect, it } from "vitest";
import {
  assignOpeningLine,
  bucketUnderRates,
  DEFAULT_MIN_GAMES,
  type StudyGame,
} from "./lineStudy";

const g = (
  id: number,
  fh: number,
  full: number,
  spread: number | null,
): StudyGame => ({
  id,
  season: 2025,
  home: "A",
  away: "B",
  firstHalfTotal: fh,
  fullGameTotal: full,
  spread,
});

describe("line study (mirrors analysis/line_study.py)", () => {
  it("defaults to 15 games per bucket", () => {
    expect(DEFAULT_MIN_GAMES).toBe(15);
  });

  it("uses the real opening line when captured, else the step-share proxy", () => {
    const tagged = assignOpeningLine(
      [g(1, 20, 50, -3), g(2, 20, 50, -24), g(3, 20, 50, -3)],
      new Map([[3, 26.3]]),
    );
    expect(tagged[0]).toEqual({ fh: 20, line: 25, source: "proxy" }); // 0.4975
    expect(tagged[1]).toEqual({ fh: 20, line: 27, source: "proxy" }); // 0.5375
    expect(tagged[2]).toEqual({ fh: 20, line: 26.5, source: "real_open" });
  });

  it("buckets by line, excludes pushes from the rate, drops thin buckets", () => {
    const rows = [
      ...Array.from({ length: 10 }, () => ({
        fh: 20,
        line: 24.5,
        source: "proxy" as const,
      })),
      ...Array.from({ length: 4 }, () => ({
        fh: 30,
        line: 24.5,
        source: "proxy" as const,
      })),
      { fh: 24.5, line: 24.5, source: "proxy" as const },
      { fh: 1, line: 30, source: "real_open" as const },
    ];
    const out = bucketUnderRates(rows, 15);
    expect(out).toEqual([
      {
        line: 24.5,
        games: 15,
        under: 10,
        push: 1,
        under_pct: 71.4,
        line_source: "proxy",
      },
    ]);
    expect(bucketUnderRates(rows, 16)).toEqual([]);
  });
});
