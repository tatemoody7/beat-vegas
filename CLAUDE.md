# Beat Vegas — project brief for Claude Code

College-football **first-half (1H) unders** on **Hard Rock Bet** (the only sportsbook bettable
from Florida): a research and decision-support system that measures whether a market-blind
1H-total model finds mispriced lines. Real money is 1H unders only; full-game lines are captured
and graded as a reference market and never bet. **It never places bets or automates gambling.**
Site: https://beat-vegas.vercel.app — readable by anyone with the link, password guards writes.

This file is the brief: what the system is, how it runs today, what is open, and the rules.
It is kept under 400 lines by `tests/test_claude_md.py`. **History lives in `docs/HISTORY.md`**
(every dated episode, newest first) — never restate it here; a change edits the relevant
paragraph below in place and appends its episode there. When this file and a memory file
disagree, **this file wins**; memory files hold lessons and point here.

## Read first
- `docs/HISTORY.md` — what happened, by date (2026-05 → today). Read the top entry before touching
  anything that shipped this week.
- `docs/HYPOTHESES.md` — the registry: every study ever run or proposed, its status and criterion.
  **Add the row first, then write the script**; `tests/test_hypotheses_registry.py` keeps it honest.
- `docs/BETTING_POLICY.md` (money rules, parity-tested), `docs/HEALTH.md` (one contract per
  scheduled job), `docs/OPS_ACCOUNTS.md` (the account-side checklist only Tate can click),
  `docs/RANKING_AND_TRUST.md` (how the board ranks and what it refuses), `docs/GLOSSARY.md`,
  `docs/ASSUMPTIONS.md` (every live money-path rule with its basis; nothing changes from it).
- Study docs, each with its verdict at the top: `STOPPING_RULE`, `MODEL_LEVEL_2026`,
  `NEGGAP_PAPER`, `INSEASON_PAPER`, `HARNESS`, `POST_MORTEM`, `TWO_SIDED`, `WEATHER`,
  `WEATHER_STYLE`, `CENSORING_STUDY`, `LEVEL_ANCHOR`, `BLEND`, `GATES`, `WHEN_TO_BET`, `HR_LAG`,
  `SHARP_BOOKS`, `CLASSIFIER_RETIREMENT`, `EXTERNAL_REVIEW`, `PIVOT`, `BV_LINE`,
  `DATA_STACK_REVIEW_2026-10-05`, `CFBD_TIER3_REVIEW_2026-10-05`, `WEPA_F`, `CFBD_CATALOGUE` (all in
  `docs/`).
- Plans: `~/.claude/plans/` (each review names its plan file in HISTORY). Private skills:
  `~/.claude/skills/bv-weekly-review`, `bv-card-check`, `bv-ship`, `bv-site-check`.
- `README.md` is the public setup + run guide; it must not contradict this file.

## Where we are (as of 2026-10-04)
- **Real money: 10-10, −0.29u through week 5** (Wilson 29.9–70.1%), $10 flat units, ≤5 bets a
  week, every card BET placed and nothing else. Week 5 went 1-4 (−3.13u) on a slate that went
  62% under: the four losers landed 3.9 pts over their lines, two by 1.5-2.5 pts, two by 7.5 and
  14.5; line value 0.00, no rule loosened — variance plus one tie-at-the-bar pick (Alabama @
  Mississippi State, gap 2.12 = bar 2.12, cap rank 5). Week-5 report: `reports/weekly/`, local.
- **System review 2026-10-04** (`docs/SYSTEM_REVIEW_2026-10-04.md`): the model cannot sharpen
  in-season by construction (it trains on seasons before the target only); the 2026 factor
  screen found no input, and not the gap itself, predicting the residual against the close
  (87 comparisons, best p 0.117); the price gate is the one live filter with a record. Seven
  registry rows (H-FACTOR-SCREEN, H-PCT-TIE, H-TIMING, H-MOVE, H-TOP3, H-SHADOW-F,
  H-INSEASON-T) — every one paper or measurement; the champion, stakes and H-STOP-2 unchanged.
- **Week 5 was the first week on the B-SERVE model** (57 inputs that were NaN at serving are out
  of the feature set; `weekly_update.py` fails a scoring run whose target rows are >90% NaN on a
  column training is <10% NaN on). It fixed the level (mean `bv_line` 0.8 under Hard Rock, bias
  +0.18 = the book's) and not the accuracy (MAE 9.03 vs 8.39; on qualifying games 8.74 vs 7.50).
  The weekly refit writes a `model_runs` row with its frame fingerprint; **any number about the
  live model comes from a runner dispatch and names it**.
- **The bar is per-slate (H-PCT)**: the k-th largest gap over the slate's Hard-Rock-priced games
  with a centred quote and a model read, k = max(1, round(0.2 × N)) — `model/score.py::slate_bar`
  mirrored by `verdict.ts::slateBar`, golden vectors in `tests/fixtures/slate_bar_vectors.json`.
  `BET_GAP_PTS = 1.75` survives only as the empty-slate fallback.
- **H-STOP-2** (SPRT, two clocks: profit and line value inside the 2 h close window, σ 0.929 /
  1.371) started at the 2026-09-29 `tue_pm` build; H-STOP is superseded. A failure boundary
  pauses real money (`scripts/rule_pause.py`); a success boundary changes nothing. **After week
  5: profit n=10, LLR −0.26; line value n=9, LLR +0.73** (bounds +3.47 / −1.58); one pick
  excluded (a Friday-night close 227 min out). A bad week is a clock reading, not a rule change.
- **H-NEGGAP-P** logs paper OVERS from the same build: three nested arms (gap < 0 / ≤ −1.75 /
  ≤ −3) on Hard Rock's MAIN line, one row per game per arm into `challenger_picks`
  (`side='over'`, never `manual_picks`), Bonferroni 0.833% per arm-clock. Measurement only;
  a pass licenses nothing at real money. The negative-gap band went over 26 of 38 live, but 23 of
  those were Hard Rock ALTERNATE lines; on main lines it is 10 of 15. First rows: card 24
  (`fri_pm` 2026-10-02), 27 rows over 15 games, recorded in `docs/NEGGAP_PAPER.md`. Week 5
  graded: `lt0` 5-11 (−6.7u), `le175` 3-5, `le3` 2-4 — the band went 12 under / 5 over.
- **What the evidence says**: 2023-25 (1,902 real closes) is exhausted for rule selection;
  everything important is validated prospectively on 2026 decisions. The model's level now
  matches the market (B-SERVE); it is still less accurate than Hard Rock, and in weeks 4-5 the
  gap did not sort unders from overs (gap ≥ 1.75 went 7-7 in week 5 while gap < 1.75 went 26-13;
  gap-vs-residual correlation +0.15 / +0.16 on main lines) — measured weekly, tracked, not gated.
  Hard Rock posts 1H lines Tue 31% → Fri 78% → Sat 97% and they barely move, so **the best look
  is Friday after 5:30pm ET**, then Saturday after 8:30am; Tate bets off the first BET-rated
  build (his call, 2026-10-04 — the Tuesday tickets closed flat or better).

## Open items (the only place pending work lives; date each)
- **Hard Rock's feed row drifts to an alternate rung near kickoff** (measured 2026-10-01:
  main-line share 97% beyond 48 h, 31% inside 2 h; 142 main→rung flips vs 5 back). Late
  candidates read `no_hr_line` because of it. Decide: ask the feed for `alternate_totals_h1`
  (2 credits an event, one probe first), report to The Odds API, or accept. (The Vercel
  `lines-close` backup ran its first Saturday on 2026-10-03: 14 hourly dispatches,
  `close_coverage_pct` 1.000 = 53 of 53, so coverage itself is no longer the casualty.)
- **Friday-night games get no close inside 2 h** (2026-10-02: Penn State @ Northwestern, last
  capture 227 min out, excluded from H-STOP-2's line-value clock). `lines-close` entries are
  Saturday-only and GitHub's weeknight cron did not fire. Decide: add Fri 22Z–01Z entries
  (`vercel.json` + the route's window), Tate's call.
- **Week-6 stack** (decided 2026-10-04, `docs/SYSTEM_REVIEW_2026-10-04.md` §12). **Done
  2026-10-04:** PR2 tracking (#269, Neon migrated first; #272 schema) and PR3 classifier
  retirement (#268). **First-rows checks:** `predictions.refit_id` after the 2026-10-04 refit,
  `poll_log` after tonight's sweeps, `injury_snapshots` + the `FROZEN:` card line + frozen
  vectors on paper picks at the Tue 2026-10-06 build (`bv-card-check`). **Remaining:** PR4
  degraded hold mirrored on the web (Tue 10-06; also fix the board's "No bets yet this week"
  headline when the week is over and 5 of 5 are placed); PR5 paper arms (`pct_tie_*`, `top3`,
  H-TIMING and H-MOVE scripts) Wed-Fri; PR6 shadow engines (`bv_shadow_f`, `bv_inseason_t`)
  Fri 2026-10-09 or week 7, sandbox-gated. Real money unchanged all week.
- **After the two data reviews (2026-10-05, `docs/CFBD_TIER3_REVIEW_2026-10-05.md` decisions 1-6,
  `docs/DATA_STACK_REVIEW_2026-10-05.md` §9), Tate's calls:** (a) **done 2026-10-06: H-WEPA-F
  ARM R ran once on the runner and was NOT MET** (`docs/WEPA_F.md`: dated WEPA fixed the 2025
  level, not the accuracy; ARM P, the 2026 WEPA engine, is not licensed); (b) PR7: weekly
  `/wepa/team/season` + CORE/Elo/FPI snapshot tables with fingerprints from the next Sunday job;
  (c) H-FHBOX (`/game/box/advanced` quarter splits → the 57 first-half inputs; 2023-25 backfill
  ~2,400 calls); (d) drop `sp_sos` from PR6 (null since 2019); (e) CFBD Tier 3 ($10) or Tier 1
  ($1) at the **Nov 6** renewal; (f) `bv_residual` shadow and Friday-night `lines-close`
  entries, both still open from 2026-10-04. The Odds API is on 20K; CFBD on Tier 3 via the
  boomtatermac key (`docs/OPS_ACCOUNTS.md` 2-3).
- **The repo is PRIVATE again since 2026-10-04** (card on file; Actions budget $10/month,
  stop-at-cap, alerts on — the $0 budget was the Sep 22 outage). 2,000 free minutes a month
  against ~2,830 measured: watch the budget page in the last week of each month.
- **Week-sandbox replay for PR #247** never ran (this Mac's SQLite is a June snapshot); the first
  live build is the check.
- **Offline backtest engine still fits the retired classifier** (`backtest/engine.py::_new_model`,
  read by `scripts/backtest.py`, `retrain.py`, `validate_engine.py` and `rank_factors`); nothing
  live reaches it since PR #268. Retire it with those four tools or leave it — Tate's call.
- **2026-12-07**: the one confirmatory look for `docs/WHEN_TO_BET.md` (H6); the script refuses
  `--confirmatory` before then.
- **H-SHARE** (share engine): spec'd (`docs/superpowers/specs/2026-09-15-share-engine.md`) and
  registered, not built; a pass of its gate licenses a paper arm, not promotion.
- **Registry vocabulary**: add `superseded` (H-STOP, H-INSEASON-P currently read `rejected`).
- **Vercel `DATABASE_URL`**: the pg driver warns at every cold start that `sslmode=require` changes
  meaning in pg v9; set `sslmode=verify-full` explicitly (same behaviour as today). Seen 2026-09-28.

## Decision calendar (all times ET; GitHub crons are the backup, Vercel is the trigger)
| When | Job | What |
|---|---|---|
| Tue / Thu / Fri, gate 3:45–5:15pm | `card.yml` slots `tue_pm` `thu_pm` `fri_pm` | whole-week 1H sweep + injuries → FINAL card; paper windows 48 h / 24 h / rest of week |
| Sat, dispatch 7:00–8:15am, gate 7:45–9:15am | `card.yml` slot `sat_am` | same sweep before the morning sitting; paper window rest of week |
| Sat 10:00am–11:59pm, one tick per UTC hour (15 entries, 14Z–04Z) | `lines-close` → `lines_watch.yml market=1h_close` | per-game Hard Rock closes, `CLOSE_LOOKAHEAD_MIN=120`; GitHub's every-30-min crons stay |
| Weeknights (GitHub cron only) | `lines_watch.yml` | opener/close sweeps 22Z–03Z |
| Sun 1–5pm (ticks 18/19/20Z) | `sunday.yml` | full-game opener capture → pace + weather → weekly refit + score → derived 1H lines; `need_capture` / `need_score` probes |
| Daily 10Z (GitHub 10:30Z; 16:00Z Sun–Fri) | `grade.yml` | finals (CFBD, ESPN fallback) → grade picks, records, ledger → post-mortem (Monday or `hist=true`) → coverage gauge |

Slot windows live in `beatvegas/ci.py` (`resolve_slot`, `PAPER_WINDOW_HOURS`), the Vercel table
in `web/lib/cronJobs.ts` (mirrored by `web/vercel.json`, which **must live in `web/`**). A
`manual` dispatch is always a preview and paper-logs nothing. The `cards`-row probe stops the
two triggers double-building; `force=true` overrides. Every job ends with
`scripts/health_check.py --job <job>` (`always()`), which writes `last_health_<job>` for the
board banner and `/api/health`, exits 1 on `failed` (GitHub emails) and 0 on `degraded`.

## Architecture
- **Engine** (`beatvegas/` + `scripts/`): capture → enrich → score → grade, run by GitHub Actions.
  Nothing runs on the Mac on a schedule and nothing texts Tate; the board is the failure surface.
  Data: CFBD (games, PBP, SP+, talent, returning production), The Odds API (`totals_h1` per
  event, full-game bulk), TeamRankings tempo, Open-Meteo weather, Rotowire injuries, ESPN scores.
- **DB**: SQLAlchemy (`beatvegas/db/models.py`, `_MIGRATIONS` + `_DATA_MIGRATIONS` in
  `db/store.py`). `DATABASE_URL` → Neon Postgres (psycopg3); unset → `data/beatvegas.db`. A
  schema change is Python first, `migrate.yml`, then the new columns **hand-added** to the
  curated `web/prisma/schema.prisma` + `npx prisma generate`, then deploy. Never commit a full
  `prisma db pull`: it introspects every table in the shared Neon database (22 models the app
  reads by raw SQL on purpose, six `swfl_*` fishing tables) and strips the comments (2026-10-04).
- **Site** (`web/`): Next.js App Router + TypeScript + Tailwind v4 + Prisma 7 (driver adapters:
  `PrismaPg`, `PrismaNeon` under `NEON_HTTP=1`) + Recharts, on Vercel. Three tabs — Board (`/`),
  Results (`/results`, read-only, opens on the bet ledger), How it works (`/how-it-works`) —
  plus `/game/[id]` (the only place a pick is logged) and `/records`. Thirteen legacy routes
  (incl. `/proof`) are 308 redirects in `next.config.ts`. **Owner-only content renders behind
  the cookie** (`viewerIsAuthed()`): ops warnings, the My-teams chip, the Monday review on
  Results, the research section on How it works, the log control. No dollars are public. API:
  `/api/picks`, `/api/picks/[id]`, `/api/bets` (31-column CSV), `/api/records`, `/api/health`,
  `/api/login`, `/api/logout`, `/api/cron/[job]`. Reads are public; writes need the
  `APP_PASSWORD` cookie (`lib/gate.ts::gateDecision` in `middleware.ts` AND
  `lib/session.ts::requireAuth` inside every pick route). `/api/cron` authenticates on
  `CRON_SECRET` and dispatches with `GITHUB_DISPATCH_TOKEN`.
- **Model**: market-blind HGB regressor on `BV_FEATURE_COLS` (`model/bv_line.py`, = `FEATURE_COLS`
  − `MARKET_COLS` − `SERVE_UNAVAILABLE_COLS`), FBS-vs-FBS training (`etl/fbs.py`,
  `data/fbs_teams.json`), global calibration intercept, re-fitted every Sunday. `score_slate`
  ranks by `gap = line − bv_line`; the 0-100 score, tier and kill line all derive from the gap
  against the slate bar. `bv_sigma` is one number per slate — never derive a probability from it.

### Workflows (`.github/workflows/`)
| File | Trigger | Writes |
|---|---|---|
| `card.yml` | Vercel dispatch + 16 backup crons; inputs slot/force/season/week/max_credits | `cards`, paper `manual_picks`, `challenger_picks` (`NEGGAP_COLLECT=1`), preview |
| `lines_watch.yml` | Vercel `lines-close` + 4 crons; input market | `odds_snapshots` (1H) |
| `sunday.yml` | Vercel + 3 crons; input force | full-game snapshots, `team_tempo`, `weather`, `predictions`, `model_runs`, `derived_lines` |
| `grade.yml` | Vercel + 2 crons; input hist | finals, graded picks/records, factor ledger, post-mortem, gauges |
| `ci.yml` | `pull_request` only | — (pytest, vitest, tsc, e2e lane on postgres:16) |
| `migrate.yml` | dispatch | `init_db` on Neon (additive) |
| `study.yml` | dispatch script/args | a read-only report artifact (runner-frame numbers) |
| `rescore.yml` | dispatch season/week | re-scores a past week, no snapshots |
| `post-lines.yml` | dispatch season/week/source | `derived_lines` |
| `backfill_intercept.yml` | dispatch season/write | `predictions.bv_intercept` |
| `backfill_1h.yml` | dispatch (paid history) | historical 1H closes |
| `enrich_tempo.yml`, `weather_backfill.yml` | dispatch | `team_tempo`, `weather_obs` |
| `residual_gate.yml`, `level_anchor_gate.yml`, `intercept_gate.yml`, `inseason_gate.yml` | dispatch | a report; never the model |

Secrets: `DATABASE_URL`, `CFBD_API_KEY`, `ODDS_API_KEY` (repository secrets only). Every
workflow installs `pip install --require-hashes -r requirements/lock.txt` (Python 3.11, 32 pins)
and dispatch inputs cross into `run:` only via `env:` (`tests/test_workflows.py` enforces both).

### Scripts (`scripts/`, grouped; every script is idempotent)
- **Live jobs**: `weekly_update` (score; `--min-games 0`, serve-skew guard, refit `model_runs`),
  `poll_lines` (1H; `--hr-universe`, ranked sweeps), `poll_full_game`, `build_card`,
  `research_preview`, `grade`, `grade_records`, `grade_factor_ledger`, `post_mortem`,
  `backfill` (season load; scores first, venues soft), `backfill_scores_espn`, `enrich_tempo`,
  `enrich_weather`, `post_derived_lines`, `close_coverage`, `record_gauge`, `health_check`.
- **Positions / rule**: `stopping_rule_position` (`--clock 2` default), `neggap_position`,
  `challenger_position`, `rule_pause`, `pick` (paper-only `add`, `grade`, `summary`).
- **Studies (registry-gated)**: `harness_report --row <id>`, `intercept_gate`, `inseason_gate`,
  `level_anchor_gate`, `residual_gate`, `weather_gate`, `blend_gate`, `gates_study`,
  `when_to_bet_study`, `hr_lag_study`, `sharp_book_probe`, `two_sided_study`, `censoring_study`,
  `neggap_level_study`, `weather_style_study`, `stopping_rule_candidates`, `frame_snapshot`.
- **Backfills / one-offs**: `backfill_1h_history`, `backfill_fg_history`, `backfill_bv_line`,
  `backfill_bv_intercept`, `backfill_game_records`, `backfill_spread`, `backfill_spread_open`,
  `backfill_pbp`, `backfill_context`, `backfill_enrichment` (pace), `backfill_weather` +
  `weather_validate`, `derive_multiplier`, `reconstruct_pick_prices`, `purge_demo_rows`,
  `wepa_weekly_extract` (the H-WEPA-F z-table from the gitignored Patreon weekly files).
- **Model / research**: `retrain`, `backtest`, `validate_engine`, `rank_factors`,
  `inspect_combo`, `explain_pbp`, `line_study`, `weekly_report`, `model_artifacts`, `bv_adjust`.
- **Deploy / dev**: `deploy_neon`, `deploy_neon_games` (both ADDITIVE), `pg_sim` +
  `simulate_week` (local week sandbox), `seed_demo`, `fetch_fbs_teams` + `fetch_team_logos`
  (each August), `dump_e2e_schema`, `hooks/post_edit.sh`, `hooks/on_stop.sh`.

## Money path (server-side; the site never trusts the browser)
- `POST /api/picks` → `lib/pickRules.ts::serverVerdict` + `checkPolicy`: a real-money BET needs
  Hard Rock's own MAIN line, a **live** verifiable price (`lib/lineCheck.ts`; none → `PRICE
  UNAVAILABLE`, a different refusal from the kill-price one), a price at or better than the kill
  price recomputed now, both teams with ≥2 current-season FBS games (`MIN_GAMES_FOR_REAL_MONEY`),
  and a free cap slot (5 a week; bonus bets use none and book no loss). Nothing defaults a price
  to −110; a missing price is NULL and refused (`PRICE MISSING`). Paper is exempt from the price
  rules so the stopping rule's observations are untouched.
- `manual_picks.bet_at` is when the ticket was WRITTEN (`placed_at` is the log time). A log more
  than `BACKDATE_MIN_MINUTES` (30) after the bet is judged by **the card in force at bet time**
  (`lib/card.ts::getLatestCard(season, week, asOf)`, `pickRules.verdictAtBetTime`); `betAtCheck`
  refuses future, >7 d and post-kickoff times; the log form's "Placed at" is blank by default.
- Picks freeze at kickoff (PATCH/DELETE refused); `uq_manual_pick_per_ledger` stops duplicates.
- Grading is side-aware in one place each: `grading.units_won(side)`,
  `picks.graded_pick_fields(side)`, `lines.book_closing_price_before_kickoff(side)`. Stored
  `clv = closing − bet`, so **negative is the good direction for an under**; the site shows `−clv`
  (`lib/clvDirection.test.ts` pins it). `price_provenance` ∈ logged / backfilled_close / unknown;
  only `logged` feeds price CLV.
- Real tickets: `manual_picks` (`is_paper=false`). Paper: `manual_picks` (`is_paper=true`, 1
  flat unit). Challenger families: `challenger_picks` only — one missed filter would contaminate
  the champion's clock.

## Setup + dev
```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -e .   # Mac venv is 3.9.6; runner 3.11
pip install -e ".[logos]"                # only for scripts/fetch_team_logos.py
cp config.example.yaml config.yaml       # keys (gitignored); config.example.yaml IS prod's odds_api config
pytest -q                                # inside a git worktree: PYTHONPATH=. python -m pytest -q
cd web && npm install && npm run dev     # web/.env DATABASE_URL: the sandbox by default, Neon commented
```
- Worktrees go under `.claude/worktrees/<name>` only; never edit the main checkout from a session
  that shares it. A worktree serves its own dev server: `bash web/scripts/dev-worktree.sh start`
  (own port 3100-3199, clean `.next`, refuses a Neon URL without `--allow-neon`).
- `.claude/settings.json` is tracked: `scripts/hooks/post_edit.sh` (ruff + matching tests + tsc
  on every Edit/Write) and `scripts/hooks/on_stop.sh` (full pytest + vitest + tsc once per turn).
- Lint: `ruff check` + `ruff format` (no pyupgrade — py3.9 runtime); `npm run lint` / `npm run
  format` in `web/` (`web/data/*.json` are prettier-ignored, keep them so).
- Local week sandbox: `scripts/pg_sim.py` + `scripts/simulate_week.py` (throwaway PG16, port
  54329, Neon-isolated); the e2e lane: `npm run e2e:db && npm run e2e` (synthetic fixture in
  `web/e2e/fixture/`, never `neon.tech`). Campus network: Neon:5432 is filtered — set
  `NEON_HTTP=1` in `web/.env`, dispatch `study.yml` for runner reads, or use Neon's HTTPS SQL
  endpoint (`POST https://<pooler-host>/sql`, header `Neon-Connection-String`, body `{"query"}`).
- Dispatch by hand: `gh workflow run <file>.yml --ref main -f key=value`. Check the exit code of
  every test run yourself — `pytest | tail -1` masks it and let a red suite push once.
- Merge with `bv-ship` (squash, CI incl. e2e, prod health, routes 200); site PRs go through
  `bv-site-check` first.

## Honest status of the edge (don't oversell)
- **Live evidence first.** Real money 9-6 (+2.84u) on 15 tickets is inside its Wilson interval
  either way. The rule's prospective record and line value are judged only by the registered
  stopping rule (H-STOP-2, `docs/STOPPING_RULE.md`); the site states every rate with its interval
  and labels the bankroll "modelled from the ledger, not reconciled". Line value at Hard Rock's
  close is the one edge measure that does not depend on a proxy.
- **What is measured, not gated**: the model's ~2-pt level deficit and its spread-bucket accuracy
  vs Hard Rock (weekly review), the negative-gap "overs" band (H-NEGGAP, H-NEGGAP-P), the gap
  ladder by band. No gate, model constant or registry row changes from an analysis; fixes land
  through their own registered row or PR.
- **The proxy era is history.** Before the 2023-25 closes were bought (Sep 2026) every backtest
  graded against a step share of the full-game total (`data/multiplier.json`: 0.4975 below a 21-pt
  spread, 0.5375 at 21+). Proxy-graded numbers flattered unders and are never quoted as an edge;
  every table splits on `line_real IS NOT NULL` with both n stated. `HISTORY.md` 2026-09-02.
- The edge, if any, is **small and unconfirmed**. The system's job is to measure it honestly.

## Visual Verification
- Captures come from headless Chrome via Playwright: `cd web && node scripts/shots.mjs --base
  http://localhost:<port> --label <name>` (every route at 1440 and 390 with height / overflow /
  header / tap-target metrics), then `--diff before after` (`--pixdiff` via odiff). **Never the
  Browser pane for captures** (it caps at 800x500); its `javascript_tool` is still the right way
  to measure the DOM.
- A worktree verifies against **its own dev server on its own port with a clean `.next`**
  (`dev-worktree.sh`). Never point shots at the main checkout's server on 3000 — the preview pane
  serves main even from a worktree.
- A phone layout is confirmed by measurement (`scrollWidth - clientWidth` must be 0), never by
  eye. Look at the picture too: screenshots caught four defects the DOM checks could not.
- Never run a capture pass against production Neon (metered egress; it tripped the 5 GB cap once).
- Design rule (Tate): **if it isn't obvious, cut it.** A chart that needs a paragraph has failed.

## Analysis Rules
Before any CLV, win-rate, hit-rate or model recommendation is reported, state, in this order:
- The data source (table + filter) and n; the grading rule (which first-half total, which guard).
- The line source — consensus vs one book, first half vs full game — and the price provenance
  (`manual_picks.price_provenance`: `logged` / `backfilled_close` / `unknown`; only `logged` may
  feed price CLV; a price is never assumed to be −110).
- Whether any row is proxy-graded. A proxy number is never presented as a real-line number; every
  table is split on `line_real IS NOT NULL` with both n stated.
- The sign convention, checked against one hand-worked pick: stored `clv` is `closing − bet`, so
  **negative is the good direction for an under** and the site displays `−clv`.
- Any number about the LIVE model comes from a runner dispatch and names its frame fingerprint
  (this Mac's CFBD cache has disagreed with the runner's before).
Nothing in an analysis changes a gate, a model constant or a registry row; fixes are proposed as a
list and land through their own registered row or PR.

## Gotchas (the rule, the reason, the pointer)
- **Never make a judgment call for Tate; bring the options.** Every fork in HISTORY was his call.
- **Hard Rock's ALTERNATE lines arrive alone as the 1H total** (Texas @ Tennessee 30.5 at −160 vs
  27.5 in the app). `devig.is_hr_rung` (−140 or worse, or 2+ pts off the field's median with 3+
  books; `devig.ts::isHrRung`, golden vectors) flags them; the card shows the last MAIN line
  (`hr_alt_line`) and they can never be bet, never set the bar, never paper-log. `RANKING_AND_TRUST` §9b.
- **BetMGM's `totals_h1` is an off-centre rung**, not a main line (61 of 63 games 2+ pts off);
  `fairPriceWindow` admits only books within 0.5 pts of Hard Rock. `RANKING_AND_TRUST` §9.
- **`centred_snaps` falls back to the rungs it rejects** (`return ok or list(snaps)`): pass
  `strict=True` from any single-book read. HISTORY 2026-09-13 (PR #123).
- **`ev` is price-shopping, not wager EV** (`ev_under(market fair, HR price)`); gating on `ev ≥ 0`
  bets nothing. The live bar is `BET_MIN_EV` (−0.05); `BREAK_EVEN_EV` is wired to nothing until a
  calibrated P(under) exists. `RANKING_AND_TRUST` §8b.
- **`checkPolicy` compares a LIVE price to a kill price recomputed now.** The "green board, refused
  log" band was stale card data, not two rules. A cached price may be displayed, never authorize money.
- **`build_feature_frame()` defaults to `min_games=2`; the live path scores at 0** (`weekly_update`
  → `score_slate` derives training from the frame it is handed). A diagnostic at the default reads
  4 rows for a season and calls it noise. Cache the frame (~8 min) before comparing anything.
- **`season_stats._cached` has no expiry**; this Mac's CFBD reference tables disagreed with the
  runner's and flipped a gate verdict. Registered runs name their frame fingerprint
  (`etl/frame_fingerprint.py`; `scripts/frame_snapshot.py` via `study.yml`). `MODEL_LEVEL_2026.md`.
- **A new `predictions` column needs a backfill**: `score_slate` rewrites only the target week, so
  every earlier row stays NULL forever (`backfill_bv_intercept.py` is the template).
- **The model scores UNPLAYED games** — never re-add a `first_half_total` filter to the target slice.
- **Features stay leak-free** (pre-kickoff only, season-to-date shifted) and numeric columns are
  clean floats (NaN, never `pd.NA`/None/bool — `bool(NaN)` is True). The regressor is
  market-blind: keep `spread` and the market columns out of `BV_FEATURE_COLS`.
- **`PRIOR_SEASON_WEIGHT = 0` and `WEATHER_OBS_LEAD_HOURS = None` ship inert on purpose**: each
  incumbent is an ARM of its gate (`LEVEL_ANCHOR.md`, `WEATHER.md`). Repairing data into a table
  nothing reads is not activation; activation is its own registered gate.
- **Open-Meteo**: always `timezone=UTC` (a local series keyed by a naive-UTC kickoff displaced
  every weather row for three years); the free quota is per UTC DAY (5,711 requests in ~2.3 h),
  so a backfill spans two days; the Historical Forecast API tracks ACTUALS — decision-time rows
  come from the Previous Runs API (`weather_obs.lead_hours` 24/72, `decision_safe`, 2024+ for
  wind/gusts, pinned to `icon_seamless`). `docs/WEATHER.md` before touching any of it.
- **CFBD quota**: `CFBDQuotaExceeded` is raised on the spot (no `Retry-After` arrives);
  `calls_remaining` is printed every run and warns under 200; the ISO-week `cfbd-cache` /
  `cfbd-cache-save` actions (save refuses unless ≥4 reference files >1 KB exist) share reference
  tables across a week's runs. ESPN (`sources/espn_scores.py`) is the no-quota scores fallback and
  its event ids ARE `games.id`; ESPN cannot replace CFBD for scoring (8 CFBD-only features).
- **ESPN**: host `site.web.api.espn.com`, send NO custom headers (Akamai 403s a spoofed UA);
  ESPN has no college injuries — Rotowire does (`sources/rotowire.py`). Line scores populate
  late: a 0-0 half is trusted only when 4+ numeric quarters sum to each side's final, or the PBP
  running score reaches the stored final (`etl/first_half.py`). **All 15 scoreless halves on file
  are real** — never "fill in" a missing half without one of those two proofs.
- **DraftKings' hidden API 403s GHA IPs and needs browser headers** (`draftkings.py::_HEADERS`);
  prod captures full-game lines with `--source oddsapi`. TeamRankings → CFBD mapping is
  exact-first (`teamrankings.map_to_cfbd`); new abbreviations go in `_ALIASES`.
- **1H sweeps are RANKED before any cap** (`beatvegas/sweep.py`: close spread > wide > none,
  outdoor, slower pace, kickoff order). Per-event 1H calls cost 1 credit with ≤10 named books
  (`bookmakers_1h`); an 11th key doubles every sweep and `sources/odds.py` refuses to start.
- **Neon**: bulk inserts CHUNKED (~500 rows/commit) or the pooler stalls; resync the id sequence
  before any bulk insert (`init_db` does it); deploys are ADDITIVE, never `--wipe`;
  `store.upsert` never overwrites a column with None; `upsert` batches its existence check.
  An index leading on `odds_snapshots.market` was tested and rejected (5.7%, two-value column).
- **Schema ordering**: a new `manual_picks` column reaches Neon via `migrate.yml` BEFORE the web
  deploy — the write path throws on a missing column, only the read path degrades.
- **GHA cron is unreliable, not just late** (fired 2 of 19, then 0 of 5, then 3 of 18). Vercel
  Hobby fires within the HOUR after the minute, so every job carries several UTC entries and the
  route refuses ticks outside its ET window; `boardHealth.ts` warns when a job's last closed
  window saw no tick. `card.yml` runs its own missing inputs before it builds.
- **`web/lib` exports with no TypeScript caller can be load-bearing**: `tests/test_gate_parity.py`
  reads constants out of `verdict.ts`, `grade.ts`, `edge.ts`, `lineCheck.ts`, `books.ts`,
  `card.ts` by regex; `test_pick_columns_parity.py` reads both INSERT column lists;
  `test_docs_parity.py` reads `BETTING_POLICY.md` and `HEALTH.md`. Grep `tests/` before deleting
  any `export const` or editing a doc sentence that names a number.
- **A "use client" file must never import a VALUE from a database-backed module** — with Prisma 7
  it pulls `pg` into the browser bundle and 500s the page (`lib/prisma.test.ts` scans for it).
- **React `cache()` is a no-op outside a render scope** — measure dedupe with a query counter,
  never a mocked-prisma unit test; key loaders on stable args (`now = new Date()` dedupes nothing).
- **Recharts 3 bars need `isAnimationActive={false}`** or they render at height 0. A sticky panel
  inside a table cell pins to the VIEWPORT in Chrome, not the scrolling table.
- **Chrome headless does not emulate a phone from `--window-size`**; measure `scrollWidth -
  clientWidth` with the Browser pane's `javascript_tool` (its screenshots are useless, its JS works).
- **Next 16.3 writes its own `AGENTS.md`/`CLAUDE.md` into `web/`** — `agentRules: false` in
  `next.config.ts` turns it off; do not remove it.
- **eslint 10, TypeScript 7 and vitest 5 are ignored in `dependabot.yml`** (eslint 10 is measured
  broken with eslint-config-next); each is its own decision. Python pins are `requirements/lock.txt`
  (`.txt` so Dependabot sees it); local dev uses `requirements.txt` on 3.9.
- **`config.yaml`, `data/*.db|*.log|cache/|pbp_cache/`, `reports/weekly/`, `/research/` are
  gitignored** — keep them so. `config.example.yaml` IS what prod reads for `odds_api`.
- **Timestamps are naive UTC everywhere**; convert to ET at the display edge (`lib/et.ts`), and
  never hand a naive string to `new Date()` without appending `Z`. Read Postgres timestamps as
  text through the MCP tool.
