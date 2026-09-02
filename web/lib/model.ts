// The one production model version. results.model_version / predictions.
// model_version rows written by scripts/weekly_update.py + grade.py carry this
// string; every ledger / research / records query must use the constant, never
// a literal, so a retrain that bumps the version is a one-line change here.
export const MODEL_VERSION = "gbm_v1";

// Ledger names in `results` (beatvegas/grading.py): the market itself, graded
// against the real closing line, per market.
export const MARKET_LEDGER_1H = "market";
export const MARKET_LEDGER_FG = "market_fg";
