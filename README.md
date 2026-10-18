# Beat Vegas

Research & analysis system for **college football first-half (1H) unders**, built
around **Hard Rock Bet** (the only book bettable from Florida). Full-game lines are
captured and graded as a reference market; real money is 1H unders only.
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
model-selected 1H unders show no confirmed edge. (52.4% is the **-110 breakeven** win rate — a
different thing from any first-half share.) The true edge, if any, lives in the gap between the **real** 1H
line and actual results, so the season's job is to collect real Hard Rock lines and
measure closing-line value (CLV). See `docs/BETTING_POLICY.md`.

**The 2026 season is the measurement.** Hard Rock's first-half lines are captured in
four whole-week builds (Tue / Thu / Fri / Sat); every game that clears the rule is logged
on paper and graded at Hard Rock's close; from week 3 the paper record runs under a
pre-registered stopping rule (`docs/STOPPING_RULE.md`) whose failure boundary pauses real
money. Every test ever run on the data has a row in `docs/HYPOTHESES.md`. The 2023-25
first-half closes were bought from the Odds API history in September 2026 (1,902 real
closes), so the backtest grades at real closes where they exist — and that set is treated
as spent for exploration.

**The product: the "BV line" (make our own number first).** We don't assume Vegas
is soft (that thesis was refuted). A **market-blind** regressor projects an
independent 1H total (`beatvegas/model/bv_line.py`); the board ranks games by the
**gap** to the real Vegas line, and the board and each game page turn the gap + Hard
Rock's price into a plain-English Bet / Watch / Pass verdict (`web/lib/verdict.ts`). The
BV line is noisy (σ ≈ 12 pts on any single game), so gates are in points from the
top-20% ranking rule, read per slate (the k-th largest gap; 1.75 only on an empty slate),
never in σ. Full write-up: `docs/BV_LINE.md`.

Components: CFBD REST client (`sources/cfbd.py`), 1H points ETL (`etl/first_half.py`),
leak-free features (`etl/features.py`), the registered-arm reader (`beatvegas/protocol.py`),
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
```

Data lands in Neon when `DATABASE_URL` is set, else `data/beatvegas.db`
(gitignored). Every script is idempotent.

**Your own bets** are logged on the site (the game page's log button, where every
policy gate runs); paper picks are written by the card build only. From the terminal:
```bash
python scripts/pick.py grade --season 2026     # after games finish
python scripts/pick.py summary                 # your hit rate, units, CLV
```

**Line Study** — how often the under cashed by opening-line value (real opening
lines where captured, else proxy). Research-only since roadmap v2.0 (the site's research
section was removed 2026-10-11); the CLI is the full version:
```bash
python scripts/archive/line_study.py --season 2025 --min-games 40 --highlight 24.5
```

**Credit budget (Odds API 20K plan, $30/month, since 2026-10-05; 100K Sep 6 - Oct 5 for the history purchase):** `totals_h1` is
served only per-event, but naming our ten books (`odds_api.bookmakers_1h`) is billed
as ONE region and overrides `regions`, so a 1H poll costs **1 credit per game**
(it was 2 on `us,us2`); listing events is free; the full game is one bulk call
priced per region (`totals,spreads,h2h` x `us,us2,us_ex` = 9 credits for the whole
slate), which is why the bulk pull still uses `regions`.
`poll_lines.py` captures EVERY Hard Rock-priced game (`--hr-universe`): opener
sweeps stop paying for a game once its Hard Rock 1H line is in (`--missing-hr-only`),
per-game closes poll only games kicking off inside the 120-minute close
look-ahead (`--kickoff-within-min`, `CLOSE_LOOKAHEAD_MIN` in `lines_watch.yml`), `--max-credits-per-run` is the runaway guard and
`--credit-floor` the month-end reserve. Expected **~567 credits/week (~2,450/month),
worst ~774** across four whole-week builds and the per-game closes, on a basis of 82
Hard Rock-priced games, plus **~200/week (~860/month)** since 2026-10-07 for every
book's full-game spread and moneyline (with prices) and the exchanges on the
Sunday opener, the card-day refresh and every close tick: **~3,300/month** of 20K
(budget comment in `.github/workflows/lines_watch.yml`).

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
| Tue / Thu ~4:05pm (ET-gated 3:45–5:15) | `card.yml` slots `tue_pm` / `thu_pm` | Full 1H sweep of the rolling week + injury refresh → FINAL card → paper-log the qualifying games kicking off before the next build (48 h / 24 h), each with its blocker |
| Fri ~4:05pm (ET-gated 3:45–5:15)   | `card.yml` slot `fri_pm` | The decision build for the weekend: same sweep, and it paper-logs the REST OF THE WEEK — 78% of Hard Rock's 1H lines are up by Friday afternoon and they barely move afterwards |
| Sat ~8:05am (ET-gated 7:45–9:15)   | `card.yml` slot `sat_am` | Same whole-week sweep before the morning sitting; also on the rest of the week, but Friday has priced most of it, so it logs only what newly qualifies |
| Hourly Tue–Fri evenings + all Saturday (Vercel), every 30 min backup crons | `lines_watch.yml` | Per-game closes inside a 2 h look-ahead (6 h on Saturday ticks): 1H, and full-game totals, spreads and moneylines |
| Mon 6am–3pm ET (12Z, 15Z retry, 18Z catch-up) | `pricing_monday.yml` | The read-only pricing report (H-PRICE-HR, rule `pv1`): run Summary + `pricing-report` artifact |
| Daily 6:30am (retry noon)          | `grade.yml`            | Finals (completed games only) + 1H play-by-play for weeks still missing it → grade market / model / picks / records → post-mortem (2023-25 history only on Monday) |

Manual-only workflows: `migrate.yml` (additive Neon schema), `backfill_1h.yml` (paid historical 1H lines),
`history_load.yml` (2003-22 games + Elo, study-only), `backfill_intercept.yml`,
`enrich_tempo.yml` (re-backfill pace), `weather_backfill.yml` (Open-Meteo into
`weather_obs`), `rescore.yml` (re-score a played week without freezing records), `study.yml`
(every registered study; the report artifact is the deliverable). Dispatch any workflow from the Mac with
`gh workflow run <file> --ref main` (add `-f market=1h|1h_close` for
`lines_watch.yml`).

## Web app (Next.js → Vercel + Neon)

The product is the Next.js app in `web/` (App Router + TypeScript + Tailwind +
Prisma + Recharts), deployed on **Vercel**, reading/writing **Neon Postgres**,
readable by anyone with the link (the password is only needed to log picks), at
**https://beat-vegas.vercel.app**. Three tabs
plus a game page: **Board** (the home page — one rolling week grouped by day, every
game with a Hard Rock total ranked best to worst, a Bet / Watch / Pass word and one
line saying what to do; each row links to **`/game/[id]`**, where the decision, the
lines, the reasons and the news live), **Record** (`/results`, since 2026-10-18: the
paper strategies' forward picks with their value against the close, the pricing
study's forward opportunities, the season comparison), **Research** (`/research`, since 2026-10-14: one
card per registered hypothesis from the stored Monday read, the protocol in plain words, the closed
hypotheses with their verdicts, how to read the Board, the terms; `/how-it-works` redirects here); `/records` is
every rated game by week, with a CSV). Plain-English,
modern-sportsbook design system (deep navy + electric-cyan accent; `.bv-*` classes
in `web/app/globals.css`).

**Architecture:** Neon Postgres is the single source of truth. GitHub Actions writes
it; the Vercel app only reads it (a read-only research record since 2026-10-18: no
login, no write route). `web/lib/*.ts` hold the SQL/scoring logic; the API routes
under `web/app/api/` are `/api/records` (CSV), `/api/health` and `/api/cron/[job]`.
`GET /api/health` (public: flags, coverage, budgets, dispatch times and verdicts) is
what the smoke check and the ship skill read after a deploy.

### Local dev
```bash
cd web
npm install
npm run dev            # http://localhost:3000
npx vitest run         # tests
```
`web/.env` holds `DATABASE_URL` (gitignored): Neon (prod data) or the local
Postgres sandbox from `scripts/simulate_week.py` (use this on the campus network,
which cannot reach Neon). There is no password: the site is read-only.

### Deploy loop
1. Edit code in `web/`, `npm run lint` / `npm run format`, test with `npm run dev`.
2. Commit and **push to `main`** → Vercel auto-builds and deploys production in
   ~1 minute. Any other branch makes a Preview URL, not production.
3. Live env vars (Vercel → Settings → Environment Variables): `DATABASE_URL`
   (Neon), `CRON_SECRET`, `GITHUB_DISPATCH_TOKEN`.

**Gotchas:**
- **Commit author must be GitHub-linked.** Vercel blocks deploys whose commit
  author email isn't tied to the repo's GitHub account (`git config user.email`).
- **Schema changes start in Python** (it owns the SQLAlchemy schema): edit
  `beatvegas/db/models.py` + `_MIGRATIONS`, run `migrate.yml`, then
  hand-add the new columns to the curated `web/prisma/schema.prisma` (never commit a full
  `prisma db pull`: the Neon database is shared), `npx prisma generate`, then push.

## Data sources
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
- **Observed weather for the history looks** (`scripts/backfill_weather_actuals.py`;
  its workflow was retired 2026-10-18, final-2026 D5): ERA5 hourly around each kickoff plus CFBD's one reading per
  game, 2013-2026, into the study-only `weather_actuals` table (`docs/WEATHER.md` §7).
  Never decision-safe, never a model input.

Pace was the one enrichment that moved 1H-total prediction error;
situational/returning were flat (kept as context). **Weather is an open hypothesis,
not a finding**: every historical weather value was mis-timed until 2026-09-14
(`docs/WEATHER.md`), so the earlier "weather helped" read was measured on the wrong
hours and is withdrawn. The corrected data sits in `weather_obs`, which the model
does not read until a pre-registered test says it should. All of it is still
proxy-graded until real lines accrue.

## Methodology note
Free sources have **no historical 1H betting line**. The backtest therefore grades
actual 1H points (from CFBD) against the calibrated step-share proxy described
above and stress-tests across a ±1.5 pt band. Real 1H lines are collected every
week of the season to validate — or kill — the proxy.
