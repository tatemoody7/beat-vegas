# Beat Vegas — project brief for Claude Code

College football **full-game + first-half (1H) unders** research & decision-support
system, focused on **Hard Rock Bet** (the only book bettable from Florida).
Research only — it never places bets or automates gambling.

## Current state (read this, then the pointers — don't restate history from memory)
- **2026-09-26 (EVERY BET WE'VE PLACED — the ledger at the top of Track record).** Prompted
  by the Paramount Sports teardown (Lee Sterling's most-cited proof is one long self-graded
  list of picks; ours is stronger but was one week at a time inside Results). `/proof` now
  opens on `BetLedger` (`lib/betLedger.ts` pure grouping/CSV + `lib/betLedgerDb.ts` ONE
  query joined to `games` for the kickoff and both teams' first-half points): real money
  first with Paper / All one click away, a summary strip (win rate, W-L-P, units, ROI, Wilson
  interval, line value), weeks newest first each with its own record, a **running units**
  column, **whole-row tint** (`.bv-row--won|--lost|--push` = `--good-bg`/`--bad-bg`/
  `--push-bg`, pending rows bare), the score as `away–home · total`, no logos, and a proof
  row per bet (our number then, the frozen decision sentence from the new shared
  `lib/loggedAs.ts`, posted ET + hours before kickoff, book + `PROVENANCE_TEXT`, closing
  line/price/capture time, note). `GET /api/bets?season=` streams the 30-column CSV with the
  stored clv beside its displayed negation. The ledger renders even when the post-mortem has
  never run. The e2e fixture gained a paper PUSH pick (id 7) so the push tint and `-1P`
  record are pinned; `csvCell` moved to `lib/format.ts`. Every fork was Tate's call. **A
  sticky panel inside a table cell pins to the VIEWPORT in Chrome, not the scrolling
  table** (measured): the details toggle scrolls the wrap back to its left edge instead.
- **2026-09-25 (HARD ROCK ALTERNATE LINES, PR #236, registry row H-PCT-U).** The Odds API
  sends Hard Rock alternate lines alone as its first-half total (Texas @ Tennessee: 30.5 at
  −160 against 27.5 in the app). The old −160 check missed 33 of them on 31 games.
  `devig.is_hr_rung` now flags a quote at −140 or worse, or 2+ points off the other books in
  the same sweep. The card and the board then show Hard Rock's last real line with its time
  (`hr_alt_line`), and it can never be bet. The 12 paper picks already logged on alternate
  lines stand as logged.
- **2026-09-23 (THE INSIGHTS-REPORT PLAN SHIPPED: TEN PRs #223-#232, ONE DAY).** Plan file
  `i-want-everything-that-smooth-lake.md`; every fork was Tate's call. **Rules + hooks (#223):**
  `## Visual Verification` and `## Analysis Rules` below; `.claude/settings.json` is now TRACKED
  (`.gitignore` says `.claude/*` with exceptions — git cannot re-include a file under an excluded
  directory) and carries two hooks: `scripts/hooks/post_edit.sh` (ruff + the matching
  `tests/test_<name>*.py` or `lib/<name>.test.ts` + tsc on every Edit/Write, exit 2 feeds the
  failure back) and `scripts/hooks/on_stop.sh` (full pytest + vitest + tsc once per turn, blocks the
  FIRST stop on red, never twice; a HEAD+worktree fingerprint stamp makes an unchanged turn 0.2 s).
  **Health contracts (#225-#227):** `beatvegas/health.py` holds one contract per scheduled job
  (card / grade / sunday / lines_watch) as data — positive facts with `failed`/`degraded` severity,
  named defaults `HR_PRICED_FLOOR=10`, `STALE_AFTER_HOURS=18` (parity-tested with `boardHealth.ts`),
  `PACE_COVERAGE_MIN=WX_COVERAGE_MIN=0.8`; `scripts/health_check.py --job` is the LAST step of each
  workflow (`always()`, values via `env:`), writes `last_health_<job>` = ok|degraded|failed with a
  `run=… event=… miss=… info=…` note, exits 1 on failed (email) and 0 on degraded (board-only);
  `docs/HEALTH.md` has a generated block parity-tested against `render_contracts()`; the board
  banner + `/api/health.gauges.health` read it. **First live verdict: grade run 35879470656 wrote
  `ok`.** No LLM, no texts (Tate). **Tooling (#224):** `web/scripts/dev-worktree.sh` (own port
  3100-3199, clean `.next`, REFUSES a Neon URL without `--allow-neon`; `--link-modules` is a named
  refusal — Turbopack rejects an out-of-tree node_modules symlink), `shots.mjs --pixdiff` via odiff,
  runbook says 308, sandbox port 54329. **Playwright e2e lane (#229, #232):** `web/playwright.config.ts`,
  a SYNTHETIC time-shifted fixture (`web/e2e/fixture/{schema.sql,week.mjs,seed.mjs,expected.mjs}`;
  14 fictional games ids 900001-900014, season = `currentCfbSeason(now)`, refuses `neon.tech`;
  `schema.sql` is dumped from `models.py` by `scripts/dump_e2e_schema.py` and parity-tested by
  `tests/test_e2e_schema_parity.py`), specs per route + `web/e2e/FEATURE_PARITY.md` two-way
  parity-tested, CI job `e2e` (postgres:16 service, `next build && next start`, ~3 min); locally
  `npm run e2e:db && npm run e2e` (203 tests, ~2 min; `E2E_PROD=1` for the production lane). Two
  defects pinned as `test.fail()`, not fixed: signed-out phone header is 87 px (the Unlock `<a>`
  has no `display`), and several tap targets under 24 px (allow-listed by name). **Measurement
  harness (#228, #230, #231):** `beatvegas/backtest/harness.py` + `scripts/harness_report.py --row
  <id>` — refuses (exit 2, before the DB) any row not `pre-registered`/`exploratory` or with an
  empty criterion (`beatvegas/registry.py`); real closes only at exactly `REAL_1H_CLOSE_WINDOW_H`;
  min_games 0/0 declared; 2023-25 uses the consensus close AS a declared stand-in for Hard Rock
  (our history has ZERO `hardrockbet` 1H rows before 2026 — the book existed, the purchased feed
  did not carry it); candidate CLV clock = consensus as of the `fri_pm` build; verdict quotes the
  registry criterion VERBATIM and an exploratory row refuses a criterion function; never writes
  `model_runs`, `score.py` or the registry. `stats.wilson` is the one Wilson (`postmortem.wilson_ci`
  delegates at z=1.96, numbers unchanged); `load_closes` in two gates wrap `snapshots`;
  `intercept_gate`/`inseason_gate` load frames through `harness.load_frame` (`--frame` snapshots
  need `attrs["build"]`; pre-#230 pickles are refused). `docs/HARNESS.md`; `study.yml` dispatches
  `harness_report`. **Skills (private, `~/.claude/skills/bv-*`):** `bv-weekly-review`,
  `bv-card-check` (both smoke-run on week 3/4 data), `bv-ship`, `bv-site-check`. **Findings for
  Tate, not fixed:** no real-money ticket has `price_provenance='logged'` (week 2 `unknown`, week 3
  NULL) so price CLV is off for all ten; the live post-mortem scope writes no `postmortem_buckets`
  rows (the weekly review computes the live ladder from `postmortem_games`).
- **2026-09-22 evening (THE SERVING SKEW — B-SERVE; H-PCT and H-STOP-2 registered; PRs
  #215-#217).** The full system review (plan file `lets-get-all-the-vast-nautilus.md`) found
  the live model scoring every upcoming game with **57 of 115 inputs NaN that are present on
  every training row**: `fh_factor_frame` joins the first-half PBP season-to-date features on
  the game's OWN id, an upcoming game has no PBP row yet, and every backtest scores played
  rows so none could see it. Masking exactly those columns on played rows moves the
  prediction **−1.99 / −1.30 / −2.58 pts** (2026 / 2025 / 2024) with MAE improving — the level
  deficit the intercept studies were chasing. **They are out of `BV_FEATURE_COLS`
  (`SERVE_UNAVAILABLE_COLS`) and `weekly_update.py` now fails a scoring run whose target rows
  are >90% NaN on a column training is <10% NaN on** (`serve_skew_report`, the guard for the
  class). Effective at the week-5 Sunday refit (2026-09-27); H-INTERCEPT/H-INSEASON are not
  reopened (they studied a symptom). **Tate's decisions from the review:** the constant 1.75
  bar becomes a per-slate percentile (**H-PCT**, top 20% of Hard-Rock-priced centred games by
  gap, `slate_bar`; code in the next PR); **H-STOP closes at n=30, superseded, and H-STOP-2**
  measures the new rule with a per-pick alternative (μ₁ᵢ = 0.04 / break-even), σ 0.929 / 1.371
  from the 55 graded 2026 paper picks, the line-value clock against the centred consensus
  close INSIDE the 2 h window (unpriced picks included), priced picks only on profit;
  `manual_picks.closing_captured_at` is new (run `migrate.yml` before the next grade) and
  `grade_pick` stores it; `stopping_rule_position.py --clock 2` is the default. The
  challenger `family_verdict` compared against `"SUCCESS"` while the verdicts are lowercase —
  no arm could ever pass; fixed with a real crossing test. The 2023-25 real-close set is
  declared exhausted for rule selection. **H-PCT shipped the same evening (#217):** `slate_bar` = the k-th largest gap, k =
  max(1, round(0.2 × N)) over the slate's Hard-Rock-priced games with a CENTRED quote and a
  model read (`beatvegas/model/score.py::slate_bar`, mirrored by `verdict.ts::slateBar`, both
  pinned to `tests/fixtures/slate_bar_vectors.json` — the repo's first shared golden vector);
  `build_card` reads it over the slate first and every item carries `bar` and `hr_centred`; a
  rung never qualifies; the kill line and the 0-100 score stretch with the bar; the board
  computes the same bar over the week's rows (`HomeBoard.slate`) and the card payload carries
  `slate`; `BET_GAP_PTS` stays only as the empty-slate fallback (docs parity test rewritten);
  gate-focused tests hold the bar fixed via `build_card(bar=…)`, the slate has its own tests.
  **Money path (#218):** picks are frozen from kickoff (PATCH/DELETE), `POST /api/picks`
  decides the verdict server-side (`pickRules.serverVerdict`), `pick.py add` is paper-only and
  nothing defaults a price to −110. **Monitoring (#219):** `beatvegas/ops.py` gauges in
  `app_settings` (CFBD calls, Odds credits, last close capture, last completed grade, last
  Vercel dispatch per job) → `OpsBanner` on the board + `/api/health`; the grade probe keys on
  the completed-grade gauge. **The dispatch gauge was write-only until the evening's follow-up:**
  the cron route wrote `last_dispatch_<job>` and nothing read it, and a hand dispatch by Tate is
  indistinguishable from a Vercel one in the runs API (same actor). Now the route records every
  in-window tick that acts (`dispatched` or `already_ran`), `boardHealth.ts` derives one gauge per
  `CRON_JOBS` entry and warns when a job's last CLOSED window saw no tick (an open window and a
  never-written row are silent), `/api/health` carries `gauges.lastDispatch`. **GitHub Actions stopped starting jobs at ~17:29Z (billing hold /
  spending limit) — every scheduled job is blocked until Tate fixes billing; see
  `docs/OPS_ACCOUNTS.md`.** **Site honesty pass (#220):** Wilson interval on the money column and
  a "modelled from the ledger, not reconciled" label on the bankroll; the Track record headline
  and the uncapped rule carry their intervals with break-even placed inside or outside; the
  board states this week's bar, its universe and how many clear it; Results' "Your decisions"
  is real-money only, with the paper ledger's decisions in their own labelled section.
  **The repository is PUBLIC since 2026-09-22 ~18:20Z (Tate):** GitHub's Payment information
  form returned the unicorn timeout on every save, so no card could be added and no Actions
  budget set; a Billing support ticket is filed; public repos have no Actions minute cap, so
  every job resumed. Pre-flip scan: no emails, phones, addresses or secret files in the tracked
  tree; commit-author emails in history are the usual public-repo exposure. Flipping back to
  private restores the 2,000-minute cap, so the card must be on file first.
- **2026-09-22 (ONE FROZEN GATE, TWO VERDICTS: THE INPUTS WERE NOT FROZEN. H-INSEASON
  TESTED-NULL, CHALLENGER FAMILY WITHDRAWN; PRs #203-#213).** Picking up the handoff's
  check ("the first build after #201 writes `bv_intercept` and logs four `challenger_picks`
  rows") found it could never have passed: `score_slate` rewrites only the target week, so
  all 214 pre-merge 2026 rows carried NULL forever and the arms would have logged NOTHING,
  silently. `scripts/backfill_bv_intercept.py` + `backfill_intercept.yml` fixed that (dry run
  verifies the stored rows reproduce, write fills NULL rows only, `bv_line` checksummed
  5,261.84 unchanged) — and its tolerance guard exposed the real story: **the runner
  recomputes the intercept as −1.2360, not the −1.8092 in `MODEL_LEVEL_2026.md`**, and
  reproduces every stored week-4 `bv_line` to 0.01 at that value. The gate workflows had
  NEVER run on the runner (a `from scripts.*` import failed there; #209); run there,
  H-INTERCEPT is still ADOPT none but **H-INSEASON misses its criterion, Holm p 0.056 vs
  the Mac's 0.004**. Tate: reconcile before either result decides anything. **Reconciled
  the same afternoon by crossing both frames with both libraries** (`MODEL_LEVEL_2026.md`,
  Reconciliation): same frame + same library reproduce to six decimals on both machines,
  thread count is irrelevant, scikit-learn 1.6.1 vs 1.9.1 moves the intercept ~0.1 and never
  a verdict — **the whole difference is the FRAME**: 40 of 196 columns, all CFBD reference
  features (advanced-stat PPA/explosiveness/success, roster experience on every 2023-25
  row, returning production), because `season_stats._cached` has no expiry, this Mac's cache
  held the tables as fetched in **June 2026**, the runner refetches each ISO week, and CFBD
  revised them in between. June data passes in both libraries; September data fails in both.
  **Tate's disposition: the criterion is judged on the data the system uses.** H-INSEASON is
  `tested-null`; **H-INSEASON-P is withdrawn before its first pick, zero rows ever logged**
  (`build_card.py` logs nothing unless `CHALLENGER_COLLECT=1`, which no workflow sets; the
  table, arm code and `challenger_position.py` stay for a family that earns its own row).
  Every gate run now writes a frame fingerprint beside its report
  (`beatvegas/etl/frame_fingerprint.py`; `scripts/frame_snapshot.py` via `study.yml` dumps
  the runner's frame); this Mac's June cache was refreshed. **Any number meant to describe
  the live model must come from a runner dispatch AND name its frame fingerprint**; the
  champion itself is re-fitted each Sunday on whatever CFBD serves that week. Also today:
  `card.yml` timeout 15 → 30 (Monday's first-of-week build was cut at 15m22s, reported
  `cancelled`); `grade.yml` skips when a run finished in the last 4 h (three triggers a day
  ran every step, ~540 min/mo); H-NEGGAP-L registered + built (`scripts/neggap_level_study.py`,
  measurement only — its arm columns now wait on a future licensed family) and
  `TWO_SIDED.md`'s live section brought to week 3 (23 over of 26); 15 merged branches deleted
  (`dataviz-audit` kept); the `cfb-*` Cowork task folders archived (the tasks were already gone
  from the scheduler).
- **2026-09-20 (WEEK 3 GRADED + A MAINTENANCE SWEEP; PRs #176-#187).**
  **Week 3 was the first live week inside the prospective validation regime.** Real money
  **3-1, +1.65u** (season **6-4, +2.01u**, bankroll $120.10) and every BET the cards named
  was placed, nothing else. Paper **14-16, −4.09u** (−3.27u re-priced at −110; two picks were
  logged at −180/−185, which the registration says to leave alone). **The registered stopping
  rule (H-STOP) is running after n=30: profit LLR −0.44, CLV LLR −0.51 against bounds
  +3.47 / −1.58.** Nothing has triggered; real money stays on.
  **The live gap ladder held and replicated across weeks 2-3** (HR-priced, n=106):
  neg 11.5% under / 0-1.75 39% / 1.75-3 38% / **3-5 69%** / 5+ 57%; above the bar the rule is
  **29-23 (55.8%)**, on the 2023-25 backtest. The 3-5 band was strong in BOTH weeks (71%, 67%)
  and 1.75-3 weak in both (40%, 38%). **Negative gaps went over 23 of 26 times** — which the
  history does NOT show (2023-25 real-close neg band is 47.6% under, n=1,200), so it is
  registered as **H-NEGGAP, `live-tracking`, measurement only**: counts and a Wilson interval
  weekly, no gate or side change may come from it.
  **The model sits ~2 pts BELOW the market every week** (bias vs outcome −1.57/−3.11/−4.23
  against the market's own −0.65/+0.59/−2.25) and its MAE is ~0.4 worse than Hard Rock's in
  each. **Early-season first halves run hot in EVERY season** (wk1-3 share of the full-game
  total 0.53-0.56 vs 0.52-0.53 from wk4), so the under went 39-41% in weeks 2-3.
  On Saturday morning **14 of 72 Hard Rock quotes were off-market or unpriceable** (2-3 pts of
  overnight move at −150..−175), which is why Friday stays the look.
  **`early_season` blocked 10 games on the Friday card** because `games_played` counts
  FBS-vs-FBS only and an FCS opener leaves a team at 1; they went 5-5. NOT changed — the count
  is correct for what the gate measures (the feature frame is FBS-only, so an FCS game gives
  the model no season-to-date row at all); whether FCS games belong in the FEATURES is a model
  question, not a gate one.
  **THE "FALSE ZERO" WAS NOT ONE (PR #176).** The 09-16 note calling week-2 SDSU @ UCLA
  "graded WON on a first half of 0, the ESPN false-zero the guard should have caught" was
  WRONG: UCLA scored all 28 after the break. **All 15 games on file with a 0-0 half against a
  scored final are real scoreless halves** — every one reconciles against ESPN's quarter box,
  three (Iowa @ Northwestern 2023, Nebraska @ Purdue 2024, SDSU @ UCLA 2026) are confirmed in
  game reports, and 15 of 11,800 graded halves is 0.127%, with 103 halves at ≤3 points and 387
  at ≤7. Only one touched a ledger. The planned repair would have destroyed real data. What
  WAS wrong is the rule's shape, now evidence-based both ways — see the ESPN gotcha below.
  **The money path got two fixes.** `web/lib/picks.ts::createPick` never wrote `book` or
  `price_provenance` and defaulted a missing price to **−110**, so all ten 2026 real tickets
  read as priced when nothing had verified the number and none carried a closing price
  (`grade_pick` computes one only when `book` is set). Now both are written, a missing price
  is stored NULL, and **`checkPolicy` refuses any real ticket without one (`PRICE MISSING`),
  at every verdict and both markets** — paper is exempt so H-STOP's observations are untouched.
  `tests/test_pick_columns_parity.py` reads both INSERT column lists out of the TypeScript by
  regex so the two writers cannot drift again. Backfilled + regraded: all ten tickets now carry
  `hardrockbet` and a closing price, and **only `closing_price` changed** (record, units and
  line value byte-identical).
  **The week sandbox had been dead since 2026-09-14 (PR #179)** — `_CLONE_TABLES` gained
  `weather_obs` and the model map did not, so `simulate_week.py` raised `KeyError`. It also now
  runs `create_all` + `_apply_migrations` on the source SQLite first, which lags the models by
  every table and column added since the last local run. Nothing exercises that path, so it
  rots silently; two guards read `_clone_inputs`' own source.
  **Prisma 5 → 7 (PR #181).** Every client now carries a driver adapter (`PrismaPg` by
  default, `PrismaNeon` under `NEON_HTTP=1`), the datasource URL moved to `prisma.config.ts`,
  and `pg` is in `serverExternalPackages`. **`isOffPolicy` moved to `lib/pickRules.ts`**:
  `PicksList` is a client component and importing it from `lib/picks` pulled prisma — and with
  Prisma 7, `pg`'s dns/net/tls — into the BROWSER bundle, 500ing Results and Track record.
  `lib/prisma.test.ts` now scans `app/` for any "use client" file importing a VALUE from a
  database-backed module, which tsc and eslint both pass happily. Verified on both lanes
  against a real week and one prod pass; **naive-UTC timestamps round-trip exactly** under
  adapter-pg (the kicked-off gate depends on it).
  **THE MODEL'S LEVEL DEFICIT IS THE CALIBRATION INTERCEPT (PRs #192, #194).** The
  model's average line was 24.81 against a realized 29.35 on Hard-Rock-priced games,
  where in 2023-25 its mean equalled the realized mean to the decimal. That inflates
  every `gap = line - bv_line` and takes the fixed 1.75 bar from selecting 10-20% of
  games to **47-51%** — the historical 85th-percentile gap is 1.79 (so 1.75 WAS the top
  ~15%), and 2026's is 5.26-6.26. **The rule was validated as "top 20% by gap" and
  deployed as a constant**; those agree only while the level is stable.
  **Cause:** `bv_line_for_slate` adds `bias_corrections(train)["global"]`, the mean
  walk-forward OOF residual. With `min_train=500` and three training seasons only TWO
  folds are scorable, so it averages two season numbers and extrapolates to a third:
  2024 needed **−1.15**, 2025 **−2.46**, 2026 **+1.09**. It applied **−1.81** — the
  opposite sign — and that 2.90-pt gap IS the whole deficit (raw model bias is only
  −1.09). The step meant to REMOVE bias adds 1.81 pts of it. Not a coding error; the
  residual sign is right. Registered as **H-INTERCEPT**, criterion written first.
  **H-INTERCEPT RAN THE SAME DAY AND IS `tested-null`: NO ARM ADOPTED** (`scripts/
  intercept_gate.py`, grid lambda in {0, 0.25, 0.5, 0.75, 1.0} declared before the run).
  Every challenger beat the incumbent on mean |bias| (1.784 -> 1.565 at lambda=0) and on
  the worst season (2.895 -> 1.990 at lambda=0.5) and every one failed the per-season
  clause, for two reasons. **2025 wants the OPPOSITE fix**: the model reads +2.46 HIGH
  there before calibration, so shrinking monotonically worsens 2025 (1.31 -> 2.46) while
  improving 2026 (-2.90 -> -1.09). No constant multiplier serves both -- which IS the
  finding. And **2024 cannot discriminate at all**: its training window is 2023 alone, so
  `oof_residuals` has no scorable fold, `bias_corrections` returns 0.0, every arm
  coincides and the interval is [0, 0]. The every-season clause is UNSATISFIABLE there,
  about the test rather than the intercept; the criterion was NOT amended to route around
  it. Two more things the run exposed: **6 of 12 challenger-season intervals have ZERO
  WIDTH** (two arms differ by a constant, so the difference of absolute means is constant
  unless a resample crosses zero bias -- "CI excludes zero" is near-vacuous against a
  constant shift), and **dropping the intercept does NOT repair selection**: 2026 still
  clears the bar on 42.6% of priced games at lambda=0 against 60.7% at the incumbent and a
  validated band of 15-20%, while **2024 sits at 18.8% with no intercept applied at all**.
  Registered alongside: **H-INSEASON** (`pre-registered`, its own family
  `in-season-calibration`) -- `score_slate` trains on `season < target_season` strictly, so
  2026's own 153 graded games reach neither the fit nor the intercept; the arms are a
  precision-weighted blend `w = n/(n+k)`, k in {25, 50, 100, 200}, `c_season` from the RAW
  pre-intercept prediction, window closing strictly before the build.
  **H-INSEASON RAN THE SAME DAY AND PASSED ITS DEVELOPMENTAL GATE -- THIS IS NOT A
  BETTING-VALUE FINDING AND MAY NOT BE QUOTED AS ONE** (Tate, 2026-09-20). All four arms
  passed (`scripts/inseason_gate.py`; mean abs bias 1.784 -> **0.810** at k=25, worst
  2.895 -> 1.776, no season worse, Holm adjusted p 0.0040 on all four), but **the primary
  level-bias measure is PARTLY MECHANICAL for this estimator**, so the pass establishes no
  prospective betting value. The estimator subtracts an estimate of the season's own level
  error and is judged on that error, so any running mean converging to the season mean
  drives the metric to zero whether or not a single prediction improves. It is NOT leakage
  (the window is strictly prior; a week-8 game sees weeks 1-7). MAE does not rescue it --
  it improves in all three seasons (8.918/9.088/8.233 -> 8.840/8.988/8.094 at k=25) by
  **exactly** what removing that much bias implies at ~9 pts of error, so it is the same
  fact restated. What the run DOES establish: the season's level is estimable from its own
  games early enough to be worth applying, and the correction is not purely mechanical --
  2024's bias drifts within the season (+1.01/+0.02/+0.97/**+2.13** by week band) and the
  prefix mean lags it, leaving +1.22 at weeks 11+. **Selection is the consequential
  number**: the share clearing 1.75 becomes far more uniform (2024 18.8 -> 24.6%, 2025
  11.9 -> **18.2%**, into the validated band; 2026 60.7 -> 49.2%), but **2026 stays at
  49.2% because a third of its 153 games are week 1**, which by construction gets no
  in-season evidence -- the estimator is weakest exactly when a season is young, which is
  when the deficit bit. And on 2026 ALONE, simply dropping the intercept beat every
  in-season arm (-1.09 vs k25's -1.78); the blend wins overall only because it also fixes
  2025 (+0.28 vs +2.46). **The only thing it licenses is properly registered prospective
  paper collection**, whose row is written before its first pick. **NO k is chosen and none
  will be chosen from this run** (Tate): the gate had no ranking rule, so picking the
  best-looking arm out of the same 2024-26 data would be post-hoc. All four go forward
  together as **one H-INSEASON challenger family** on identical decision-time snapshots,
  beside the frozen champion; if one challenger must be named for display it is the FAMILY,
  never an arm. The prospective phase is judged on measures NOT mechanically tied to the
  correction -- paper profit at actually available prices and CLV vs the closing market --
  with prediction error and level bias as secondary diagnostics, multiplicity controlled
  across the four arms, and no k selected until the prospective rule allows it. Live
  selection, `bias_corrections` and `BET_GAP_PTS` are untouched, and **H-STOP is completely
  unchanged**.
  **THE PROSPECTIVE LEDGER IS BUILT AND REGISTERED (H-INSEASON-P, `docs/INSEASON_PAPER.md`).**
  Four arms log paper observations at every card build from the same snapshot, through the
  SAME `build_card` the champion runs (only `bv_line` moves), and grade through the SAME
  `picks.grade_pick`. They write to **`challenger_picks`, never `manual_picks`** -- its own
  table because every query feeding the bankroll, the cap, Results and H-STOP's observations
  reads `manual_picks`, and one missed filter would contaminate the champion's clock; the
  table has no `is_paper`/`is_bonus` column at all. **`Prediction.bv_intercept` is new** and
  is what makes it work: the RAW pre-intercept prediction is `bv_line - bv_intercept`, and
  `c_season` MUST come from the raw number (a calibrated one re-applies `c_prior` scaled by
  `w`, and no report would show it). The as-of window is SQL, not memory: a game counts only
  if it kicked off before the build AND its first half is graded. Position:
  `PYTHONPATH=. python scripts/challenger_position.py`. Budget is `stopping.CHALLENGER` --
  H-STOP's own mu1/sigma reused, but 5% split /4 arms (Bonferroni) then /2 clocks = 0.625%
  per arm-clock, bounds ln A +4.8520 / ln B -1.6032. An arm PASSES only when BOTH clocks
  cross A, is DROPPED when EITHER crosses B; **if more than one arm passes, no k is chosen --
  that needs its own registered row**. **Run `migrate.yml` before the next card build** (new
  table + column).
  **Ruled out, so do not re-run these:** no feature changed (143 vs 153 rows at
  `min_games=0`; nothing missing, max NaN shift 7.7pp, max level shift 0.76sd — the
  weather lead is dead); week-of-season (OOF by band −1.62/−1.05/−1.76/−2.44, an early
  slate is mis-corrected by 0.19); and the prior-season level anchor (**H-LEVEL
  tested-null** on the reserved 2025 set — and it could not have passed, since 2025's
  incumbent bias is **+1.24**, the model reads HIGH there).
  **A real train/serve difference found alongside, NOT fixed:** `weekly_update.py`
  builds the frame at `min_games=0` and `score_slate` derives TRAINING from whatever
  frame it is handed, so the live board trains on a population every backtest path
  (`backtest/engine.py`, `backtest.py`, `validate_engine`, `retrain`, `residual_gate`,
  `weekly_report`, all `min_games=2`) excludes. Worth **+1.72** [+1.23, +2.22] on 2026
  but **−0.37** on 2025 and **−0.27** on 2024 — an interaction, not the cause.
  **Nothing above changed live selection:** a level shift cannot reorder the board
  (which is why the gap ladder still reads sanely), and H-STOP is measuring the frozen
  rule.
  **Dependency hygiene:** matplotlib is the `logos` extra, not a runner dep (it dragged in a
  contourpy needing 3.12), lock regenerated 39 → 32 pins; `requirements/.python-version` = 3.11
  so Dependabot stops proposing wheels the runner cannot install (its resolver ignores
  Requires-Python, and those were MINOR bumps a major-ignore could not catch); `overrides` clear
  the 4 HIGH advisories Prisma 7 put in the PRODUCTION tree (`@prisma/client` → `prisma` CLI →
  `@prisma/config`/mysql2); **react-dom 19.2.4 → 19.3.0**, a mismatch merged in #167 that
  stopped `next dev` starting. **eslint 10 is MEASURED BROKEN here** (eslint-config-next's
  eslint-plugin-react throws in `usedPropTypes`), so it, TypeScript 7 and vitest 5 are ignored
  in `dependabot.yml` and are each a decision to take on their own.
- **2026-09-16 (SITE IS PUBLIC READ-ONLY).** Tate wanted friends to open the link. Every page
  and every GET is open; the password guards WRITES only — `POST /api/picks`,
  `PATCH`/`DELETE /api/picks/[id]`, `/api/logout`. The rule is one pure function,
  `web/lib/gate.ts::gateDecision` (safe methods pass; unsafe + no cookie → 401 under `/api`,
  redirect to `/login` elsewhere; Vercel without `APP_PASSWORD` still 503s everything), called
  by `middleware.ts`, AND every pick route calls `lib/session.ts::requireAuth` itself so a
  matcher edit can never open the ledger. `viewerIsAuthed()` (cookies()) drives the header
  (Lock when signed in, **Unlock** link otherwise), hides PicksList's edit/delete for readers,
  and swaps the game page's log button for "Unlock to log a pick" → `/login?next=/game/<id>`
  (`safeNext` accepts same-origin paths only). `app/robots.ts` + `robots: noindex` keep
  crawlers off (each render is metered Neon egress). What a stranger with the link now sees:
  the board, the real-money ledger and bankroll figure, Track record, the CSV export. Verified
  live on a gated dev server: public GETs 200, unsigned POST/PATCH/DELETE 401, form POST 307,
  cookie flow 200 → Lock shown → `POST /api/picks` reaches validation (400).
- **2026-09-16 (SECURITY REVIEW + COST AUDIT; PR 1 of 5 = Actions minutes + CFBD cache).**
  Full-codebase security pass found **no exploitable vulnerability** (auth, injection,
  secrets history, workflow permissions, headers all verified, live-probed); three
  hardening items ship in PR 4. Cost: **~$62/mo → ~$33/mo** — The Odds API 100K ($59) is
  2.5x oversized for ~1,000-1,500 live credits/mo (Tate downgrades to 20K/$30 on Oct 6);
  Neon Launch (~$3) stays and the egress gets fixed anyway (PR 3). **The two FREE quotas
  were the real risks:** GitHub Actions on a private repo ran **~2,830 billed min/mo vs
  2,000 free** (CI 58%: PR + push double-ran every merge; no pip cache on ci/grade/sunday;
  20 of 29 card runs installed Python to discover `slot=skip`), and CFBD ran **~4,000
  calls/mo vs 3,000** because **`.github/actions/cfbd-cache` had been saving an EMPTY
  payload all season** — `actions/cache` saves in its post hook whoever runs first, and
  the first job each ISO week was the Tuesday research preview (zero CFBD calls), so the
  key held 12,840 bytes of `espn_teams.json` and every later run "hit" it and re-fetched
  22 reference calls; `grade.yml` (the heaviest caller, 2x/day) never mounted it at all.
  PR 1: CI is `pull_request` only + `cache: pip` (also grade/sunday/preview); `card.yml`
  runs a stdlib-only **`GATE_ONLY=true` ET gate on the runner's python3 before
  setup-python**, so out-of-window backup crons cost seconds; the cache is split into
  `cfbd-cache` (restore, outputs `key`/`hit`) and **`cfbd-cache-save`, which refuses to
  save unless ≥4 reference files >1 KB exist**, wired into every feature-frame workflow
  incl. grade and the gates (`tests/test_workflows.py` enforces both); both pinned to the
  v4.3.0 SHA; `grade.yml` runs the 2023-25 post-mortem `scope=both` **only Monday ET or
  `hist=true`**, not on every dispatch (the Vercel cron IS a dispatch, so it ran daily).
  Plan + full audit: `~/.claude/plans/in-this-next-session-lovely-wind.md`.
  **PR 2 (sunday.yml):** the `captured` probe now answers TWO positive facts — `need_capture`
  (no full-game snapshot today ET) and **`need_score` (no model prediction row for the active
  week today ET)** — and pace/weather/score/derived-lines/warn are all gated on `need_score`;
  a run that captured but died before scoring leaves no row, so the next tick still scores
  (2026-09-13 ran FOUR full ticks for one capture: ~1,150 Open-Meteo calls, 88 CFBD calls,
  40 runner-min). `enrich_weather.py` is **FBS-vs-FBS only by default** via `etl/fbs.py`
  (`--all-divisions` opts out): week 3 was 311 games fetched for 57 scored, 8 of the job's
  11 minutes. `weekly_update.py --write-refs` dumps `factor_references(frame)` and
  `post_derived_lines.py --refs` reads it (`factors/board.py::save_references` /
  `load_references`, falls back to `historical_references()`), so the ~4.6 MB historical
  frame is built once per Sunday run, not twice.
  **PR 3 (Neon egress):** the board picks its week off a 3-column `boardUniverse` (cached;
  `universeWhere()` is the ONE definition of the universe, shared with `boardGames`) and
  only then loads that week's rows, `consensusLines(season, market, week)` and
  `getLineCheck(season, market, week)`; `getPreviewByGame`, `getMovements` (string key —
  React `cache()` compares arrays by identity) and `gameSeasonWeek` are `cache()`d, so
  `/game/[id]`'s metadata+body double render dedupes. **Measured with a per-query byte
  meter (JSON-serialized results) on the week-3 board: 2.28 MB → 1.05 MB per board render,
  2.31 → 1.08 on Results, 2.74 → 0.98 MB per game page.** `store.py::upsert` batches its
  existence check (one `IN` per 500 rows, row-value tuples for composite keys) — was one
  SELECT per row, ~7,400 round trips/day from `backfill.py`. `grade.yml` ESPN look-back
  10 → 4 days. `web/lib/prisma.ts` warns once when a dev server's `DATABASE_URL` is
  `neon.tech` — `next dev` + screenshot passes against PROD through the redesign sprint are
  what tripped the 5 GB; `web/.env.example` documents the `simulate_week.py` sandbox as the
  default. NOT done: trimming `factors_json` on the board
  row (`factor_board` inside it feeds `edge.ts`, so it cannot be dropped). The
  **`odds_snapshots` index was TESTED 2026-09-20 and REJECTED** — see the gotcha below.
  **PR 4 (security hardening — the review's three items):** (1) `card.yml`'s dispatch
  `season`/`week` were echoed raw to `$GITHUB_OUTPUT` and then inlined as
  `${{ steps.active.outputs.* }}` into four `run:` blocks on a job holding all three secrets
  — `${{ }}` is substituted into the script TEXT before bash parses it, so a dispatcher (Tate,
  or whoever holds `GITHUB_DISPATCH_TOKEN`) could run a shell with `DATABASE_URL` in scope.
  Now shape-checked (`^[0-9]{4}$` / `^[0-9]{1,2}$`) and every value crosses into bash via
  `env:`; `test_workflows.py` enforces **no `${{ inputs./steps./github.event.` inside any
  `run:` of a job with secrets in `env`**, repo-wide (grade and sunday's trusted inlines were
  converted too so the rule has no exceptions). (2) `actions/cache` pinned + Dependabot dirs
  (landed in PR 1). (3) **`requirements/lock.txt`**: `uv pip compile --generate-hashes` for
  Python 3.11 / x86_64 manylinux (the runner), 39 pins incl. `setuptools`+`wheel`; every
  workflow installs `pip install --require-hashes -r requirements/lock.txt` then
  `pip install --no-deps --no-build-isolation -e .`, and `cache: pip` keys on the lock.
  **Local dev is unchanged** (`pip install -e .` against `requirements.txt`; this Mac is 3.9).
  Regenerate per the lock's header; Dependabot (`pip`, monthly) bumps pins with hashes.
  **The lock is `requirements/lock.txt`, not `requirements.lock`** (moved the same evening):
  Dependabot's Python fetcher only sees `.txt`/`.in` files, so a `.lock` was invisible and its
  first pip run (#171, closed) raised every range in `requirements.txt` to the latest release
  instead — `scikit-learn>=1.7.2` would have broken the local 3.9 venv. The pip entry points at
  `directory: /requirements`, which holds nothing else.
  **PR 5: `research_preview.yml` is DELETED.** Its Tue/Fri 13Z runs previewed **week 1 all
  season** — `research_preview.py::_upcoming_week` took the smallest week with a
  `home_points IS NULL` game, and week 1 has never-final rows — so every run was ~650 ESPN
  calls and 456 `game_previews` rewrites for a week nobody was looking at, and it was the
  job that claimed each ISO week's empty CFBD cache key (PR 1). The four decision builds in
  `card.yml` already run the preview with an explicit `--week`; the script stays, and its
  default week now comes from `beatvegas.season.detect_week` (the same rule `card.yml` and
  `sunday.yml` use), with the old scan only as the off-season fallback.
- **2026-09-16 (SITE REDESIGN — discovery + five stacked PRs #154-#158).** A full
  page-by-page review with Tate (every page and state captured at 1440 and 390, seven
  Q&A rounds, two mockup rounds). **Outcome: the structure, the gradient cards, the three
  typefaces, the colours and the board's full action sentence all STAY** — he rejected a
  trimmed status and a flat "surface tiers" treatment. What changed: copy cut to the bone
  site-wide (a definition lives once, in the glossary); the game page's decision block is
  the three tiles + the sentence + the log button (`GapBar`, gap caption, blocker/price
  lines, tier word and full-game footer are gone); **Results is Concept A "Scoreboard"**
  (`ScoreboardBand` = rule on paper / my money / line value with the curve inside, one
  `RecordTable` for market/model/rule/you/full game, `DecisionsStrip`); **Track record is
  Concept A "One finding"** (headline + `GapLadderChart` in one card with games and units
  under each bar, `RecordTable` with a "plausibly" column, `PmLiveNotes` as one panel, flags
  as rows, ONE fold for method, glossary as two-column one-liners). Foundations: one-row
  header at every width (69px, `--header-h` is one value), `.bv-chip`, `.bv-btn--ghost`,
  dead classes gone, `a.bv-card:hover` lifts board rows, `/proof/records` opens on the
  latest GRADED week. **`web/scripts/shots.mjs`** (Playwright driving the installed Chrome,
  `channel: "chrome"`) captures every page at both widths with height / overflow / header /
  first-answer / small-text / tap-target counts and `--diff before after`. Direction doc:
  `docs/superpowers/specs/2026-09-16-redesign-direction.md` (+ two research reports beside
  it). Measured: Results 3,408 → 2,890px, Track record 2,840 → 2,211, game page ~1,925 →
  1,644, phone header 97 → 69 everywhere. Deleted: `RuleRecord`, `BankrollHero`,
  `RecordCard`, `GapBar`. (A data item flagged here on 09-16 — "SDSU @ UCLA graded WON on
  a first half of 0, the false zero the guard should have caught" — was WRONG: the half
  really was 0-0; see the 2026-09-20 bullet.)
- **2026-09-15 (FULL SYSTEM REVIEW BEFORE WEEK 3; PRs #129 weather/money-path, #130 site,
  plus measurement and docs PRs).** Verified top to bottom against live Neon, the GHA logs,
  `/api/health`, ESPN and the API headers. **Ops were healthy** (grading current, CFBD
  Academic tier live with ~2,640 calls left, 0 failed runs in 40). **The 44.9K Odds API
  credits "used" this cycle are the one-time 2023-25 historical 1H-close purchase of Sep
  6-8** (used went 162 → 38,317 → 44,309 in two days); live spend is ~50-100/day, 55K
  left, renews Oct 6. `weather-clock` shipped: `weather_obs` = **27,876 rows** (2023 lead
  0 only; 2024-26 at leads 0/24/72), validator 3/3, activation still OFF; `price` is never
  overwritten and all 31 picks carry `price_provenance` (25 logged / 6 unknown); the
  censoring re-run at 2,000 draws kept **DO NOT BUILD** (CI −0.0075..+0.0156/pt, paired
  ΔBrier CI spans zero); the Historical Forecast API is **null through 2017, data from
  2018**. **Early season (<2 current-season games) is PAPER ONLY on every surface now** —
  `card.py::build_item` (blocker `early_season`), `verdict.ts`, `edge.ts` and
  `pickRules.checkPolicy` read the same fact in the same gate position (Tate: card and site
  must agree). **Live week-2 model read** (85 games, 72 HR-priced): model bias −3.1, MAE
  competitive with Hard Rock under 28 pts, **−10.2 and 29% under on 28+ spreads (n=20)** —
  the blowout blind spot confirmed live; Tate: **hold the frozen 1.75 rule**, keep measuring.
  Gap quartiles run 8/42/67/50% under, so negative gaps carry over-side information at
  n=13 — a two-sided *diagnostic* (measurement only) is the first research item. **Week 3
  is the first live week inside the validated regime** (the 2023-25 gap ladder holds ~1
  game from weeks 1-2; by week band 57.4 / 50.0 / 62.7 / 55.6%). Week 1's 50 retro
  predictions were frozen into `game_records` with `captured_at` after kickoff and the
  records grid marks them "scored after". Fixed: `grade_market_fg` idempotency,
  `_rows_for_market` over-first + split-rung skip, duplicate `contrast_*` flags. Site:
  answer bar marks placed bets, `MovementChart` and `betSlip.ts` deleted. Deleted the paused
  `cfb-sunday-ops` task. Dependabot: #99/#104/#102 merged; **#100/#101/#103 are one
  coordinated Prisma 5→7 migration** (schema `url` unsupported, adapter API change) and
  wait on Tate's call. Research queue (Tate, in order) — ALL SHIPPED the same day: two-sided
  diagnostic (`TWO_SIDED.md`), Hard Rock lead/lag + microstructure (#135), weather ×
  offensive style (#137), share-engine spec (#136, NOT built; registered as `H-SHARE` in
  `HYPOTHESES.md` — a pass of its gate licenses a prospective paper arm, not promotion);
  classifier retirement planned for after 09-19. The 1H board's
  `bv_sigma` is one number per slate (11.26) — never derive a probability from it.
- **2026-09-13 (RESULTS + TRACK RECORD REBUILT, PR #122).** The Board is not SHORTER than
  the other two pages — 6,877px against 7,753 and 9,159. It works because it is **one
  element repeated 34 times under 5 headings**, and because it never makes you read a
  visual. Results had **16 headings**, Track record **19**, each block its own shape with
  its own paragraph. So the fix was consolidation, not deletion.
  **Results is READ-ONLY** (Tate: "all the logging should happen on the board page. The
  results is just to see what I picked and how it turned out"). `BetSlip`, `CardPanel` and
  `BankrollStrip` are DELETED — all three are about a bet not yet placed. Logging is
  `/game/[id]` only (`LogPickButton`/`LogPickForm`, already linked from every board row).
  **Nothing was lost on safety: the kill line/price is enforced SERVER-SIDE for every path
  by `pickRules.ts::checkPolicy`**, not by the slip — check there before ever "porting" it
  again. `CardStatusBanner` moved to the BOARD, beside the missed-build and stale-results
  banners. Three tables became one (`Breakdown.tsx`, a By week / By reason / By blocker
  toggle); the blocker view drops the real-money columns rather than dashing them.
  **"Vs our number" is gone** — a game is only logged when Hard Rock's line sits ABOVE our
  number, so "went against it" was `— (0)` by construction. The picks table lost `Market`
  and hides `Week` when filtered to one; **`Stake` STAYS** — it looks constant but a bonus
  bet is staked differently.
  **Track record leads with the finding.** The gap ladder (48.4/44.5/53.9/54.9/58.8) was an
  8-column table under a 60-word caption while a tangent had the only chart;
  `GapLadderChart.tsx` draws it (same Recharts pattern as `LineStudyView`, and
  **`isAnimationActive={false}` is load-bearing there too**). Everything secondary folds
  away (`Fold.tsx`, a native `<details>`): the estimated block, methodology, calibration,
  the line study, and the WATCH tier of "What to change" (7 cards, 6 of them the same
  sentence). `/proof/records` paginates by week — it was **3,681 rows and 255,202px**.
  **Measured:** Results 7,753 → **3,327px** at 1440 (16 → 12 headings, 5 → 3 tables) and
  7,811 → 5,662 at 375; Track record 9,159 → **2,840px** and 9,199 → 4,529. No horizontal
  overflow at either width. Web tests 414, Python 890.
  **The design rule that came out of it (Tate): "if it isn't obvious I don't want it."** He
  rejected three proposed Results charts as unreadable — a chart that needs a paragraph
  under it has already failed, and the plain big numbers ($103.60, +5.1%) are the right
  form there. Only the gap ladder earned one. **Screenshots caught four defects the DOM
  checks could not**: the break-even label rendered dark-on-green ON the tallest bar, the
  y-axis label clipped to "How often the under wo", auto-ticks came out 40/47/54/61/65, and
  the 4-card grid stranded one alone. **Look at the picture, not just `scrollHeight`.**
- **2026-09-13 (THE PAPER LEDGER WAS MEASURING ONE BUILD OUT OF FOUR).** Every one of
  week 2's 25 paper picks was placed Sat 12:00 UTC — the `sat_am` build. Across the week's
  six builds **33 distinct games qualified**; the ledger holds 25, and the FRIDAY card's
  **three clean BETs were never logged at all** against the one Saturday recorded (8 games
  that qualified Thursday never qualified again). Cause: `PAPER_WINDOW_HOURS` gave each slot
  the gap to the next build, and college football kicks off on **Saturday** — `thu_pm`'s 24 h
  reached 6 games on the whole slate, `fri_pm`'s 16 h reached 8, neither of them a priced
  Hard Rock game, and `sat_am`'s 80 h swept up the rest. The design was doing exactly what its
  comment said. **Tate's call: Friday anchors the weekend** — `fri_pm` and `sat_am` are now
  `None` (the rest of the week), `tue_pm`/`thu_pm` keep their gaps so they can never claim a
  Saturday game before Friday prices it. Replayed against the REAL week-2 payloads: Friday
  logs 26, Saturday adds 1, nothing double-logged.
  **Second, independent bug: `add_pick` never wrote `model_line_at_pick` /
  `model_score_at_pick`.** The Next.js `createPick` was the only writer in the repo, so every
  card paper pick and every `pick.py add` left OUR NUMBER NULL — which prints "—" in the picks
  table and, because `decision-quality.ts::beatMyModel` filters on `model_line_at_pick != null`,
  dropped the whole paper ledger out of the agreed/against split. `add_pick` now takes both;
  the card reads them off the item (`card.py` exports `under_score` beside `bv_line`, same
  prediction row) and `pick.py add` reads them through the new `picks.py::model_read`, which
  mirrors the web's rule (model row over the display-only `derived_lines` row). Week 2 is
  backfilled by two `_DATA_MIGRATIONS` entries: our number reconstructs EXACTLY as
  `hr_line_at_pick - gap_at_pick` (a card item only qualifies when Hard Rock priced it, so the
  gap basis is always `hardrock`) — verified to 0.000 on all 25.
- **2026-09-13 (every scheduled text retired; PR #118).** The Mac routines were **local**
  Claude sessions, and on battery this Mac sleeps after ONE MINUTE with no `pmset` wake
  events — so they fired only if the laptop happened to be awake. Measured:
  `cfb-saturday-card` ran **twice all season** (once two days late, once 6:45pm instead of
  8:50am, on the first real-money Saturday); `cfb-weeknight-card` **never fired on a Tue,
  Thu or Fri**; `cfb-sunday-ops` ran once, three days late. iMessage cannot move to the
  cloud (it needs the Messages app and `send-verified`'s local `chat.db` read-back).
  **Tate's call: no scheduled texts at all, and no fixed decision rhythm** — which dissolves
  the problem rather than fixing it. Deleted `cfb-saturday-card`, `cfb-weeknight-card` and
  two long-dead tasks; `ainhub-ai-daily-brief` is KEPT; `cfb-sunday-ops` is PAUSED until the
  new cron below is seen to fire on a real Sunday, then delete it. A deleted task leaves its
  SKILL.md on disk.
- **`sunday.yml` finally has a Vercel cron** (`/api/cron/sunday`, three Sunday entries,
  1pm–5pm ET window). It was the LAST workflow whose only trigger was GitHub's cron, and its
  last SCHEDULED run was **2026-09-06** — a week of nothing, on the only full-game opener
  capture, which also refreshes pace, weather, scoring and the derived 1H lines. Empty
  `inputs` (it declares one OPTIONAL `force`, unlike `grade.yml` which declares none and
  422'd on any until 2026-09-16, when it gained an optional `hist` flag the cron never sends).
  `cronJobs.test.ts` already checks every entry lands whole in both DST regimes.
- **The board is now the ONLY failure signal**, so `web/lib/boardHealth.ts` (was
  `gradeHealth.ts`) reports stale RESULTS and a MISSED BUILD. A missed build means no card
  *and no line sweep*, which otherwise looks completely normal. The build check asks whether
  a `cards` row exists since the most recent build window OPENED — not a fixed threshold,
  which would have to tolerate the ~72h Sat→Tue gap and would then never fire.
- **When to look at the board** (measured on week 2): Hard Rock posts 1H lines Tue 31%,
  Wed 59% cumulative, Fri 78%, Sat morning 97% — and then they barely move (**48 of 71
  games never changed**, mean drift −0.18 pts). So waiting costs nothing on price; what
  improves is selection (BET-qualified by build: Tue 1, Wed 0, Thu 1, **Fri 3**, Sat 1).
  Best single look: **Friday after 5:30pm ET**, second: Saturday after 8:30am ET.
- **2026-09-13 (week-2 review; PRs #111-#115, all merged): THE SYSTEM DID NOT MEASURE ITS
  OWN WEEK.** `grade.yml` failed four consecutive runs from Sat 2026-09-12 morning and
  nobody knew for two days — the only failure channel is GitHub's failed-run email. Root
  cause: `backfill.py`'s FIRST action was an unguarded `backfill_venues()`, and CFBD
  returned 429. Week 2 finished with finals for **14 of 303** games, **0 of 31** picks
  graded, no CLV anywhere. Fixed in four layers: scores load BEFORE reference data and a
  venue failure warns instead of raising (a season failure is still fatal); the CFBD retry
  ladder is (5, 20, 60) over 4 attempts and honours `Retry-After`; `grade.yml` marks the
  two *enrichment* steps `continue-on-error` (PBP, factor ledger) while grading stays
  fatal; and the board carries a **stale-results banner** (`lib/gradeHealth.ts`,
  also on `/api/health`) so this can never again be invisible.
- **CFBD IS OUT OF MONTHLY QUOTA** (`{"message":"Monthly call quota exceeded."}`, every
  endpoint, resets ~Oct 1). No retry clears it — the wait is the rest of the calendar
  month, and CFBD sends **no `Retry-After`** with it, so until 2026-09-13 every call of
  every job spent the full 5/20/60s ladder and three extra calls against a budget already
  at zero. `cfbd.py` now raises **`CFBDQuotaExceeded`** on the spot (an `HTTPError`
  subclass, so existing handlers are unaffected), recognised by
  `x-calllimit-remaining: 0` or a "quota" body. Measured against the live exhausted key:
  1 call, 0.68s, was 4 calls + 85s.
  **The budget is now visible before it runs out:** CFBD reports
  `x-calllimit-remaining` on EVERY response (including the 429) and nothing read it,
  which is why this went unnoticed until grading had been dead two days.
  `CFBDClient.calls_remaining` holds the last value, every run prints it once, and under
  `_LOW_CALLS_WARN` (200) it raises a `::warning::` annotation. Tiers:
  https://collegefootballdata.com/api-tiers — free 1,000, Academic 3,000 (.edu), Tier 1
  $1/mo 5,000, Tier 2 $5/mo 30,000.
  **Scores now have a second source:**
  `sources/espn_scores.py` + `scripts/backfill_scores_espn.py` read ESPN's public
  scoreboard — no key, no quota — and ESPN's event ids ARE `games.id`, so it UPDATES
  scores on existing rows and never inserts a game, touches a team name or a line. It
  emits CFBD's key names so `etl/first_half.py` (incl. `line_scores_trustworthy`) applies
  unchanged. **ESPN cannot replace CFBD for SCORING**: no 247 talent composite, no SP+,
  no returning production — 8 feature columns are CFBD-only. Week 2 went 14 → 94 finals
  and all six real tickets graded exactly as the Hard Rock slips read.
  **The quota went on reference data**: `season_stats.py::_cached` writes to `data/cache/`,
  a GHA runner starts cold, and a feature build re-fetches sp/talent/roster/returning for
  every season (~17 calls) on all 26 card builds + 17 Sunday runs + 10 previews.
  `.github/actions/cfbd-cache` now shares that across each week's runs — keyed by ISO week
  with **no restore-keys on purpose**, since `_cached` has no expiry and a longer key would
  silently freeze SP+ at week 1. **It did not work until 2026-09-16** — the single
  `actions/cache` step saved whatever the first job of the week left in `data/cache`, which
  was nothing; see the 2026-09-16 bullet for the restore/save split. Tate is registering the **free Academic tier** (3,000
  calls, .edu) — if that is not enough, Tier 2 is $5/mo for 30,000.
- **2026-09-13 (LINE VALUE WAS REPORTED WITH THE SIGN INVERTED, PR #115).**
  `grading.py::clv_under` = `closing - bet`. Every bet is an UNDER and a HIGHER number is
  easier, so a line that **FALLS** after the bet is the GOOD one — **negative clv is
  favourable**. The glossary always said so; `decision-quality.ts` counted `clv > 0` as
  "moved your way" and `record.ts` fed the raw mean to every RecordCard's "Line value", so
  the site reported the share that moved AGAINST us. Stored values are UNCHANGED (the raw
  difference is the fact); the direction now lives in exactly two named places —
  `decision-quality.ts::favourable` and `record.ts` — and `lib/clvDirection.test.ts` pins
  it against Tate's real six week-2 tickets, so a "fix" to the sign fails CI. Displayed
  figures are negated: **+1.45 means the market came 1.45 pts toward us.**
- **2026-09-13 (week 2 graded — the first real measurement).** Real money **2-3, −1.18u
  (−$11.78)**; the bonus won, so **+0.36u (+$3.60)** all in. Paper **13-11, −0.57u**.
  **CLV is the good news: of 30 graded picks, 11 lines moved toward us, 18 flat, 1
  against** (+1.45 pts mean). **Model accuracy is the bad news.** Over 98 graded games
  (weeks 1+2) the model is LESS accurate than Hard Rock's number in every spread bucket,
  and on 21+ spreads it runs **−5.23** (book −1.79) while the 1.75-pt gate fires on **27
  of 36** of them. Realized 1H share rises with the spread (0.51 → 0.57 over 4,392
  historical games, again in 2026) and the model's is flat ~0.46 — `spread` is not in
  `FEATURE_COLS`. **Tate's call 2026-09-13: no model or gate change for week 3; fix the
  measurement, keep tracking.** Full review + every decision:
  `~/.claude/plans/here-are-all-the-hashed-lantern.md`.
- **2026-09-13 (THE LEVEL ANCHOR WAS TESTED AND REJECTED, PR #124).** Seeding
  `_season_to_date`'s expanding window with `k` synthetic games of prior-season form
  was the fix for weeks 1-2 being scored with 68 of 115 features NaN. **It does not
  work, and `etl/features.PRIOR_SEASON_WEIGHT` stays 0** (the seeded code ships inert;
  `k=0` reproduces the unseeded frame exactly, so the incumbent is an ARM of the gate).
  Weeks 1-2 showed nothing (pooled n=180, gains −0.019 to +0.131, every 95% CI spanning
  zero, not monotone in k); weeks 3+, which nobody was testing, improved monotonically
  (+0.038 to +0.117, CI excluding zero at k≥1) — the seed is ordinary shrinkage and helps
  where a team already has SOME data.
  **The NaNs are not INHERENTLY the problem: `HistGradientBoostingRegressor` handles
  missing values natively**, learning a routing direction for them, so "no games played
  yet" is a usable SIGNAL to the tree rather than an absence. Counting NaN cells and
  concluding the model is starved conflates *missing* with *harmful*. (Softened
  2026-09-14 from "were never the problem": what the experiment proved is that THIS
  remedy was not justified, not that missingness is costless — it can still remove
  information or create train/serve skew.)
  **And MAE is close to blind to what the change does.** The seed genuinely lifts
  bv_line's level (2026 wks 1-2: 24.26 → 25.20 at k=3 against a realized 26.90, about a
  third of the bias) while MAE barely moves — ~1 pt of bias is nothing against ~11 pts of
  per-game spread. But the system spends `gap = line − bv_line` against `BET_GAP_PTS`, so
  a level shift moves SELECTION even when accuracy is flat: on the 23 of those games with
  a real close, the count clearing the bar fell 14 → 11. The gate now reports **bias and
  gate-crossings**, fixed before that question is put to the **still-untouched 2025**
  season. Do not rebuild this: read `docs/LEVEL_ANCHOR.md` and re-run
  `scripts/level_anchor_gate.py` (or the `level_anchor_gate` workflow).
  Two real defects shipped alongside: **`season_stats._cached` served an empty payload as
  a permanent hit** (the 2026 sp/adv/talent/roster/returning caches were all 2 bytes,
  written 2026-06-03, so any LOCAL 2026 feature build silently NaN'd eight more columns —
  GHA starts cold and refetches, which is why it hid for three months), and **a season
  whose priors cannot be fetched now warns instead of killing the build** (`_cached_soft`,
  the same trade `backfill.py` makes for venues).
- **2026-09-14 (EVERY WEATHER ROW WAS WRONG, AND "FORECAST" MEANT TWO THINGS).**
  Coverage was the reported problem (38.3%, 729/1,902 modelled games). The real one
  is that **all 2,647 outdoor rows were wrong**. Both writers asked Open-Meteo for
  `timezone=auto` and then indexed the **local** hourly array at the **UTC** kickoff
  hour — `Game.start_date` is naive UTC — so every reading was displaced by the
  venue's UTC offset, 4-10 h for US venues, onto the wrong calendar day for a late
  kickoff. LA Coliseum `2023-08-27 00:00Z` stored **63.2°F** (local midnight) against
  **78.1°F** at the real 5pm PDT kickoff; Cramton Bowl stored 93.6 against 99.8 via
  `backfill_enrichment.py`'s blind `T19` string-replace fallback. That is almost
  certainly why `docs/POST_MORTEM.md` calls `wx_temp`/`wx_wind` **noise in every row**
  while `factors/registry.py` still labels them tier 1 — the feature was never
  measured, it was measured wrong. Fix is `timezone=UTC` everywhere, which makes the
  hourly index equal the UTC hour; the ERA5 lookup then returns 78.1 and 99.8 exactly.
  `sources/weather.py` had **zero tests** and **no retries** (a 429 and a network error
  both returned `{}` — that is the 647 `empty` venues in `data/backfill_weather_full.log`
  and why coverage stalled at 21%); it now shares `sources/_http.py` with `cfbd.py` and
  raises `WeatherUnavailable`.
  **Second, and it reshaped the design: "the forecast before kickoff" is not one
  thing.** Open-Meteo's Historical Forecast API stitches the first hours of successive
  runs, so it TRACKS ACTUALS — measured over 12 real kickoffs it sits **1.82°F / 1.55mph**
  from the ERA5 actual, closer than a 1-day-lead forecast (2.30 / 1.67) or a 3-day
  (3.55 / 2.26). Calling it decision-time would have been look-ahead bias. So the new
  **`weather_obs`** table keys on `(game_id, lead_hours)` and stores `decision_safe`:
  **lead 0 = near kickoff, never decision-safe**; **leads 24/72 = the Previous Runs API**,
  the forecast that genuinely existed that far ahead, and the ONLY rows a market-edge
  study may use. Fixed-lead **wind/gusts/precip start with the 2024 season** (2023 is
  temperature-only), max lead is 7 days, and the model is **pinned to `icon_seamless`**
  because the default `gfs_seamless` returns **gusts BELOW the mean wind** from 48h out
  (7-9 of 18 samples; icon 0/18 at every lead). Gusts are captured for the first time.
  **Repairing the data does NOT activate it**: the backfill writes a table nothing reads,
  and `etl/features.py::WEATHER_OBS_LEAD_HOURS` ships `None`, reproducing the legacy
  frame exactly — the incumbent is an ARM, same shape as `PRIOR_SEASON_WEIGHT = 0`.
  Venue coordinates were audited BEFORE spending the requests (720 venues, lat
  21.29→53.34, lon −157.82→−0.28, **zero** lat/lon swaps despite `backfill.py:183-184`'s
  GeoJSON `x`/`y` fallback); `etl/venues.py::coord_problems` is the standing guard and
  the backfill refuses to start on a bad pair. `backfill_enrichment.py`'s weather path
  is DELETED. Read `docs/WEATHER.md` before touching any of this.
  **Backfilled and promoted 2026-09-14: `weather_obs` holds 24,714 rows and the
  modelled set went 38.3% -> 95.8% coverage** (95.4/95.9/96.2 by season), 14,365 of them
  decision-safe. Measured cost of the bug, against the 2,567 overlapping legacy rows:
  mean |Δtemp| **6.79°F**, p90 13.6, max 34.9, and **55.8% of games off by more than 5°F**.
  **Open-Meteo's free tier weights a request by variables x days and caps per UTC DAY** —
  5,711 requests exhausted it in ~2.3h at 86% of the work; the rest resumes after 00:00 UTC.
  **ACTIVATION IS DEFERRED.** `scripts/weather_gate.py` run two ways (train 2023-24 and
  2024-only, test 2025): **31-62 of 622 priced games change side of `BET_GAP_PTS`** against
  a pre-registered eyeball limit of 5, so the rule says wait until after the next card.
  **Do not repeat two readings that did NOT replicate**: MAE improved 9.120 -> 9.024 on the
  first split and was flat (9.313/9.315/9.318/9.341) on the second; and the selection shift
  looked uniformly conservative on the first split (133 -> 121/114/120 clearing) but FLIPPED
  for lead72 on the second (97 -> 103). Only the blast radius is stable. Running it twice
  also exposed that leads 24/72 hold nothing before 2024, so a 2023-24 train window starves
  the two decision-safe arms while their OVERALL coverage still reads 60% — the gate now
  reports coverage per training season and calls such an arm handicapped, not null.
- **2026-09-14 (THE CENSORING PREMISE WAS TESTED AND THE MARKET WINS).**
  The two-team probabilistic engine was to exploit the fact that an underdog's 1H
  score is censored at zero and the censoring grows with the spread. **It is not
  being built.** `scripts/censoring_study.py` (report: `docs/CENSORING_STUDY.md`)
  asked the only question that matters — *does censoring leave information the
  PRICE has not already absorbed?* — by controlling for the book's own de-vigged
  probability and testing whether spread still predicts the Under. On 1,873
  decided games with a real 1H close: **spread coef +0.00369/pt, bootstrap 95% CI
  [−0.0083, +0.0157], includes zero.** The sign FLIPS by season (+0.0057 / −0.0038
  / +0.0093); out of sample it improves Brier in the fourth decimal (0.25040 →
  0.25029); and taken at face value it is worth **+1.94 pp across the whole 7-to-28
  spread range against a 2.38 pp vig hurdle**. Bucket diffs are non-monotone
  (−1.4 / −0.1 / +2.7 / **−6.2** / **+6.7**) with every Wilson interval spanning
  the implied value.
  **The mechanism is real — that is the useful part.** Dog 1H shutout rate runs
  8.6% → 12.0% → 16.3% → 17.0% → **23.1%** by spread bucket while the favourite's
  falls to **0.0%**. So the finding is not "no censoring".
  **CORRECTED 2026-09-14 — do not restate the old, stronger version.** This used to
  read "and the market prices it correctly", which the evidence does not support:
  the CI `[−0.0083, +0.0157]` per point is **−4.36 pp to +8.24 pp** across the
  7-to-28 range, consistent with no effect AND with effects worth having. The
  supported claim is *no stable residual signal was DETECTED after conditioning on
  the price*. DO NOT BUILD stands on the season-by-season sign flip, the absent
  out-of-sample gain and the non-monotone buckets — not on the point estimate.
  Likewise **"Brier 0.2500 = a correctly centred line" was wrong**: a constant 0.50
  forecast scores exactly 0.25 at any base rate, and p̄(1−p̄) here IS 0.2500, so the
  number was the uncertainty term. Calibration is carried by the 0.57 pp
  implied-vs-realized gap and by `calibration_intercept_slope` / `reliability`.
  **Correction to an earlier figure:** the 37.6% dog-shutout rate at 28+ quoted in
  planning is from the full 3,601-row population; on the real-close cut it is
  **23.1%**. The unpriced games are not a random sample. Split on `line_real`.
  **PUSHES ARE NOT OPTIONAL when comparing a de-vigged price to a hit rate.** A
  two-way de-vig gives `fair_over + fair_under = 1` and so carries NO push mass.
  27% of 1H closes are integer totals and those push **5.66%**; the Under rate is
  48.74% counting pushes and **49.49% among decided games**, a 0.75 pp gap — the
  same order as the effect being hunted. On an integer line a push VOIDS the bet,
  so the book's two prices already price `{under|decided}` vs `{over|decided}`:
  compare against the DECIDED rate and report push rate separately.
  **New, and reusable:** `beatvegas/backtest/censoring.py` carries the repo's first
  `brier`, `log_loss`, `brier_multi`, `wilson` and `reliability` — there was no
  proper scoring rule anywhere before (the only model probability, `score.py`'s
  `predict_proba`, is uncalibrated and squashed into `under_score` without ever
  being scored). Written THREE-OUTCOME-aware so a future engine emitting
  P(under)/P(push)/P(over) is graded by the same functions and its numbers stay
  comparable. Also validated for later: the dog's 1H score is extremely lumpy
  (7/10/0/14/3 = 63% of games), so any future scoring model must be **discrete**.
- **Decided, NOT yet built (next session):** delete `MovementChart.tsx` + its
  `GameDetail.tsx:165-170` call site and the now-dead `movement.ts::pivot` — keep
  `BookTable` (Tate: the graph "looks like scribbles"; the per-book list stays); and mark
  already-placed bets in `AnswerBar` (muted + a marker, sorted below open ones — the data
  is already on `HomeGame.picked`, `answerBar.ts::buildAnswer` just never sees it).
  (The Results / Track record rework SHIPPED — see the PR #122 bullet above.)
- **2026-09-10 (full system review, PR #98, MERGED):** a code + security pass over the
  engine, the workflows and the site. **Two things were actually broken.**
  (1) `grade_records` was the ONLY one of eight grading paths that skipped
  `grading.trusted_first_half_total`, so a line-score false zero would have booked a
  fabricated UNDER win into the records grid, the credibility ledger and bv_line
  recalibration. Nothing live was corrupted (no graded rows yet, no false zeros on file);
  the fix is preventive and its test fails against the old code.
  (2) A mid-sweep Odds API 5xx/429 produced **NO card at all** — `poll_lines` exits 1 after
  writing its status file and `card.yml`'s sweep step had no `continue-on-error`, so the job
  died before `build_card`. The sweep now continues on error and a final `always()` step
  fails the run: the card ships DEGRADED **and** the failed-run email still goes out.
  `sources/odds.py` gained the retries `cfbd.py` always had (the free API retried; the paid
  one did not).
  **Security:** `next` 16.2.7 → **16.3.4** (1 critical + 3 high; prod `npm audit` is now 0).
  The auth cookie was literally `sha256(APP_PASSWORD)` — unsalted, so a leaked cookie was
  permanent access *and* a fast offline crack of the password; it is now
  `v1.<issuedAt>.<hmac>` under a **PBKDF2-derived key memoised per instance** (100k
  iterations would otherwise be paid on every request the middleware sees), with the
  issued-at inside the MAC so a stolen cookie ages out server-side. `POST /api/login` has a
  per-instance throttle (10 per IP per 15 min). **The middleware matcher's exemptions were
  unanchored prefixes** — `/api/healthz`, `/api/cronjobs`, `/loginhelper` would all have
  been public the moment anyone added them; anchored and verified in prod. `next.config.ts`
  gained security headers (the board was framable). Actions pinned to SHAs +
  `permissions: contents: read` on all twelve, with `.github/dependabot.yml` as the other
  half of that trade.
  **Money path:** `uq_manual_pick_per_ledger` — a partial unique index on
  `(game_id, COALESCE(market,'1H'), COALESCE(is_paper,false))`, because Postgres treats
  NULLs as distinct and legacy rows carry NULL in both. The cap + duplicate check were three
  round-trips with no transaction; a double-click could log twice or reach six bets.
  `updatePick`/`deletePick` are one guarded statement now. None of the pick endpoints had
  any try/catch, so a Neon blip showed `failed (500)`.
  **Measured** (raw queries per render, counted against a live server): `/results` 34 → 26,
  `/game/[id]` 36 → 26, via React `cache()` on `loadPicks`/`loadResults`/`getBoard`/
  `getLineCheck`. Routes 25 → 14. `app/error.tsx` + `not-found.tsx` added — there was no
  error boundary anywhere, so one bad table took down all of `/results`.
  `sunday.yml`'s three crons each spent 6 Odds credits; the capture is gated on a
  full-game snapshot already written today (ET), `force` to override.
  Tests: Python 837 → 856, web 372 → 389. Plan:
  `~/.claude/plans/run-a-complete-code-review-glistening-hippo.md`.
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
  **Results + `/proof` shipped the same day (see the next bullet).**
  **Team logos shipped 2026-09-10** (see the bullet below). The eleven legacy redirect
  files are gone as of the system review below — as `next.config` redirects, not deletions,
  so every old bookmark still resolves.
  Audit, per-page layouts and every decision: `~/.claude/plans/i-like-a-lot-cuddly-dusk.md`
  and `~/.claude/plans/session-handoff-beat-staged-sutton.md`.
- **2026-09-10 later (Results reorganised + `/proof` built, same branch):** the nav is now
  **three tabs — Board / Results / Track record — plus `/game/[id]` and `/proof/records`**.
  `/research`, `/research/records` and `/glossary` are redirect stubs; `lib/research.ts` is
  now `lib/proof.ts` (the gap-vs-line-value table died — n=1 buckets).
  **Results** (5,000px → ~2,300px) is the money page: slip block, then a **bankroll hero**
  (`BankrollHero.tsx` — bankroll at display size, units, ROI, curve beneath; `BankrollStrip`
  gave those numbers up and keeps the cap + the rules), then only the record cards that have
  data, then the review tables and the 9-column picks table (three frozen fields behind a
  per-row expand that composes with, and does not fight, the edit form). **An empty section
  is ONE LINE, never a card** (`Section` / `EmptyLine` / `.bv-empty`) — week 2 had eight
  placeholder boxes. The per-week scorecard is deleted; "closest to a bet" is gone from
  `CardPanel` (the board's answer bar already names them, off LIVE lines rather than the
  frozen card).
  **`/proof`** is organised **by grading basis, not by era** — the same cap-5 rule returns
  +15.9% at the real close and +5.4% at the estimate, so real closes lead (Hard Rock's own
  number counts as real) and the estimated block sits under a divider with every number
  **NEUTRAL**: green and red only ever appear on a real closing line, and `RecordCard` /
  `BandTable` take `basis="estimated"` to enforce it. 60.8% leads with three caveats —
  169 bets, a cap applied to the history afterwards rather than lived, and no Hard Rock in
  those seasons. **The coverage caveat is WRONG for this cut** and was dropped: within
  `fbs_only`, 1,902 of 1,934 games carry a real close (98%); the unpriced games the gotcha
  below warns about are almost all non-FBS and are already excluded (`postmortem.ts::coverage`
  reads those counts from the data). The **real-close gap ladder** (48.4 / 44.5 / 53.9 /
  54.9 / 58.8) is on the site for the first time — only the estimated one was ever shown.
  `PostMortemPanel` is broken into `BandTable` / `PmFlags` / `PmLiveNotes` + the shared
  `RecordCard`. `--header-h` is UNCHANGED and was measured, not assumed (97px at 375, 69px
  at 640/1440): the nav takes its own full-width row below `sm` whatever the label count.
  Three fixes rode along: **a bonus bet no longer spends a cap slot on screen**
  (`picks.ts::countsAgainstCap`; the server already excluded them, the display did not, so
  the site said 2 of 5 when four slots were free); **the line study buckets over the UNION
  of seasons** and defaults to all of them (per-season bucketing then merging drops any
  total under `minGames` in every single year, and 2026 has none that clear it); and
  **`LineStudyView`'s bars were invisible** — under Recharts 3.8 they animate up from
  height 0, the animation never completes, and a zero-height rectangle renders as an empty
  group, so `isAnimationActive={false}` is load-bearing there. Web tests 351 → 368.
- **2026-09-10 (team logos):** a small **18px mark before each team name** on the board row
  and the `/game/[id]` header — nowhere else, and **no fallback**: a team with no artwork
  renders NOTHING (no circle, no initials, no reserved box). The marks are **vendored**,
  not hotlinked: `scripts/fetch_team_logos.py` pulls CFBD `/teams` and writes 264 FBS+FCS
  PNGs into `web/public/logos/<cfbd id>.png` (929 KB of actual bytes; `du` reports 1.4M because
  264 tiny files each take a 4 KB block) plus the index `web/data/team_logos.json`,
  refreshed each August alongside `fetch_fbs_teams.py`. **Use the `logos-dark/` variant** —
  it is the dark-background artwork (Iowa's black Hawkeye renders gold), which is what the
  navy canvas needs. The ids are the ones `games.home_team_id` already stored and never
  selected; `board.ts` now carries `awayTeamId`/`homeTeamId`. The script composites every
  mark over `--bg-2` and PRINTS the low-contrast ones rather than shipping a navy blob
  (only Montana, 1.86, on the 2026 set — legible, kept). **The mark is centred on the text's
  CAP BAND, not sat on the baseline** — `vertical-align: calc(0.355em - var(--bv-logo-size)/2)`,
  because Archivo's cap height is 0.71em; one rule covers both the 16px row and the 24px header,
  where a single em value could not (the mark is a fixed size, cap height is not). Measured
  centring error: 0.01px on the board, 0.00px in the header. Spacing is an even **6px each side
  of the mark** (9px in the header) via `margin-right: 0.375em` plus a `margin-left: 0.1394em`
  that tops the preceding word space up to match; the `@` keeps the natural word gap, which binds
  each mark to its own name. **Do not use `word-spacing` for this** — it also loosens the space
  INSIDE a name ("Southern Miss", "Oklahoma State"), and the literal text spaces must stay because
  they are the matchup's only line-break opportunities on a phone. `web/data/team_logos.json` is
  web-only and deliberately NOT in `dataMirror.test.ts`; `lib/teamLogos.test.ts` guards the
  index against the vendored files in both directions. `TeamLogo` uses `next/image` with
  `unoptimized` — a bare `<img>` would be the repo's first lint warning, and the files are
  already the size they render at. **Measured cost:** desktop is free (page height identical
  at 1440); at 375 the board grows 520px (+5.5%) and matchups on two lines go 18 → 38 of 49.
  Tate accepted that rather than shrinking or hiding the mark on phones. Web tests 368 → 372.
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
  and `sat_am` (~8:05am ET), all status `final`, paper windows 48/24 h midweek and the
  REST OF THE WEEK on Friday and Saturday (they were 48/24/16/80 h = the gap to the next
  build until 2026-09-13; see the top bullet). `manual` builds publish but paper-log NOTHING. Expected spend
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
  (per-season CFBD `/teams/fbs`, refresh each August via `scripts/fetch_fbs_teams.py`;
  run `scripts/fetch_team_logos.py` in the same pass — see the team-logos bullet)
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
- **Every study has a row in `docs/HYPOTHESES.md`** (status, data, n, comparisons run, the criterion written before the run). Add the row FIRST, then write the script; `tests/test_hypotheses_registry.py` keeps it honest. 2023-25 is exploratory from 2026-09-15 on.

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
  `card.yml`, `grade.yml`). No notification code: GitHub emails
  failed runs. Nothing runs the engine on the Mac, and **since 2026-09-13 nothing texts
  Tate either** — every scheduled routine was retired (see the bullet below). The bet
  card is built in the cloud (`card.yml`; slots in
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
pip install -e ".[logos]"            # only for scripts/fetch_team_logos.py (matplotlib)
cp config.example.yaml config.yaml   # add CFBD + Odds API keys (gitignored)
pytest -q                            # run `pytest -q` / `cd web && npx vitest run` for current counts
```
Inside a **git worktree** run tests as `PYTHONPATH=. python -m pytest -q` — the venv's
editable install points at the main checkout, so a bare `pytest` imports the wrong tree.
Key scripts: `backfill.py`, `backfill_enrichment.py` (pace),
`backfill_weather.py` + `weather_validate.py` (weather -> `weather_obs`), `weekly_update.py`
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
Vercel (Neon-backed; **readable by anyone with the link since 2026-09-16, password only to log
picks**) at https://beat-vegas.vercel.app.
- **Views (3 tabs)** — Board / Results / Track record, plus `/game/[id]` and
  `/proof/records`. Historical description of the old four-tab shape follows; see the
  2026-09-10 bullets above for what ships now. Board (`/`, THE home page — the week grouped by day, every game with a
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
  the page loaders use; **reads are public, writes need the `APP_PASSWORD` cookie**
  (`lib/gate.ts::gateDecision` in `middleware.ts`, plus `lib/session.ts::requireAuth` inside
  every pick route).
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

## Visual Verification
- Captures come from headless Chrome via Playwright: `cd web && node scripts/shots.mjs --base
  http://localhost:<port> --label <name>` (every route at 1440 and 390 with height / overflow /
  header / tap-target metrics), then `--diff before after`. **Never the Browser pane for captures**
  (it caps at 800x500); its `javascript_tool` is still the right way to measure the DOM.
- A worktree verifies against **its own dev server on its own port with a clean `.next`**:
  `bash web/scripts/dev-worktree.sh start` (refuses a Neon URL without `--allow-neon`; prints the
  base URL; `stop` when done). Never point
  shots at the main checkout's server on 3000 — the preview pane serves main even from a worktree.
- A phone layout is confirmed by measurement (`scrollWidth - clientWidth` must be 0), never by eye;
  see the Chrome-headless gotcha below.
- Never run a capture pass against production Neon (metered egress; it tripped the 5 GB cap once).

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

## Gotchas
- **Open-Meteo's free tier weights a request by variables x days, and the cap is per
  UTC DAY.** A full weather backfill does not fit in one day: measured 2026-09-14,
  **5,711 requests exhausted the daily quota in ~2.3 hours** (86% of 6,636
  venue-season-leads), and `"Daily API request limit exceeded"` resets at 00:00 UTC
  rather than on a rolling window — waiting an hour does nothing. Plan for two days or
  split by lead. `backfill_weather.py` resumes from `data/cache/weather_staging.done`
  and halts after 10 consecutive failures instead of grinding through doomed calls.
- **Never ask Open-Meteo for `timezone=auto`.** A local-time series cannot be keyed by
  a UTC timestamp, and `Game.start_date` is naive UTC. That mismatch silently wrecked
  every weather row for three years (see the 2026-09-14 bullet). `timezone=UTC` makes
  the hourly index equal the UTC hour. `tests/test_weather_source.py` pins it.
- **Open-Meteo's Historical Forecast API is NOT "the forecast at decision time".** It
  stitches the first hours of successive runs, so it tracks actuals (1.82°F from ERA5,
  closer than a 1-day-lead forecast). Decision-time forecasts come from the **Previous
  Runs API** (`*_previous_dayN`), 2024+ for wind/gusts/precip, max lead 7 days, and must
  be pinned to `models=icon_seamless` — the default blend's gusts fall BELOW its own
  mean wind from 48h out. Any market-edge query filters `weather_obs.decision_safe`.
- **BetMGM's `totals_h1` is NOT a centred main line** (confirmed live 2026-09-12).
  It serves an off-centre rung: 4.86 pts from the market median on average, 61 of 63
  games 2+ pts off, with two-way prices ~235 points from -110 where every normal book
  is 15-47 (Western Kentucky @ Georgia: BetMGM 36.5 over +195 / under -275 while six
  books sat 30.5-32.5). **Not our parser and not staleness** — a live call returns 2
  outcomes at ONE point per book, and BetMGM's `last_update` was the freshest of the
  seven. The fair price is already safe (`fairPriceWindow` admits only books within
  0.5 pts of Hard Rock), but the consensus MEDIAN moves on 13 of 63 games by up to
  **0.5 pts** — exactly `HR_OFF_MARKET_PTS`, so it can flip the off-market gate on a
  borderline game. Details + options: `docs/RANKING_AND_TRUST.md` §9.
- **`build_feature_frame()` DEFAULTS to `min_games=2`, and the live board does not.**
  The default drops any game where either team has under 2 FBS-vs-FBS games played, so
  weeks 1-3 come back with **4 rows for a whole season** instead of 143 — a diagnostic
  that forgets this is reading noise (it cost a whole pass on 2026-09-20). The live
  scoring path is `scripts/weekly_update.py`, which builds at **`min_games=0`**
  (`--min-games` default 0) and hands that frame to `score_slate`, which derives its
  TRAINING set from whatever frame it is given — so the eligibility rule and the
  training rule are the same knob, which they should not be. Every backtest and
  validation path passes `min_games=2`. The frame takes ~8 minutes to build: cache it
  (`df.to_pickle(...)`) before running more than one comparison against it.
- **An index on `odds_snapshots.market` does NOT help, and the criterion is why we know.**
  The cost audit left "add an index leading on `market`" as an open item because every read
  filters on it first (`lineCheck.ts`, `board.ts::consensusLines`, `movement.ts`) and nothing
  led on it. Tested 2026-09-20 on the live database with the keep-rule frozen BEFORE the
  numbers were read (keep only if the season-wide `lineCheck` statement's execution time falls
  ≥30% on the median of three warm runs; plan shape alone does not count):
  **31.5 ms → 29.7 ms, a 5.7% gain. Rejected and dropped.** The reason is cardinality —
  `market` holds two values in a 45/55 split, so leading with it cannot filter: Postgres
  switched from a Seq Scan to a Bitmap Index Scan and still read all 28,200 `1H_total` rows.
  The plan LOOKED fixed, which is exactly what the time-based criterion was written to catch.
  Do not re-propose this index; a useful one would lead on something selective, and at ~30 ms
  for a whole season the scan is not the cost.
- **`ev` IS NOT THE EV OF THE BET, and gating on `ev >= 0` bets nothing** (measured
  2026-09-13, PR #123). `ev` is `ev_under(fair_under, hr_price)` where `fair_under` is the
  **market's** no-vig fair probability at Hard Rock's number (`card.py::market_read`) — a
  *price-shopping* number: "is Hard Rock's price better than the rest of the market's?"
  The model's edge is not in it at all; that lives in `hr_gap`, in POINTS, on a different
  scale, and the two are never combined into one expected value. So `ev >= 0` is not a
  strict gate, it is an **unsatisfiable** one — it asks Hard Rock to beat the no-vig
  consensus, which is a free arb. On the live week-2 card **0 of 42 priced rows cleared
  it** (5 BET, 18 EDGE, 19 PASS; mean ev -0.04 to -0.07) and all six real tickets were
  negative (-0.0086 to -0.0530). The other direction fails too: implying `P(under)` from
  the gap and `bv_sigma` (a **constant 11.26** on all 156 of 2026's rows) makes a 5.32-pt
  gap worth **+30% EV at -110**, while that season's grading says the model is LESS
  accurate than Hard Rock in every spread bucket. **A true EV gate needs a calibrated
  `P(under)`** — the two-team hurdle engine. `BREAK_EVEN_EV = 0.0` exists in
  `model/score.py` + `verdict.ts`, parity-mirrored, **wired to nothing**, waiting for it.
  The live bar is `BET_MIN_EV` (= `EV_FLOOR`), now the ONE name shared by `verdict.ts`,
  `card.py::is_bet`, the kill price and `pickRules.checkPolicy`.
  `docs/RANKING_AND_TRUST.md` §8b.
- **The "green board, refused log" band was STALENESS, not two rules** (PR #123 — §8 of
  `RANKING_AND_TRUST.md` used to say otherwise and was wrong). `breakEvenPrice` returns
  the worst rung whose EV clears the bar, so `price >= killPrice` **is** `ev >= bar`: the
  two agree at every price by construction. The quoted -113 was true break-even worked out
  by hand; the code's kill price on that game was -125, and -120 clears it. The real cause
  was `checkPolicy` comparing a LIVE price against a `killPrice` read off the **stored card
  payload** — and `marketFairUnder` moves between builds. All six real week-2 tickets had a
  kill price that changed across the week's eight builds (2-4 distinct values each; one game
  went +100 → -105 → +100 in three days). **`POST /api/picks` now recomputes from
  `lib/lineCheck.ts` and FAILS CLOSED**: no verifiable live price, no real-money BET
  (`PRICE UNAVAILABLE`, deliberately a different rejection from the kill-price one — an
  outage must never read as a run of discipline). A cached price may be displayed; it may
  never authorize money. `PolicyContext.livePrice` is REQUIRED so a new caller cannot skip
  the check by omission.
- **`centred_snaps` falls back to the rungs it exists to reject** — `return ok or
  list(snaps)` (`lines.py`). Fine for a multi-book consensus (some number beats none),
  WRONG for one book: there is no consensus to fall back to, so it hands back the quote the
  filter just rejected. Hard Rock is off-centre on 26 of 28 quotes inside 3h of kickoff —
  the close-poll window — so the fallback fired EVERY TIME the filter mattered. Pass
  **`strict=True`** from any single-book read; `book_closing_before_kickoff` and
  `book_closing_price_before_kickoff` now do (the latter had no filter at all). PR #123.
- **The Odds API serves Hard Rock's ALTERNATE lines as its 1H total, and -160 did not
  catch them** (fixed 2026-09-25, registry row H-PCT-U, `docs/RANKING_AND_TRUST.md` §9b).
  Texas @ Tennessee read 30.5 at -160 while the app and six books said 27.5; a live call
  showed that alternate arriving ALONE as the one Over/Under pair, so it is the feed, not
  our parser. Hard Rock prices a 2-pt alternate at ~-145/-150 and a 3-pt one at exactly
  -160, which `is_centred_quote` (tuned to BetMGM) passes: 33 on 31 games in weeks 1-4.
  `devig.is_hr_rung` (mirrored `devig.ts::isHrRung`, golden vectors in
  `tests/fixtures/hr_rung_vectors.json`) calls a Hard Rock 1H quote an alternate at -140 or
  worse OR 2+ pts from the other books' median in the same sweep (3+ books). The card
  (`market_read` → `hr_live`/`hr_as_of`/`hr_alt_line`) and `lineCheck.ts` then show the LAST
  MAIN line with its time, blocker `hr_alt_line`, display only — never the bar, never a
  paper pick, never a real ticket (`PRICE UNAVAILABLE`). Hard Rock's 1H closes skip
  alternates too, which means `snapshots.hr_closes` now loads every book. The general
  -160 bar is unchanged (other books post real lines at -140..-159). `sources/odds.py`
  keeps the most balanced pair when a book sends several (it used to keep the LAST) and
  prints a `::warning::`.
- **A `web/lib/` export with no TypeScript caller may still be LOAD-BEARING.**
  `tests/test_gate_parity.py` reads constants OUT of `verdict.ts`, `grade.ts`, `edge.ts`,
  `lineCheck.ts`, `books.ts` and `card.ts` **by regex** and compares them to
  `model/score.py` / `card.py` — that guard is what stops the Friday card and the live site
  disagreeing about what counts as a bet. `MODEL_BET_THRESHOLD` and `MIN_GAMES_FOR_MODEL`
  look dead in the web app and are not. Grep `tests/` before deleting any `export const`.
  (`CONFIDENCE_LABEL` and `WATCH_GAP_MIN` were genuinely dead and were removed.)
- **React `cache()` is a NO-OP outside a render/request scope**, so the per-request query
  dedupe cannot be unit-tested with a mocked prisma — a test asserting one call fails
  against correct code. Measure it instead: wrap `$queryRaw` in `lib/prisma.ts` with a
  `console.log` counter, hit the route twice (the first compiles), diff the dev-log lines,
  revert. Also key the cache on the loader with STABLE args: `getHomeBoard` takes
  `now = new Date()`, so caching that dedupes nothing.
- **Chrome headless does not emulate a mobile device from `--window-size` alone.** A 375-wide
  capture lays out at desktop assumptions and looks exactly like horizontal overflow. Confirm
  with the Browser pane's `javascript_tool` (its screenshots are useless, its JS works):
  `document.documentElement.scrollWidth - clientWidth`. Measured 0 on the board.
- `npm run format` reformats `web/data/*.json` (written by the Python lane) into a 1,600-line
  diff on every run. They are in `web/.prettierignore` now — keep them there.
- **Next 16.3 writes its own `AGENTS.md` and `CLAUDE.md` into `web/` on every dev start**,
  which would compete with this file. `agentRules: false` in `web/next.config.ts` turns it
  off; do not remove it.
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
  (`.github/workflows/sunday.yml` + `lines_watch.yml` + `card.yml` + `grade.yml`).
  **DK's API 403s GHA datacenter IPs** (confirmed), so prod captures full-game lines with
  `poll_full_game --source oddsapi` (`auto` falls back to **CFBD /lines**, `sources/cfbd_lines.py`;
  DK only works from the Mac, which can't write Neon). Local jobs degrade gracefully via
  `store.try_init_db` (logs "unreachable", exits 0). `GET /api/health` reports capture AND
  grading/build freshness over HTTPS (it used to be read by the retired Sunday routine).
  Secrets `DATABASE_URL`/`CFBD_API_KEY`/
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
- **ESPN line scores populate LATE, and a scoreless half is real football.**
  `sources/espn_scores.py` is the no-quota scores fallback. SDSU @ UCLA (2026 wk 2) came
  back `[0,0,0,0]` against a 38-point final mid-week and the `summary` endpoint returned
  nulls; `line_scores_trustworthy` rejected the box (quarters did not sum to the final —
  the reconciliation rule) and CFBD PBP later graded the game at a REAL 0-0 half (UCLA
  scored all 28 after the break). **Fifteen games on file (2023-26) have a 0-0 first half
  against a scored final; all fifteen check out against ESPN's box score and three against
  game reports** — none was a false zero. So since 2026-09-20 the guard is EVIDENCE-based: a
  0-0 half is trusted from line scores when four or more numeric quarters sum to each side's
  final, and from PBP only when the same feed's running score reaches the stored final
  (`etl/first_half.py::final_from_plays`, `attach_first_half(pbp_final=...)`). The
  all-zero placeholder box is still rejected by reconciliation. Never "fill in" a missing
  1H without one of those two proofs.
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
