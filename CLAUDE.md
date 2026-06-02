# Beat Vegas — project brief for Claude Code

College football **first-half (1H) unders** research & decision-support system.
Research only — it never places bets or automates gambling.

## How to resume / orient (read this first)
- Full design + history: `~/.claude/plans/i-have-a-strong-tingly-reddy.md` (see
  ADDENDUMs 1–5; **ADDENDUM 5 is the active deploy plan**).
- Long-term memory (decisions, status) auto-loads from this project's memory dir.
- **Current phase: B** — build the Next.js web app (see "Resuming Phase B" below).

## What it does
Pulls free data (CFBD, TeamRankings tempo, Open-Meteo weather, The Odds API 1H
totals), derives ground-truth 1H points, builds leak-free features, scores each
upcoming game 0–100 for under value, tracks line movement, sends iMessage alerts,
and grades market vs model vs the user's own picks.

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
pytest -q                            # 56 tests
```
Key scripts: `backfill.py`, `backfill_enrichment.py` (pace/weather), `weekly_update.py`
(score), `poll_lines.py` (lines + alerts), `grade.py`, `pick.py`, `line_study.py`,
`retrain.py`, `seed_demo.py`. Streamlit: `streamlit run beatvegas/dashboard/app.py`
(point at demo with `BEATVEGAS_DB=data/demo.db`).

## Honest status of the edge (don't oversell)
- Backtest is **proxy-graded** (no free historical 1H lines; uses 0.52×full-game
  total). Real lines collected going forward are the true test.
- Top-20% model picks: ~**53.7% under / +2.45% ROI** (2018–25) after pace+weather
  were backfilled into the model. **Pace + weather carry the signal**;
  situational/returning were flat (kept as display chips only).
- Edge is **decaying** recently (57–59% in 2018–21 → ~50% in 2023–25). Marginal,
  unconfirmed. The system's job is to *measure* it honestly, not to promise profit.

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
- `config.yaml` (keys + phone) and `data/*.db|*.log|cache/` are gitignored — keep it that way.
