import { describe, expect, it } from "vitest";
import { PROXY_TEXT, RULE_TEXT } from "./labels";
import {
  bandTable,
  flagsFrom,
  headline,
  liveNotesFrom,
  type PmBucket,
  type PmRun,
} from "./postmortem";

const b = (o: Partial<PmBucket>): PmBucket => ({
  scope: "hist_2023_25",
  segment: "fbs_only",
  proxy_kind: "step",
  selection: "all",
  dimension: "all",
  bucket: "all",
  bucket_order: 0,
  n: 0,
  unders: 0,
  overs: 0,
  pushes: 0,
  under_pct: null,
  units: 0,
  roi: null,
  ci_lo: null,
  ci_hi: null,
  p_beat: null,
  ...o,
});

const buckets: PmBucket[] = [
  b({
    selection: "cap5",
    n: 166,
    unders: 89,
    overs: 72,
    pushes: 5,
    under_pct: 0.553,
    units: 8.9,
    roi: 0.0536,
    ci_lo: 0.476,
    ci_hi: 0.628,
    p_beat: 0.77,
  }),
  b({
    selection: "cap5",
    proxy_kind: "flat",
    n: 181,
    unders: 114,
    overs: 67,
    under_pct: 0.63,
    units: 36.6,
    roi: 0.202,
  }),
  b({
    dimension: "gap_band",
    bucket: "3+",
    bucket_order: 4,
    n: 304,
    unders: 168,
    overs: 136,
    under_pct: 0.553,
    units: 16.7,
    roi: 0.055,
    ci_lo: 0.496,
    ci_hi: 0.608,
  }),
  b({
    dimension: "gap_band",
    bucket: "<0",
    bucket_order: 0,
    n: 2135,
    unders: 1074,
    overs: 1061,
    under_pct: 0.503,
    units: -84.6,
    roi: -0.04,
    ci_lo: 0.482,
    ci_hi: 0.524,
  }),
  b({
    dimension: "gap_band",
    bucket: "1.75–3",
    bucket_order: 3,
    n: 20,
    unders: 12,
    overs: 8,
    under_pct: 0.6,
    units: 2.9,
    roi: 0.145,
    ci_lo: 0.39,
    ci_hi: 0.78,
  }),
  b({
    scope: "live_2026",
    segment: "live",
    proxy_kind: "hr",
    selection: "bet",
    n: 0,
  }),
  b({
    scope: "live_2026",
    segment: "live",
    proxy_kind: "hr",
    selection: "all_hr",
    n: 13,
    unders: 7,
    overs: 6,
    under_pct: 0.538,
    units: 1.7,
    roi: 0.13,
  }),
];

describe("headline", () => {
  it("returns the record for the requested scope/segment/proxy/selection", () => {
    const rec = headline(buckets, "hist_2023_25", "fbs_only", "step", "cap5");
    expect(rec).toMatchObject({
      n: 166,
      record: "89-72-5P",
      hit: "55.3%",
      units: "+8.90",
    });
    expect(rec?.roi).toBe("+5.4%");
  });

  it("is null when the bucket is missing or has nothing graded", () => {
    expect(headline(buckets, "hist_2023_25", "all", "step", "cap5")).toBeNull();
    expect(headline(buckets, "live_2026", "live", "hr", "bet")).toBeNull();
  });
});

describe("bandTable", () => {
  it("orders by bucket_order and renders the interval text", () => {
    const rows = bandTable(
      buckets,
      "hist_2023_25",
      "fbs_only",
      "step",
      "gap_band",
    );
    expect(rows.map((r) => r.bucket)).toEqual(["<0", "1.75–3", "3+"]);
    expect(rows[2]).toMatchObject({
      n: 304,
      hit: "55.3%",
      ci: "49.6–60.8%",
      units: "+16.70",
      roi: "+5.5%",
    });
  });

  it("marks small buckets so the page can grey them out", () => {
    const rows = bandTable(
      buckets,
      "hist_2023_25",
      "fbs_only",
      "step",
      "gap_band",
    );
    expect(rows.find((r) => r.bucket === "1.75–3")?.size).toBe("small");
    expect(rows.find((r) => r.bucket === "3+")?.size).toBe("full");
  });

  it("is empty for an unknown dimension", () => {
    expect(
      bandTable(buckets, "hist_2023_25", "fbs_only", "step", "nope"),
    ).toEqual([]);
  });
});

describe("flagsFrom / liveNotesFrom", () => {
  const run: PmRun = {
    scope: "hist_2023_25",
    run_id: "pm-x",
    computed_at: "2026-09-07T12:00:00Z",
    n_games: 3601,
    notes: {
      flags: [
        {
          code: "score_gate",
          severity: "change",
          text: "drop the score clause",
          evidence: {},
        },
        {
          code: "multiple_comparisons",
          severity: "ok",
          text: "n tests",
          evidence: {},
        },
      ],
      caveats: ["proxy lines"],
    },
  };

  it("keeps flag order and tolerates missing notes", () => {
    expect(flagsFrom(run).map((f) => f.code)).toEqual([
      "score_gate",
      "multiple_comparisons",
    ]);
    expect(flagsFrom(undefined)).toEqual([]);
    expect(flagsFrom({ ...run, notes: null })).toEqual([]);
  });

  it("reads the live diagnostics with safe defaults", () => {
    const live = liveNotesFrom({
      ...run,
      scope: "live_2026",
      notes: {
        flags: [],
        caveats: [],
        n_bets: 0,
        n_graded: 13,
        derived_line: {
          n: 13,
          mae: 6.1,
          hr_mae: 5.9,
          market_mae: 5.8,
          share: 0.51,
        },
        price_read_counts: { pos: { under: 2, over: 1, push: 0 } },
      },
    });
    expect(live).toMatchObject({
      nBets: 0,
      nGraded: 13,
      derivedMae: 6.1,
      hrMae: 5.9,
      share: 0.51,
    });
    expect(live.priceReads).toEqual([
      { band: "pos", under: 2, over: 1, push: 0 },
    ]);
    expect(liveNotesFrom(undefined)).toMatchObject({
      nBets: 0,
      nGraded: 0,
      priceReads: [],
    });
  });
});

describe("RULE_TEXT / PROXY_TEXT", () => {
  it("names every surviving rule the script emits", () => {
    for (const k of [
      "cap5",
      "gap175",
      "gap300",
      "top20",
      "all",
      "bet",
      "price_read",
      "all_hr",
      "qualifying",
    ]) {
      expect(RULE_TEXT[k]).toBeTruthy();
    }
  });

  it("drops the retired classifier rules and the old flat line", () => {
    expect(RULE_TEXT.score53).toBeUndefined();
    expect(RULE_TEXT.both).toBeUndefined();
    expect(PROXY_TEXT.flat).toBeUndefined();
  });

  it("names every proxy the script emits", () => {
    for (const k of [
      "real",
      "fg",
      "step",
      "hr",
      "hr_close",
      "market",
      "market_close",
    ]) {
      expect(PROXY_TEXT[k]).toBeTruthy();
    }
  });
});
