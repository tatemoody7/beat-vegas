# Beat Vegas — project brief for Claude Code

College football **first-half (1H) unders** research & decision-support system.
Research only — it never places bets or automates gambling.

## How to resume / orient (read this first)
- **LATEST (2026 pivot): mispricing system shipped.** Reframed from "prove unders
  win" to "find games where the book mispriced the 1H under." The **predict-the-1H-
  total engine is now PRIMARY**: `score_slate` ranks the board by the gap between
  the line and our market-blind predicted 1H total (unders only), not the old
  classifier probability. Validated +3.0% ROI vs the classifier's +1.4% (proxy OOS).
  Full write-ups: `docs/PIVOT.md`; memory `beat-vegas-factor-pivot`; plan
  `~/.claude/plans/we-need-to-pivot-lazy-bonbon.md`.
- **Factor framework**: `beatvegas/factors/` ranks 117 factors by OOS relationship
  to the 1H under (`scripts/rank_factors.py` → `factor_scores`). Includes 1H-specific
  play-by-play factors (`fh_team_game`, from a free bulk PBP backfill).
- Long-term memory (decisions, status) auto-loads from this project's memory dir.
- **Phase B shipped**: Next.js app is live on Vercel (Neon-backed, password-gated)
  at https://beat-vegas.vercel.app. The board reads Neon, orders by `rank` (= gap).
- The **"BV line"** regressor (`docs/BV_LINE.md`) is the engine core, now promoted
  from display-only to the primary ranking signal (gate passed — see Gotchas).

## What it does
Pulls free data (CFBD, **bulk play-by-play via cfbfastR parquet + CFBD /plays**,
TeamRankings tempo, Open-Meteo weather, The Odds API 1H totals), derives ground-truth
1H points, builds leak-free features (incl. **1H-specific PBP factors**: EPA/success/
explosive/opening-drive/havoc/redzone/4th-down), predicts each game's 1H total with a
market-blind regressor, ranks the board by line-vs-prediction **gap** (the mispricing
signal), tracks line movement, sends iMessage alerts, and grades market vs model vs
the user's own picks. Also generates a weekly report (`scripts/weekly_report.py`).

## Architecture
- **Local Mac engine** (`beatvegas/` + `scripts/`): scrape → score → grade →
  alert, scheduled by launchd (`scripts/run_daily.sh`, `deploy/com.beatvegas.daily.plist`).
- **DB**: SQLAlchemy. `DATABASE_URL` env → Postgres (Neon); else local SQLite
  (`data/beatvegas.db`). See `beatvegas/config.py::database_url` + `db/store.py`.
- **Dashboard today**: Streamlit (`beatvegas/dashboard/app.py`) — local quick-view.
- **Dashboard target**: Next.js app in `web/` on Vercel, reading/writing Neon
  (replaces Streamlit as the product; Streamlit stays for local dev).

## Setup
```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -e .
cp config.example.yaml config.yaml   # add CFBD + Odds API keys (gitignored)
pytest -q                            # 61 tests
```
Key scripts: `backfill.py`, `backfill_enrichment.py` (pace/weather), `weekly_update.py`
(score), `poll_lines.py` (lines + alerts), `grade.py`, `pick.py`, `line_study.py`,
`retrain.py` (logs model_runs + BV calibration), `backfill_bv_line.py`, `seed_demo.py`.
**Pivot scripts**: `backfill_pbp.py` (1H PBP aggregates → `fh_team_game`),
`backfill_context.py` (venue/talent/roster), `rank_factors.py` (factor ranking →
`factor_scores`), `validate_engine.py` (gbm_v2 gate + MAE ablation), `inspect_combo.py`
+ `explain_pbp.py` (factor deep-dives), `weekly_report.py` (markdown board), `deploy_neon.py`
(additive Neon push). Streamlit: `streamlit run beatvegas/dashboard/app.py` (demo via
`BEATVEGAS_DB=data/demo.db`). 84 tests.

## Honest status of the edge (don't oversell)
- Backtest is **proxy-graded** (no free historical 1H lines; uses 0.52×full-game
  total). Real DraftKings lines collected going forward are the true test.
- **Predict-total engine (gbm_v2): top-20% by gap = 54.0% under / +3.0% ROI** OOS
  (2018+), vs the old classifier's 53.1% / +1.4%. Profitable 6/8 seasons.
- **The proxy-under ROI is partly a PROXY ARTIFACT**: the flashy proxy-leaders
  (1H explosive/turnovers) actually correlate with *more* 1H scoring — they win the
  under via the flat-0.52 proxy over-pricing low-1H-share games, not real low scoring.
  The `corr_1h` diagnostic (`rank_factors.py`) measures genuine 1H-scoring signal,
  immune to this. **Genuine signal = pace + efficiency/scoring levels.**
- The heavy PBP backfill **did not improve 1H-total prediction** (MAE ablation in
  `validate_engine.py`: 9.22 full vs 9.18 without) — base features already capture
  it. PBP factors confirmed the thesis + exposed the artifact; they stay as display
  chips and could be trimmed from the predictor.
- The edge is real but **small and unconfirmed**. The system's job is to *measure* it
  honestly vs real lines, not to promise profit.

## Resuming Phase B (Next.js app)
Build in `web/`: Next.js (App Router) + TypeScript + Tailwind + **Prisma** + **Recharts**.
- **Dev against local data**: Prisma `sqlite` provider → `data/beatvegas.db`
  (has 2015–25 games, predictions, results, snapshots). Switch datasource to
  `postgresql` for Neon/Vercel deploy. `prisma db pull` introspects the schema.
- **Use `beatvegas/dashboard/app.py` as the visual spec** — port these views:
  Opportunities (ranked 0–100 cards w/ chips: Pace, Weather, Def/Off eff, 1H hist,
  Spot, Returning), Line movement (per-game chart), Line Study (under% by opening
  line vs 52.4% breakeven), Ledger (3-way market/model/you), Research (model_runs).
  Score color thresholds + chip logic are in `model/score.py` and `app.py`.
- **API routes** read the same SQL the Streamlit `q()` calls use. **My Picks** =
  writable form → `POST /api/picks` (insert ManualPick). Lock the app with a
  password gate (`middleware.ts` + `APP_PASSWORD` cookie).
- Deploy needs (user): Neon `DATABASE_URL`, Vercel project + env vars
  (`DATABASE_URL`, `APP_PASSWORD`). `gh` is authed (tatemoody7); repo is
  private: https://github.com/tatemoody7/beat-vegas

## Gotchas
- Features must stay **leak-free** (only pre-kickoff info; season-to-date shifted).
- Numeric model columns must be clean floats (NaN, never `pd.NA`/None/bool) — see
  `features.build_feature_frame` coercion; `bool(NaN)` is `True` (bit us on dome).
- ESPN/TeamRankings are **unofficial** — keep isolated in `sources/`, fail-silent.
- `config.yaml` (keys + phone) and `data/*.db|*.log|cache/|pbp_cache/` are gitignored —
  keep it that way (`pbp_cache/` holds 56MB parquet files per season).
- **Neon id-sequence**: rows seeded from SQLite carry explicit ids without advancing
  the Postgres sequence, so the next insert collides on the pkey. Before any bulk
  insert to Neon (`backfill_bv_line.py`, `retrain.py`, `deploy_neon.py`), resync:
  `SELECT setval(pg_get_serial_sequence('<table>','id'), (SELECT MAX(id) FROM <table>))`.
- **Neon bulk inserts must be CHUNKED** (~500 rows/commit) — a single big
  `bulk_insert_mappings` STALLS the Neon pooler indefinitely. See `deploy_neon.py::_chunked_insert`.
- **psycopg3** required for Neon (`pip install "psycopg[binary]"`); the engine normalizes
  `postgresql://` → `postgresql+psycopg://` (config.py). NOT psycopg2.
- **Deploy to Neon is ADDITIVE** (`deploy_neon.py`) — never `--wipe`/full-migrate to
  prod: `manual_picks`, `odds_snapshots`, `results` are live Neon-only data.
- **BV gap is now the PRIMARY ranking** (gate passed in `validate_engine.py`).
  `score_slate` sorts by `bv_gap` desc; `is_opportunity` = `bv_gap_z >= 0.5`. Calibration
  still uses a **global** intercept + `era_post2023` feature (per-era would double-count).
  The regressor is MARKET-BLIND (`BV_FEATURE_COLS = FEATURE_COLS − MARKET_COLS`) — keep it so.
