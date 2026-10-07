// The one production model version. results.model_version / predictions.
// model_version rows written by scripts/weekly_update.py + grade.py carry this
// string; every ledger / research / records query must use the constant, never
// a literal, so a retrain that bumps the version is a one-line change here.
export const MODEL_VERSION = "gbm_v1";

// The earliest season the site lists (2026-10-06). Seasons before 2023 are
// loaded into `games` only as training history for the H-HIST / H-ELO-F
// studies; they carry no predictions, lines or picks, so no page shows them.
// Mirrors beatvegas/etl/features.py::FRAME_MIN_SEASON (tests/test_gate_parity.py).
export const SITE_MIN_SEASON = 2023;

// The display-only derived lines (scripts/post_derived_lines.py): shown on a
// card when no model row exists, never ranked above one.
export const DERIVED_LINES_MODEL_VERSION = "derived_lines";

// The prediction versions any "the model's line" read may see (2026-10-06).
// An ALLOW-list: a shadow engine writing into `predictions` (bv_fg_v1 for
// H-FG-P, the PR6 shadows) is never read as the champion. Mirrors
// beatvegas/model/score.py::CHAMPION_READ_VERSIONS (tests/test_gate_parity.py).
export const CHAMPION_READ_VERSIONS = [
  MODEL_VERSION,
  DERIVED_LINES_MODEL_VERSION,
] as const;

// Ledger names in `results` (beatvegas/grading.py): the market itself, graded
// against the real closing line, per market.
export const MARKET_LEDGER_1H = "market";
export const MARKET_LEDGER_FG = "market_fg";
