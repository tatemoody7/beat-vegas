// The factors_json payload the scorer writes (beatvegas/model/score.py
// ::_factors) and the green/red explainer board (beatvegas/factors/board.py
// ::build_factor_board), typed and parsed for the web board. Keep the shapes
// faithful to those two.
//
// The old Streamlit colour bands, tier headings and 7-chip builder lived here
// too; nothing renders them now (grades come from lib/grade.ts and the board
// shows one flat factor list), so they are gone.

// One factor on the green/red board (pure explainer; never affects the rank).
// Mirrors beatvegas/factors/board.py::build_factor_board.
export type BoardFactor = {
  key: string;
  label: string;
  family: string;
  tier: number; // 1 proven · 2 context · 3 speculative
  direction: number; // +1 helps under, -1 hurts, 0 neutral/unknown
  hypothesis: boolean; // unverified — rendered amber
  binary: boolean;
  value: number;
  color: "green" | "red" | "neutral" | "amber" | "unknown";
  intensity: number; // 0..1 tint strength
  lean: number; // signed; under-favorable positive
  sentence: string;
  // Filled by the credibility ledger: real-line 1H-under record when green.
  live: {
    n: number;
    mean: number;
    lo: number;
    hi: number;
    cooling: boolean;
  } | null;
};

// Per-game factor payload stored as JSON in predictions.factors_json.
export type Factors = {
  factor_board?: BoardFactor[] | null;
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
  // genuine 1H-scoring signal (corr_1h drivers) from PBP
  fh_off_epa_home?: number | null;
  fh_off_epa_away?: number | null;
  fh_off_success_home?: number | null;
  fh_off_success_away?: number | null;
  // --- Board context (beatvegas/etl/context.py + form). ALL OPTIONAL: written
  // for every card (derived rows included) once the context job runs; read
  // defensively — any key may be absent on older rows.
  combined_sec_play?: number | null;
  combined_plays?: number | null;
  wx_temp?: number | null;
  wx_wind?: number | null;
  wx_precip?: number | null;
  wx_dome?: number | null;
  dome?: boolean | null;
  /** Raw 1H priors by feature-frame name (context.py); the model row's
   *  `fh_home_pf` etc. above are the same numbers under the scoring names. */
  home_fh_pf?: number | null;
  home_fh_pa?: number | null;
  away_fh_pf?: number | null;
  away_fh_pa?: number | null;
  fh_prior_source?: string | null;
  /** Prior games played this season by each team (scripts/weekly_update.py). */
  h_games_played?: number | null;
  a_games_played?: number | null;
  combined_off_ppa?: number | null;
  combined_def_ppa?: number | null;
  home_rest_days?: number | null;
  away_rest_days?: number | null;
  away_travel_dist?: number | null;
  away_tz_shift?: number | null;
  kickoff_local_hour?: number | null;
  form_home?: TeamForm | null;
  form_away?: TeamForm | null;
  split_home?: TeamSplit | null;
  split_away?: TeamSplit | null;
};

/** Last-n first-half points for / against, oldest → newest. */
export type TeamForm = {
  pf: number[];
  pa: number[];
  n: number;
  source?: "season_to_date" | "prior_season" | string | null;
};

export type SplitLeg = { pf: number; pa: number; n: number } | null;

/** Home / away first-half splits. context.py writes `at_home` / `on_road`;
 *  `home` / `away` are accepted as aliases. */
export type TeamSplit = {
  at_home?: SplitLeg;
  on_road?: SplitLeg;
  home?: SplitLeg;
  away?: SplitLeg;
  source?: "season_to_date" | "prior_season" | string | null;
};

export function parseFactors(raw: string | null | undefined): Factors {
  if (!raw) return {};
  try {
    return JSON.parse(raw) as Factors;
  } catch {
    return {};
  }
}

// rgba tint for a board row: color at an alpha scaled by intensity.
export function factorTint(f: BoardFactor): { bg: string; dot: string } {
  const rgb: Record<string, string> = {
    green: "22,163,74",
    red: "220,38,38",
    amber: "224,164,74",
    neutral: "120,135,170",
    unknown: "120,135,170",
  };
  const base = rgb[f.color] ?? rgb.neutral;
  // binary/active factors read full-strength; continuous scale with intensity.
  const alpha =
    f.color === "neutral" || f.color === "unknown"
      ? 0.05
      : 0.08 + 0.22 * f.intensity;
  return { bg: `rgba(${base},${alpha.toFixed(3)})`, dot: `rgb(${base})` };
}

/** The one line above the factor list (Tate 2026-10-15, Q5), with the count
 *  from research/1h-factors-2026-10/report.md (H-1H-FACTORS, development
 *  evidence): 64 factors screened, none passed either level. */
export const FACTOR_NOTE =
  "These explain the line. None has been shown to beat it: 64 factors tested against the closing line, none passed (H-1H-FACTORS).";

/**
 * A stored factor sentence in scoring words (Q5): "— helps the under" becomes
 * "— points to less scoring", and so on. Rows scored before 2026-10-15 carry
 * the old words in predictions.factors_json (board.py writes the new ones);
 * this makes every week read the same. A hypothesis ("unproven for the under")
 * loses its direction; its "unproven" chip says it.
 */
export function scoringWords(sentence: string): string {
  return sentence
    .replace(/\s+—\s+helps the under/g, " — points to less scoring")
    .replace(
      /\s+—\s+(hurts|works against) the under/g,
      " — points to more scoring",
    )
    .replace(/\s+—\s+is neutral for the under/g, " — small effect, if any")
    .replace(/\s+—\s+unproven for the under\.?/g, ".")
    .replace(/,\s*works against the under/g, ", points to more scoring")
    .replace(/\.\s*\(/g, " (")
    .replace(/\.\./g, ".");
}
