// Port of the score-color + chip logic from beatvegas/dashboard/app.py and
// beatvegas/model/score.py::_factors. Keep faithful to those so the web board
// matches the Streamlit view exactly.

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
  live: { n: number; mean: number; lo: number; hi: number; cooling: boolean } | null;
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

// Short tier label for the score, matching the scoreColor bands above.
// Additive — purely for display; doesn't change any existing logic.
export function scoreLabel(score: number | null | undefined): string {
  if (score === null || score === undefined) return "no read";
  if (score >= 60) return "Strong under";
  if (score >= 53) return "Lean under";
  if (score >= 47) return "Coin flip";
  if (score >= 40) return "Lean over";
  return "Over";
}

// Group the board into the tiers the Option-A card renders. Hypotheses are
// pulled into their own amber group regardless of tier (we never show them as
// a plain green/red signal until the real-line ledger has earned them).
export type FactorTierGroup = { tier: number; title: string; factors: BoardFactor[] };

export function groupFactorBoard(board: BoardFactor[] | null | undefined): FactorTierGroup[] {
  const fb = board ?? [];
  const proven = fb.filter((f) => !f.hypothesis && f.tier === 1);
  const context = fb.filter((f) => !f.hypothesis && f.tier === 2);
  const speculative = fb.filter((f) => !f.hypothesis && f.tier >= 3);
  const hypotheses = fb.filter((f) => f.hypothesis);
  return [
    { tier: 1, title: "Proven — history + live", factors: proven },
    { tier: 2, title: "Context — real info, flat in backtest", factors: context },
    { tier: 3, title: "Speculative — weight 0 until proven", factors: speculative },
    { tier: 0, title: "Unverified — amber until the ledger speaks", factors: hypotheses },
  ].filter((g) => g.factors.length > 0);
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
  const alpha = f.color === "neutral" || f.color === "unknown" ? 0.05 : 0.08 + 0.22 * f.intensity;
  return { bg: `rgba(${base},${alpha.toFixed(3)})`, dot: `rgb(${base})` };
}

export type Chip = { label: string; value: string; hint: string };

const has = (v: unknown): v is number => v !== null && v !== undefined;

// The 7 chips, matching the order/labels/tooltips/fallbacks in app.py.
export function buildChips(f: Factors): Chip[] {
  const oneH = has(f.fh_home_pf)
    ? `${f.fh_home_pf}/${f.fh_home_pa} · ${f.fh_away_pf}/${f.fh_away_pa}`
    : "—";
  return [
    {
      label: "Pace",
      value: f.pace || "live ✦",
      hint: "How fast both teams play — seconds per play and plays per game.",
    },
    {
      label: "Weather",
      value: f.weather || "live ✦",
      hint: "Temperature, wind, and rain near kickoff.",
    },
    {
      label: "Defense",
      value: has(f.def_ppa) ? String(f.def_ppa) : "—",
      hint: "Points each team gives up per play this season (lower = tougher defense).",
    },
    {
      label: "Offense",
      value: has(f.off_ppa) ? String(f.off_ppa) : "—",
      hint: "Points each team gains per play this season (lower = less explosive).",
    },
    {
      label: "1st-half pts",
      value: oneH,
      hint: "Average first-half points scored / allowed this season — home · away.",
    },
    {
      label: "1st-half offense",
      value: has(f.fh_off_epa_home)
        ? `${f.fh_off_epa_home!.toFixed(2)} · ${(f.fh_off_epa_away ?? 0).toFixed(2)}`
        : "—",
      hint: "How efficient each offense is per play in the first half (home · away).",
    },
    {
      label: "Rest & travel",
      value: f.spot || "—",
      hint: "Days of rest, miles traveled, and kickoff time. Context only — not part of the pick.",
    },
    {
      label: "History estimate",
      value: has(f.proj_1h_total) ? f.proj_1h_total!.toFixed(1) : "—",
      hint: "A rough first-half total from past scoring. Context only — the model, not this, drives the score.",
    },
    {
      label: "Our number",
      value: has(f.bv_line) ? f.bv_line!.toFixed(1) : "—",
      hint: "Our model's own predicted first-half total, from the full feature set (pace, efficiency, weather). It never looks at the Vegas line.",
    },
  ];
}
