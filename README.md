# Beat Vegas

Research & analysis system for **college football first-half (1H) unders**. It
identifies, scores, and ranks the best 1H-under opportunities each week and
tracks line movement over time.

> **Research / decision-support only.** This project never places bets and never
> automates any gambling activity. It exists to inform your own decisions.

## Status

**Phase 1 (edge gate) — done. Verdict: no edge confirmable on free historical data.**
Across 10 seasons (9,492 games) first halves realize ~52.4% of the full-game
total — right where books price the 1H line. Blanket *and* model-selected 1H
unders do not reliably beat the -110 breakeven, and the apparent signal is
inside the ±1.5 pt uncertainty of the synthetic proxy line. See
`beatvegas/backtest/` and the `scripts/backtest.py` output.

**Why:** no free source has *historical* first-half lines, so the backtest can
only grade against a proxy. The true edge (if any) lives in the gap between the
real 1H line and actual results — invisible to a proxy.

**Phase 2 (current) — collect REAL 1H lines going forward and grade them.**
Built & tested:
- The Odds API client + normalizer for `totals_h1` (`beatvegas/sources/odds.py`)
- Event→CFBD game matcher (`beatvegas/etl/match.py`)
- Line poller with movement dedupe (`scripts/poll_lines.py`)
- Consensus open/close grading + CLV ledger (`scripts/grade.py`, `beatvegas/grading.py`)

This is the path that can actually prove or kill the edge, starting when lines
post for the season.

### Earlier Phase 1 components
- CFBD REST client (`sources/cfbd.py`), 1H points ETL (`etl/first_half.py`)
- Historical backfill (`scripts/backfill.py`)
- Leak-free features (`etl/features.py`), proxy calibration (`etl/proxy_line.py`)
- Walk-forward backtest (`backtest/engine.py`)

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .                 # installs all deps from requirements.txt
```

Get a **free** CFBD API key at https://collegefootballdata.com/key, then either:

```bash
cp config.example.yaml config.yaml   # put the key in cfbd.api_key
# or:
export CFBD_API_KEY=your_key_here
```

## Run

```bash
python scripts/backfill.py                 # load seasons from config (2015–2024)
python scripts/backfill.py --season 2023   # one season
python scripts/backfill.py --use-pbp       # fill 1H gaps via play-by-play
python scripts/backtest.py                 # the edge gate (walk-forward)
pytest -q                                  # tests
```

Data lands in `data/beatvegas.db` (gitignored). The backfill is idempotent.

### In-season real-line workflow (Phase 2)
Needs a free Odds API key (https://the-odds-api.com/) in `config.yaml`
(`odds_api.api_key`) or `ODDS_API_KEY`.

```bash
python scripts/backfill.py --season 2026          # load schedule/games
python scripts/enrich_tempo.py --season 2026 --week 5    # TeamRankings pace
python scripts/enrich_weather.py --season 2026 --week 5  # Open-Meteo weather
python scripts/poll_lines.py                      # 1–2x/day: capture 1H totals + movement + alerts
python scripts/poll_lines.py --dry-run-alerts     # print alerts instead of texting
python scripts/backfill.py --season 2026           # re-run after games for actual 1H pts
python scripts/grade.py --season 2026              # grade unders vs real closing line + CLV
```

**Log your own bets** (graded vs the same real lines, so your intuition is
measured next to the market):
```bash
python scripts/pick.py add --home "Ohio State" --away "Michigan" --line 24.5
python scripts/pick.py grade --season 2026     # after games finish
python scripts/pick.py summary                 # your hit rate, units, CLV
```

**Line Study** — rank how often the under cashed by opening-line value (tests
"which line number hits most"); real opening lines where captured, else proxy:
```bash
python scripts/line_study.py --season 2025 --min-games 40 --highlight 24.5
```

**Dashboard** (opportunity board, line-movement charts, Line Study, market +
your-picks ledger with CLV, research verdict):
```bash
streamlit run beatvegas/dashboard/app.py
```

**Credit budget (free tier = 500/month):** `totals_h1` is an Odds API
*additional market*, served only per-event. `poll_lines.py` lists events for
free, then spends **1 credit per game that has a 1H total posted**, but only for
games kicking off within `--days-ahead` (default 8). Games with no posted 1H
market cost 0 credits. A ~10-game Saturday slate polled daily for its game-week
≈ well under 500/month. Widen/narrow with `--days-ahead` and `--max-events`.

## Web app (Next.js → Vercel + Neon)

The product face is a Next.js app in `web/` (App Router + TypeScript + Tailwind +
Prisma + Recharts), deployed on **Vercel**, reading/writing a **Neon Postgres**
database, behind a simple password gate. Views: Opportunities, Line Study,
Movement, Ledger, Research, and writable My Picks. The Streamlit dashboard
remains for local quick-views; it is not deployed.

**Architecture:** Neon Postgres is the single source of truth. The local Python
engine (`run_daily.sh` etc.) writes to Neon; the Vercel app reads it and writes
manual picks. `web/lib/*.ts` port the Streamlit SQL/scoring; API routes under
`web/app/api/` mirror those queries.

### Local dev
```bash
cd web
npm install
npm run dev            # http://localhost:3000
```
`web/.env` holds `DATABASE_URL` (gitignored). It currently points at **Neon**, so
what you see locally is the live production data — and Postgres-specific issues
surface *before* you push. Leave `APP_PASSWORD` unset locally to keep the gate
off; set it to require the login. (To dev fully offline, point `DATABASE_URL` at
`file:../../data/demo.db` and set the Prisma datasource `provider` back to
`sqlite`.)

### Deploy loop
1. Edit code in `web/`, test with `npm run dev`.
2. Commit and **push to `main`** → Vercel auto-builds (`prisma generate &&
   next build`) and deploys to production (**https://beat-vegas.vercel.app**) in
   ~1 minute. Pushing any *other* branch makes a Preview URL, not production.
3. Live env vars (Vercel → Settings → Environment Variables): `DATABASE_URL`
   (Neon) and `APP_PASSWORD` (the login).

**Gotchas:**
- **Commit author must be GitHub-linked.** Vercel blocks deploys whose commit
  author email isn't tied to the repo's GitHub account. This repo's git author is
  set to the GitHub noreply email — keep it that way (`git config user.email`).
- **Schema changes start in Python** (it owns the SQLAlchemy schema): edit
  `beatvegas/db/models.py` + migrations, run against Neon, then
  `cd web && npx prisma db pull && npx prisma generate`, then push.
- **Fresh data** (predictions, lines, grades) comes from the local engine writing
  to Neon, which needs a network allowing outbound Postgres (port 5432). Some
  campus/corporate networks let the TCP connect but drop the data path — run the
  daily chain off such networks (home/hotspot). The deployed site is unaffected.

### One-time data migration (SQLite → Neon)
```bash
DATABASE_URL="postgresql://…neon…" python scripts/migrate_to_postgres.py --sqlite data/demo.db --wipe
```

## Data sources (all free)
- **CollegeFootballData** — games, line scores, play-by-play, advanced stats, SP+, full-game lines, venues
- **TeamRankings** — tempo (seconds/play), 1Q/1H scoring (Phase 1 enrichment)
- **Open-Meteo** — weather by venue (Phase 1 enrichment)
- Free odds pages — current-season 1H totals for live tracking (Phase 3)

## Auto-run (set and forget)
A daily job runs the whole chain — refresh data → enrich pace/weather → capture
lines + alert → score the slate → grade market/model/you — so you just open the
dashboard and log picks.

```bash
bash scripts/run_daily.sh --dry-run     # test on demo DB, alerts printed not sent
# install the 8am daily launchd job:
cp deploy/com.beatvegas.daily.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.beatvegas.daily.plist
# stop it later:  launchctl unload ~/Library/LaunchAgents/com.beatvegas.daily.plist
```
Caveats: only runs while the Mac is awake; first run may prompt to allow Messages
automation; logs to `data/run_daily.log`. If a root `.env` with `DATABASE_URL` is
present, the live chain writes to **Neon** (the same DB the Vercel app reads);
otherwise local SQLite. `--dry-run` always stays on `data/demo.db`.

**Weekly loop pieces** (also runnable individually):
`weekly_update.py` (score + log model picks) · `grade.py` (grade market + model) ·
`pick.py grade` (grade your picks) · `retrain.py` (log a model_runs metrics row to
track whether it sharpens as seasons accrue).

## iMessage alerts
`poll_lines.py` texts you when a 1H total is **newly posted** or the consensus
**moves ≥ threshold**, via AppleScript → Messages.app (works unattended; a plain
script can't use MCP). Set the recipient + threshold in `config.yaml`:
```yaml
alerts:
  imessage_to: "you@example.com"   # or your phone number
  line_move_threshold: 1.0
```
First run may trigger a macOS Automation permission prompt for Messages. Use
`--dry-run-alerts` to preview, `--no-alerts` to disable.

## Free enrichments
- **Situational** (`etl/situational.py`): rest, short week, off-bye, travel distance,
  time-zone shift, kickoff hour — model features + a "Spot" card chip.
- **Returning production** (CFBD `/player/returning`): roster-churn prior + chip.
- **News/injuries** (`sources/espn.py`, ESPN hidden API): display-only "📰 News"
  expander on the My Picks tab; fail-silent.
- **Historical pace/weather** (`scripts/backfill_enrichment.py`): backfills
  TeamRankings tempo + Open-Meteo weather so they feed the model.
  ```bash
  python scripts/backfill_enrichment.py --tempo --weather --start 2018 --end 2025
  ```
  (Weather is slow — one ranged call per venue; safe to re-run, idempotent.)

Backtest impact (top-20% of picks, 2018–2025): baseline +0.97% ROI → **+2.45%**
with pace + weather. Pace/weather carried the lift; situational/returning were flat
(kept as context). Still proxy-graded until real lines accrue.

## Methodology note
Free sources have **no historical 1H betting line**. The backtest therefore
grades actual 1H points (from CFBD) against a **calibrated proxy 1H total**
derived from the full-game total, and stress-tests across a ±1.5 pt band. Real
1H lines are collected going forward to validate the proxy.
