# Beat Vegas

Research & analysis system for **college football full-game + first-half (1H)
unders**, built around **Hard Rock Bet** (the only book bettable from Florida).
It pulls the week's slate + news, captures Hard Rock vs the rest of the market,
logs your bets, and reviews each week (market vs model vs you, with CLV). Decision-support — you pick the games.

> **Research / decision-support only.** This project never places bets and never
> automates any gambling activity. It exists to inform your own decisions.

## Status (honest)

**No edge is confirmable on free historical data.** No free source carries
*historical* first-half lines, so the backtest grades against a **proxy** 1H line:
a step share of the full-game total — **0.4975 below a 21-point spread, 0.5375 at
21+** — fitted MAE-optimally on FBS-vs-FBS games (`data/multiplier.json`,
`scripts/derive_multiplier.py`). Against that fair proxy, blanket *and*
model-selected 1H unders show no confirmed edge. (The 52.4% figure you will see on
the Line Study page is the **-110 breakeven** win rate — a different thing from any
first-half share.) The true edge, if any, lives in the gap between the **real** 1H
line and actual results, so the season's job is to collect real Hard Rock lines and
measure closing-line value (CLV). See `docs/BETTING_POLICY.md`.

**The product: the "BV line" (make our own number first).** We don't assume Vegas
is soft (that thesis was refuted). A **market-blind** regressor projects an
independent 1H total (`beatvegas/model/bv_line.py`); the board ranks games by the
**gap** to the real Vegas line, and the This Week page turns the gap + Hard Rock's
price into a plain-English BET / WATCH / PASS verdict (`web/lib/verdict.ts`). The
BV line is noisy (σ ≈ 12 pts on any single game), so gates are in points from the
validated top-20% ranking rule (≥ 1.75), never in σ. Full write-up: `docs/BV_LINE.md`.

Components: CFBD REST client (`sources/cfbd.py`), 1H points ETL (`etl/first_half.py`),
leak-free features (`etl/features.py`), walk-forward backtest (`backtest/engine.py`),
The Odds API client for `totals_h1` (`sources/odds.py`), event→game matcher
(`etl/match.py`), line poller with movement dedupe (`scripts/poll_lines.py`),
open/close grading + CLV ledger (`scripts/grade.py`, `beatvegas/grading.py`).

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .                 # installs all deps from requirements.txt
cp config.example.yaml config.yaml   # CFBD key (free: https://collegefootballdata.com/key)
                                     # + Odds API key (free: https://the-odds-api.com/)
pytest -q                            # or, inside a git worktree: PYTHONPATH=. python -m pytest -q
```

Keys can also come from the environment (`CFBD_API_KEY`, `ODDS_API_KEY`,
`DATABASE_URL`). `config.example.yaml` is what production reads for
`odds_api.regions` (GitHub Actions has no `config.yaml`) — treat it as prod config.

## Run (by hand)

```bash
python scripts/backfill.py --season 2026                 # schedule + finals
python scripts/enrich_tempo.py --season 2026 --week 5    # TeamRankings pace
python scripts/enrich_weather.py --season 2026 --week 5  # Open-Meteo weather
python scripts/poll_full_game.py --source oddsapi        # full-game openers (prod source)
python scripts/poll_lines.py                             # 1H totals + movement
python scripts/weekly_update.py                          # score + rank the board
python scripts/grade.py --season 2026                    # grade unders vs real close + CLV
python scripts/backtest.py                               # the proxy-graded edge gate
```

Data lands in Neon when `DATABASE_URL` is set, else `data/beatvegas.db`
(gitignored). Every script is idempotent.

**Log your own bets** (graded vs the same real lines, so your intuition is
measured next to the market):
```bash
python scripts/pick.py add --home "Ohio State" --away "Michigan" --line 24.5 --market 1h
python scripts/pick.py grade --season 2026     # after games finish
python scripts/pick.py summary                 # your hit rate, units, CLV
```

**Line Study** — how often the under cashed by opening-line value (real opening
lines where captured, else proxy):
```bash
python scripts/line_study.py --season 2025 --min-games 40 --highlight 24.5
```

**Credit budget (Odds API paid tier, 100K/month since 2026-09-06):** `totals_h1` is
served only per-event, but naming our ten books (`odds_api.bookmakers_1h`) is billed
as ONE region and overrides `regions`, so a 1H poll costs **1 credit per game**
(it was 2 on `us,us2`); listing events is free; full-game totals are one bulk call
priced per region, which is why the bulk pull still uses `regions`.
`poll_lines.py` captures EVERY Hard Rock-priced game (`--hr-universe`): opener
sweeps stop paying for a game once its Hard Rock 1H line is in (`--missing-hr-only`),
per-game closes poll only games kicking off within 75 minutes
(`--kickoff-within-min`), `--max-credits-per-run` is the runaway guard and
`--credit-floor` the month-end reserve. Expected **~567 credits/week (~2,450/month),
worst ~774** across four whole-week builds and the per-game closes, on a basis of 82
Hard Rock-priced games (budget comment in `.github/workflows/lines_watch.yml`).

## How it runs

Nothing runs on the Mac on a schedule. The engine runs in **GitHub Actions**
(`.github/workflows/`, secrets `DATABASE_URL` / `CFBD_API_KEY` / `ODDS_API_KEY`)
because the campus network cannot reach Neon:5432. Failures: GitHub emails every
failed run, and the board itself carries the stale-results and missed-build banners
(`web/lib/boardHealth.ts`) — since 2026-09-13 nothing texts.
GitHub cron is best-effort (it drops most single-slot runs), so a Vercel cron is the
primary trigger, each job has retry slots, and the card job runs any missing input
itself before it builds.

| When (ET)                          | Workflow / routine     | What                                                                 |
| ---------------------------------- | ---------------------- | -------------------------------------------------------------------- |
| Sun 2pm / 3pm / 4:30pm             | `sunday.yml`           | Openers (multi-book incl. exchanges) → pace + weather → score → derived 1H lines |
| Tue / Fri 9am                      | `research_preview.yml` | News + injuries / QB-out → This Week cards                              |
| Tue / Thu ~4:05pm (ET-gated 3:45–5:15) | `card.yml` slots `tue_pm` / `thu_pm` | Full 1H sweep of the rolling week + injury refresh → FINAL card → paper-log the qualifying games kicking off before the next build (48 h / 24 h), each with its blocker |
| Fri ~4:05pm (ET-gated 3:45–5:15)   | `card.yml` slot `fri_pm` | The decision build for the weekend: same sweep, and it paper-logs the REST OF THE WEEK — 78% of Hard Rock's 1H lines are up by Friday afternoon and they barely move afterwards |
| Sat ~8:05am (ET-gated 7:45–9:15)   | `card.yml` slot `sat_am` | Same whole-week sweep before the morning sitting; also on the rest of the week, but Friday has priced most of it, so it logs only what newly qualifies |
| Every 30 min, evenings + all Saturday | `lines_watch.yml`   | Per-game Hard Rock 1H closes ~30–75 min before each kickoff             |
| Daily 6:30am (retry noon)          | `grade.yml`            | Finals (completed games only) + 1H play-by-play for weeks still missing it → grade market / model / picks / records → post-mortem (2023-25 history only on Monday) |

Manual-only workflows: `post-lines.yml` (derived lines for the board),
`migrate.yml` (additive Neon schema), `backfill_1h.yml` (paid historical 1H lines),
`enrich_tempo.yml` (re-backfill pace). Dispatch any workflow from the Mac with
`gh workflow run <file> --ref main` (add `-f market=1h|1h_close` for
`lines_watch.yml`).

## Web app (Next.js → Vercel + Neon)

The product is the Next.js app in `web/` (App Router + TypeScript + Tailwind +
Prisma + Recharts), deployed on **Vercel**, reading/writing **Neon Postgres**,
behind a simple password gate, at **https://beat-vegas.vercel.app**. Four tabs:
**Board** (the home page — every game with a Hard Rock total in one ranked list, an
edge score 0-100, a BET / EDGE / PASS tier, one line saying what to do, and cards that
expand into the lines, the model, the reasons and the news), **Results** (market /
model / your-picks ledgers with CLV plus the bankroll curve), **Research**
(calibration, gap-vs-CLV, model runs), **Glossary**. Plain-English,
modern-sportsbook design system (deep navy + electric-cyan accent; `.bv-*` classes
in `web/app/globals.css`).

**Architecture:** Neon Postgres is the single source of truth. GitHub Actions writes
it; the Vercel app reads it and writes manual picks. `web/lib/*.ts` hold the
SQL/scoring logic; API routes under `web/app/api/` mirror those queries.
`GET /api/health` (ungated, aggregate timestamps only) tells the Sunday routine
whether today's opener capture landed.

### Local dev
```bash
cd web
npm install
npm run dev            # http://localhost:3000
npx vitest run         # tests
```
`web/.env` holds `DATABASE_URL` (gitignored): Neon (prod data) or the local
Postgres sandbox from `scripts/simulate_week.py` (use this on the campus network,
which cannot reach Neon). Leave `APP_PASSWORD` unset locally to keep the gate off.

### Deploy loop
1. Edit code in `web/`, `npm run lint` / `npm run format`, test with `npm run dev`.
2. Commit and **push to `main`** → Vercel auto-builds and deploys production in
   ~1 minute. Any other branch makes a Preview URL, not production.
3. Live env vars (Vercel → Settings → Environment Variables): `DATABASE_URL`
   (Neon), `APP_PASSWORD`, `BANKROLL_USD`, `UNIT_USD`.

**Gotchas:**
- **Commit author must be GitHub-linked.** Vercel blocks deploys whose commit
  author email isn't tied to the repo's GitHub account (`git config user.email`).
- **Schema changes start in Python** (it owns the SQLAlchemy schema): edit
  `beatvegas/db/models.py` + `_MIGRATIONS`, run `migrate.yml`, then
  `cd web && npx prisma db pull && npx prisma generate`, then push.

## Data sources (all free)
- **CollegeFootballData** — games, line scores, play-by-play, advanced stats, SP+, full-game lines, venues
- **The Odds API** — full-game totals (bulk) and first-half totals (per event); Hard Rock via region `us2`, no-vig exchanges via `us_ex` (price comparison only)
- **TeamRankings** — tempo (seconds/play); unofficial, fail-silent
- **Open-Meteo** — weather forecasts by venue
- **Rotowire** (injuries) + **ESPN** (news) — unofficial, display-only, never a model input

## Free enrichments
- **Situational** (`etl/situational.py`): rest, short week, off-bye, travel distance,
  time-zone shift, kickoff hour — model features + a "Spot" card chip.
- **Returning production** (CFBD `/player/returning`): roster-churn prior + chip.
- **Historical pace** (`scripts/backfill_enrichment.py`): backfills TeamRankings
  tempo so it feeds the model.
  ```bash
  python scripts/backfill_enrichment.py --start 2018 --end 2025
  ```
- **Weather** (`scripts/backfill_weather.py`): Open-Meteo into `weather_obs`, one
  call per venue-season, resumable. Two kinds of row, never interchangeable:
  `lead_hours = 0` is the near-kickoff series (tracks what actually happened —
  good for modelling, **never** for a market-edge claim), and `lead_hours = 24/72`
  is the forecast that genuinely existed that far ahead. Only the latter carries
  `decision_safe = true`.
  ```bash
  python scripts/backfill_weather.py --start 2023 --end 2026 --leads 0,24,72
  python scripts/backfill_weather.py --promote          # staging file -> weather_obs
  ```
  (Slow — ~90 min for the full range; safe to re-run, resumes from the staging file.)

Pace + weather were the only inputs that moved 1H-total prediction error;
situational/returning were flat (kept as context). All of it is still proxy-graded
until real lines accrue.

## Methodology note
Free sources have **no historical 1H betting line**. The backtest therefore grades
actual 1H points (from CFBD) against the calibrated step-share proxy described
above and stress-tests across a ±1.5 pt band. Real 1H lines are collected every
week of the season to validate — or kill — the proxy.
