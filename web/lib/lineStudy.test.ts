import { describe, expect, it } from "vitest";
import {
  assignOpeningLine,
  bucketUnderRates,
  DEFAULT_MIN_GAMES,
  type StudyGame,
  type TaggedGame,
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

describe("line study across seasons", () => {
  it("buckets the union, so a total under the minimum in every single season still counts", () => {
    // This is why /proof buckets once over every season instead of calling
    // getLineStudy per season and merging the LineBucket[] it returns:
    // ten games at 27.5 in each of two seasons is twenty at 27.5, but
    // neither season alone reaches minGames=15, so a merge would show
    // nothing at all.
    const season = (unders: number, total: number): TaggedGame[] =>
      Array.from({ length: total }, (_, i) => ({
        fh: i < unders ? 20 : 34,
        line: 27.5,
        source: "proxy" as const,
      }));
    const a = season(6, 10);
    const b = season(6, 10);

    expect(bucketUnderRates(a, 15)).toEqual([]);
    expect(bucketUnderRates(b, 15)).toEqual([]);

    const union = bucketUnderRates([...a, ...b], 15);
    expect(union).toHaveLength(1);
    expect(union[0].games).toBe(20);
    expect(union[0].under).toBe(12);
  });
});
