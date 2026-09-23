// Seed the e2e database with the fixture week: TRUNCATE the tables the app
// reads, then INSERT the synthetic season laid out RELATIVE TO NOW by
// week.mjs, with the card, ledger and post-mortem rows expected.mjs derives.
//
//   DATABASE_URL=postgresql://postgres@127.0.0.1:54329/beatvegas_e2e node e2e/fixture/seed.mjs
//
// Plain Node + `pg` (already a dependency), so the CI job needs no Python and
// no Prisma client. Every timestamp is written as NAIVE UTC text
// ("YYYY-MM-DD HH:MM:SS"), the convention of every timestamp column in
// beatvegas/db/models.py; the app appends the Z itself.
//
// It REFUSES any URL that names Neon. There is no flag to override that: the
// seed truncates fifteen tables, and the one time a dev tool pointed at
// production by accident cost a month of egress (2026-09-16). Point it at the
// pgserver sandbox (scripts/e2e-db.sh) or a CI service container only.

import pg from "pg";
import { pathToFileURL } from "node:url";
import { buildWeek, HR } from "./week.mjs";
import { buildExpected, lineUsedFor, round2 } from "./expected.mjs";

export const DEFAULT_URL =
  "postgresql://postgres@127.0.0.1:54329/beatvegas_e2e";

/** The tables the seed owns: truncated together, then filled. */
export const TABLES = [
  "manual_picks",
  "challenger_picks",
  "results",
  "game_records",
  "game_previews",
  "predictions",
  "odds_snapshots",
  "cards",
  "postmortem_buckets",
  "postmortem_runs",
  "model_runs",
  "factor_ledger",
  "bv_adjustments",
  "app_settings",
  "games",
  "teams",
];

/** Naive UTC text for a timestamp column. */
export const ts = (d) => d.toISOString().slice(0, 19).replace("T", " ");

export function refuseNeon(url) {
  if (/neon\.tech/i.test(url)) {
    throw new Error(
      "seed.mjs refuses to touch a neon.tech database: this seed TRUNCATES tables. Use the local sandbox (npm run e2e:db).",
    );
  }
}

async function insert(client, table, rows) {
  if (rows.length === 0) return 0;
  const cols = [...new Set(rows.flatMap((r) => Object.keys(r)))];
  const values = [];
  const tuples = rows.map((r) => {
    const slots = cols.map((c) => {
      values.push(r[c] === undefined ? null : r[c]);
      return `$${values.length}`;
    });
    return `(${slots.join(", ")})`;
  });
  await client.query(
    `INSERT INTO ${table} (${cols.join(", ")}) VALUES ${tuples.join(", ")}`,
    values,
  );
  return rows.length;
}

// --- the rows -----------------------------------------------------------------

function factorBoard(g) {
  const pace = 26.5 + (g.id % 5) * 0.7;
  const wind = 4 + (g.id % 4) * 4;
  return [
    {
      key: "combined_sec_play",
      label: "Combined pace",
      family: "pace",
      tier: 1,
      direction: 1,
      hypothesis: false,
      binary: false,
      value: round2(pace),
      color: pace >= 28 ? "green" : "neutral",
      intensity: pace >= 28 ? 0.7 : 0.1,
      lean: pace >= 28 ? 0.9 : 0.0,
      sentence:
        pace >= 28
          ? `Both offenses play slowly (${pace.toFixed(1)} seconds a play) — helps the under.`
          : `Average pace (${pace.toFixed(1)} seconds a play).`,
      live: null,
    },
    {
      key: "wx_wind",
      label: "Wind",
      family: "weather",
      tier: 2,
      direction: 1,
      hypothesis: false,
      binary: false,
      value: wind,
      color: wind >= 12 ? "green" : "neutral",
      intensity: wind >= 12 ? 0.5 : 0.1,
      lean: wind >= 12 ? 0.4 : 0.0,
      sentence: `${wind} mph wind at kickoff${wind >= 12 ? " — helps the under." : "."}`,
      live: null,
    },
    {
      key: "spread_abs",
      label: "Spread",
      family: "market",
      tier: 2,
      direction: -1,
      hypothesis: false,
      binary: false,
      value: Math.abs(g.fg.spread),
      color: Math.abs(g.fg.spread) >= 14 ? "red" : "neutral",
      intensity: Math.abs(g.fg.spread) >= 14 ? 0.6 : 0.1,
      lean: Math.abs(g.fg.spread) >= 14 ? -0.7 : 0.0,
      sentence:
        Math.abs(g.fg.spread) >= 14
          ? `A ${Math.abs(g.fg.spread)}-point favourite — blowouts score early, works against the under.`
          : `A ${Math.abs(g.fg.spread)}-point spread.`,
      live: null,
    },
  ];
}

function modelFactors(g) {
  const lineUsed = lineUsedFor(g);
  const fhShare = round2(g.ref / g.fg.total);
  const pf = (seed) => [10 + (seed % 7), 14 + (seed % 5), 7 + (seed % 9)];
  return {
    line: lineUsed,
    bv_line: g.bv,
    bv_gap: round2(lineUsed - g.bv),
    bv_lo: round2(g.bv - 6.2),
    bv_hi: round2(g.bv + 6.2),
    bv_sigma: 11.26,
    rank_basis: "bv_gap",
    fh_share: fhShare,
    full_game_total: g.fg.total,
    spread: g.fg.spread,
    h_games_played: g.gamesPlayed.home,
    a_games_played: g.gamesPlayed.away,
    combined_sec_play: round2(26.5 + (g.id % 5) * 0.7),
    combined_plays: 138,
    wx_temp: 71,
    wx_wind: 4 + (g.id % 4) * 4,
    wx_precip: 0,
    wx_dome: 0,
    dome: false,
    home_fh_pf: 13.4,
    home_fh_pa: 11.1,
    away_fh_pf: 12.8,
    away_fh_pa: 12.2,
    fh_home_pf: 13.4,
    fh_home_pa: 11.1,
    fh_away_pf: 12.8,
    fh_away_pa: 12.2,
    fh_prior_source: "season_to_date",
    home_rest_days: 7,
    away_rest_days: 7,
    away_travel_dist: 412,
    away_tz_shift: 0,
    kickoff_local_hour: 15,
    form_home: {
      pf: pf(g.id),
      pa: pf(g.id + 3),
      n: 3,
      source: "season_to_date",
    },
    form_away: {
      pf: pf(g.id + 1),
      pa: pf(g.id + 4),
      n: 3,
      source: "season_to_date",
    },
    split_home: {
      at_home: { pf: 14.0, pa: 10.5, n: 2 },
      on_road: { pf: 12.5, pa: 12.0, n: 2 },
      source: "season_to_date",
    },
    split_away: {
      at_home: { pf: 13.0, pa: 12.5, n: 2 },
      on_road: { pf: 12.5, pa: 11.5, n: 2 },
      source: "season_to_date",
    },
    factor_board: factorBoard(g),
  };
}

function previewJson(g) {
  return {
    news: JSON.stringify({
      home: [`${g.home} named its captains for the week.`],
      away: [`${g.away} returns two starters on the offensive line.`],
    }),
    injuries: JSON.stringify({
      home: [`WR — questionable (hamstring)`],
      away: [],
    }),
  };
}

export function fixtureRows(week, expected) {
  const { now, season, games, teams } = week;
  const rows = {};

  rows.teams = teams.map((t) => ({
    id: t.id,
    school: t.school,
    conference: t.conference,
  }));

  rows.games = games.map((g) => ({
    id: g.id,
    season,
    week: g.week,
    season_type: "regular",
    start_date: ts(g.kick),
    neutral_site: false,
    home_team: g.home,
    away_team: g.away,
    home_team_id: g.homeTeamId,
    away_team_id: g.awayTeamId,
    home_points: g.played ? g.played.homePts : null,
    away_points: g.played ? g.played.awayPts : null,
    home_first_half_points: g.played ? g.played.homeFh : null,
    away_first_half_points: g.played ? g.played.awayFh : null,
    first_half_total: g.played ? g.played.homeFh + g.played.awayFh : null,
    first_half_source: g.played ? "linescores" : null,
    full_game_total: g.fg.total,
    full_game_total_book: HR,
    spread: g.fg.spread,
    full_game_total_source: "oddsapi",
    spread_source: "oddsapi",
    spread_open: g.fg.spread,
    spread_open_source: "oddsapi",
  }));

  // odds_snapshots: Hard Rock's 1H captures as given (two per priced game), every
  // other book at both of the same instants, and the full-game total from Hard
  // Rock (the universe) and DraftKings at the first capture.
  rows.odds_snapshots = [];
  for (const g of games) {
    const caps = g.hr ? g.hr.map((c) => c.capturedAt) : [];
    for (const c of g.hr ?? []) {
      rows.odds_snapshots.push({
        game_id: g.id,
        book: HR,
        market: "1H_total",
        line: c.line,
        over_price: c.over,
        under_price: c.under,
        captured_at: ts(c.capturedAt),
        last_seen_at: ts(c.capturedAt),
      });
    }
    // Books without a Hard Rock quote (900010) still need two capture instants.
    const bookCaps = caps.length
      ? caps
      : [week.captures.cap1, week.captures.cap2];
    for (const [book, [line, over, under]] of Object.entries(g.books)) {
      for (const at of bookCaps) {
        rows.odds_snapshots.push({
          game_id: g.id,
          book,
          market: "1H_total",
          line,
          over_price: over,
          under_price: under,
          captured_at: ts(at),
          last_seen_at: ts(at),
        });
      }
    }
    const fgAt = bookCaps[0];
    for (const book of [HR, "draftkings"]) {
      rows.odds_snapshots.push({
        game_id: g.id,
        book,
        market: "full_game_total",
        line: g.fg.total,
        spread: g.fg.spread,
        over_price: -110,
        under_price: -110,
        captured_at: ts(fgAt),
        last_seen_at: ts(fgAt),
      });
    }
  }

  // predictions: the model row (gbm_v1) and the display-only derived_lines row.
  const rankOf = new Map(expected.rankOrder.map((id, i) => [id, i + 1]));
  rows.predictions = [];
  for (const g of games) {
    const lineUsed = lineUsedFor(g);
    const f = modelFactors(g);
    rows.predictions.push({
      game_id: g.id,
      model_version: "gbm_v1",
      under_probability: round2(g.underScore / 100),
      under_score: g.underScore,
      projected_first_half_total: g.bv,
      bv_line: g.bv,
      bv_gap: round2(lineUsed - g.bv),
      bv_lo: f.bv_lo,
      bv_hi: f.bv_hi,
      bv_sigma: 11.26,
      bv_intercept: -1.24,
      line_used: lineUsed,
      rank: rankOf.get(g.id) ?? (g.id === 900012 ? 12 : g.id - 900012),
      factors_json: JSON.stringify(f),
      created_at: ts(g.scoredAt),
    });
    rows.predictions.push({
      game_id: g.id,
      model_version: "derived_lines",
      line_used: g.ref,
      rank: null,
      factors_json: JSON.stringify({
        line_kind: "derived_fg",
        line: g.ref,
        full_game_total: g.fg.total,
        spread: g.fg.spread,
        fh_share: round2(g.ref / g.fg.total),
      }),
      created_at: ts(new Date(g.scoredAt.getTime() + 60_000)),
    });
  }

  rows.cards = [
    {
      season,
      week: week.week,
      built_at: ts(expected.builtAt),
      payload: JSON.stringify(expected.card),
    },
  ];

  rows.manual_picks = expected.picks.map((p) => ({
    game_id: p.game.id,
    season,
    week: p.week,
    home_team: p.game.home,
    away_team: p.game.away,
    side: "under",
    market: "1H",
    line: p.line,
    price: p.price,
    stake: 1.0,
    is_paper: p.isPaper,
    is_bonus: false,
    book: HR,
    placed_at: ts(p.placedAt),
    note: p.note,
    model_score_at_pick: p.modelScore,
    model_line_at_pick: p.modelLine,
    graded: p.graded,
    actual_first_half_total: p.graded ? p.actualFh : null,
    result: p.graded ? p.result : null,
    units: p.graded ? p.units : null,
    closing_line: p.graded ? p.closingLine : null,
    closing_captured_at: p.graded
      ? ts(new Date(p.game.kick.getTime() - 3_600_000))
      : null,
    closing_price: p.graded ? p.closingPrice : null,
    price_provenance: "logged",
    clv: p.graded ? p.clv : null,
    clv_prob: p.graded ? p.clvProb : null,
    factors_json_at_pick: JSON.stringify({ factor_board: factorBoard(p.game) }),
    opening_line: p.graded ? p.openingLine : null,
    verdict_at_pick: p.verdict,
    reason: p.reason,
    gap_at_pick: p.gap,
    ev_at_pick: p.ev,
    hr_line_at_pick: p.hrLine,
    blocker: p.isPaper ? p.blocker : null,
  }));

  // results: the market (1H and full game) and the model, graded at the close.
  rows.results = [];
  for (const g of games.filter((x) => x.played)) {
    const fh = g.played.homeFh + g.played.awayFh;
    const full = g.played.homePts + g.played.awayPts;
    const close = g.hr[g.hr.length - 1].line;
    const closeAt = ts(g.hr[g.hr.length - 1].capturedAt);
    const graded = (mv, market, actual, line, kind) => ({
      game_id: g.id,
      model_version: mv,
      market,
      actual_first_half_total: actual,
      line_used: line,
      line_kind: kind,
      under_hit: actual < line,
      closing_line: line,
      closing_captured_at: closeAt,
      closing_price: -110,
      clv: 0,
      clv_prob: 0,
      units: actual < line ? round2(100 / 110) : actual > line ? -1.0 : 0,
    });
    rows.results.push(graded("market", "1H", fh, close, "real"));
    rows.results.push(graded("market_fg", "full", full, g.fg.total, "real"));
    rows.results.push(graded("gbm_v1", "1H", fh, lineUsedFor(g), "real"));
  }

  rows.game_records = games.map((g) => {
    const lineUsed = lineUsedFor(g);
    const fh = g.played ? g.played.homeFh + g.played.awayFh : null;
    return {
      game_id: g.id,
      season,
      week: g.week,
      captured_at: ts(g.scoredAt),
      model_version: "gbm_v1",
      engine: "bv_line",
      features_json: "{}",
      line: lineUsed,
      line_kind: g.hr
        ? "hr_1h"
        : Object.keys(g.books).length
          ? "observed_1h"
          : "derived_fg",
      bv_line: g.bv,
      bv_gap: round2(lineUsed - g.bv),
      bv_gap_z: round2((lineUsed - g.bv) / 11.26),
      under_score: g.underScore,
      first_half_total: fh,
      under_hit: fh === null ? null : fh < lineUsed,
      outcome:
        fh === null
          ? null
          : fh < lineUsed
            ? "under"
            : fh > lineUsed
              ? "over"
              : "push",
      graded_at:
        fh === null ? null : ts(new Date(g.kick.getTime() + 14 * 3_600_000)),
    };
  });

  rows.game_previews = games.map((g) => ({
    game_id: g.id,
    season,
    week: g.week,
    qb_out: false,
    qb_out_detail: null,
    ...(() => {
      const p = previewJson(g);
      return { news_json: p.news, injuries_json: p.injuries };
    })(),
    updated_at: ts(new Date(now.getTime() - 30 * 3_600_000)),
  }));

  // post-mortem: the historical scope and this season's live scope.
  const liveScope = `live_${season}`;
  const computedAt = ts(new Date(now.getTime() - 3 * 3_600_000));
  rows.postmortem_runs = [
    {
      run_id: "pm-hist-e2e",
      computed_at: computedAt,
      scope: "hist_2023_25",
      params_json: JSON.stringify({ seasons: [2023, 2024, 2025] }),
      notes_json: JSON.stringify({
        n_bets: 169,
        n_graded: 1934,
        flags: [
          {
            code: "gap_ladder",
            severity: "ok",
            text: "The gap ladder holds at real closing lines: the wider the gap, the more often the under wins.",
            evidence: {},
          },
          {
            code: "multiple_comparisons",
            severity: "watch",
            text: "Eleven statements are judged on this page; at the 5% level one of them is expected to look significant by chance alone.",
            evidence: {},
          },
          {
            code: "spread_bias",
            severity: "watch",
            text: "Model bias by spread band is flat at real closing lines, but the sample above a 28-point spread is thin (72 games).",
            evidence: {},
          },
        ],
        caveats: [
          "2023-25 is graded at the consensus close; Hard Rock did not exist then.",
        ],
      }),
      dropped_json: "[]",
      n_games: 3601,
      n_buckets: 60,
    },
    {
      run_id: "pm-live-e2e",
      computed_at: computedAt,
      scope: liveScope,
      params_json: JSON.stringify({ season }),
      notes_json: JSON.stringify({
        n_bets: 10,
        n_graded: 106,
        n_items: 190,
        derived_line: {
          n: 106,
          mae: 9.9,
          bias: -2.1,
          hr_mae: 8.7,
          market_mae: 8.6,
          share: 0.531,
        },
        price_read_counts: {
          neg: { under: 8, over: 10, push: 0 },
          fair: { under: 30, over: 32, push: 1 },
          pos: { under: 12, over: 14, push: 0 },
        },
        flags: [
          {
            code: "live_small_n",
            severity: "watch",
            text: "Ten real bets is too few to read anything into; the counts run until a group reaches 30.",
            evidence: {},
          },
        ],
      }),
      dropped_json: "[]",
      n_games: 106,
      n_buckets: 12,
    },
  ];

  const bucket = (
    scope,
    segment,
    proxy,
    selection,
    dimension,
    name,
    order,
    u,
    o,
    p,
    units,
  ) => {
    const n = u + o + p;
    const decided = u + o;
    const pct = decided ? u / decided : null;
    const z = 1.96;
    let ci_lo = null;
    let ci_hi = null;
    if (decided) {
      const denom = 1 + (z * z) / decided;
      const centre = (pct + (z * z) / (2 * decided)) / denom;
      const half =
        (z *
          Math.sqrt(
            (pct * (1 - pct)) / decided + (z * z) / (4 * decided * decided),
          )) /
        denom;
      ci_lo = Math.max(0, centre - half);
      ci_hi = Math.min(1, centre + half);
    }
    return {
      run_id: scope.startsWith("live") ? "pm-live-e2e" : "pm-hist-e2e",
      computed_at: computedAt,
      scope,
      segment,
      proxy_kind: proxy,
      selection,
      dimension,
      bucket: name,
      bucket_order: order,
      n,
      unders: u,
      overs: o,
      pushes: p,
      under_pct: pct,
      units,
      roi: n ? units / n : null,
      ci_lo,
      ci_hi,
      post_mean: pct,
      p_beat: pct === null ? null : pct > 0.524 ? 0.9 : 0.3,
    };
  };
  const H = "hist_2023_25";
  const ladder = (proxy) => [
    bucket(
      H,
      "fbs_only",
      proxy,
      "all",
      "gap_band",
      "<0",
      0,
      571,
      618,
      11,
      -104.3,
    ),
    bucket(
      H,
      "fbs_only",
      proxy,
      "all",
      "gap_band",
      "0–1.75",
      1,
      176,
      220,
      4,
      -60.0,
    ),
    bucket(
      H,
      "fbs_only",
      proxy,
      "all",
      "gap_band",
      "1.75–3",
      2,
      96,
      82,
      2,
      5.3,
    ),
    bucket(H, "fbs_only", proxy, "all", "gap_band", "3–5", 3, 77, 61, 2, 9.0),
    bucket(H, "fbs_only", proxy, "all", "gap_band", "5+", 4, 35, 24, 1, 7.8),
  ];
  rows.postmortem_buckets = [
    bucket(H, "fbs_only", "real", "cap5", "all", "all", 0, 102, 66, 1, 26.9),
    bucket(H, "fbs_only", "real", "gap175", "all", "all", 0, 285, 230, 5, 28.2),
    bucket(H, "fbs_only", "real", "gap300", "all", "all", 0, 112, 85, 3, 16.4),
    bucket(H, "fbs_only", "real", "all", "all", "all", 0, 921, 955, 26, -78.1),
    bucket(H, "fbs_only", "step", "cap5", "all", "all", 0, 88, 82, 0, -1.9),
    bucket(
      H,
      "fbs_only",
      "step",
      "gap175",
      "all",
      "all",
      0,
      271,
      263,
      6,
      -17.2,
    ),
    bucket(H, "fbs_only", "step", "all", "all", "all", 0, 940, 968, 26, -111.0),
    ...ladder("real"),
    ...ladder("step"),
    bucket(liveScope, "live", "hr", "bet", "all", "all", 0, 6, 4, 0, 2.01),
    bucket(
      liveScope,
      "live",
      "hr",
      "price_read",
      "all",
      "all",
      0,
      7,
      5,
      0,
      1.4,
    ),
    bucket(
      liveScope,
      "live",
      "hr",
      "all_hr",
      "all",
      "all",
      0,
      50,
      56,
      1,
      -10.5,
    ),
    bucket(
      liveScope,
      "live",
      "hr",
      "all_hr",
      "hr_vs_market",
      "HR below",
      0,
      8,
      12,
      0,
      -4.7,
    ),
    bucket(
      liveScope,
      "live",
      "hr",
      "all_hr",
      "hr_vs_market",
      "HR at market",
      1,
      28,
      32,
      1,
      -6.5,
    ),
    bucket(
      liveScope,
      "live",
      "hr",
      "all_hr",
      "hr_vs_market",
      "HR above",
      2,
      14,
      12,
      0,
      0.7,
    ),
    bucket(
      liveScope,
      "live",
      "market_close",
      "all_hr",
      "hr_vs_market",
      "HR below",
      0,
      9,
      11,
      0,
      -2.8,
    ),
    bucket(
      liveScope,
      "live",
      "market_close",
      "all_hr",
      "hr_vs_market",
      "HR at market",
      1,
      29,
      31,
      1,
      -4.6,
    ),
    bucket(
      liveScope,
      "live",
      "market_close",
      "all_hr",
      "hr_vs_market",
      "HR above",
      2,
      13,
      13,
      0,
      -1.2,
    ),
  ];

  rows.model_runs = [
    {
      version: "gbm_v1",
      train_window: "2023-2025",
      test_window: "walk-forward OOF",
      metrics_json: JSON.stringify({
        mae: 9.02,
        bv_residual: {
          n: 1934,
          overall_mean_residual: -0.12,
          by_era: { post2023: { n: 1934, mean_residual: -0.12 } },
          by_tempo: {
            fast: { n: 600, mean_residual: 0.31 },
            mid: { n: 734, mean_residual: -0.05 },
            slow: { n: 600, mean_residual: -0.6 },
          },
          by_dome: {
            dome: { n: 210, mean_residual: 0.8 },
            outdoor: { n: 1724, mean_residual: -0.2 },
          },
        },
      }),
      notes: "e2e fixture",
      created_at: ts(new Date(now.getTime() - 5 * 24 * 3_600_000)),
    },
  ];

  const hourAgo = ts(new Date(now.getTime() - 3_600_000));
  rows.app_settings = [
    {
      key: "rule_paused",
      value: "false",
      note: null,
      updated_at: ts(new Date(now.getTime() - 10 * 24 * 3_600_000)),
    },
    {
      key: "cfbd_calls_remaining",
      value: "2500",
      note: null,
      updated_at: hourAgo,
    },
    {
      key: "odds_credits_remaining",
      value: "15000",
      note: null,
      updated_at: hourAgo,
    },
    {
      key: "last_close_capture_at",
      value: ts(new Date(now.getTime() - 2 * 24 * 3_600_000)),
      note: null,
      updated_at: ts(new Date(now.getTime() - 2 * 24 * 3_600_000)),
    },
    {
      key: "last_close_capture_events",
      value: "40",
      note: null,
      updated_at: ts(new Date(now.getTime() - 2 * 24 * 3_600_000)),
    },
    {
      key: "last_grade_completed_at",
      value: hourAgo,
      note: null,
      updated_at: hourAgo,
    },
    ...Object.entries(expected.lastDispatch).map(([job, at]) => ({
      key: `last_dispatch_${job}`,
      value: ts(at),
      note: "e2e fixture: a tick inside the last closed window",
      updated_at: ts(at),
    })),
    // The health contracts' last verdicts (scripts/health_check.py writes
    // these as each scheduled job's final step): every job ok, so the banner
    // stays silent and /api/health reports four known verdicts.
    ...Object.entries(expected.health).map(([job, h]) => ({
      key: `last_health_${job}`,
      value: h.verdict,
      note: h.note,
      updated_at: ts(h.at),
    })),
  ];

  return rows;
}

export async function seed(
  url = process.env.DATABASE_URL ?? DEFAULT_URL,
  now = new Date(),
) {
  refuseNeon(url);
  const week = buildWeek(now);
  const expected = buildExpected(week);
  const rows = fixtureRows(week, expected);
  const client = new pg.Client({ connectionString: url });
  await client.connect();
  const counts = {};
  try {
    await client.query("BEGIN");
    await client.query(
      `TRUNCATE ${TABLES.join(", ")} RESTART IDENTITY CASCADE`,
    );
    // Parents first: games and teams carry explicit ids the rest reference.
    for (const table of [...TABLES].reverse()) {
      counts[table] = await insert(client, table, rows[table] ?? []);
    }
    // games/teams were inserted with explicit ids: bring their sequences up so
    // an app-side INSERT (a logged pick) cannot collide (the Neon id gotcha).
    const seqs = await client.query(
      "SELECT sequencename FROM pg_sequences WHERE schemaname = 'public' AND sequencename LIKE '%_id_seq'",
    );
    for (const { sequencename } of seqs.rows) {
      const table = sequencename.slice(0, -"_id_seq".length);
      await client.query(
        `SELECT setval('${sequencename}', COALESCE((SELECT MAX(id) FROM ${table}), 0) + 1, false)`,
      );
    }
    await client.query("COMMIT");
  } catch (e) {
    await client.query("ROLLBACK").catch(() => {});
    throw e;
  } finally {
    await client.end();
  }
  return { week, expected, counts };
}

const isMain =
  process.argv[1] !== undefined &&
  import.meta.url === pathToFileURL(process.argv[1]).href;
if (isMain) {
  const url = process.env.DATABASE_URL ?? DEFAULT_URL;
  seed(url)
    .then(({ week, expected, counts }) => {
      console.log(`seeded ${url.replace(/\/\/.*@/, "//***@")}`);
      console.log(
        `  season ${week.season} week ${week.week}: ${week.games.length} games, bar ${expected.bar}, card ${JSON.stringify(expected.card.counts)}, slot ${expected.card.slot}`,
      );
      console.log(
        "  rows:",
        Object.entries(counts)
          .filter(([, n]) => n > 0)
          .map(([t, n]) => `${t}=${n}`)
          .join(" "),
      );
    })
    .catch((e) => {
      console.error(e.message ?? e);
      process.exit(1);
    });
}
