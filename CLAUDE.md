# Beat Vegas — project brief for Claude Code

**Mission (Tate, 2026-10-07): "Find where the market is wrong. Prove it with data. Bet only when we
have an edge. Build trust by showing the truth."** Beat Vegas is a college-football betting research
lab that may become a business; it follows the evidence to whatever market holds the strongest,
most repeatable, most defensible edge. **`docs/ROADMAP_2026.md` (v2.2) governs 2026**: every
strategy runs on paper, judged by line value against the de-vigged consensus close; Tate also bets
first-half unders with real money as a personal ledger that is never evidence (v1.4). It began as a first-half (1H) unders system on **Hard Rock Bet** (the only sportsbook
bettable from Florida); that is now one hypothesis among several. **It never places bets or
automates gambling.** Site: https://beat-vegas.vercel.app — readable by anyone with the link,
password guards writes.

This file is the brief: what the system is, how it runs today, what is open, and the rules.
It is kept under 400 lines by `tests/test_claude_md.py`. **History lives in `docs/HISTORY.md`**
(every dated episode, newest first) — never restate it here; a change edits the relevant
paragraph below in place and appends its episode there. When this file and a memory file
disagree, **this file wins**; memory files hold lessons and point here.

## Read first
- `docs/ROADMAP_2026.md` — the governing 2026 plan (v2.2): what is tested, how an edge is judged,
  what real money does. Changed only by a versioned amendment logged at its bottom. `docs/CONSENSUS.md`
  is the judge it names (engine `cv1`, table `hp1`); `docs/PROTOCOL_2026.md` is the test every arm
  runs (weekly SPRT, alpha 0.5% each, K = 10).
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
  `DATA_STACK_REVIEW_2026-10-05`, `CFBD_TIER3_REVIEW_2026-10-05`, `WEPA_F`, `CFBD_CATALOGUE`,
  `FG_MARKET`, `KNOWLEDGE` (the Discord/community knowledge base), `CFBD_BUSINESS_TEARDOWN`,
  `LEGAL_MEMO_2026-10` (payment rails gate a paid tier; not legal advice), `HISTORY_DEPTH`,
  `ELO_F`, `MARGIN`, `CFBD_PACK` (the Starter Pack walkthrough), `LITERATURE` (the verified papers
  behind the six history looks), `MODEL_FIX` (the four-fix model, NOT MET 10-10), `PRICING_RESEARCH` (Hard Rock against the market, exploratory) (all in `docs/`).
- `docs/program/REVIEW_2026-10.md` — the October review (Tate's 16 decisions, 2026-10-11);
  `docs/program/JANUARY_2027_REVIEW.md` — the two reads (12-07, 2027-01-25) and the 2027 default (v2.1);
  `docs/external/` — outside reports, dated. Plans: `~/.claude/plans/`. Private skills: `~/.claude/skills/bv-monday-read` (the one-page Monday read; replaced bv-weekly-review 2026-10-13), `bv-card-check`, `bv-ship`, `bv-site-check`.
- `README.md` is the public setup + run guide; it must not contradict this file.
## Where we are (as of 2026-10-11)
- **The reset (`docs/ROADMAP_2026.md`)**: a strategy is promoted only by passing a
  pre-registered sequential test on line value — EV at the wager's exact terms against the
  vig-free median-of-books consensus close (newest snapshot ≤2 h before kickoff) — designed for +3%
  EV, inside a 5% family-wise budget held as a fixed ledger (K = 10 tests, 0.5% each, never
  recycled). Promotion → $10 flat live validation. Up to 8 uncapped paper arms (v1.8): 1H unders,
  1H overs (bottom 20%), full-game unders, derivative consistency + stale lines (4-5, not built),
  weather (6-7), 60+ totals (8); shadow engines sit outside the slots. Every confirmatory clock
  starts after the Statistical Protocol is registered; all earlier rows are development evidence.
- **Real money: Tate's personal first-half-unders ledger since 2026-10-08 (v1.4)** — the old rule
  (BET at the per-slate bar, top 5 a week by gap, every money-path check), $10 flat, no stop rule,
  never an observation for any arm; paused 2026-10-07 → 10-08 and again since 2026-10-17 (audit). Signed in, a BET inside the cap
  reads "Bet one unit", past it "Paper signal"; visitors never see bet wording.
- **Real money stood 10-10, −0.29u through week 5** (Wilson 29.9–70.1%), plus two week-6 tickets
  placed 2026-10-06 before the pause (`manual_picks` 102, 103; they grade as normal). H-STOP-2
  closed inconclusive (profit n=10, LLR −0.26; line value n=9, LLR +0.73); H-NEGGAP-P, H-FG-P,
  H-PCT-TIE, H-TIMING and H-CLOSE-W superseded; H-MARGIN closed (Pick'em dropped). The neggap and
  H-FG-P collectors were retired 2026-10-08; the registered arms log from 2026-10-13.
- **What the evidence says**: the market-blind 1H model is level with the market at best (2026
  average first-half miss 8.34 vs Hard Rock 8.22 over 213 games; H-HIST pooled 8.75 vs the close
  8.73, live on 2003+ training since 2026-10-07); the 2026 factor screen found no input, nor the
  gap, predicting the residual against the close (87 comparisons, best p 0.117); in weeks 4-5 the
  gap did not sort unders from overs. Closed null: 1H censoring, weather × style, two-sided overs,
  Hard Rock lag at a day grain, WEPA-F, ELO-F, the margin model, the four-fix model (H-MODEL-FIX).
  2023-25 (1,902 real closes) is spent for rules we derive; a literature hypothesis gets one look,
  judged on the years after the paper's own sample (Arscott, national TV, Bennett: NOT MET 10-09).
- **The model and bar as built** (they feed the paper arms): market-blind HGB, 55 inputs (B-SERVE
  dropped 57 NaN at serving, the leak fix 3 kickoff-weather; rivalry = trophy games; kickoff clock and
  time-zone change = the venue's IANA zone, `venues.timezone`, since 2026-10-17; `weekly_update.py`
  fails a run >90% NaN on a column training has <10% NaN). The per-slate bar (H-PCT) is the k-th largest gap
  over the slate's Hard-Rock-priced games, k = max(1, round(0.2 × N)) — `model/score.py::slate_bar`
  mirrored by `verdict.ts::slateBar`, golden vectors in `tests/fixtures/slate_bar_vectors.json`;
  `BET_GAP_PTS = 1.75` survives only as the empty-slate fallback. The weekly refit writes a
  `model_runs` row with its frame fingerprint; **any number about the live model comes from a
  runner dispatch and names it**.
- **Market facts**: Hard Rock posts 1H lines Tue 31% → Fri 78% → Sat 97% and they barely move; its
  feed row drifts to alternate rungs near kickoff (open item); the negative-gap band's live overs
  were mostly Hard Rock ALTERNATE lines (`docs/NEGGAP_PAPER.md`).

## Open items (the only place pending work lives; date each)
- **This week (2026-10-14)**: alternate-line probe Sat 10-17 ~3pm ET with app screenshots (`probe_alt_totals_h1`);
  first scheduled Monday read 10-19; H-ARM-EVP collects exploratory (`beatvegas/evp_paper.py`, no slot), decided in January.
- **Roadmap build queue (2026-10-07; each its own PR, `docs/ROADMAP_2026.md`)**: multi-book
  spreads + moneylines (capture shipped 2026-10-07: `full_game_spread` / `full_game_ml` rows with
  `home_price` / `away_price`, `us_ex` on every pull, ~+860 credits/month) and one team-total
  probe (`H-MKT-PROBE`, Saturday 10-10, then Tate decides capture) → literature looks (papers
  verified 2026-10-08, `docs/LITERATURE.md`, v1.3: six looks, Holm 5% outside the ledger;
  Arscott/TV/Bennett all NOT MET 10-09 and Cox NOT MET 10-11 (final); Coleman/Salaga parked; team
  totals and full-game weather tracked as candidates) → arms: 1-3 registered 2026-10-08 (H-ARM-1HU /
  1HO / FGU, clocks start at the 10-13 card (p1.1; weeks per p1.2, 10-14); 6-7 = weather unders,
  10+ mph forecast, v1.6, `wx_paper.py`; 8 = 1H unders at a 60+ total, v1.8, `ht_paper.py`; `protocol_position.py` on Mondays; 4-5 not designed) → shadow engines (none this season, v2.0);
  the offline backtest engine is retired (2026-10-11). The
  full game's week-wide move is re-read once it has six weeks of in-window closes (protocol p1).
- **The pause switch (`rule_paused`) is ON since 2026-10-17 13:27 UTC, so the personal ledger is PAUSED** (audit round 1, Tate's call, until he
  lifts it after the plan's data-trust phases; written through Neon's HTTPS endpoint like `scripts/rule_pause.py`; earlier on 10-07 → 10-08).
- **Hard Rock's feed row drifts to an alternate rung near kickoff** (measured 2026-10-01:
  main-line share 97% beyond 48 h, 31% inside 2 h; 142 main→rung flips vs 5 back). Late
  candidates read `no_hr_line` because of it. Decide: ask the feed for `alternate_totals_h1`
  (2 credits an event, one probe first), report to The Odds API, or accept. (The Vercel
  `lines-close` backup ran its first Saturday on 2026-10-03: 14 hourly dispatches,
  `close_coverage_pct` 1.000 = 53 of 53, so coverage itself is no longer the casualty.)
- **Arms 1-3 clocks started at the 2026-10-13 tue_pm card** (`cards.id` 29, 20:51:39Z; `protocol.ARMS_START`;
  the 10-11 refit `model_runs` 10). First read 10-19. `weather_actuals` fetch ~46% (2013-mid 2019), resumed on Mon-Wed only (v2.1).
- **Reads (v2.1)**: light read 2026-10-12; first one-page Monday read 2026-10-19 (then weekly); mid-point
  2026-12-07 (with H6, no decisions); final 2027-01-25. After 10-19: one late GitHub cron per job,
  post-mortem tables stop. All four literature looks closed NOT MET; Coleman and Salaga parked.
- **Accounts (v2.1)**: CFBD to Tier 1 at the **Nov 6** renewal (boomtatermac key, `docs/OPS_ACCOUNTS.md`);
  The Odds API stays on 20K; Actions cap to $20. Kalshi account only on the January H-VENUE-1 read.
- **The repo is PUBLIC again since 2026-10-16** (Tate): the $10/month Actions cap was hit mid-month
  and GitHub refused every job from ~04:00Z (a refused job has 0 steps; its check-run annotation
  names billing). Public removes the minute cap; nothing secret is tracked (scanned 2026-10-16).
- **2026-12-07**: the one confirmatory look for `docs/WHEN_TO_BET.md` (H6); the script refuses
  `--confirmatory` before then.

## Decision calendar (all times ET; GitHub crons are the backup, Vercel is the trigger)
| When | Job | What |
|---|---|---|
| Tue / Thu / Fri, gate 3:45–5:15pm | `card.yml` slots `tue_pm` `thu_pm` `fri_pm` | whole-week 1H sweep + injuries → FINAL card; paper windows 48 h / 24 h / rest of week |
| Sat, dispatch 7:45–9:00am, gate 7:45–9:15am | `card.yml` slot `sat_am` | same sweep before the morning sitting; paper window rest of week |
| Sat 10:00am–11:59pm, one tick per UTC hour (15 entries, 14Z–04Z) | `lines-close` → `lines_watch.yml market=1h_close` | per-game Hard Rock closes, 6 h look-ahead on Saturday ticks (`CLOSE_LOOKAHEAD_MIN_SAT=360`, since 2026-10-11; weeknights 120); GitHub's every-30-min crons stay |
| Tue–Fri 6–11:59pm ET, hourly (24 entries, 22Z–03Z) | `close-weeknight` → same close poll | weeknight closes (1H + full game); GitHub's 22Z–03Z crons stay as backup |
| Sun 1–5pm (ticks 18/19/20Z; 23Z catch-up, v2.2) | `sunday.yml` | full-game opener capture → pace + weather → weekly refit + score → derived 1H lines; `need_capture` / `need_score` probes |
| Mon 6am–3pm ET (ticks 12Z, 15Z retry; 18Z catch-up; GitHub 12:30Z backup) | `pricing-monday` → `pricing_monday.yml` | the Monday read: the pricing report (H-PRICE-HR, `pv1`, forward since 2026-10-13) and every arm's position, one `arm_positions` row per hypothesis per read date (the site, the Monday read and January read that row); health contract `monday` |
| Daily 10Z + 20Z catch-up (GitHub 10:30Z; 16:00Z Sun–Fri) | `grade.yml` | finals (CFBD, ESPN fallback) → grade picks, records, ledger → post-mortem (Monday or `hist=true`) → coverage gauge |

Slot windows live in `beatvegas/ci.py` (`resolve_slot`, `PAPER_WINDOW_HOURS`), the Vercel table
in `web/lib/cronJobs.ts` (mirrored by `web/vercel.json`, which **must live in `web/`**). A
`manual` dispatch is always a preview and paper-logs nothing. The `cards`-row probe stops the
two triggers double-building; `force=true` overrides (and is the one override of a named slot's
ET gate on a hand dispatch, 2026-10-14). Every scheduled Neon-writing job ends with
`scripts/health_check.py --job <job>` (`always()`), which writes `last_health_<job>` for the
board banner and `/api/health`, exits 1 on `failed` (GitHub emails) and 0 on `degraded`.

## Architecture
- **Engine** (`beatvegas/` + `scripts/`): capture → enrich → score → grade, run by GitHub Actions.
  Nothing runs on the Mac on a schedule and nothing texts Tate; the board is the failure surface.
  Data: CFBD (games, PBP, SP+, talent, returning production), The Odds API (`totals_h1` per
  event; full-game bulk totals + spreads + moneylines), TeamRankings tempo, Open-Meteo weather,
  Rotowire injuries, ESPN scores.
- **DB**: SQLAlchemy (`beatvegas/db/models.py`, `_MIGRATIONS` + `_DATA_MIGRATIONS` in
  `db/store.py`). `DATABASE_URL` → Neon Postgres (psycopg3); unset → `data/beatvegas.db`. A
  schema change is Python first, `migrate.yml`, then the new columns **hand-added** to the
  curated `web/prisma/schema.prisma` + `npx prisma generate`, then deploy. Never commit a full
  `prisma db pull`: it introspects every table in the shared Neon database (22 models the app
  reads by raw SQL on purpose, six `swfl_*` fishing tables) and strips the comments (2026-10-04).
- **Site** (`web/`): Next.js App Router + TypeScript + Tailwind v4 + Prisma 7 (driver adapters:
  `PrismaPg`, `PrismaNeon` under `NEON_HTTP=1`) + Recharts, on Vercel. Three tabs — Board (`/`, one
  ranked list under a slim research line), Results (`/results`: the personal stake, the arms' forward picks, the
  pricing opportunities), Research (`/research`: a card per hypothesis from `arm_positions`, the closed
  hypotheses from `web/data/hypotheses.json`) — plus `/game/[id]` (the only place a pick is logged)
  and `/records`. Fourteen legacy routes (incl. `/proof`, `/how-it-works`) are 308s in `next.config.ts`. **Owner-only content renders behind
  the cookie** (`viewerIsAuthed()`): ops and build warnings, the owner's pick list with its edit/delete controls on Results, the log
  control (roadmap v2.0 removed the My-teams chip, the answer bar, the Monday review and the research section). **A visitor sees the board and game page as the owner does, ratings before kickoff included, in paper wording** (roadmap v1.7, `lib/signalGate.ts`);
  `/records`, the ledger and both CSVs still withhold a game until kickoff. No dollars are public. API:
  `/api/picks`, `/api/picks/[id]`, `/api/bets` (30-column CSV), `/api/records`, `/api/health`,
  `/api/login`, `/api/logout`, `/api/cron/[job]`, `/api/price-refresh` (owner; one-game poll). Reads are public; writes need the
  `APP_PASSWORD` cookie (`lib/gate.ts::gateDecision` in `middleware.ts` AND
  `lib/session.ts::requireAuth` inside every pick route). `/api/cron` authenticates on
  `CRON_SECRET` and dispatches with `GITHUB_DISPATCH_TOKEN`.
- **Model**: market-blind HGB regressor on `BV_FEATURE_COLS` (`model/bv_line.py`, = `FEATURE_COLS`
  − `MARKET_COLS` − `SERVE_UNAVAILABLE_COLS` − `LEAKY_WEATHER_COLS`), FBS-vs-FBS training (`etl/fbs.py`,
  `data/fbs_teams.json`), trained on 2003+ (`score.CHAMPION_TRAIN_MIN_SEASON`; other frames
  2023+), global intercept, re-fitted every Sunday. `score_slate` ranks by `gap = line − bv_line`;
  the 0-100 score, tier and kill line all derive from the gap against the slate bar. `bv_sigma` is
  one slate-wide number — no probability from it.

### Workflows (`.github/workflows/`)
| File | Trigger | Writes |
|---|---|---|
| `card.yml` | Vercel dispatch + 16 backup crons; inputs slot/force/season/week/max_credits | `cards`, paper `manual_picks` (H-ARM-1HU), `challenger_picks` (H-ARM-1HO/FGU/WX1H/WXFG/HT1H), `build_forecasts`, preview |
| `lines_watch.yml` | Vercel `lines-close` / `close-weeknight` + 4 crons; input market | `odds_snapshots` (1H; full-game totals, spreads, moneylines) |
| `sunday.yml` | Vercel + 3 crons; input force | full-game snapshots, `team_tempo`, `weather`, `predictions`, `model_runs`, `derived_lines` |
| `grade.yml` | Vercel + 2 crons; inputs hist/regrade | finals, graded picks/records, factor ledger, post-mortem, gauges |
| `ci.yml` | `pull_request` only | — (pytest, vitest, tsc, e2e lane on postgres:16) |
| `pricing_monday.yml` | Vercel `pricing-monday` (12Z + 15Z retry + 18Z catch-up) + 1 cron, dispatch | `arm_positions` (one row per hypothesis per read date; `--write` only here) + the pricing report (run Summary + `pricing-report` artifact) |
| `migrate.yml` | dispatch | `init_db` on Neon (additive) |
| `study.yml` | dispatch script/args | a read-only report artifact (runner-frame numbers) |
| `rescore.yml` | dispatch season/week | re-scores a past week, no snapshots |
| `backfill_intercept.yml` | dispatch season/write | `predictions.bv_intercept` |
| `backfill_1h.yml`, `history_load.yml` | dispatch (paid / free CFBD) | historical 1H closes; 2003-22 FBS games + pregame Elo (study-only) |
| `enrich_tempo.yml`, `weather_backfill.yml` | dispatch | `team_tempo`, `weather_obs` |
| `weather_actuals.yml` | dispatch start/end/sources/promote | `weather_actuals` (study-only observed weather, ERA5 + CFBD) |
| `opening_watch.yml` | Vercel `opening-watch` hourly + GitHub 20-min backup, Fri 10-16 → Tue 10-20 (temporary research) | — (artifacts and cache only; no database) |

Secrets: `DATABASE_URL`, `CFBD_API_KEY`, `ODDS_API_KEY` (repository secrets only). Every job runs on
`ubuntu-24.04` (pinned 2026-10-17, never `ubuntu-latest`), installs `pip install --require-hashes -r
requirements/lock.txt` (Python 3.11, 32 pins), and takes dispatch inputs into `run:` only via `env:` (`tests/test_workflows.py`).

### Scripts (`scripts/`, grouped; every script is idempotent)
- **Live jobs**: `weekly_update` (score; `--min-games 0`, serve-skew guard, refit `model_runs`),
  `poll_lines` (1H; `--hr-universe`, ranked sweeps), `poll_full_game`, `build_card`, `publish_shortlist`
  (H-1H-SHORTLIST, stopped 2026-10-16; dry runs only), `research_preview`, `grade`, `grade_records`, `grade_factor_ledger`, `post_mortem`,
  `backfill` (season load; scores first, venues soft), `backfill_scores_espn`, `enrich_tempo`,
  `enrich_weather`, `post_derived_lines`, `close_coverage`, `record_gauge`, `health_check`,
  `fg_shadow` (H-FG-P's `bv_fg_v1` scorer; never read as the champion), `consensus_backfill`
  (the judge's columns on graded picks; grade.yml writes, study.yml reports).
- **Positions / rule**: `protocol_position` (the registered arms; `--write` stores `arm_positions`, Monday workflow only), `stopping_rule_position`,
  `neggap_position`, `fg_position`, `challenger_position`, `rule_pause`, `pick` (no `add`).
- **Studies (registry-gated)**: `harness_report --row <id>`, `residual_gate`, `level_anchor_gate`,
  `intercept_gate`, `inseason_gate` (closed gates; the position scripts import them), `weather_gate`,
  `blend_gate`, `gates_study`, `when_to_bet_study`, `sharp_book_probe`, `censoring_study`,
  `neggap_level_study`, `frame_snapshot`, `margin_backtest`, `week_shock_study` and `protocol_sim` (size the 2026 Statistical Protocol), `literature_look`, `weather_history_look`, `judge_check`, `model_fix_study` (H-MODEL-FIX), `venue_check` (H-VENUE-1), `wind_forecast_check` (H-WX-ICON-BIAS, ICON wind vs observed).
- **Backfills / one-offs**: `backfill_1h_history`, `backfill_fg_history`,
  `backfill_bv_intercept`, `backfill_game_records`, `backfill_spread`, `backfill_spread_open`,
  `backfill_pbp`, `backfill_enrichment` (pace), `backfill_weather` +
  `weather_validate`, `backfill_weather_actuals` (study-only observed weather), `derive_multiplier`, `reconstruct_pick_prices`, `build_trophy_games` (rivalry list),
  `wepa_weekly_extract` (the H-WEPA-F z-table from the gitignored Patreon weekly files),
  `build_halfpoint_table` (the consensus engine's frozen line-conversion table, study.yml), `build_shortlist_reference` (freezes `data/shortlist_reference.json` from the H-1H-FACTORS screen).
- **Model / research**: `line_study`, `model_artifacts`, `bv_adjust` (the offline backtest engine and
  its tools went 2026-10-11, roadmap v2.0).
- **Pricing research (exploratory, read-only)**: `pricing_check` (H-PRICE-HR, rule `pv1`; `docs/PRICING_RESEARCH.md`).
- **Probes**: `probe_hr_keys` (one-off, by hand: `hardrockbet` vs `hardrockbet_fl` with the feed's
  raw keys and stamps kept; prints the credits it spent; writes nothing); `probe_alt_totals_h1` (programme 4.4, one run, Hard Rock + 9 books in one region, ≤24 credits); `opening_watch` (temporary, ≤5,500 credits).
- **Deploy / dev**: `deploy_neon` (ADDITIVE), `pg_sim` + `simulate_week` (local week sandbox), `seed_demo`, `fetch_fbs_teams` + `fetch_team_logos`
  (each August), `dump_e2e_schema`, `export_registry` (→ `web/data/hypotheses.json`, parity-tested), `hooks/post_edit.sh`, `hooks/on_stop.sh`.

## Money path (server-side; the site never trusts the browser)
- **Live again for the personal ledger since 2026-10-08** (`docs/BETTING_POLICY.md`, v1.4; paused
  2026-10-07 → 10-08); a promoted strategy's live validation will be its own track.
- POST + PATCH `/api/picks` → `lib/ticketPolicy.ts::evaluateRealTicket` (`live`|`as_of_bet_time`): a BET needs
  Hard Rock's own MAIN line, a **live** verifiable price seen ≤6 h ago (`lib/lineCheck.ts`; none →
  `PRICE UNAVAILABLE`, old → `PRICE STALE` + the form's Refresh price), a price at or better than the kill
  price recomputed now, both teams with ≥2 current-season FBS games (`MIN_GAMES_FOR_REAL_MONEY`),
  and a free cap slot (5 a week; bonus bets use none and book no loss). Nothing defaults a price
  to −110; a missing price is NULL and refused (`PRICE MISSING`). **Paper is build-only** (2026-10-07):
  POST refuses `isPaper`, `pick.py add` is gone, and paper rows cannot be PATCHed or DELETEd.
- `manual_picks.bet_at` is when the ticket was WRITTEN (`placed_at` is the log time). A log more
  than `BACKDATE_MIN_MINUTES` (30) after the bet is judged **as of bet time**: that card must rate it
  BET, HR's price seen ≤6 h before (`lineCheck.HR_PRICE_MAX_AGE_H`, `getLineCheck(..., asOf)`); `betAtCheck`
  refuses future, >7 d and post-kickoff times; the log form's "Placed at" is blank by default.
- Real tickets freeze at kickoff; until then PATCH edits price/stake/note (a new price is re-judged,
  never null; bonus is set at log only). `uq_manual_pick_per_ledger` stops duplicates.
- Grading is side-aware in one place each: `grading.units_won(side)`,
  `picks.graded_pick_fields(side)`, `lines.book_closing_price_before_kickoff(side)`. Stored
  `clv = closing − bet` (the close never counts Hard Rock, Fliff or the feed's consensus row:
  `lines.CLOSE_EXCLUDED_BOOKS`), so **negative is the good direction for an under**; the site shows
  `−clv` (`lib/clvDirection.test.ts` pins it). `price_provenance` ∈ logged / backfilled_close / unknown;
  only `logged` feeds price CLV.
- Real: `manual_picks` (`is_paper=false`). Paper: `manual_picks` (`is_paper=true`, 1 unit, build
  only). Challengers: `challenger_picks` only — one missed filter contaminates the champion's clock.

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
- `.claude/settings.json` is tracked: `post_edit.sh` (ruff + matching tests + tsc per edit; refuses an
  added skip/xfail/only), `on_stop.sh` (full suites once per turn) and `pre_bash.sh` (push on green only, merge on all-green CI, no masked test runs) in `scripts/hooks/`.
- Lint: `ruff check` + `ruff format` (no pyupgrade — py3.9 runtime); `npm run lint` / `npm run
  format` in `web/` (`web/data/*.json` are prettier-ignored, keep them so).
- Local week sandbox: `scripts/pg_sim.py` + `scripts/simulate_week.py` (throwaway PG16, port
  54329, Neon-isolated); the e2e lane: `npm run e2e:db && npm run e2e` (synthetic fixture in
  `web/e2e/fixture/`, never `neon.tech`). Campus network: Neon:5432 is filtered — set
  `NEON_HTTP=1` in `web/.env`, dispatch `study.yml` for runner reads, or use Neon's HTTPS SQL
  endpoint (`POST https://<pooler-host>/sql`, header `Neon-Connection-String`, body `{"query"}`).
- Dispatch by hand: `gh workflow run <file>.yml --ref main -f key=value`. Check the exit code of
  every test run yourself — `pytest | tail -1` masks it and let a red suite push once.
- Merge with `bv-ship` (squash, CI incl. e2e, prod health, routes 200); site PRs: `bv-site-check` first.

## Honest status of the edge (don't oversell)
- **Live evidence first.** Real money stood 10-10 (−0.29u) on 20 tickets when it paused, inside its
  Wilson interval either way (the v1.4 personal ledger is never evidence); H-STOP-2 (`docs/STOPPING_RULE.md`) closed inconclusive. From 2026-10-07 the
  only judge is each arm's registered sequential test on line value against the consensus close;
  the site states every rate with its interval and labels the bankroll "modelled from the ledger,
  not reconciled". Line value against the close is the one edge measure that needs no proxy; it
  is read at each wager's exact terms by `beatvegas/consensus.py` (`ev_cons` on every graded pick).
- **What is measured, not gated**: the model's ~2-pt level deficit and its spread-bucket accuracy
  vs Hard Rock (the post-mortem tables; not read weekly since 10-13), the negative-gap band (superseded 10-14), the gap
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
  Browser pane for captures** (it caps at 800x500); its `javascript_tool` still measures the DOM.
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
- Whether any row is proxy-graded (never presented as a real-line number; every table splits on
  `line_real IS NOT NULL` with both n stated).
- The sign convention, checked against one hand-worked pick: stored `clv` is `closing − bet`, so
  **negative is the good direction for an under** and the site displays `−clv`.
- Any number about the LIVE model comes from a runner dispatch and names its frame fingerprint.
- **Every number carries the query, script or run id that produced it, and its row count**; an
  inference is labelled as one. A count or list Tate cannot re-run is not stated (2026-10-13).
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
  late: a 0-0 half is trusted only when 4+ numeric quarters sum to each side's final (stored as
  `linescores_verified`) or the PBP running score reaches the final (`pbp`); the grader trusts those two
  labels only (`grading.ZERO_PROVEN_SOURCES`). Never "fill in" a missing half without one of the two proofs.
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
  route refuses out-of-window ticks; `boardHealth.ts` warns on a closed window with no tick.
  `card.yml` runs its own missing inputs. Before calling a job missed or failed, run `gh run list
  --workflow <file> --event workflow_dispatch`: a hand run from another session counts.
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
