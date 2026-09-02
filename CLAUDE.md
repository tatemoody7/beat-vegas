# Beat Vegas — project brief for Claude Code

College football **full-game + first-half (1H) unders** research & decision-support
system, focused on **Hard Rock Bet** (the only book bettable from Florida).
Research only — it never places bets or automates gambling.

## Current state (read this, then the pointers — don't restate history from memory)
- **2026-09-01 (week-1 audit, PRs #23-#26):** landing page `/` is the plain-English
  **This Week** verdict page (BET / WATCH / PASS + why + bankroll strip,
  `web/lib/verdict.ts`); the ranked board moved to `/board`. Betting rules live in
  `docs/BETTING_POLICY.md` ($100 roll, $10 flat units, ≤5 bets/wk, 1H unders only).
  **Gates are in POINTS from the validated top-20%-by-gap rule (≥1.75 pts) — never
  σ:** `bv_sigma` ≈ 12 pts is per-game outcome noise, so a 1σ gap never occurs.
  Paper picks (`manual_picks.is_paper`, stake forced 0) sit apart from the real
  ledger. Sunday job now refreshes pace/weather before scoring; Monday job refreshes
  1H PBP and grades `game_records` + the factor ledger. The model cannot score
  weeks 1–2 (needs 2 games/team) — by design. **Florida platforms (verified
  2026-09-01):** Hard Rock Bet is still the only sportsbook; "FanDuel in Florida"
  = FanDuel Predicts (CFTC prediction market), not a sportsbook. Exchanges
  (Kalshi/Novig/ProphetX/BetOpenly, Odds API `us_ex`) are captured on the Sunday
  full-game poll only as a no-vig PRICE-COMPARISON source (`web/lib/books.ts`
  `EXCHANGE_KEYS`) — never bet there (no 1H totals). See `docs/BETTING_POLICY.md`.
- **What ships today:** decision-support for **full-game + 1H unders on Hard Rock Bet** (the only FL book). The model number is a reference chip, not a pick gate; the edge is *measured* via CLV, not promised (full-game backtest found no edge on the thin 2023-25 regime).
- **2026-07-17 (review closed):** the pre-season readiness review is fully worked
  off — blockers (PR #16), 13 should-fixes (PR #17), and the remainder (S8 strict
  pick matching, S15 postseason capture, S16 multiplier margin gate — fitted curve
  REVERTED to flat 0.52, S17-S19, S21-S22, nits). Accepted as-is: GHA cron lag
  (S20), sunday.yml DST double-fire (N12), ntfy alt path (N13), plaintext local
  keys (N14), no login rate limit (store-less). Odds API totals rows carry no
  spread by design (spreads market would double credits).
- **2026-07 (Hard Rock pivot, PRs #7-#9):** multi-book capture incl. Hard Rock via The Odds API (`hardrockbet`, FL-specific `hardrockbet_fl`); Pushover push alerts; web views `/preview`, `/line-check`, `/weekly-review`; both markets logged + graded (`manual_picks.market`, `market_fg` ledger). Before season: set Pushover config + GH secrets, `odds_api.regions: "us,us2"`.
- **2026-06 (cloud + board):** Neon-writing jobs run in GitHub Actions, not launchd (campus network can't reach Neon:5432; DK 403s GHA IPs → CFBD `/lines` fallback). Derived-1H lines post to the board as "DERIVED · no model pick"; board query is season-scoped.
- **2026-05 (opener capture):** Sunday DK full-game opener via free hidden API + gated spread-adjusted 1H multiplier (`data/multiplier.json`; absent = flat 0.52). Next.js on Vercel is the product (Streamlit removed).
- **2026-09-02 (FBS-only training):** the `games` table holds every CFBD game incl.
  FCS/D2/D3, and from 2022 CFBD carried lines for FCS games, so ~40% of trainable
  rows in 2022-25 had no FBS team. `etl/fbs.py` + git-tracked `data/fbs_teams.json`
  (per-season CFBD `/teams/fbs`, refresh each August via `scripts/fetch_fbs_teams.py`)
  now filter training/backtest/scoring to FBS-vs-FBS. Like-for-like on demo.db
  (2015-25, flat-0.52 proxy): gbm_v2 top-20% 53.9%/+2.9% → **55.7%/+6.3%**, 7 of 8
  seasons profitable (2018 the loser). Still proxy-graded: realized FBS 1H share is
  ~0.51, so the 0.52 proxy flatters unders; proxy re-fit is a separate open item.
  Details: `research/swarm/2026-09-01-1h-under-edges/FBS_FILTER_RESULTS.md`.
- **2026-09-02 (fair proxy):** `data/multiplier.json` is now a STEP share fitted
  MAE-optimally on FBS-vs-FBS games with spreads (2023-25): **0.4975 of the total
  below a 21-pt spread, 0.5375 at 21+** (walk-forward MAE 8.289 vs 8.347 flat,
  cleared the 0.05 gate in `derive_multiplier.py`). The mean 1H ratio is ~0.52 but
  the MEDIAN game lands near half the total, which is what books post. Against this
  fair proxy the proxy-graded edge disappears: gbm_v2 top-20% = 50.2% / -4.1% on
  2023-25 (was 58.5% / +11.6% at flat 0.52) and 52.7% / +0.6% on 2015-25. The old
  54-56% reads were the flat-0.52 artefact. The model is a reference number; only
  real-line CLV can show an edge. Details: `research/swarm/2026-09-01-1h-under-edges/PROXY_FIX_RESULTS.md`.
- **Engine:** market-blind 1H-total regressor ranks the board by line-vs-prediction gap (`score_slate`, gbm_v2). Proxy-graded selection stats are no longer quoted as an edge (see fair-proxy note above); 117-factor framework in `beatvegas/factors/`.
- **History & details live in:** git log + PR descriptions, `docs/` (`PIVOT.md`, `BV_LINE.md`), `~/.claude/plans/`, and this project's memory dir (auto-loads). Read those instead of reconstructing from this file.

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
pytest -q                            # 226 tests (plus 32 vitest in web/)
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
the real Next.js app, Neon-isolated). 226 tests. **Lint/format**: `ruff check` + `ruff
format` for Python (`[tool.ruff]` in `pyproject.toml`, pragmatic F/E/I/B set — NOT pyupgrade,
which would break the py3.9 runtime); `npm run lint` + `npm run format` in `web/`
(ESLint flat config via Next 16's native arrays + Prettier).

## Honest status of the edge (don't oversell)
- Backtest is **proxy-graded** (no free historical 1H lines). The proxy is the
  step share in `data/multiplier.json` (~0.50 of the total, 0.54 in 21+ blowouts),
  fitted on FBS-vs-FBS games. Real Hard Rock/DK lines collected forward are the true test.
- **Predict-total engine (gbm_v2) shows NO proxy-graded edge against the fair proxy**
  (top-20% by gap 50.2% / -4.1% on 2023-25; 52.7% / +0.6% on 2015-25). The earlier
  54.0% / +3.0% and 55.7% / +6.3% figures were graded against a flat 0.52 line that
  sits ~1 pt above fair and flattered every under selection.
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
