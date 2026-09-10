# Beat Vegas — project brief for Claude Code

College football **full-game + first-half (1H) unders** research & decision-support
system, focused on **Hard Rock Bet** (the only book bettable from Florida).
Research only — it never places bets or automates gambling.

## Current state (read this, then the pointers — don't restate history from memory)
- **2026-09-10 (site restructure, branch `board-and-game-page`, NOT merged):** the site
  goes to **three tabs — Board / Results / Track record — plus `/game/[id]`**. A board row
  is now a **LINK**, never a disclosure: `GameCard` is deleted, `GameRow` carries only the
  rank badge, matchup, kickoff, Hard Rock's number and price, one action line, and the two
  chips that change whether to bet (`bet logged`, past the cap). The badge is **rank plus
  colour with no tier word** ("Watch" was true of 35 of 49 games, so it discriminated
  nothing; `ScoreBadge` takes `label={null}`, and still names the tier to screen readers).
  Everything analytical lives on the game page: the decision block with a **gap bar**
  (`GapBar.tsx` — our number against the line on one axis, split at `BET_GAP_PTS`, kill
  number ticked), Lines, What is behind it, Injuries and news. **There is no "Our number"
  section** — Tate cut it as a repeat of the decision block, which also took the 0-100
  score, the confidence meter and the 7-35 range off the page (the score still sets the
  tier and the ranking). An **answer bar** (`AnswerBar.tsx` + pure `lib/answerBar.ts`)
  replaces `BankrollStrip`/`BetSlip`/`CardPanel` at the top of the board and carries the
  live bets, the three closest with the action trimmed to its "needs …" clause, and the
  next build window from `lib/nextBuild.ts` (derived from `CRON_JOBS`, stated as a WINDOW
  because Vercel Hobby fires within the hour). **Nothing renders below the last game row.**
  The slip, card panel, card status banner and bankroll strip now sit at the **TOP of
  `/results`** — `/slip` was built and deleted the same day. `lib/labels.ts::distinctTag`
  drops a blocker tag the action line already says (they share a blocker, so most Watch
  games printed the sentence twice). `CardPanel` rows link to `/game/[id]`, so its
  `onBoard` prop and the "Not on the board" fallback are gone. Week 2: 11,608px → 7,329px,
  839KB → 198KB HTML; web tests 336 → 351.
  **Still to do:** team logos (chosen by Tate, but NO logo data exists anywhere — `teams`
  holds only id/school/conference and `data/fbs_teams.json` is a season→names map, so it
  needs a CFBD `/teams` fetch into a cached lookup plus a text fallback), the Results
  reorganisation (bankroll/curve hero, trimmed picks table, collapse the eight empty
  sections, post-mortem out), `/proof` absorbing Research + `/research/records` + the
  Glossary, and deleting the eight legacy redirect files.
  Audit, per-page layouts and every decision: `~/.claude/plans/i-like-a-lot-cuddly-dusk.md`.
  **Screenshot with headless Chrome, never the Browser pane** (it caps captures at 800x500).
- **2026-09-09 night (PR #94, merged):** the board **ranks** instead of scoring. Each card's
  badge is its place on the week (`#1` = best), assigned in `homeBoard.ts::assignBoardRanks`
  over the whole board inside `getHomeBoard` — before `page.tsx` filters, so a day or team
  filter never renumbers. A kicked-off game has no rank: `inPlayAt` (5 h) gives it LIVE,
  then FINAL, then the result word. **A live BET card is lit green** (`.bv-card--lit`:
  `--good` border + `--good-bg` wash, plus a hover companion because `.bv-card:hover`
  hard-codes cyan); Watch and Pass are untouched, so lit means act. The 0-100 score still
  sets the colour, still decides the tier, and still drives Results/Research — it moved
  inside the card under "Our number", and the glossary gained a Rank entry. `capRank` is
  unchanged but renders as "cap slot" so it can't be read as the board rank. Two fixes rode
  along: `sortGames` now breaks a score tie on **gap** (the score clamps at 100 and a slate
  can pin a dozen games there — kickoff order was silently deciding "best game of the
  week"), and a played-but-ungraded game says FINAL rather than claiming to be live.
  Spec: `docs/superpowers/specs/2026-09-09-ranked-board-design.md`.
- **2026-09-09 evening (PRs #87-#92, all merged; real money Sat Sep 12):** four changes
  landed together. (1) **Per-event 1H calls cost 1 credit**, not 2: `odds_api.bookmakers_1h`
  names ten books, which the Odds API bills as ONE region and which overrides `regions`
  (verified live — same event, same eight books incl. `hardrockbet`, half the credits).
  The BULK full-game pull still prices by region and needs `us_ex`; an 11th book key
  doubles every sweep, so `sources/odds.py` refuses to start with one. (2) **Four decision
  builds a week** replace the daily morning card: `tue_pm`/`thu_pm`/`fri_pm` (~4:05pm ET)
  and `sat_am` (~8:05am ET), all status `final`, paper windows 48/24/16/80 h = exactly the
  gap to the next build. `manual` builds publish but paper-log NOTHING. Expected spend
  ~567 credits/wk (was ~1,308) on a measured basis of **82** HR games, not the 60 the old
  comments assumed. (3) **A Vercel cron is the primary trigger** (`web/vercel.json` ->
  `/api/cron/[job]`, table in `web/lib/cronJobs.ts`); GitHub cron is the backup and the
  `cards`-row probe now suppresses a duplicate DISPATCH too (`force=true` overrides).
  (4) **Bonus bets + pick editing** — see the gotchas.
- **Board:** anchor jumps from the bet card now clear the sticky header (one `--header-h`
  property drives `scroll-padding-top` and the day heading); a card row whose game is not
  on the board reads "Not on the board" instead of a dead link.
- **2026-09-08 (site rebuild + rolling week, PRs #76-#81; real money from week 2, Sep 12):**
  the board (`/`) is ONE rolling week grouped by ET day; each game locks at its own kickoff.
  Grade = a coloured 0-100 **score** (`web/lib/grade.ts`: 70+ green/bet, 55-69 amber/watch,
  <55 red/pass; settled games colour by result), scaled so a gap of exactly `BET_GAP_PTS` at a
  fair price = 70 (`edge.ts`/`card.py` `SCORE_PER_GAP_PT`). "EDGE" renders as **Watch**. A
  strong-but-blocked game keeps its colour and carries a plain tag (`lib/labels.ts::blockerTag`).
  Score/gap basis = Hard Rock's line → market consensus → our reference line, said in words;
  a real-money BET still needs Hard Rock's own line. **Model minimum is 0 games** (every FBS
  game scored off last season's priors; rows with <2 games carry `h/a_games_played` → "early
  season" tag). Schedule, credits and triggers: see the 2026-09-09 bullet above.
  `grade.yml` runs daily 6:30am ET; `lines_watch` opener crons retired.
  Every raw enum goes through `lib/labels.ts`; no Trust page, no honesty
  caveat line (Tate). Specs: `docs/superpowers/specs/2026-09-08-*.md`. Dev on a network that
  filters Neon:5432: `NEON_HTTP=1` in `web/.env` (Prisma Neon adapter over 443).
  **Score is gap only (no price bonus, no off-market/QB-out penalty) since 2026-09-09**, floored so
  70 ⇔ gap ≥ 1.75 exactly; no-model rows are always Pass; the settled colour only grades against a
  real book line (Hard Rock, else market) — a reference-only played game shows a neutral final.
- **2026-09-01 (week-1 audit, PRs #23-#26):** verdict logic (BET / WATCH / PASS + why,
  `web/lib/verdict.ts`) behind the board; `/board` redirects to `/` since 2026-09-02. Betting rules live in
  `docs/BETTING_POLICY.md` ($100 roll, $10 flat units, ≤5 bets/wk, 1H unders only).
  **Gates are in POINTS from the validated top-20%-by-gap rule (≥1.75 pts) — never
  σ:** `bv_sigma` ≈ 12 pts is per-game outcome noise, so a 1σ gap never occurs.
  Paper picks (`manual_picks.is_paper`, stake forced to 1 flat unit so units/ROI are
  comparable) sit apart from the real ledger. Sunday job now refreshes pace/weather before scoring; Monday job refreshes
  1H PBP and grades `game_records` + the factor ledger. (Grading is daily and the
  model minimum is 0 games since 2026-09-08 — see the top bullet.) **Florida platforms (verified
  2026-09-01):** Hard Rock Bet is still the only sportsbook; "FanDuel in Florida"
  = FanDuel Predicts (CFTC prediction market), not a sportsbook. Exchanges
  (Kalshi/Novig/ProphetX/BetOpenly, Odds API `us_ex`) are captured on the Sunday
  full-game poll only as a no-vig PRICE-COMPARISON source (`web/lib/books.ts`
  `EXCHANGE_KEYS`) — never bet there (no 1H totals). See `docs/BETTING_POLICY.md`.
- **What ships today:** decision-support for **full-game + 1H unders on Hard Rock Bet** (the only FL book). The model number is a reference chip, not a pick gate; the edge is *measured* via CLV, not promised (full-game backtest found no edge on the thin 2023-25 regime).
- **2026-09-06 (post-mortem):** `scripts/post_mortem.py` (pure math in `beatvegas/postmortem.py`)
  regrades every rated game vs its outcome — the 2023-25 walk-forward ratings at the flat 0.52 AND
  the fair step proxy (FBS-only + all), plus the season's cards at Hard Rock's numbers — into
  `postmortem_runs/buckets/games` (last step of `grade.yml`) and `docs/POST_MORTEM.md`; the Results
  page renders the headline records, rating bands and change flags (`web/lib/postmortem.ts`).
- **2026-07-17 (review closed):** the pre-season readiness review is fully worked
  off — blockers (PR #16), 13 should-fixes (PR #17), and the remainder (S8 strict
  pick matching, S15 postseason capture, S16 multiplier margin gate — fitted curve
  REVERTED to flat 0.52, S17-S19, S21-S22, nits). Accepted as-is: GHA cron lag
  (S20), sunday.yml DST double-fire (N12), plaintext local keys (N14), no login
  rate limit (store-less); N13 is moot since the push-notification layer was removed 2026-09-02. Since PR-1 data plumbing
  (2026-09) the Odds API bulk pull requests `totals,spreads` together (4-6 credits per slate), so each
  book's row carries its home spread; `Game.spread` is the run's cross-book median and Monday's CFBD
  upsert no longer clobbers Odds-API-sourced totals/spreads (`*_source` columns + `line_sources.py`).
- **2026-07 (Hard Rock pivot, PRs #7-#9):** multi-book capture incl. Hard Rock via The Odds API (`hardrockbet`; the `hardrockbet_fl` key folds onto it at write time); web views `/preview`, `/line-check`, `/weekly-review`; both markets logged + graded (`manual_picks.market`, `market_fg` ledger). Before season: GH secrets set, `odds_api.regions: "us,us2"`. (The phone push-notification layer shipped here was removed 2026-09-02 — failure alerts are GitHub's failed-run email + the routines.)
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
signal), tracks line movement, and grades market vs model vs
the user's own picks. Also generates a weekly report (`scripts/weekly_report.py`).

## Architecture
- **Engine** (`beatvegas/` + `scripts/`): capture → enrich → score → grade,
  run by **GitHub Actions** (`.github/workflows/`: `sunday.yml`, `lines_watch.yml`,
  `card.yml`, `grade.yml`, `research_preview.yml`). No notification code: GitHub emails
  failed runs. Nothing runs the engine on the Mac; two Mac routines text Tate:
  `cfb-saturday-card` (Sat 8:50am ET: verify/kick the morning card, text the BET list
  with line, price and kill numbers) and `cfb-sunday-ops` (verify/kick `sunday.yml`,
  text the recap). The bet card itself is built in the cloud (`card.yml`; slots in
  `beatvegas/ci.py::resolve_slot`: `tue_pm`/`thu_pm`/`fri_pm` ET-gated 3:45–5:15pm and
  `sat_am` ET-gated 7:45–9:15am — four whole-week decision builds timed to when Hard Rock
  actually posts 1H lines; `manual` on dispatch is always a `preview`. Builds are triggered
  by a **Vercel cron** dispatching the slot by name, with GitHub cron as the backup; the
  `cards`-row probe (never `gh run list`) now suppresses a duplicate DISPATCH as well as a
  duplicate cron, so the two triggers cannot both build — `force=true` overrides.)
  `rescore.yml` (dispatch: season + week) re-scores a past week without snapshots.
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
pytest -q                            # run `pytest -q` / `cd web && npx vitest run` for current counts
```
Inside a **git worktree** run tests as `PYTHONPATH=. python -m pytest -q` — the venv's
editable install points at the main checkout, so a bare `pytest` imports the wrong tree.
Key scripts: `backfill.py`, `backfill_enrichment.py` (pace/weather), `weekly_update.py`
(score), `poll_lines.py` (1H lines), `grade.py`, `pick.py`, `line_study.py`,
`retrain.py` (logs model_runs + BV calibration), `backfill_bv_line.py`, `seed_demo.py`.
**Pivot scripts**: `backfill_pbp.py` (1H PBP aggregates → `fh_team_game`),
`backfill_context.py` (venue/talent/roster), `rank_factors.py` (factor ranking →
`factor_scores`), `validate_engine.py` (gbm_v2 gate + MAE ablation), `inspect_combo.py`
+ `explain_pbp.py` (factor deep-dives), `weekly_report.py` (markdown board), `deploy_neon.py`
(additive Neon push). **Opener/cloud scripts**: `poll_full_game.py` (full-game capture,
`--source dk|cfbd|auto|oddsapi`; prod uses `oddsapi`), `derive_multiplier.py` (gated spread
multiplier), `backfill_spread.py` (surgical `Game.spread` from CFBD), `deploy_neon_games.py`
(additive games+spread push), `post_derived_lines.py` (writes display-only `derived_lines`
predictions for the board), `build_card.py` (the weekly bet card → `cards` row + paper picks
via `beatvegas/picks.py::add_pick`, the same insert `pick.py add` uses), `residual_gate.py`
(one-shot walk-forward report: residual engine vs incumbent vs the close, dispatched by
`.github/workflows/residual_gate.yml`; the report itself is the doc). **Sim/dev scripts**: `pg_sim.py` (throwaway local PG16 sandbox at
`~/.cache/beatvegas/pg_sim`) + `simulate_week.py` (replay a real week into it, rendered by
the real Next.js app, Neon-isolated). **Lint/format**: `ruff check` + `ruff
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
- **ALWAYS split the post-mortem on `line_real` before concluding anything.** Only 1,902
  of the 3,601 `hist_2023_25` rows carry a real captured 1H close; the other 1,699 are
  proxy-graded, and they are not a random sample — they are the games no book priced.
  Measured 2026-09-09: model bias by spread reads −0.70 / +0.37 / +0.53 / +2.00 over all
  3,601 rows, but the whole effect sits in the unpriced games (+3.36 at 28+) while the
  book-priced ones are flat (−0.47 at 28+), and wide-spread bets swing from −20.8 units
  at the proxy to +1.3 at the real close. This is the same artifact as the flat-0.52
  bullet above, one level up: it bites analysis of the model, not just of factors. State
  which grading basis every number came from, and the n for the real-line cut (thin at
  width — 72 games above a 28-pt spread).
- The edge is real but **small and unconfirmed**. The system's job is to *measure* it
  honestly vs real lines, not to promise profit.

## Web app (`web/`) — shipped + redesigned
Next.js (App Router) + TypeScript + Tailwind v4 + **Prisma** + **Recharts**, live on
Vercel (Neon-backed, password-gated) at https://beat-vegas.vercel.app.
- **Views (4 tabs)**: Board (`/`, THE home page — the week grouped by day, every game with a
  Hard Rock total, coloured **rank badge** (`#1` = best game of the week, assigned over the
  whole board before filters so a filter never renumbers; no rank once a game kicks off —
  it reads LIVE for 5 h then FINAL, then the result) + Bet/Watch/Pass word + action line from
  `web/lib/edge.ts` + `web/lib/grade.ts`, composed by `web/lib/homeBoard.ts`; bankroll strip,
  day/my-teams/Hard-Rock filters, expandable cards with Lines / Our number / What is behind it /
  Injuries and news, writable picks via `POST /api/picks`), Results (market/model/you ledgers with
  line value + bankroll curve + post-mortem), Research (accuracy, gap vs line value, line study),
  Glossary (15 terms). `/board` redirects to `/`. Grade bands live in `web/lib/grade.ts`
  (`SCORE_BET_MIN`/`SCORE_WATCH_MIN` mirrored in `model/score.py`); every enum label lives in
  `web/lib/labels.ts`; the point gates are exported from `model/score.py` and parity-tested
  against `verdict.ts`. API routes read the same SQL
  the page loaders use; the app is locked by `middleware.ts` + `APP_PASSWORD` cookie.
- **Design system**: plain-English copy + a modern sportsbook look in
  `web/app/globals.css` — deep-navy canvas, electric-cyan brand accent, Archivo display
  font, reusable `.bv-card`/`.bv-pill`/`.bv-stat`/`.bv-table`/`.bv-btn`/`.bv-nav-link`
  classes plus `.bv-badge` / `.bv-num` / `.bv-day-head`. **Colour is the grade language:**
  `--good` (bet / won), `--warn` (watch / warning), `--bad` (pass / lost), `--push`; cyan is
  chrome only (links, active nav, buttons) and never a grade. `MainNav.tsx` gives the
  active-route highlight.
- **Dev**: `web/.env` `DATABASE_URL` points at Neon (prod) or the local sim PG
  (`simulate_week.py`); the Neon line is commented as a fallback. On a network that filters
  Neon:5432 (campus) set `NEON_HTTP=1` in `web/.env` — `lib/prisma.ts` then uses the Prisma
  Neon adapter over HTTPS/WebSockets (443). `npm run lint` / `npm run format`
  before committing. Deploy is automatic from `main` (Vercel).

## Gotchas
- Features must stay **leak-free** (only pre-kickoff info; season-to-date shifted).
- Numeric model columns must be clean floats (NaN, never `pd.NA`/None/bool) — see
  `features.build_feature_frame` coercion; `bool(NaN)` is `True` (bit us on dome).
- ESPN/TeamRankings/**DraftKings**/**Rotowire** are **unofficial** — keep isolated in
  `sources/`, fail-silent. **ESPN: use host `site.web.api.espn.com`** — `site.api.espn.com`
  is Akamai-403 from every network we run on (Mac, GHA, fetchers), and ESPN publishes
  **no college injuries** on any endpoint (core API returns 0 for every FBS team).
  Injuries come from `sources/rotowire.py` (one JSON call for the whole slate). DK's hidden API returns **403 without browser-like headers** (set in
  `draftkings.py::_HEADERS`); the host, operator key (`dkusoh`) and league id (`87637`)
  drift — if capture goes empty mid-season, re-discover the `leagues/{id}` XHR in
  DevTools. Schema is `events`/`markets`/`selections` (the old `eventgroups` endpoint
  is dead). The default payload carries only main full-game markets (1H totals post
  later via a subcategory query), which is exactly the Sunday opener we want.
- **Neon is UNREACHABLE from the campus/fgcu network** (port 5432 TLS data filtered;
  HTTPS/443 works — and so does **Neon's HTTPS SQL endpoint**: `POST https://<pooler-host>/sql`
  with header `Neon-Connection-String: $DATABASE_URL` and body `{"query": "..."}` returns
  rows as JSON from campus in <1s. Use it for ad-hoc reads/small writes when 5432 is blocked;
  the SQLAlchemy scripts still need GHA). So **Neon-writing scheduled jobs run in GitHub Actions**
  (`.github/workflows/sunday.yml` + `lines_watch.yml` + `card.yml` + `grade.yml` + `research_preview.yml`).
  **DK's API 403s GHA datacenter IPs** (confirmed), so prod captures full-game lines with
  `poll_full_game --source oddsapi` (`auto` falls back to **CFBD /lines**, `sources/cfbd_lines.py`;
  DK only works from the Mac, which can't write Neon). Local jobs degrade gracefully via
  `store.try_init_db` (logs "unreachable", exits 0). The Sunday ops routine (`cfb-sunday-ops`)
  reads `GET /api/health` over HTTPS to confirm capture. Secrets `DATABASE_URL`/`CFBD_API_KEY`/
  `ODDS_API_KEY` are the only GH secrets. Pushing `.github/workflows/` needs the gh
  `workflow` token scope.
- **Bonus bets book NO loss** (`manual_picks.is_bonus`, 2026-09-09). Grading is
  `stake x units_won` and a loss returns -1/unit, so a $20 bonus logged as 2 units would
  show -$20 on a loss that cost nothing. `picks.graded_pick_fields` floors units at 0 when
  `is_bonus`; the WIN side is untouched because `units_won` already returns profit only,
  which is exactly what a bonus bet pays. Bonus bets are also excluded from the 5-bet
  weekly cap in BOTH `build_card.py::real_bets_this_week` and the web POST cap query.
  A pending pick's price/stake/note/bonus flag are editable (`PATCH /api/picks/<id>`,
  rules in `web/lib/pickRules.ts::parsePickEdit`); line/market/game never are, and a
  graded pick is refused. **Schema ordering:** a new `manual_picks` column must reach Neon
  via `migrate.yml` BEFORE the web deploy — the cap query reads `COALESCE(is_bonus, false)`
  and would throw on a missing column. The READ path degrades gracefully (`isMissingColumn`
  fallback in `web/lib/picks.ts`); the write path does not.
- **The model DISAGREES WITH HARD ROCK ON BLOWOUTS, and who is right is UNMEASURED**
  (found 2026-09-09; re-examined the same day — the earlier "HR is right" reading did not
  survive). On week-2 Hard-Rock-priced games the model's implied 1H share is 0.469 close /
  0.482 at 14-21 / **0.450 at 21+**, against HR's 0.504 / 0.524 / 0.541; average gaps +2.0
  / +2.2 / **+5.0**. HR prices these (5 of 5 at 21-28, 4 of 7 above 28), so `no_hr_line`
  does not filter them, and the top of the board is mostly wide-spread games.
  **But do not treat that as a known model error.** Against the 1,902 rows in
  `postmortem_games` (`hist_2023_25`) carrying a REAL captured close (`line_real`), the
  model has NO spread bias — mean miss −0.01 / −0.02 / +0.41 / −0.47 across
  <14 / 14-21 / 21-28 / 28+ — and wide-spread bets at `gap_real >= 1.75` returned +1.1%
  ROI over 120 bets, positive in 2 of 3 seasons. In 2023-25 weeks 1-4 the model ran a
  0.556 share on book-priced blowouts vs the book's 0.540, with gaps averaging −0.84: the
  2026 sign is FLIPPED. And `game_records` has **zero graded rows** — no 2026 prediction
  has ever been checked against a result (week 1 played but never scored, week 2 scored
  but not played), so nothing yet says which side is wrong.
  **Two traps here.** (1) The big blowout bias (+2.00 at 28+ over all 3,601 rows) is
  concentrated entirely in the 1,699 games NO BOOK PRICED (+3.36 at 28+); always cut
  `where line_real is not null` before concluding anything, and state the n — it is thin
  at width (72 games above a 28-pt spread). (2) Gating 21+ spreads on the proxy numbers
  was proposed and rejected: it drops a third of the board and the drag it targets
  disappears at real lines. Decision (Tate, 2026-09-09): **track it live, do not gate or
  retrain.** `grade.yml` runs `grade_records.py` + `post_mortem.py --write` daily, so each
  week's predictions grade themselves; watch model-vs-HR share by spread week over week.
  If it is an early-season priors effect the gap should shrink as season-to-date features
  fill in. If it persists, options are mismatch features from talent/SP+ (stays
  market-blind), a spread-keyed residual correction (precedent: `data/multiplier.json`,
  `residual_gate.py`), or adding spread outright — note `spread` is NOT in `MARKET_COLS`
  (only `full_game_total` and `proj_1h_ratio`); it was simply never added to
  `FEATURE_COLS`. `rescore.yml` would score 2026 week 1 for ~60 graded results at zero
  Odds credits. Meanwhile: do not read a 9-pt gap as a 9-pt edge.
- **GHA cron is UNRELIABLE, not just late** (Aug 28-30 2026: `lines_watch.yml` fired 2 of 19
  scheduled runs; 2026-09-09: `card.yml` fired 0 of 5 morning builds on time, the 12:05Z tick
  running at 16:33Z; no GitHub incident posted either time). So since 2026-09-09 the card and
  grading builds are **triggered by a VERCEL cron** (`web/vercel.json` -> `/api/cron/[job]`,
  table in `web/lib/cronJobs.ts`) which dispatches the workflow over the GitHub REST API;
  GitHub's own crons stay as the backup and the `cards`-row probe stops both from building.
  **`vercel.json` must live in `web/`** — the Vercel project's root directory — or it is
  silently ignored, with no build error and no crons in the dashboard. Vercel Hobby fires
  within the HOUR after the scheduled minute, so each job carries several UTC hours and the
  route refuses any tick outside its ET window. `/api/cron` is exempted in `middleware.ts`
  (Vercel sends no session cookie) and authenticates on `CRON_SECRET`; the other new env var
  is `GITHUB_DISPATCH_TOKEN` (fine-grained PAT, Actions read+write on this repo). Both are
  production-only and set by Tate in the dashboard. Anything else that must happen at a time
  is still dispatched by hand (`gh workflow run <wf> -f market=1h`), and `card.yml` checks its
  own inputs: it runs the 1H sweep / preview itself when today's is missing before it builds.
- **1H sweeps are RANKED before any cap** (`beatvegas/sweep.py`; the paid tier has no event cap, `--max-credits-per-run` is the runaway guard): close spread
  (|spread| ≤ 14, from the Sunday full-game capture) > wide > none; outdoor > dome; slower pace
  first; kickoff order last. A plain `[:18]` swept Friday night + the noon wave and never
  reached the evening games the card wants.
- **ESPN: send NO custom headers.** Akamai 403s a bare spoofed UA (`Mozilla/5.0`, or a Chrome UA
  without client hints); requests' default UA is served. The spoof blanked every preview until
  2026-09-02. `research_preview.py` now exits 3 when the team list is empty instead of writing
  455 blank rows. ESPN's CFB `/injuries` feed is usually EMPTY (no official CFB injury reports)
  — the QB-out flag is real but rare; check starters by hand before betting.
- **TeamRankings → CFBD mapping is exact-first** (`teamrankings.map_to_cfbd`). `name_score`
  scores a prefix school as a perfect match ("Kansas St" → Kansas AND Kansas State at 1.0) and
  the old first-scanned tie-break dropped 26 FBS teams/season and stored Ole Miss's tempo under
  Mississippi State (2023-25). Same exact-first rule in `espn.best_team_id`. Any new
  TeamRankings abbreviation goes in `_ALIASES` with the CFBD spelling from the `teams` table.
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
- `db/store.py::upsert` **never overwrites a column with None** — a partial row (e.g. the
  Monday finals backfill) must not null `spread`/`full_game_total` on upcoming games. Keep it so.
- **The model scores UNPLAYED games**: target rows have no `first_half_total`. Never re-add a
  `first_half_total` filter to the target slice (it silently empties the board).
- **BV gap is now the PRIMARY ranking** (gate passed in `validate_engine.py`).
  `score_slate` sorts by `bv_gap` desc; verdict gates are in POINTS (`model/score.py`). Calibration
  still uses a **global** intercept + `era_post2023` feature (per-era would double-count).
  The regressor is MARKET-BLIND (`BV_FEATURE_COLS = FEATURE_COLS − MARKET_COLS`) — keep it so.
