# Beat Vegas — project brief for Claude Code

College football **full-game + first-half (1H) unders** research & decision-support
system, focused on **Hard Rock Bet** (the only book bettable from Florida).
Research only — it never places bets or automates gambling.

## How to resume / orient (read this first)
- **LATEST (full-game + 1H Hard Rock pivot — SHIPPED to `main`, PRs #7→#8→#9):** the
  system now covers **full-game unders AND 1H unders**, organized around Tate's weekly
  Hard Rock workflow. **Decision-support, not a model-pick board** — the model number is
  one reference chip (the full-game backtest `scripts/backtest_full_game.py` found **no
  edge** on the thin 2023-25 regime; we *measure* the edge via CLV, not gate on it).
  Pieces: **multi-book capture incl. Hard Rock** via The Odds API bulk `/odds`
  (`odds.normalize_full_game` + `list_full_game_totals`; `poll_full_game --source oddsapi
  --regions us,us2`; HR key is **`hardrockbet`**, FL-specific `hardrockbet_fl` when prices
  diverge — `beatvegas/hardrock.py`). **Cloud push alerts** (Pushover; `alerts/push.py` +
  `detect_full_game_posted`/`detect_first_half_posted`; `--push` on both pollers;
  `.github/workflows/lines_watch.yml` = Sunday FG opener window every 10 min + daily 1H).
  **Web views:** `/preview` (Week Preview — slate + ESPN news/injuries/QB-out from
  `game_previews`, built by `scripts/research_preview.py`), `/line-check` (Hard Rock vs
  best-available total, verdict + per-book detail), `/weekly-review` (market/model/you ×
  full-game/1H scorecard + your picks + UNCONFIRMED trend scan). **Logging + grading both
  markets:** additive `manual_picks.market` + `results.market`; `pick.py` grades full-game
  OR 1H; `grade.py` adds the full-game market ledger (`market_fg`). New Neon schema applies
  via `.github/workflows/migrate.yml` (workflow_dispatch → `init_db`). **Setup before
  season:** Pushover (config `push.pushover` + GH secrets `PUSHOVER_TOKEN`/`PUSHOVER_USER`),
  `odds_api.regions: "us,us2"` locally. Plan:
  `~/.claude/plans/the-overall-plan-right-dreamy-stardust.md`; memory
  `beat-vegas-hardrock-oddsapi`.
- **EARLIER (web redesign + cleanup): the Next.js app got a plain-English rewrite and a
  modern "sportsbook" visual system** (deep navy + electric-cyan; `.bv-*` classes in
  `web/app/globals.css`; active-route nav in `MainNav.tsx`). The old **Streamlit
  dashboard was removed** (Next.js is the product). Added a **Neon-isolated week-sim**
  (`scripts/simulate_week.py` + `pg_sim.py`) for off-season dry-runs, and **lint/format
  tooling** (Ruff for Python, ESLint+Prettier for `web/`). The prod **"Log pick" Neon
  bug is fixed** (`web/lib/picks.ts`: `::timestamp` cast + boolean `graded`). All shipped
  to `main` (PR #1, deployed via Vercel). See plan
  `~/.claude/plans/session-handoff-week-1-eager-matsumoto.md`.
- **LATEST (cloud + board): scheduled Neon writes run in GitHub Actions; derived-1H
  lines show on the board.** The Mac's usual network (campus/fgcu) **can't reach Neon**
  (5432 TLS filtered; 443 fine), so the Sunday capture+score runs in **GitHub Actions**
  (`.github/workflows/sunday.yml` cron; `bootstrap.yml` one-time; `post-lines.yml` to
  publish derived lines). **DK 403s GHA datacenter IPs**, so the cloud uses
  `poll_full_game --source auto` → **CFBD `/lines` fallback** (`sources/cfbd_lines.py`).
  Local jobs degrade gracefully via `store.try_init_db` (logs + exits 0, no traceback);
  the iMessage heads-up is local notify-only (`scripts/notify_sunday.py` +
  `deploy/com.beatvegas.sunday-notify.plist`). Two read paths to the posted lines:
  `scripts/grade_lines.py` (terminal report) and `scripts/post_derived_lines.py` (writes
  display-only `predictions` rows, `model_version=derived_lines`, model fields NULL,
  `factors_json.line_kind="derived_fg"`) → board cards labeled **"DERIVED · no model
  pick"**. The board query is **season-scoped** (`web/lib/board.ts`) so derived rows for
  one season don't hide another's real model board; real in-season scoring auto-supersedes
  derived rows. GH secrets set: `DATABASE_URL`/`CFBD_API_KEY`/`ODDS_API_KEY`.
- **LATEST (opener capture): DraftKings free poller + spread-adjusted multiplier.**
  Full-game totals open Sunday; retail 1H totals post later — so we capture the
  **full-game opener from DK's free hidden API** (`beatvegas/sources/draftkings.py`,
  `scripts/poll_full_game.py`) and **derive a 1H number** from it via a spread-aware
  multiplier (`proxy_line.fh_share`/`proxy_total(total, spread=...)`). The Sunday
  board ranks off that derived opener (`opening_line_lookup` returns `(lines, kinds)`;
  kind `derived_fg` vs `observed_1h`, surfaced in `factors_json.line_kind`).
  Scheduled by `scripts/run_sunday.sh` + `deploy/com.beatvegas.sunday.plist`
  (Sun 12:30pm), which also texts a single "DK fired" heads-up (no picks). The
  spread-adjusted multiplier is **gated**: `scripts/derive_multiplier.py` writes
  `data/multiplier.json` ONLY if it beats flat 0.52 walk-forward; absent file =>
  flat 0.52 (zero behavior change). Run `scripts/backfill.py` to populate
  `Game.spread` (now captured from CFBD /lines) before fitting. Plan:
  `~/.claude/plans/users-tatemoody-desktop-compass-artifac-jolly-whistle.md`.
- **EARLIER (2026 pivot): mispricing system shipped.** Reframed from "prove unders
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
- **Dashboard**: Next.js app in `web/` on Vercel, reading/writing Neon, is the
  product (the old Streamlit dashboard was removed — see git history if you need
  the original `_score_color`/chip reference). Plain-English copy + a modern
  "sportsbook" visual system (deep navy + electric-cyan accent; green/red reserved
  for under/over outcomes) live in `web/app/globals.css` (`.bv-*` component classes).

## Setup
```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -e .
cp config.example.yaml config.yaml   # add CFBD + Odds API keys (gitignored)
pytest -q                            # 104 tests
```
Key scripts: `backfill.py`, `backfill_enrichment.py` (pace/weather), `weekly_update.py`
(score), `poll_lines.py` (lines + alerts), `grade.py`, `pick.py`, `line_study.py`,
`retrain.py` (logs model_runs + BV calibration), `backfill_bv_line.py`, `seed_demo.py`.
**Pivot scripts**: `backfill_pbp.py` (1H PBP aggregates → `fh_team_game`),
`backfill_context.py` (venue/talent/roster), `rank_factors.py` (factor ranking →
`factor_scores`), `validate_engine.py` (gbm_v2 gate + MAE ablation), `inspect_combo.py`
+ `explain_pbp.py` (factor deep-dives), `weekly_report.py` (markdown board), `deploy_neon.py`
(additive Neon push). **Opener/cloud scripts**: `poll_full_game.py` (DK/CFBD full-game
capture, `--source dk|cfbd|auto`), `derive_multiplier.py` (gated spread multiplier),
`backfill_spread.py` (surgical `Game.spread` from CFBD), `deploy_neon_games.py` (additive
games+spread push), `grade_lines.py` (terminal derived-1H report), `post_derived_lines.py`
(writes display-only `derived_lines` predictions for the board), `notify_sunday.py` (local
iMessage heads-up). **Sim/dev scripts**: `pg_sim.py` (throwaway local PG16 sandbox at
`~/.cache/beatvegas/pg_sim`) + `simulate_week.py` (replay a real week into it, rendered by
the real Next.js app, Neon-isolated). 104 tests. **Lint/format**: `ruff check` + `ruff
format` for Python (`[tool.ruff]` in `pyproject.toml`, pragmatic F/E/I/B set — NOT pyupgrade,
which would break the py3.9 runtime); `npm run lint` + `npm run format` in `web/`
(ESLint flat config via Next 16's native arrays + Prettier).

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

## Web app (`web/`) — shipped + redesigned
Next.js (App Router) + TypeScript + Tailwind v4 + **Prisma** + **Recharts**, live on
Vercel (Neon-backed, password-gated) at https://beat-vegas.vercel.app.
- **Views**: Opportunities (ranked under-score cards + chips), Line movement (per-game
  chart), Line Study (under% by opening line vs 52.4% breakeven), Ledger (3-way
  market/model/you), Research (model_runs/calibration), writable My Picks
  (`POST /api/picks`). Score-color thresholds + chip logic live in `web/lib/score.ts`
  (ported from `model/score.py`; keep the two in sync). API routes read the same SQL
  the page loaders use; the app is locked by `middleware.ts` + `APP_PASSWORD` cookie.
- **Design system**: plain-English copy + a modern sportsbook look in
  `web/app/globals.css` — deep-navy canvas, electric-cyan brand accent, Archivo display
  font, reusable `.bv-card`/`.bv-pill`/`.bv-stat`/`.bv-table`/`.bv-btn`/`.bv-nav-link`
  classes. **Green/red are reserved for under/over outcomes** — never use them as a UI
  accent (cyan is the brand). `MainNav.tsx` gives the active-route highlight.
- **Dev**: `web/.env` `DATABASE_URL` points at Neon (prod) or the local sim PG
  (`simulate_week.py`); the Neon line is commented as a fallback. Neon is unreachable
  from the campus/fgcu network — use the sim there. `npm run lint` / `npm run format`
  before committing. Deploy is automatic from `main` (Vercel).

## Gotchas
- Features must stay **leak-free** (only pre-kickoff info; season-to-date shifted).
- Numeric model columns must be clean floats (NaN, never `pd.NA`/None/bool) — see
  `features.build_feature_frame` coercion; `bool(NaN)` is `True` (bit us on dome).
- ESPN/TeamRankings/**DraftKings** are **unofficial** — keep isolated in `sources/`,
  fail-silent. DK's hidden API returns **403 without browser-like headers** (set in
  `draftkings.py::_HEADERS`); the host, operator key (`dkusoh`) and league id (`87637`)
  drift — if capture goes empty mid-season, re-discover the `leagues/{id}` XHR in
  DevTools. Schema is `events`/`markets`/`selections` (the old `eventgroups` endpoint
  is dead). The default payload carries only main full-game markets (1H totals post
  later via a subcategory query), which is exactly the Sunday opener we want.
- **Neon is UNREACHABLE from the campus/fgcu network** (port 5432 TLS data filtered;
  HTTPS/443 works). So **Neon-writing scheduled jobs run in GitHub Actions**
  (`.github/workflows/sunday.yml` cron + `bootstrap.yml` one-time), not local launchd.
  **DK's API 403s GHA datacenter IPs** (confirmed), so the cloud job uses
  `poll_full_game --source auto` → **CFBD /lines fallback** (`sources/cfbd_lines.py`,
  reliable but less fresh than DK; DK only works from the Mac, which can't write Neon).
  Local jobs degrade gracefully via `store.try_init_db` (logs "unreachable", exits 0).
  The Sunday iMessage stays local + notify-only (`scripts/notify_sunday.py` +
  `deploy/com.beatvegas.sunday-notify.plist`). Secrets `DATABASE_URL`/`CFBD_API_KEY`/
  `ODDS_API_KEY` are set as GH secrets. Pushing `.github/workflows/` needs the gh
  `workflow` token scope.
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
