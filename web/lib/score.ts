// Port of the score-color + chip logic from beatvegas/dashboard/app.py and
// beatvegas/model/score.py::_factors. Keep faithful to those so the web board
// matches the Streamlit view exactly.

// Per-game factor payload stored as JSON in predictions.factors_json.
export type Factors = {
  pace?: string | null;
  weather?: string | null;
  spot?: string | null;
  returning?: string | null;
  off_ppa?: number | null;
  def_ppa?: number | null;
  fh_home_pf?: number | null;
  fh_home_pa?: number | null;
  fh_away_pf?: number | null;
  fh_away_pa?: number | null;
  proj_1h_total?: number | null;
  bv_line?: number | null;
  bv_gap?: number | null;
  bv_lo?: number | null;
  bv_hi?: number | null;
  bv_sigma?: number | null;
  bv_gap_z?: number | null;
  qb_out_home?: boolean | null;
  qb_out_away?: boolean | null;
  qb_out_detail?: string | null;
  line?: number | null;
  edge?: number | null;
  // derived-line entries (scripts/post_derived_lines.py): our 1H number off the
  // posted full-game line, no model. `line_kind="derived_fg"` flags these cards.
  line_kind?: string | null;
  full_game_total?: number | null;
  spread?: number | null;
  fh_share?: number | null;
  // primary-engine fields (gbm_v2 gap ranking, Phase 3)
  rank_basis?: string | null;
  is_opportunity?: boolean | null;
  // genuine 1H-scoring signal (corr_1h drivers) from PBP
  fh_off_epa_home?: number | null;
  fh_off_epa_away?: number | null;
  fh_off_success_home?: number | null;
  fh_off_success_away?: number | null;
};

export function parseFactors(raw: string | null | undefined): Factors {
  if (!raw) return {};
  try {
    return JSON.parse(raw) as Factors;
  } catch {
    return {};
  }
}

// app.py::_score_color — 50 is the breakeven anchor (-110 ⇒ 52.4%).
export function scoreColor(score: number | null | undefined): string {
  if (score === null || score === undefined) return "#6b7280"; // grey
  if (score >= 60) return "#16a34a"; // strong under (green)
  if (score >= 53) return "#65a30d"; // lean under (lime)
  if (score >= 47) return "#ca8a04"; // neutral (amber)
  if (score >= 40) return "#ea580c"; // lean over (orange)
  return "#dc2626"; // over (red)
}

export type Chip = { label: string; value: string; hint: string };

const has = (v: unknown): v is number => v !== null && v !== undefined;

// The 7 chips, matching the order/labels/tooltips/fallbacks in app.py.
export function buildChips(f: Factors): Chip[] {
  const oneH =
    has(f.fh_home_pf)
      ? `${f.fh_home_pf}/${f.fh_home_pa} · ${f.fh_away_pf}/${f.fh_away_pa}`
      : "—";
  return [
    {
      label: "Pace",
      value: f.pace || "live ✦",
      hint: "Combined seconds/play + plays/game (TeamRankings)",
    },
    {
      label: "Weather",
      value: f.weather || "live ✦",
      hint: "Temp / wind / precip near kickoff (Open-Meteo)",
    },
    {
      label: "Def eff",
      value: has(f.def_ppa) ? String(f.def_ppa) : "—",
      hint: "Combined defensive PPA allowed (lower = stronger D)",
    },
    {
      label: "Off eff",
      value: has(f.off_ppa) ? String(f.off_ppa) : "—",
      hint: "Combined offensive PPA (lower = less explosive)",
    },
    {
      label: "1H hist",
      value: oneH,
      hint: "Season-to-date 1H pts for/against (home · away)",
    },
    {
      label: "1H eff",
      value: has(f.fh_off_epa_home)
        ? `${f.fh_off_epa_home!.toFixed(2)} · ${(f.fh_off_epa_away ?? 0).toFixed(2)}`
        : "—",
      hint: "Season-to-date 1H offensive EPA/play (home · away), from play-by-play — the genuine 1H-scoring driver",
    },
    {
      label: "Spot",
      value: f.spot || "—",
      hint: "Rest days (home/away) · away travel · ~local kickoff (context only — not a model input)",
    },
    {
      label: "Hist proj",
      value: has(f.proj_1h_total) ? f.proj_1h_total!.toFixed(1) : "—",
      hint: "Naive 1H projection from scoring history (context only — the model, not this, drives the score)",
    },
    {
      label: "BV line",
      value: has(f.bv_line) ? f.bv_line!.toFixed(1) : "—",
      hint: "The model's own calibrated 1H projection from the full feature set (pace, efficiency, weather, era). Large Vegas−BV gaps can be model blind spots, not edges — validated only by the CLV-by-gap table in Research.",
    },
  ];
}
