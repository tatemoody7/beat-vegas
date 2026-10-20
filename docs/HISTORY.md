# History — what happened, by date

Every dated episode that used to live in `CLAUDE.md`'s "Current state" section, moved here
verbatim on 2026-09-28 (newest first; a later entry overrides an earlier one where they
disagree). `CLAUDE.md` is the brief and stays current; **a change edits the brief in place and
appends its episode here** (`tests/test_claude_md.py` caps the brief). PR bodies and `git log`
hold the rest.



## 2026-10-20

- **2026-10-20 (PAPER WORDING ON THE GAME PAGE AND THE BOARD, AND A CAPTURE TIME ON EVERY PRICE).**
  Final-2026 plan D4 build 5; three wording problems found on the live site, display text only (no rank,
  score, gate, number or Board structure changed). (1) The game page's top block is headed **Paper read**
  (was "The decision"); a not-qualifying sentence keeps its facts as a research condition: "Not a paper
  signal yet: Hard Rock's under price is -115; the rule needs -105 or better." (was "Not yet — … needs …");
  "It becomes a paper signal at …"; the alternate-line and QB-out sentences lost "check the app" and
  "recheck"; `labels.ts::blockerTag` and the held-row text follow. The note under it reads "Prices are Hard
  Rock Bet (Florida) as captured; see the time beside each." (the "your book / price to beat" sentence,
  also on `/research`, is gone). (2) The Board's strip reads "Research season · six paper strategies judged
  against the closing price · up to N of 30 readings · next read …" (the count is still `arms.length`).
  (3) **Every Hard Rock price shows when it was captured**: `as of Tue 4:44 PM ET` beside the price on a
  Board row and the game page's Hard Rock tile, and "Hard Rock Bet price captured …" over the Lines table;
  the time is `lineCheck`'s `hrSeenAt` (max of captured_at and last_seen_at of the snapshot the row uses,
  falling back to `hrAsOf`), via `et.ts::etClockZone` / `parseNaiveUtc` and `labels.ts::hrSeenText`; no
  timestamp, no label. `hrQuoteText` no longer carries the alternate line's inline "· as of" (the separate
  label replaced it). Specs and `FEATURE_PARITY` follow; `e2e/fixture/expected.mjs` mirrors the sentences.
  **Left alone**: `beatvegas/card.py` still writes the old "Not yet —" sentences into stored card items
  (Python mirror of `edge.ts`, other sessions editing tonight; the site rebuilds the sentence itself, so
  only a card row read straight from `cards.items` would show them).

## 2026-10-18

- **2026-10-18 (THE SITE IS A READ-ONLY RESEARCH RECORD: THE LOG PATH, THE LEDGER AND THE LOGIN GO).**
  Final-2026 plan PR-12+13, decisions D2 / D16 / D17. **What left the site**: the owner log path
  (`POST`/`PATCH`/`DELETE /api/picks`, `/api/price-refresh`, `lib/ticketPolicy.ts`, `priceRefresh.ts`, the
  write half of `pickRules.ts` and `picks.ts`, the log form and button, the "bet logged" / cap-slot /
  past-the-cap chips, the price-age note, the QB-unknown warning, the "Bet one unit" opening — every BET
  sentence now opens `Paper signal:` for everyone); the personal real-money ledger (`BetLedger`,
  `BankrollCurve`, `PicksList`, `personalStake.ts`, `betLedgerDb.ts`, `loggedAs.ts`, `clvDirection.ts`,
  `curveTicks.ts`, `weeklyReview.ts`, the week picker, `/api/bets` and its CSV); the login and lock
  (`/login`, `/api/login`, `/api/logout`, `lib/auth.ts`, `session.ts`, `viewerIsAuthed()`, Lock/Unlock in
  the footer, `HeaderChrome`); `lib/signalGate.ts` (visitor = owner: ratings, our number, `/records` and
  its CSV show before kickoff too); `lib/rulePause.ts`, the pause banner and the `rulePaused` keys in
  `/api/health` (the switch stays ON in `app_settings`; nothing on the site reads it). **Results is
  Record** (path `/results` kept): the arms' forward picks with their EV readings, then the pricing
  opportunities, then the season comparison — market research, the paper rule, the full-game market —
  with no Personal-stake row. **The 30 real tickets stay in `manual_picks`**, untouched, and appear only
  in the final report (`docs/program/SEASON_2026_FINAL.md`, PR-17). Ops and build warnings, run ids and
  the API budgets render for everyone. One sentence on every page (`labels.ts::RESEARCH_BANNER`): "A
  college-football betting research lab. Six strategies on paper, judged against the market's closing
  price. Nothing here is a bet." **The one secret left is `CRON_SECRET`** (`lib/gate.ts::cronGate` in
  `middleware.ts`, matcher `/api/cron/:path*`, and again inside the route); `APP_PASSWORD` is read by
  nothing and Tate can remove it from Vercel after the deploy. Guards: `tests/test_pick_columns_parity.py`
  now refuses any `INSERT INTO manual_picks` under `web/app` or `web/lib` (`beatvegas/picks.py::add_pick`
  is the one writer); `test_gate_parity.py` reads `verdict.ts` and `edge.ts` only; the e2e lane signs
  nobody in (no `APP_PASSWORD`, no storageState), `ledger-integrity.spec.ts` asserts the gone routes
  answer 404, `login.spec.ts` is deleted, `FEATURE_PARITY.md` carries 66 lines. The early-season sentence
  in `edge.ts` still says "real money needs 2" because it mirrors `card.py` (frozen Python) and no FBS
  team has under two games from week 8 on. Shots at 1440 and 390: overflow 0 on every route, header 69.

- **2026-10-18 ~22:00 UTC (THE CLOSED STUDIES MOVE TO `scripts/archive/`).** Final-2026 plan PR-19. Twenty-seven
  scripts whose question is closed (or whose collector was retired) left `scripts/` by `git mv`, so the brief, the
  study menu and the test suite carry only what still runs: the gates and blends (`blend_gate`, `gates_study`,
  `residual_gate` (the shim), `level_anchor_gate`, `intercept_gate`, `inseason_gate`, `weather_gate`,
  `censoring_study`, `sharp_book_probe`), the position scripts of the retired collectors (`neggap_position`,
  `neggap_level_study`, `fg_position`, `challenger_position`, `stopping_rule_position`), the one-look studies
  (`margin_backtest`, `model_fix_study`, `literature_look`, `weather_history_look`, `wepa_weekly_extract`), the
  generic `harness_report`, the shortlist pair (`publish_shortlist`, `build_shortlist_reference`) and the retired
  tools and probes (`bv_adjust`, `line_study`, `model_artifacts`, `probe_hr_keys`, `probe_alt_totals_h1`). Each
  result stays where it was written: `scripts/archive/README.md` has one line per script with its registry row,
  verdict and result doc. **No registry row, gate, model constant or live path changed.** What did change: the six
  scripts that found the repo root by `parents[1]` / `.parent.parent` now use `parents[2]`; `inseason_gate` and
  `intercept_gate` import `load_closes` from `scripts.archive.level_anchor_gate`; `study.yml` lost 12 options
  (default now `when_to_bet_study`) and the `publish_shortlist` write guard; `tests/conftest.py::_load_script`
  falls back to `scripts/archive/`, and the tests of the closed studies stay in `tests/` (they also cover the
  `beatvegas/` code each study called, which is live), pointed at the new paths; the empty-PYTHONPATH test keeps
  only `health_check`; `neggap_position` is asserted archived, not a study option. New
  `tests/test_archive_scripts.py` keeps every archived file compiling, the README complete, and nothing live
  importing from the archive. To run one: `PYTHONPATH=. python scripts/archive/<name>.py --help`; to dispatch one
  again, a PR re-adds it to `study.yml` (docs/HARNESS.md says so for `harness_report`).

- **2026-10-18 ~22:00 UTC (THE ODDS API PROGRAMME, STEP 4a: A SHARP REFERENCE BESIDE EVERY FULL-GAME PULL).** Final-2026
  plan PR-C4a. `scripts/poll_full_game.py` takes `--research-regions`, `--research-markets` (default `totals`) and
  `--research-purpose` (default `sharp_eu`). With `--research-regions eu` it makes a SECOND bulk `/odds` call after the
  live pull is written (regions × markets, no bookmaker named, the client's ledger `purpose` set to `sharp_eu` for that
  call only) and writes Pinnacle and the other `eu` books' full-game totals and moneylines to `research_snapshots`
  (`purpose` `sharp_eu`, `region` `eu`, `request_id` = the `odds_spend` row, `game_id` set when the event matches a CFBD
  game, NULL for an FCS pairing; the same write-on-change rule as `odds_snapshots`). **The judge sees none of it:** the
  live bulk call keeps `us,us2,us_ex` and `odds_snapshots` gets no `eu` book (a test counts the rows with and without
  the flags); cv1, pv1, the HT1H trigger and the card read `odds_snapshots` only, and `sharp_eu` rows feed cv2 at the
  final read (`docs/CONSENSUS.md`). Before the paid call the budget controller (PR-C3) is asked in-process: the balance
  is the live response's own credit header, the floor and recurring need come from `app_settings`; an allowance below
  markets × regions prints `research eu: skipped (allowance ...)` and makes no call. No live pull (Hard Rock gate,
  credit floor, nothing due in the window) means no research pull, and a research failure is a warning, never the live
  pull's exit code. One summary line: `research eu: <written> written, <reseen> reseen, <credits> credits`. Wired into
  `card.yml` (full-game refresh, `totals,h2h` = 2 credits), `sunday.yml` (opener, 2 credits) and the `lines_watch.yml`
  close step (`totals` = 1 credit, only on ticks that pass the gate). Expected cost about **32 credits a week** (plan
  C11: 4 card refreshes × 2 + the Sunday opener 2 + one credit per gated close tick); `odds_spend` records the actual.

- **2026-10-18 (THE DAILY GRADE JOB STOPS PLAY-BY-PLAY, POST-MORTEM AND FACTOR-CHIP COLLECTION).** Final-2026 plan PR-09,
  decision D5. `grade.yml` lost four steps: the 1H play-by-play refresh (`backfill_pbp.py --only-missing` into
  `fh_team_game`), the SP+ factor credibility ledger (`grade_factor_ledger.py`), the post-mortem (`post_mortem.py` into
  `postmortem_*`) and the CFBD reference-cache restore/save pair that existed only for the ledger's feature frame; its
  `OUTCOME_PBP` / `OUTCOME_LEDGER` / `OUTCOME_PM` health inputs and the Eastern-weekday output went with them.
  `weather_actuals.yml` is deleted (the study-only observed-weather backfill, about 46% done). The `grade` health
  contract dropped `grade.postmortem_written` and `grade.reference_cache_populated` (the sunday contract keeps its own
  cache check); the two 2026-09 failure modes stay as history with no live check. **Why:** CFBD drops to the free tier
  (1,000 calls a month) on 2026-11-05 and no page or job reads those rows. **CFBD calls saved (an estimate from the
  step design, not a measured count):** at most one `/plays` call per run for the weeks still missing rows (usually
  none), plus the reference fetch (~22 calls) on every run where the weekly cache missed, plus the factor ledger's
  `/ratings/sp`. **Kept:** `backfill.py`'s own `/plays` call (the grader's 0-0 half proof), `close_coverage`, the `hist`
  and `regrade` inputs, moneylines. `fh_team_game`, `weather_actuals` and `postmortem_*` keep their rows; nothing reads
  them live (the model has not used the PBP table since the B-SERVE fix). The three scripts stay in place until PR-19
  archives them. First run proving it: Monday 2026-10-19 10Z (the four-hour guard makes a same-day hand dispatch skip).

- **2026-10-18 ~21:00 UTC (THE ODDS API PROGRAMME, STEP 6: THE ARCHIVE QUEUE'S WORKFLOW AND ITS PROBE).** Final-2026
  plan PR-C6. Credits do not roll over, so Tate's decisions C-D5 / C-D9 / C-D13 / C-D17 turn the unspent balance of
  each cycle into permanent datasets in the last four days before the reset: `scripts/archive_buy.py` holds the queue
  in his order with his caps (Pinnacle 2026 closes 1,500 → Hard Rock 1H ladder at close 2026 3,900 → full-game paths
  2026 on `us` 3,000 → Hard Rock 1H release times wks 1-4 6,000 → Pinnacle 2025 closes 2,100 → Hard Rock ladder 2025
  4,500 → full-game paths on `us2` 2,500 → Pinnacle 2024 closes 2,600), reads each item's `spent` from the `odds_spend`
  ledger, and asks the budget controller (`beatvegas/credit_plan.py`: balance − floor 1,500 − the cycle's recurring
  need) before every paid call; `auto` runs nothing until the reset date is set and the window is open, and the items
  themselves land in PR-C10. `.github/workflows/archive.yml` is dispatch-only for now (`status`, `probe`, `auto`;
  inputs via env; job `archive` in the ledger). **The probe** (≤40 credits, Tate's approval in the plan) asks the
  archive, as of kickoff −30 min, whether it carries `alternate_totals_h1`, `team_totals` and `team_totals_h1` for a
  week-5 Hard Rock game (default Notre Dame @ North Carolina, 2026-10-03 16:00Z): one historical events list (1
  credit) to find the event id, one historical event-odds call for Hard Rock alone (10 per market returned, 0 if
  empty); `--live` adds one live four-book call for the next Hard Rock game (≤3). Its finding sizes the Hard Rock
  ladder archive item (keep / drop) before the Nov 1-4 window and tells PR-C9 whether team totals are archivable;
  the report is an artifact and this log. `OddsAPIClient.historical_event_odds` is the one new client method.

- **2026-10-18 (THE CLOSE TICKS SPEND ONLY ON WHAT THE JUDGE READS).** Final-2026 plan PR-C2 (programme C, E1; decisions
  C-D11 and C-D19). Four changes, measured against the week Tue 10-13 → Sun 10-18 (831 credits itemised = 831 gauge delta):
  (1) **Look-ahead**: the Saturday resolve step now gives a tick a 360-minute look-ahead only when its UTC hour is divisible
  by 3 (15Z 18Z 21Z 00Z 03Z) and 120 otherwise, GitHub backup crons by the same hour rule; the pre-check and the poll still
  read the one resolve output. The old 6 h on all 15 ticks cost about 185 credits a week more than 2 h and bought no judge
  coverage (cv1 reads snapshots inside 2 h of kickoff only; ticks ≤119 min apart still reach every such kickoff).
  (2) **Spreads leave the close ticks**: the full-game close asks `totals,h2h` (6 credits, was 9); nothing reads the close
  `full_game_spread` rows, `h2h` stays because pv1 reads it (`pricing.py::_close_ev_ml`); about 54 a week. `card.yml` and
  `sunday.yml` keep `totals,spreads,h2h` (`spreads` fills `Game.spread` there). (3) **`poll_full_game.py --hr-only-gate`**:
  after the free event list the paid pull is made only if a Hard Rock-universe game (`hr_universe_game_ids`: a full-game
  total Hard Rock has priced this season) kicks off inside `--kickoff-within-min`; otherwise it prints "no Hard Rock game
  inside the window", writes the status file `complete: true, events_in_window: 0, reason: no_hr_game` and spends nothing
  (the `fg_close_polled` check reads that as n/a). Not measured separately; the weeknight full-game closes were 90 a week.
  (4) **Double-tick skip**: `poll_lines.py --skip-read-within-min 30` (close step) drops an event whose Hard Rock 1H total
  was read (max of `captured_at`, `last_seen_at`) in the last 30 minutes AND that kicks off MORE than 120 minutes
  (`REAL_1H_CLOSE_WINDOW_H`) from now, about 50 a week of GitHub-plus-Vercel double reads. A game inside 2 h is never
  skipped (C-D19). **What cv1 sees is unchanged**: inside 2 h nothing is skipped and the only market narrowed
  (`full_game_spread`) is not one it, pv1, the HT1H trigger or the card reads at a close; the extra reads dropped were beyond
  2 h or repeat reads of an unchanged number. Every Odds-calling step of `lines_watch.yml`, `card.yml` and `sunday.yml` now
  sets `BV_ODDS_JOB`, so the `odds_spend` ledger stops reading "hand". Tests pin the markets, flags, hour rule, env and both
  skip rules. No gate, model constant or registry row changes.

- **2026-10-18 (THE FULL-GAME CLOSE CAPTURE HAS A HEALTH CONTRACT).** Final-2026 plan PR-05. The full-game close step in
  `lines_watch.yml` (`poll_full_game.py` on every close tick) is `continue-on-error` and exits 0 on an empty or
  credit-floor-skipped pull, so a silent failure left every run green while the two full-game arms (H-ARM-FGU, H-ARM-WXFG)
  accumulated `stale_close` exclusions. `poll_full_game.py --status-file` now writes `{complete, reason, events_in_window,
  events_polled, events_unmatched, rows_written, rows_reseen}` on every exit past the fetch (`credit_floor`, `db_unreachable`
  and `no_match` read `complete: false`; an event the matcher cannot tie to a game is counted, not a failure). The step gets
  `id: fgclose` and the health step `OUTCOME_FG` plus `--fg-status`; `scripts/health_check.py` loads it as the `fg` file.
  New degraded check `lines_watch.fg_close_polled`: when the 1H close found events and the FG step ran, the status file must
  exist and say complete, and (if it found an event in its own 180-min window) a `full_game_total` row must be captured or
  re-seen since `RUN_STARTED_AT`. `docs/HEALTH.md` regenerated with a new step 3 under "When lines_watch is degraded". No
  gate, model constant, registry row or credit spend changes.

- **2026-10-18 ~21:30 UTC (P1.4: THE FULL-GAME ARMS IGNORE HARD ROCK'S ALTERNATE RUNGS; THE REPLAY FOUND NONE).**
  Final-2026 plan PR-03 (decision D9). The audit found H-ARM-FGU and H-ARM-WXFG took Hard Rock's newest full-game
  total on the −160 "centred" test alone, while the 1H arms also apply `devig.is_hr_rung` (−140 or worse, or 2+
  points off the median of 3+ other centred books as of the same capture). Now both full-game arms read
  `fg_paper.hr_main_quotes` (the card's `lines.hr_rung_flags` over every book's full-game rows at the build): the
  newest MAIN Hard Rock line, the last main line when the newest row is a rung, nothing when every row is a rung;
  the build summary counts `hr_alt_ignored`. **Replay before the change (Neon, read-only, 2026-10-18 ~20:50Z):** for
  each of the 39 FGU / WXFG picks, Hard Rock's newest `full_game_total` row at or before `placed_at` and the other
  non-exchange books' newest centred rows at that moment (`DISTINCT ON (book)`, prices > −160, Hard Rock / Fliff /
  consensus / Kalshi / Novig / ProphetX / Polymarket / BetOpenly excluded): price rung (min price ≤ −140) 0 of 39;
  distance rung (3+ books and |line − median| ≥ 2) 0 of 39 (16-17 reference books on 37 picks, 9-10 on two).
  So no pick is retagged, no reading changes and the planned `challenger_picks.audit_flag` column is not needed.
  `PROTOCOL_VERSION` → `p1.4` (`docs/PROTOCOL_2026.md` p1.4; roadmap v2.7; the two registry rows carry the
  amendment); `tests/test_fg_paper.py` and `tests/test_wx_paper.py` pin that a rung newest row yields the last main
  line and a rung-only game leaves the universe. Applies from the first card built after the merge (Tue 10-20 or
  Thu 10-22). Same PR: `tests/conftest.py` pins one OpenMP / BLAS thread for the test session,
  because on this Mac the whole-suite run (the pre-push hook's exact command) raised numpy's "Identity cache already
  includes the item" inside sklearn's threaded binning in `tests/test_artifacts.py` -- main passed, this tree failed
  5 of 5, `OMP_NUM_THREADS=1` passed the full suite; the test itself is untouched and CI results are unchanged.

- **2026-10-18 ~17:00 UTC (THE SHUTDOWN RUNBOOK, DATED; CFBD PATREON CANCELLED).** Final-2026 plan PR-22 (docs only).
  `docs/OPS_ACCOUNTS.md` drops its stale "Do now" and "Done 2026-10-05" sections for one dated table (date, action, kind,
  precondition, who) with a paragraph on what stop, cancel a renewal, retain and downgrade mean here and the rule that only
  Tate cancels anything. The rows: real money ended and the Saturday report task deleted (10-18); **Tate cancelled the CFBD
  Patreon membership on 10-18** (Tier 3 runs to Nov 5, then the key is the free tier, 1,000 calls a month; measured use is
  ~600-900 and a hand season reload ~500, so no reload runs after Nov 5 without reading the balance); The Odds API resets for
  its last cycle ~Nov 5 (Tate confirms the date on the dashboard); the archive queue drains Nov 1-4 and Nov 30-Dec 4 (floor
  1,500); last capture Sat 11-28, last grade Sun 11-29; the Mon 11-30 final read, with the gate for everything after it (the
  week-13 judge readings present, `data/evidence/2026-w13` committed, the export verified by a restore into the local
  sandbox); Tate cancels The Odds API between Nov 30 and Dec 4, after the archive run and after PR-24 removes the Vercel crons
  (a dead key would redden `lines_watch` and `card` daily); Tate moves Neon to the free plan after the export is verified.
  This supersedes plan B8's "CFBD Tier 1 on Nov 6, cancel before Dec 6". Read 2026-10-18 and to be re-read on the billing pages
  before clicking: The Odds API's cancellation guide says access continues to the end of the paid period with no refund;
  Neon's free plan is 1 GB a project since its 2026-10-02 changelog (older pages say 0.5 GB; the database is 131 MB) with a
  restore window of about 6 hours against 7 days on Launch. `CLAUDE.md`: the Accounts item is one line pointing at the runbook.
  The `odds_cycle_reset_at` controller setting named in the runbook is from the Odds API programme (reference plan C11) and does
  not exist in the code yet. No code, workflow or test changed.

- **2026-10-18 ~22:00 UTC (THE ODDS API PROGRAMME, STEP 3: THE CREDIT BUDGET CONTROLLER).** Final-2026 plan PR-C3.
  The guardrail in one sentence (Tate): every optional pull and archive buy must leave the balance at or above the
  floor (1,500) plus the measured recurring need for the cycle's remaining weeks (to min(reset, Nov 29 04Z
  `protocol.SEASON_LAST_KICKOFF`)), and archive buys run only in the last four days before the reset once that
  Saturday's closes are captured. `beatvegas/credit_plan.py` holds the arithmetic (`remaining_weeks`, `allowance` =
  balance − floor − recurring/week × weeks left, may be negative; `archive_window_open`; `measured_recurring` = the
  trailing 7-day `odds_spend.credits` of jobs `card` / `lines_watch` / `sunday`, None until the ledger is a week old;
  `PLAN`, the per-week estimate per purpose for the digest). `scripts/credit_plan.py` is the command line: `report`
  (table, `$GITHUB_STEP_SUMMARY`, writes the new gauge `odds_projected_end` = balance − recurring need; the TS
  `BASE_GAUGE_KEYS` carries it), `allow --purpose P --estimate N` (exit 0 when the allowance covers N, else 1 with
  one line; an `archive_*` purpose is also refused with the reset unset or outside the window, `--drain` waives the
  window for the post-season drain of C-D13), and `set-reset` / `set-floor` / `set-recurring`, which write through
  `ops.record_gauge` so `app_settings_log` keeps the history. Settings in `app_settings`: `odds_cycle_reset_at` (ISO
  naive UTC, unset by default: Tate confirms Nov 5 on the dashboard, so `report` says unset and non-archive purposes
  count to the season end), `odds_credit_floor` (1,500), `odds_archive_window_days` (4),
  `odds_recurring_fallback_per_week` (840 until PR-C2 lands, then set to ~450 with no deploy). "Last Saturday's closes
  captured" is read from the `close_coverage_pct` gauge's note (`sat=` the latest finished Saturday in ET, at least one
  game covered). **No workflow runs it yet:** the optional pulls (PR-C4a / C4b / C10) call `allow` and the digest
  (PR-C11) calls `report`. Spends nothing, never read by a gate.

- **2026-10-18 ~20:30 UTC (THE ODDS API PROGRAMME, STEP 1: A CREDIT LEDGER AND A RESEARCH TABLE).** Tate asked
  how to use the 20,000-credit plan (18% used, ~840 credits a week measured Tue 10-13 → Sun 10-18: 1H sweeps 215,
  Saturday 1H closes 319, weeknight 1H 18, Saturday full-game 153, weeknight full-game 90, card full-game 36, Sunday
  opener 9; the 10-15 line-release study cost 7,059, not the 6,509 quoted above). His decisions (plan sections
  C6-C12): the moderate capture set as the baseline (a sharp `eu` reference, Monday openers, Hard Rock's alternate
  1H ladder at close, Wed-Fri noon 1H sweeps and Mon-Fri totals-only full-game pulls, team totals where posted), four
  zero-alpha exploratory collectors (derivative consistency ≥1.5 pts on `data/multiplier.json`'s share, Hard Rock vs
  Pinnacle ≥+2%, full-game early-move follow, team-total mispricing), a budget controller (floor 1,500 + the measured
  recurring need), and an archive queue that drains expiring credits automatically in the last four days of each
  cycle (Pinnacle 2026 closes → Hard Rock ladder 2026 → full-game paths `us` → Hard Rock 1H release times → Pinnacle
  2025 → Hard Rock ladder 2025 → full-game paths `us2` → Pinnacle 2024). No new confirmatory arm: with five or six
  reading weeks left, 3 picks a week has ~10% power at +3%. **Rule: every frozen reader (cv1, pv1, the HT1H trigger,
  the card) keeps reading `odds_snapshots`; all new capture lands in `research_snapshots`.** This PR (C1) adds that
  table, `odds_spend` (one row per priced response, written by `OddsAPIClient._record_spend` with `x-requests-last`,
  the balance after, job and purpose from `BV_ODDS_JOB` / `BV_ODDS_PURPOSE`; a failed insert is a warning), the
  writer `beatvegas/research_capture.py` (write-on-change for live purposes, every wave for archive rows) and the
  book→region table `sources/odds_regions.py`. A test forbids the provider's host anywhere but the client (the
  temporary `opening_watch.py` exempt until PR-08). `migrate.yml` before the next pull; the tables are empty until C4.
- **2026-10-18 ~16:00 UTC (THE SEASON ENDS NOV 28 AND THE FINAL READ IS NOV 30; ROADMAP v2.6, PROTOCOL p1.3).** Final-2026
  plan PR-04 (paperwork and the `--season-over` wiring; Tate's decisions D1, D4, D12 of 2026-10-18). `beatvegas/protocol.py`
  gains `SEASON_LAST_KICKOFF = "2026-11-29T04:00:00"` (week 13's last kickoff), `FINAL_READ_DATE = "2026-11-30"`,
  `FINAL_READ_AT` (12:00 UTC that day, the p1.2 R2 clock) and `season_over(now)`; `PROTOCOL_VERSION` is `p1.3`.
  `scripts/protocol_position.py::resolve_season_over` ends the season on the flag, on `SEASON_OVER=true`, or on the clock,
  so the 11-30 Monday run times every running arm out by itself; `pricing_monday.yml` adds the boolean `season_over` dispatch
  input, passed to the positions step as `env: SEASON_OVER` (never into `run:`); the report JSON records `season_over`.
  H6's `when_to_bet.CONFIRMATORY_DATE` moves 2026-12-07 → 2026-11-30 (rule untouched, no confirmatory number read;
  `RULE`, the study script, `docs/WHEN_TO_BET.md`, `docs/ASSUMPTIONS.md` and the registry row say so); the H-JUDGE,
  H-VENUE-1, H-PRICE-HR and H-ARM-EVP rows date their reads 11-30 with the January / 12-07 dates kept as history;
  `web/data/hypotheses.json` re-exported. `docs/ROADMAP_2026.md` v2.6 records D1-D14 in one row; `docs/PROTOCOL_2026.md`
  p1.3 adds only the season-end rule (every running arm times out at the 11-30 read; nothing after the last kickoff is an
  observation; the FGU/WXFG rung rule is PR-03); `docs/program/JANUARY_2027_REVIEW.md` is retitled to the 11-30 final read
  (file name kept; the 12-07 section marked dropped; the 2027 default stays). `web/lib/research.ts` mirrors
  `FINAL_READ_DATE` and the exploratory card's wording names the Nov 30 read. `CLAUDE.md`: the Reads, Accounts and Monday
  rows carry the two dates; the 10-14 "this week" and the 12-07 H6 items are cut (399 lines). Tests: `test_protocol`
  (the clock), `test_arms` (the resolver and `p1.3`), `test_workflows` (the input via env), `test_research_parity`
  (`FINAL_READ_DATE`), `test_docs_parity` (every governing doc states 2026-11-30), `test_when_to_bet` (the new date).
  No arm's selection rule, start, judge, alpha or boundary changed.

- **2026-10-18 ~15:30 UTC (CHALLENGER GRADING AND THE JUDGE STEP FAIL LOUDLY).** Final-2026 plan PR-02 (evidence
  integrity, Tate's approval of 2026-10-18). Five of the six registered paper arms live in `challenger_picks` and are
  graded by `grade_challenger_picks`, which `scripts/pick.py::cmd_grade` wrapped in a try/except that only printed a
  warning, and the judge's backfill step in `grade.yml` ("Line value at each pick's exact terms") was
  `continue-on-error: true`: either could fail and leave the run green with the arms silently ungraded or unread.
  Now `cmd_grade` lets the exception propagate (the champion ledger still commits first, in its own session) and the
  judge step is fatal. Both sit before "Mark grading complete", so a failure leaves `grade.completed_this_run`
  missed and the `grade` contract `failed` (the health step already runs on `always()`; `beatvegas/health.py`
  unchanged). Tests: `test_workflows.py` pins no `continue-on-error` on the judge step and its order after
  `pick.py grade`; `test_challenger_end_to_end.py` pins that a raising `grade_challenger_picks` escapes `cmd_grade`.
  `docs/HEALTH.md` names the two fail paths.

- **2026-10-18 (THE JUDGE'S COLUMNS ARE WRITE-ONCE; A DIFFERING RECOMPUTATION IS AUDITED).** Final-2026 plan
  PR-01. The audit found three paths that overwrote a pick's reading in place: `picks.grade_pick` at grading
  time (after `consensus_backfill` had usually read the pick an hour past kickoff, p1.2 R3′), `pick.py grade
  --regrade`, and `consensus_backfill --write` without `--missing-only`; a changed past reading left no trace,
  and the Monday read recomputes every SPRT path from the stored `ev_cons`. Now every writer goes through
  `picks.apply_judge_reading`: a row with no reading (`cons_version` NULL) gets this one; a row already read
  keeps it, and a recomputation that differs (floats beyond 1e-9) writes one `judge_reading_audit` row (ledger,
  pick id, stored and computed values, the fields that differ, reason grade / regrade / backfill, run id) and
  nothing to the pick; an identical recomputation writes nothing. `challenger_picks` and `manual_picks` share
  the function. The backfill's summary counts written / kept / audited. New table via `init_db`
  (`migrate.yml` before the next grade run; the write path would otherwise fail on the insert).
  `docs/CONSENSUS.md` "Where it runs" rewritten; `tests/test_judge_write_once.py` works each path on SQLite
  with the real judge and grader. Standing rule until this is on Neon: no `grade.yml regrade=true` dispatch.

- **2026-10-18 ~15:00 UTC (REAL MONEY ENDED; THE MONEY DOCS DESCRIBE A FROZEN LEDGER).** Tate's decision D2 in the
  final-2026 plan (PR-11, docs only): the personal first-half-unders ledger (v1.4) ends. Its 30 graded real tickets
  stay as a frozen historical ledger, never edited; the `rule_paused` switch is set on today and stays on; the owner
  log path leaves the site in later PRs (PR-12/13). `docs/BETTING_POLICY.md` gets a banner and past tense where it
  called the path live, `docs/ASSUMPTIONS.md` is marked historical, one `docs/GLOSSARY.md` entry notes the unit now
  reads paper picks only, and `CLAUDE.md` is reworded in its four places that said real money was on. No row, rule,
  constant, test or code changed; every sentence `tests/test_docs_parity.py` pins is untouched.

- **2026-10-18 ~15:00 UTC (THE FINAL-2026 PLAN; REAL MONEY ENDED; THE SATURDAY REPORT STOPPED).** Tate asked
  for an independent audit of the whole system and a plan to run the rest of 2026 as an automated testing
  machine, then stop paying (`~/.claude/plans/beat-vegas-final-fluffy-hollerith.md`: the assessment, his
  fourteen decisions, a 25-PR roadmap). The decisions: paid operation ends after Sat 11-28 (week 13; no
  championship or Army-Navy capture; the Odds API's ~12-05 renewal is cancelled); **real money ended today**
  (`rule_paused` = true at 14:59Z through Neon's HTTPS endpoint, `app_settings_log` 674; the 30 graded tickets
  are a frozen ledger, the owner log path leaves the site in later PRs); the Sunday refit stays as registered
  and model code is frozen to the final read; the final read moves to **Mon 11-30** (roadmap amendment v2.6
  to follow; the 12-07 mid-point is dropped; H6, H-JUDGE and H-VENUE-1 read the same day); play-by-play,
  weather-actuals, post-mortem and factor-chip collection stop (moneylines stay: pv1 compares them); the
  Board will rank by arm membership; the Mac Saturday board report is deleted (scheduled task
  `bv-saturday-board-report` removed 2026-10-18; its skill folder stays on disk); alerts are GitHub email
  only from one daily digest with age checks; FGU / WXFG apply `is_hr_rung` forward (p1.3 to follow); after
  11-30 a full export goes to the public repo and Neon drops to the free tier; a weekly evidence snapshot
  (`data/evidence/2026-wNN/`) is committed by the Monday workflow; the final report is
  `docs/program/SEASON_2026_FINAL.md` plus a Final read section on `/research`, with the pre-arm paper and
  the retired neggap picks reported in full as development evidence. Live state at the audit: 30 real
  tickets −1.83u (mean `ev_cons` −4.1%, n 18 read); every registered arm's first picks read −3% to −6%
  `ev_cons` at n 3-23; 11,356 Odds credits left (the 10-15 line-release study spent 6,509 in a day).

- **2026-10-18 ~15:10 UTC (THE RESIDUAL-GATE SHIM HAS NO IMPORTERS LEFT).** Final-2026 plan PR-18 (mechanical, S). Fifteen
  scripts imported `report_paths` / `append_step_summary` through `scripts/residual_gate.py`, a re-export shim: `protocol_position`
  (the live Monday job), `stopping_rule_position`, `neggap_position`, `neggap_level_study`, `fg_position`, `challenger_position`,
  `when_to_bet_study`, `gates_study`, `sharp_book_probe`, `blend_gate` (bare `from residual_gate import`) and `inseason_gate`,
  `weather_gate`, `level_anchor_gate`, `intercept_gate`, `censoring_study` (`from scripts.residual_gate import`). All now import
  from `beatvegas.backtest.reporting`, where the two functions are defined; import order re-sorted by ruff, nothing else touched.
  `blend_gate` also took `load_closes` and `load_played_frame`, which the shim defines itself rather than re-exports; it now
  carries its own two-line copies (same calls: `snapshots.consensus_closes` over `kickoffs_for`; `training_frame(build_feature_frame(min_games=2))`).
  `scripts/residual_gate.py` stays untouched for PR-19; only its own file and the tests that test it still name it
  (`test_residual_gate_script.py`, `test_reporting.py`, `test_harness_consumers.py`, `test_gate_scripts_run_without_pythonpath.py`).
  Checked: `ruff check` / `ruff format --check` clean; full suite 1,848 passed (exit 0); every repointed script's `--help` exits 0 with PYTHONPATH unset.

## 2026-10-17


- **2026-10-17 ~23:00 UTC (RECORDS SPLIT: HARD ROCK RECORDS AND MARKET RESEARCH, NEVER MIXED).** From the fact-check
  audit's plan (P1.1/P1.2, Tate's calls). `/records` graded every game against `predictions.line_used`: in 2026 a derived
  or median line (only 64 of 334 equal to Hard Rock's), and for 2023-25 the proxy line written 2026-06-03 from a share
  fitted on those seasons' own first halves (0 pushes in 1,667 whole-number lines; mechanism not found). Now two tabs:
  **Hard Rock Records** grade each game on Hard Rock's MAIN line and under price as the last scheduled card built before
  kickoff froze them (`card.py` `hr_line`/`hr_price`; 293 of 337 played 2026 games, 150-143, -10.55u at Hard Rock's
  price), and a game without one reads "No verified Hard Rock line" and stays out; **Market Research** grades on the
  judge's consensus close (`consensus.market_close`: 3+ other books confirmed inside 2 h of kickoff, median line), a
  record with no units. 2023-25 have no Hard Rock quote at all, so they open on Market Research. `grade_market` now
  writes that close (and deletes a stale row before every skip: two Fliff-only rows had survived); `grade.yml hist=true`
  also grades 2023-25. Results: the market row is "Market research ... consensus close", record only (its stored -110
  units are never shown); the paper row leaves out the 12 weeks 2-4 picks logged on a Hard Rock alternate line
  (`manual_picks.excluded_reason = 'alt_line'`, a data migration pinned to each pick's line and price) and says so. The
  Board's Played list settles on the same last-card Hard Rock line, with no market fallback, and every settle uses the
  grader's zero-half trust rule (`grade.ts::trustedFirstHalf`). The records CSV drops `line_1h`/`bv_gap`/`outcome` for the
  Hard Rock and consensus columns (18 columns).

- **2026-10-17 ~22:00 UTC (THE PERSONAL STAKE READS ONLY WHAT CAN BE VERIFIED).** From the fact-check audit's plan
  (P1.3, Tate's calls). The ticket check found settlement and payout right on all 26 graded tickets, but 10 carry no
  logged price (6 `unknown`, 4 NULL), id 7's price was changed after kickoff, id 105 was logged at 28.5 while Hard
  Rock's feed showed 29.5, ids 85/86 were bet Friday and logged Saturday, and id 9's boost is not modelled. Results now
  reads the record over every graded cash ticket; units, ROI, line move and value vs the close over price-verified
  (`logged`) cash tickets only, naming how many were left out; bonus bets on their own line with what they paid; the
  Board-rule (BET at the log) tickets as a sub-line (`lib/personalStake.ts`). The comparison table's Personal stake row
  and the units curve follow the same rule. Rows carry "price not verified", "off-rule: Watch/Pass" and "flagged";
  `manual_picks.audit_flag` (new, TEXT) holds the plain reason for ids 7, 9, 85, 86 and 105 (a `_DATA_MIGRATIONS` fill,
  guarded on each ticket's line and price) and joins the bets CSV (31 columns). Nothing is regraded and no price is
  substituted; Hard Rock's own bet history, when Tate supplies it, is the only reconciliation.

- **2026-10-17 ~20:30 UTC (GREEN MEANS A PAPER SIGNAL; THE BOARD SAYS A GAP IS NOT AN EDGE).** From the fact-check
  audit's plan (P1.4, Tate's call): a rank badge is coloured by its verdict only, green for a game meeting the week's
  rule, amber not yet, red pass, at every rank; this reverses 2026-10-16's green #1-#10 (#411), which had eight "Not
  yet" rows and a Pass reading green while the Research key said green is a paper signal. The ranking is unchanged.
  The Board carries one line under its heading (`labels.ts::BOARD_HONESTY_TEXT`): ranked by the gap, green a paper
  signal and not a proven bet, our number has missed by more than Hard Rock's line this season. The glossary's "Our
  number" no longer claims weather (excluded since 10-09, `LEAKY_WEATHER_COLS`) and "Market line" says Hard Rock is in
  it. The brief's accuracy sentence now carries the re-runnable query (n 280, +0.57 a game; champion n 65, +1.10).

- **2026-10-17 ~19:30 UTC (A REAL-MONEY SIGNAL SAYS THE STARTING QB IS UNCONFIRMED).** A second independent audit
  (read-only, chat report) found the QB gate reads unknown as clear: every week-7 `game_previews` row was written at
  12:02Z (before #418) with `qb_out = false`, card 32 rated Louisville @ Syracuse BET with Syracuse's starter unsettled
  (Odom out, Nelson questionable, Angeli doubtful), and after #418 `bool(None)` is still False in `card.py`. Tate's call:
  allow the BET, warn on it. Every lit BET row, the game page's decision block and the log form now read "QB status
  unknown — check before logging" (`labels.ts::QB_UNKNOWN_TEXT`); no gate, card or money rule changed. The same audit
  found `venues.timezone` empty on all 852 venues (the 14:09Z grade run skipped its CFBD refresh under the minutes
  guard, so #417's repair had not landed); a hand `grade.yml` dispatch at 17:57Z (run 39055975940, Tate's call) loaded
  them: 364 of 852 venues carry a zone, all 385 rated 2026 games among them, before the 10-18 refit.

- **2026-10-17 17:10 UTC (REAL MONEY BACK ON).** Tate asked to turn real money back on so he could log first-half
  unders from the day's board; `rule_paused` was set to false through Neon's HTTPS endpoint (mirroring
  `scripts/rule_pause.py off`; `app_settings_log` 546). This lifts the audit pause of 13:27 UTC (row 520) the same day,
  by his call; the measured figure that prompted it (−3.6% per bet against the consensus close, 14 of 26) is unchanged.

- **2026-10-17 UTC (A SATURDAY BOARD REPORT, TEXTED: THE ONE EXCEPTION TO "NO SCHEDULED TEXTS").** Tate liked a
  hand-built analysis of the Board's top 10 (each game's offense, defense, first halves, injuries, weather, coaching and
  market, with reasons for and against the under) and asked for one every week, texted. His calls: Saturday after the
  8am card (9:30am ET); a Mac scheduled task (`bv-saturday-board-report`, skill `~/.claude/skills/bv-board-report`)
  that publishes a new private page and texts the link only; a run that starts after 3:30pm ET is skipped with a
  one-line text, one after 10am covers only games not yet started. This reverses the 2026-09-13 "no scheduled texts"
  call knowingly: it runs only when the Mac is awake, it is research only, and nothing in the engine depends on it.
  It reads Neon read-only and writes nothing to Beat Vegas. The same day Tate asked why the site's wind (ICON, e.g. 9
  mph at Southern Miss) reads below the National Weather Service (13-15 mph, gusts agreeing); he chose to measure
  which is right before changing anything (the registered weather arms are frozen on ICON).

- **2026-10-17 UTC (THE KICKOFF CLOCK READS THE VENUE'S TIME ZONE; A DATA-BUG REPAIR TO FOUR MODEL INPUTS).**
  `etl/situational.py` built `kickoff_local_hour` as `(UTC hour + longitude / 15) % 24`: solar time, no minutes, no
  DST. Penn State @ Michigan (19:30Z = 3:30pm EDT) read "~13:00 local kickoff" and was flagged `early_kickoff`; the
  same longitude math gave `away_tz_shift` 0.39 hours. All four (`kickoff_local_hour`, `early_kickoff`, `night_game`,
  `away_tz_shift`) are in `BV_FEATURE_COLS`. Tate fixed it as a data bug, not a gate (independent-audit plan, Phase
  1d): `venues.timezone` (CFBD /venues `timezone`, refreshed by `scripts/backfill.py` in grade.yml) now gives the real
  wall clock (hour + minutes/60) and the whole-hour UTC-offset difference between the visitor's home venue and the
  game venue at kickoff; a venue without a zone gives NaN for all four, never a guess (CFBD has none for 488 of its
  852 venues, mostly lower-division; on FBS-vs-FBS games 2003-26 that is 33 games at 9 venues, none in 2026). The
  2026-10-18 Sunday refit is the first trained and scored on the repaired inputs; earlier `predictions.factors_json`
  rows keep the old numbers, so the game page now reads the clock and the time change from the venue tables directly.
  The factor sentence reads "3:30pm local kickoff"; the `spot` chip "3:30pm kick". `docs/HYPOTHESES.md` notes the
  affected rows.

- **2026-10-17 UTC (INJURIES SAY "NOT AVAILABLE"; QB STATUS UNKNOWN, NEVER CLEAR).** The audit found Rotowire's public
  injury table is a capped teaser: every `injury_snapshots` row 2026-10-06..10-17 held 5-7 rows, all for that day's
  games, so a Saturday game was never in a Tue/Thu/Fri pull, yet its page showed "Injuries and news" with national
  articles and `qb_out` read false. `injuries_json` now carries `covered` (the pull named one of the game's teams),
  `qb_out` is True or NULL (unknown), and the game page says "Injury report not available for this game ... Starting
  QB status unknown" when uncovered, "Partial list" when covered, reading the newest pull rather than Sunday's flag.
  The card's QB gate is unchanged (every Python reader bool()s the flag); whether "unknown" should block a BET is
  Tate's call before real money resumes. A Saturday-capable source is the plan's next injuries step.

- **2026-10-17 UTC (INDEPENDENT AUDIT; REAL MONEY PAUSED; SATURDAY WINDOW INSIDE ITS GATE).** Tate commissioned an
  outside-critic audit (findings, his 16 decisions and the improvement plan: `~/.claude/plans/pasted-content-id-29b8-i-want-recursive-rabbit.md`,
  to be filed as `docs/program/AUDIT_2026-10-16.md`). Two actions shipped first. (1) `rule_paused` = true at 13:27Z
  (`app_settings_log` 520), written through Neon's HTTPS endpoint like `scripts/rule_pause.py on`: the personal stake
  read -3.6% per bet against the consensus close (14 read of 26, interval -6.2% to -1.1%), and it stays paused until
  Tate lifts it after the plan's data-trust phases. (2) `card-sat-am`'s Vercel window moved from 7:00-8:15 to 7:45-9:00
  ET: since #379 a named slot dispatched before the 7:45 gate skips, the skipped run concludes "success", and
  `suppressedBy` counted it as the build, so the first Hobby tick stood the morning down about three times in four.
  Today's tick happened to land at 7:50 and card 32 built at 8:06. A new test pins every card window inside its gate.

- **2026-10-17 UTC (EVERY WORKFLOW PINNED TO UBUNTU 24.04).** GitHub's run annotations announced that `ubuntu-latest`
  moves to Ubuntu 26 from 2026-10-19, the first scheduled Monday read, and no job here had run on it. All 20 jobs in
  the 16 workflows now name `runs-on: ubuntu-24.04` (the image they were already on); the `postgres:16` service in
  ci.yml's e2e lane was already pinned. `test_every_job_runs_on_the_pinned_runner_image` fails on any other label, so
  moving to 26 is its own PR, tested first.

## 2026-10-16

- **2026-10-16 UTC (THE ANALYSIS IS REMOVED; WIND BACK IN THE FACTORS LIST).** Tate did not want the analysis box:
  it is off every game page, and no card saves it any more (the card.yml step, the `card.shortlist_published` check and
  `shortlist_publish.yml` are gone; H-1H-SHORTLIST rejected; card 31's rows stay as the record). The wind is back as a
  row in "What is behind it": the steady wind at kickoff from the newest card forecast, green at 10+ mph, plain below,
  no gusts; the weather box (and its temperature and rain lines) is gone.

- **2026-10-16 UTC (THE BOARD'S TOP 10 OPEN THE ANALYSIS; A BILLING HOLD; DATED WEATHER).** GitHub refused every job
  from ~04:00Z (the $10 Actions cap); Tate made the repo public again (~20:15Z, history since 10-04 scanned clean) and
  grading, the fri_pm card and the first publication ran. Tate then set the Board's #1-#10 green (#411), had the game
  page show the newest card-build forecast with its source and time instead of the undated, ~6-day-old Sunday weather
  (19 of 47 outdoor week-7 games were 5+ mph off; #412), and reshaped H-1H-SHORTLIST: no separate price-ranked list;
  every scheduled card saves the analysis of every game it rates (alternate rungs and missing prices saved unpriced),
  and the Board's #1-#10 open it ("Analysis — Board #N"). The bar line, the key line and the estimate fine print were
  removed as clutter. Card 31's publication (the old top-10 shape) stays frozen; the next card is the first full one.

## 2026-10-15

- **2026-10-15 UTC (THE FACTOR SCREEN'S RESULT, AND THE WEBSITE PLAN SHIPS IN FIVE PRS).** H-1H-FACTORS screened 64
  factors over 2,040 FBS games (2023 616, 2024 630, 2025 637, 2026 157 before the 10-13 card; leak audit 400 games, 0
  mismatches): none passed Level 1 and none passed Level 2 (`research/1h-factors-2026-10/report.md`). Tate's site audit
  Q&A (Q1-Q14, four adjustments) then shipped as #405-#409: the Board opens with one slim research line, one list in
  rank order, badges coloured by the verdict (green meets the week's rule; a key line says neither rank nor colour is a
  proven edge), short Pass lines, the research-season sentence in the footer (#405); factors worded by scoring, never
  the bet, under the screen's result (#406); Research dates in words and run ids owner-only, the Results week picker
  filtering the bet table, an honest units chart, and the stale "1.75+ is the band we bet" replaced by the per-slate
  rule (#407); H-1H-SHORTLIST, the frozen price-first research top 10 published after each scheduled card, insert-only
  with a degraded health check and a recovery workflow, reproducing the approved prototype exactly on card 30 (#408);
  the Research top 10 above the Board and each shortlisted game's full analysis, frozen beside the latest price (#409).
  Ranks, arms, pv1 and the real-money rules unchanged; the ledger choice (v1.4 / shortlist picks / both) stays open.
- **2026-10-15 UTC (H-1H-FACTORS REGISTERED BEFORE ANY NUMBER).** Tate's first-half-unders reassessment: a full,
  exploratory factor screen (~44 football and market factors) of where a first-half total lands against the consensus
  close, registered before any computation. Decision times, the outcome, the leakage rule for every factor family, the
  leak audit, the two levels (preliminary association; improves on the market out of sample) and their thresholds are
  fixed in the row. It feeds a research shortlist prototype only; no arm, pv1, Board or money rule changes, and any
  factor that passes needs its own forward test before it can carry weight.
- **2026-10-15 UTC (THE OPENING WATCH MOVES TO VERCEL'S HOURLY TRIGGER).** GitHub fired 0 of ~4 scheduled watch ticks in
  its first 95 minutes (its other scheduled jobs had last fired at 07:35Z), so Tate chose Vercel's hourly entries as the
  trigger (`web/lib/cronJobs.ts` `opening-watch`: 24 daily entries, one per UTC hour, every tick dispatches; Vercel lands
  each within the hour) with GitHub's 20-minute cron kept as a backup. Live ticks find the hour each book opened; the
  provider's 5-minute archive then narrows the key openings afterwards (~30 credits an opening). The script still
  refuses to spend outside Fri 18:00 - Tue 18:00 ET. Removed with the watch after Tuesday.
- **2026-10-15 UTC (THE MARKET-OPENING WATCH, TEMPORARY).** Tate asked when every book we can see opens next week's
  first-half totals, team totals and full-game totals. History first (Odds API 5-minute archive, research run
  `research/line-release-2026-10-15/`, 6,509 credits): Hard Rock's first-half totals for 20 of 20 sampled week-5
  games appeared Monday 9-28 between ~8:20am and noon ET, and week 6 and 7 games mostly Monday morning (a few Monday
  afternoon or Tuesday) -- 6 to 32 hours before our first Tuesday capture; Kalshi listed week 5's first-half totals
  Monday 5:17pm ET. Live next: `.github/workflows/opening_watch.yml` runs `scripts/opening_watch.py` every 20 minutes
  (every 10 on Monday 6am-1pm ET) from Friday 10-16 6pm to Tuesday 10-20 6pm ET. It asks each market only of books that
  have not posted it (an empty answer is free, so credits are spent only at an opening), reads full-game totals every
  other tick, snapshots opened first halves every 6 hours, keeps each first sighting's window (last miss -> first hit),
  stops all paid calls at 5,500 credits, and writes nothing to the database (state in the actions cache, ticks as
  artifacts). Two local test ticks: 92 calls, 5 credits, then 0. Kalshi is read afterwards from its public history
  (creation to the microsecond, per-minute bid/ask), finer than polling. Removed by its own PR after Tuesday.
- **2026-10-15 UTC (THE ALTERNATE-LINE PROBE COMPARES HARD ROCK WITH THE MARKET).** Tate approved adding up to nine
  other books to Saturday's one probe run. The same call now names the configured `bookmakers_1h` list (Hard Rock plus
  nine). The Odds API bills an event call as unique markets returned x regions, and up to 10 named books are one region
  (the provider's v4 guide, read 2026-10-15; the repo verified it live 2026-09-09), so the cost is unchanged: 2 credits
  an event, 24 at the 12-event cap; the probe stops after the first event if the feed bills more. The report adds every
  book's rows as fed (a missing side stays empty), Hard Rock against the other books at the identical line and side
  only, each two-sided quote's hold and de-vigged fair share, Hard Rock's unders by price range (-150/-200/-250 named),
  and data-quality lines (books absent, no ladder, one-sided quotes, a line priced two ways, stamp age). `--csv` keeps
  the raw rows for the Florida-app comparison. It writes nothing; no collector, arm, pv1 or Board change.
- **2026-10-15 UTC (THE WRITER AND THE GRADER NOW SHARE ONE 0-0 STANDARD).** The board read DEGRADED from
  2026-10-11: App State-Old Dominion (2026-10-10, `games.id` 401869843) stored a 0-0 first half and its record
  never graded. Cause: the writer (`etl.first_half.attach_first_half`) keeps a scoreless line-score half in a
  game that scored only when the full box reconciles (4+ numeric quarters per side summing to the final),
  while the grader (`grading.trusted_first_half_total`) refused every line-score 0. The box checks out on both
  feeds, read 2026-10-15: App State 0-0-3-0 = 3, Old Dominion 0-0-2-8 = 10 (CFBD `/games?id=` and ESPN's
  summary, identical). Tate chose to fix the cause (option 2). The writer now labels a proven scoreless
  line-score half `linescores_verified`; the grader trusts a 0-0 half in a scoring game under
  `linescores_verified` or `pbp` and no other label (`grading.ZERO_PROVEN_SOURCES`), so a plain `linescores` 0
  -- every row written before the fix, including the placeholder corruption -- is still refused. The nightly
  season load (`scripts/backfill.py --season 2026` in `grade.yml`) re-derives every finished 2026 game from
  CFBD, so the labels change only where the writer re-proves the box; nothing is relabelled by hand.
  `tests/test_zero_half_parity.py` runs one case matrix through the writer and then the grader: whatever the
  writer stores, the grader grades.
  **Impact, measured 2026-10-15 before the change** (all ten 2026 games with a stored 0-0 half and points;
  every one passes the writer's check on both CFBD and ESPN):

  | Game(s) | What changes | What does not |
  |---|---|---|
  | App State-Old Dominion (FBS, wk 6) | label → `linescores_verified`; its rating record grades (first half 0); `challenger_picks` 41 (H-ARM-1HO, placed 2026-10-09, development) grades; post-mortem `live_2026` reads its half (was NULL); 4 unflagged first-half states in the pricing CSV gain a result; `grade.records_graded` clears | no forward arm pick, no real ticket, no pricing opportunity on the game |
  | San Diego State @ UCLA (FBS, wk 2) | label → `linescores_verified`; post-mortem and 4 unflagged pricing states read its half (were NULL) | its rating record (graded 2026-09-13, first half 0) and paper pick `manual_picks` 33 (graded under 2026-09-12, before any arm) are write-once and already agree |
  | Eight Division II/III and FCS games | label only | no rating record, pick, snapshot or post-mortem row |
  | 47 pre-2026 line-score zeros (2003-25) | nothing: the nightly load reloads 2026 only | the frozen studies, the hp1 table and every historical record |

  The six arms, their selection rules, the judge, pv1, the protocol, the Board and the personal-ledger logic
  are unchanged; development rows stay development.

## 2026-10-14

- **2026-10-14 UTC (H-ARM-EVP COLLECTS, EXPLORATORY).** Tate chose option A for the value-at-price idea: collect in
  2026 with no ledger slot, no alpha and no sequential test, keep the +2% threshold and the calculation documented,
  treat the design replay as development evidence, compare it with the gap rule, decide in January 2027.
  `beatvegas/evp_paper.py` runs the spec's rule on each scheduled build's card items (Hard Rock's main line and
  under price, the card's fair under, market centre and model number; w = 0.80 frozen from H3A; hp1; value >= +2%),
  logs to `challenger_picks` with arm `H-ARM-EVP` inside its own savepoint, and counts every unread game by reason;
  missing inputs or a table that does not cover the shift never qualify. Run against the stored weeks 4-7 cards it
  reproduces the spec's replay exactly (5 / 3 / 2 / 0 picks, the same games and values); that replay wrote no row.
  The Monday workflow's `protocol_position.py --write` stores an `arm_positions` row (standard `exploratory`) over
  the same complete reading weeks the arms use, with H-ARM-1HU's forward readings over exactly those weeks and the
  games both rules chose; the `monday.positions_written` contract now expects it. Research shows it in its own
  Exploratory section, with no progress bar or LLR and the ten-reading rule on both sides of the comparison. Not in
  `protocol.ARMS`; the six arms, the judge, pv1, grading, the Board and the personal ledger are unchanged. Registry
  row `H-ARM-EVP`; January review slot added.
- **2026-10-14 UTC (P1.2 R3′: A READING NEVER WAITS FOR THE SCORE).** Tate approved R3′ in place of the draft's
  seven-day permanent exclusion, asking that only valid, trustworthy closing-line data can produce a reading
  and that outcome grading stays separate. Verified in the code: the judge reads only quotes captured before
  kickoff, confirmed inside 2 hours of it, from 3+ books, within 1.5 points of the pick's line; anything less
  is a named exclusion. `scripts/consensus_backfill.py` now reads every pick an hour after kickoff, graded or
  not (`needs_reading`); `protocol_position.completed` completes a week when every pick is judged; ungraded
  results are counted beside each arm as "result not verified yet"; grading is untouched. Roadmap v2.5.
  Measured today: one pick is newly read -- H-ARM-1HO's development row on Old Dominion @ App State (10-10,
  the 0-0 line-score half awaiting proof). **Correction:** earlier episodes today said that game carries no
  arm pick; it carries this development row, placed 10-09 before the arm's clock, so it never counts.

- **2026-10-14 UTC (BOARD ALIGNMENT: ONE BAR, SCHEDULED CARDS ONLY, ONE QB READ, THE HELD GROUP).** Tate approved all
  four behaviour items with "verify every change against existing games before activating" and "missing or
  uncertain information should never silently become a favourable betting signal". B1: the Board's bar over
  upcoming games only (`homeBoard.upcomingSlateGaps`). B2b: the server and the Board read the newest
  scheduled card (`card.getScheduledCard`), and `serverVerdict` returns Watch without a slate bar (no 1.75
  fallback). B4: the QB check is the scheduled build's own injury read (`CardItem.qbOut`); an unread status
  is never favourable (server `qbOut: null` → Watch; Board: a game no scheduled build has read is not lit,
  `not_on_card`). B3: a game a failed input touched is Held -- its own group on the Board, not lit, and a
  ticket on it is recorded as Watch (`serverVerdict held`, `verdictAtBetTime`). Verified on real games:
  B1 changes 0-3 upcoming games per Saturday checkpoint in weeks 4-6 and none on this week's Board as of
  10-14 20:51Z (bar 0.85 either way); B2b, B3 and B4 had no occurrence in weeks 4-7 (no empty-slate manual
  card, no degraded card, one QB disagreement touching no game at the bar); the unread hold would have kept
  two week-4 games (Sam Houston @ Texas Tech, Colorado State @ UTSA) from lighting on Monday 9-21 before
  Tuesday's card, which the server already rated Pass then. `docs/BETTING_POLICY.md` gains the section.
- **2026-10-14 UTC (FOCUSED AUDIT AFTER TATE'S DECISIONS).** After #391-#394 merged and today's Monday read was re-run
  under p1.2 (run 38638358028): the Board lights exactly Tuesday's card's two Bets (Louisiana Tech @ UL Monroe,
  Virginia @ SMU; bar 0.8 over 55 priced games); the money path is unchanged (pause off since 10-08, 26 tickets,
  all graded, −1.43u); the six arms' and H-PRICE-HR's registry criteria and every arm, judge, grading and pv1
  constant are unchanged since the programme began (only `PROTOCOL_VERSION` moved to p1.2); `arm_positions`
  holds one row per hypothesis for 10-14, all from one run, which the Research page shows; H-ARM-1HO's
  week-7 pick reads pending, as p1.2 intends. One consistency fix: the Results page's forward picks for
  H-ARM-1HU now also require the arm tag, as the reader does (0 untagged rows today). Grade's health still
  reads degraded for the App State half awaiting proof.

- **2026-10-14 UTC (H-ARM-EVP SPECIFIED; NOT REGISTERED).** Tate asked to confirm the value-at-price arm's exact rules,
  assumptions and method before activation. `docs/program/EVP_SPEC_2026-10.md`: the rule step by step (fair
  centre = market + 0.2 × (model − market) with the frozen w = 0.80, the hp1 conversion with fractional
  shifts, ev at Hard Rock's under price ≥ +2%), the assumptions, protocol p1.2's method, and a development
  replay on weeks 4-7 cards: 5 / 3 / 2 / 0 picks a week at +2%. At about 2 readings a week, 30 readings take
  12-15 weeks, longer than the season left, so a confirmatory arm would almost certainly time out and
  spend its ledger slot. Recommended: an exploratory collector in 2026 (no slot), a 2027 confirmatory
  decision in January. Waiting on Tate.

- **2026-10-14 UTC (THE ALTERNATE-LINE PROBE, READY FOR ONE RUN).** Programme 4.4, approved by Tate as a one-time
  experiment within about 20 credits. `scripts/probe_alt_totals_h1.py` asks the feed, for the next games
  kicking off (default: within 2 h, 10 games), for Hard Rock's `totals_h1` and `alternate_totals_h1`, and
  prints whether the row fed as the 1H total is an alternate rung and whether the ladder still carries a
  main-priced line. 2 credits a game, a hard cap of 12 games (24 credits); writes nothing; separate from
  every arm and from pv1. To run once on Saturday 2026-10-17 around 3pm ET, beside Florida-app
  screenshots logged in `data/fl_app_checks.csv`.
- **2026-10-14 UTC (PROTOCOL P1.2: THE READING UNIT AND THE MONDAY COMPLETION RULE).** Tate approved R1 and R2
  of the p1.2 draft; roadmap v2.4. R1: postseason picks read in the ISO week of kickoff (CFBD files every
  bowl as week 1, which would have made the bowl season one reading). R2: a reading week enters only
  when every pick is graded and the read runs at or after the Monday 12:00 UTC after its last kickoff
  (`protocol_position.week_closes_at`), so no partial week can enter mid-week. The reader now joins each
  pick to its game for kickoff and season type (`with_games`); `PROTOCOL_VERSION` p1.2. The seven-day
  permanent exclusion (draft R3) was NOT adopted: the arms' observation is `ev_cons`, which uses only
  the close and the price, so a missing result never needs to discard a reading; the replacement R3′
  (the judge reads a pick once its close exists, graded or not) waits on Tate. Same PR, programme 4.2:
  each arm's report now lists exclusions by the close's book count (`excluded_by_books`, also in the
  stored position payload). Measured impact: no reading changes; H-ARM-1HO's graded week-7 pick reads
  `pending` until Monday 10-19 12:00 UTC.

- **2026-10-14 UTC (FINAL AUDIT OF THE PROGRAMME).** After steps 1-14 and the three decision memos
  merged (#375-#389), a read of the repo, database, workflows, production and the research record
  found two records lost to a refused command: this file had no episode for the Research page (#385)
  and the brief's and README's site paragraphs still named How it works. Both are restored here (the
  episode below, dated as merged). Audit results are in the PR.

- **2026-10-14 UTC (THREE DECISION MEMOS FOR TATE: P1.2, BOARD ALIGNMENT, FOUR PROPOSALS).** Programme
  steps 9, 15 and 16: documents only, nothing activated. `docs/program/P1_2_AMENDMENT_DRAFT.md` (the
  reading unit with postseason ISO weeks, a week completes only after the next Monday's read, the
  seven-day `ungradable` exclusion made permanent through an additive `arm_exclusions` table so grading
  is untouched; measured impact today: none). `docs/program/BOARD_ALIGNMENT_2026-10.md` (B1 Board bar from
  upcoming games: 0-3 games a Saturday checkpoint would change tier in weeks 4-6; B2b fallback bar: 0
  occurrences; B4 QB-out: 1 disagreement, no would-be Bet; B3 Held: 0 degraded cards).
  `docs/program/PROPOSALS_2026-10.md` (H-ARM-EVP recommended, ledger slot 9, +2% at Hard Rock's price;
  book count already stored as `cons_books`, every exclusion had 0 or 2 books, so a Monday report line
  instead of a new field; the late-line collector NOT recommended -- zero Saturday games first priced
  after the morning build in weeks 4-6; the alternate-line probe recommended, about 20 credits).
- **2026-10-14 UTC (THE REGISTRY STATUSES MATCH THE STATE).** Programme step 8b (Tate's rule from the Q&A:
  set every row to its true state). The six arms `pre-registered` → `live-tracking` with their clock
  starts in the data cell; H-NEGGAP and H-NEGGAP-L `live-tracking` → `superseded` (no reader since
  10-13; collector off since 10-08, zero rows); H-PCT names H-ARM-1HU as its live test; H-VENUE-1's
  result doc is the 10-11 development read; H-SHARE points at a file that exists; `live-tracking` is
  defined in the vocabulary. No criterion, rule or result changed. `web/data/hypotheses.json`
  regenerated (the Research page's closed table now lists H-NEGGAP and H-NEGGAP-L as superseded).

- **2026-10-14 UTC (A LIT BET SAYS HOW OLD ITS PRICE IS; THE SERVER'S VERDICT IS NEVER SILENT).** Step 14
  of the 2026-10-14 programme (B5 and B2a; display and reply only -- no rule, verdict or stored value
  changes). A lit BET row on the Board and the game page's Hard Rock stat now say when a poll last saw
  the price ("price seen 3 h ago"; past `HR_PRICE_MAX_AGE_H`, "refresh before logging"), since the log
  refuses a price older than 6 h while the Board's colour carries no age (`labels.priceAgeText`). The
  ticket route now returns the server's verdict beside the Board's, and when they differ a plain
  `disagreement` message ("The Board showed Watch, but the server rated this Bet from the latest
  card's bar...") that the log form shows instead of closing silently; the ticket is stored with the
  server's verdict exactly as before (`pickRules.verdictDisagreement`). The behaviour items that WOULD
  change which games read Bet or how a ticket is judged (B1 Board bar, B2b fallback bar, B4 QB-out, B3
  Held) wait for Tate's separate decision.
- **2026-10-14 UTC (RESULTS RELABELLED: THE PERSONAL STAKE, THE JUDGE'S VALUE, THE ARMS' FORWARD PICKS).**
  Step 13 of the 2026-10-14 programme (Tate's calls: the personal ledger shown as a record only,
  labelled never evidence; no ROI without an interval; everything shown and labelled). The real-money
  ledger is "Personal stake" everywhere (the strip, the tab, the season comparison, the owner's pick
  list) with "never evidence for any strategy; units modelled from the ledger, not reconciled"; the
  strip drops ROI; its second headline is now the judge's number -- "Value vs the close", the mean
  `ev_cons` with a 95% interval from two readings, with the point move of the line as the secondary
  line (B6); ROI elsewhere no longer counts a bonus bet's stake, which risked nothing (B7,
  `lib/record.ts`); the season comparison carries the Wilson interval on every win rate (P7). Paper
  rows placed before the 1H-unders clock started carry a "development" tag. Two new sections: every
  registered arm's FORWARD graded picks with their value or the exclusion reason
  (`lib/armPicks.ts`, the same selection `protocol_position.arm_rows` makes; graded rows only, so
  nothing shows before kickoff; arm starts pinned to `protocol.py` by `test_research_parity.py`),
  and the pricing study's forward opportunities, which the stored H-PRICE-HR row now carries
  (`positions.pricing_position` payload, `compact_opportunity`), so the site recomputes nothing.
  No rule, grading or ticket logic changes.

- **2026-10-14 UTC (THE RESEARCH PAGE: ONE CARD PER HYPOTHESIS FROM THE STORED MONDAY READ).** Step 11
  of the 2026-10-14 programme (#385; Tate's calls: the Board stays the homepage; Option A cards;
  nothing ranked before an arm's first decision window; everything shown and labelled). `/research`
  replaces How it works (308; `/glossary` → `/research#glossary`): seven cards in ledger-slot order
  from `arm_positions` (`web/lib/armPositions.ts`, never recomputed) showing each hypothesis's own
  standard (readings of 30 / forward opportunities of 40), weeks, exclusions, pending, the judge's EV
  with its interval only from ten readings, the SPRT position between STOP and PROMOTE, the read date
  with its run id, the next read, "outdated" past eight days and "not yet read" with no row; the
  protocol in plain words (numbers pinned to `protocol.py`/`pricing.py` by
  `tests/test_research_parity.py`); the closed hypotheses with their verdicts from
  `web/data/hypotheses.json` (`scripts/export_registry.py`, parity-tested against
  `docs/HYPOTHESES.md`); the Board key, the glossary, the records link and the helpline. The 2023-25
  backtest card, the gap ladder and the accuracy block went with the old page. Nothing on the Board,
  in the ledger or in any rule changed.

- **2026-10-14 UTC (THE RESEARCH STATUS STRIP ABOVE THE BOARD).** Step 12 of the 2026-10-14
  programme (Tate: the Board stays first, with a thin status strip above it). One line -- how many
  strategies run on paper, the most readings any has toward 30, the next Monday read -- and a pill
  per hypothesis with what it has logged (the pricing study: forward opportunities of 40), with the
  link to Research. It reads the same stored Monday row the cards do (`web/lib/armPositions.ts`)
  and touches no rating; a visitor sees the same line. The Board's rows, order and wording are
  unchanged (e2e: the strip sits above the week heading, never inside the board).

- **2026-10-14 UTC (ARM POSITIONS STORED: ONE ROW PER HYPOTHESIS PER MONDAY READ).** Step 10 of the
  2026-10-14 programme. Until now the six arms' position lived only in a `study.yml` artifact and the
  pricing verdict only in a report file, so the site could not show either and a missing Monday read
  was invisible. `arm_positions` (`beatvegas/positions.py`; unique on hypothesis + read date) is
  written ONLY by `pricing_monday.yml`: `pricing_check.py --write` (H-PRICE-HR: forward
  opportunities of 40, the verdict word, close-EV mean and interval) and `protocol_position.py
  --write` (each arm: readings of 30, weeks, LLR, mean EV with its interval, exclusions, pending,
  the next Monday). A retry on the same Monday rewrites the same rows with the newer run id. The
  workflow gains a 12:30Z GitHub backup cron, a run clock and the `monday` health contract
  (`monday.positions_written` FAILED = email; `monday.pricing_report_written` degraded); `monday`
  joins `HEALTH_JOBS` on both sides and the e2e fixture. The site reads the newest row per
  hypothesis through `web/lib/armPositions.ts` (never recomputes; "outdated" past 8 days,
  "sufficient" at readings >= needed); the Prisma model is hand-added; the e2e schema is
  regenerated. Nothing about the arms' rules, the judge, pv1 or grading changes; a `study.yml`
  dispatch of `protocol_position` still writes nothing.

- **2026-10-14 UTC (THE WRITTEN RECORD CATCHES UP WITH THE CODE).** Step 8 of the 2026-10-14
  programme (docs only; nothing runs differently). From the whole-system review's drift list:
  `CLAUDE.md` (Cox closed NOT MET 10-11, not "running"; the neggap/H-FG-P collectors retired 10-08,
  not "keep logging"; the card.yml row names the arms it writes, not `NEGGAP_COLLECT`/`FG_COLLECT`;
  pricing-monday's window is 6am-3pm ET; lines_watch is also dispatched by `close-weeknight`;
  grade.yml takes `regrade`; "every scheduled Neon-writing job" ends with the health check);
  `docs/HEALTH.md` (the full-game close step pulls totals, spreads and moneylines over `us,us2,us_ex`
  at 9 credits; the promised `fg_rows_touched` check is dropped, not pending); `docs/ASSUMPTIONS.md`
  (H-STOP-2 superseded; the live instrument is each arm's protocol test); `docs/OPS_ACCOUNTS.md`
  (the $20 Actions cap and Tier 1 at Nov 6 are decided, account-side for Tate); `README.md`
  (deleted `scripts/backtest.py` and `backtest/engine.py`, the removed research section, the real
  close look-ahead, the pricing row, no `prisma db pull`, "all free" dropped); the 10-13 weather
  episode says sustained wind, not gust; `docs/program/REVIEW_2026-10.md` carries a bracketed
  correction (six of eight arms were registered by 10-11); `docs/ROADMAP_2026.md` v2.3 records Cox
  and the retired collectors in the ledger table and adopts the 17-step programme. The registry
  status diff (step 8b) is its own PR, held for Tate's approval row by row.

- **2026-10-14 UTC (PRICING REPORT: THE TRUSTED HALF, EACH ERA'S OWN DROPS, THE TWO MISSING TABLES).**
  Step 7 of the 2026-10-14 programme (report only; pv1's constants untouched and still pinned by
  `tests/test_pricing.py`). The Monday report graded first halves on the raw `games.first_half_total`,
  skipping the 0-0 guard every pick's grading uses, so a false-zero half would have read as an under
  win; it now grades on `trusted_first_half_total` with the half's source. One drop counter served
  both the development and the forward summaries, so `forward.drops` carried development drops;
  `price_states` now counts every drop per era beside the flat count and `drops_for` serves each
  block its own. The two tables the registry criterion names and the report never printed -- every
  drop reason per market, and the flag share by hours to kickoff and by weekday (ET) -- now render
  under each era. Before/after on the data: all five development opportunities' halves are
  `linescores` with non-zero finals, so no result changes; the forward block is still empty.
- **2026-10-14 UTC (/api/health: THE OWNER'S DETAIL RIDES ONLY ON THE COOKIE).** Step 3 of the
  2026-10-14 programme. The public endpoint carried the real-money pause switch, the CFBD and Odds
  API budgets, every job's run note and the private repo's run links inside the warnings. A visitor
  now reads `ok`, the stale/missed flags, the capture counts, close coverage, dispatch times and
  each job's verdict with its time (`lib/healthBody.ts::publicBody`, keys removed, never nulled;
  each warning cut before its "Run:" link); the signed-in owner reads the full body as before. The
  smoke check and the board's banners read what they always read. Unit test on the projection;
  the e2e health spec gains a signed-out case.
- **2026-10-14 UTC (THE FULL-GAME ARM'S INPUT HAS A HEALTH CHECK).** Step 6 of the 2026-10-14
  programme (integrity). H-ARM-FGU selects on `bv_fg_v1` reads that only the Sunday shadow step
  writes (`scripts/fg_shadow.py`), and that step is `continue-on-error` so a shadow failure never
  costs the champion's Sunday; nothing reported the failure, so an empty FGU week would have been
  silent. `sunday.fg_shadow_scored` (degraded: at least one `bv_fg_v1` prediction for the week's
  games since ET midnight) joins the Sunday contract; the step is relabelled as the arm's input
  (it was still "H-FG-P"); `docs/HEALTH.md` regenerated. No rule, window or grading changes.
- **2026-10-14 UTC (A HAND DISPATCH OF A SCHEDULED SLOT OBEYS THE ET GATE).** Step 5 of the
  2026-10-14 programme (integrity). `ci.resolve_slot` gated only cron ticks; a `workflow_dispatch`
  naming `tue_pm` / `thu_pm` / `fri_pm` / `sat_am` built at any hour and, being a scheduled slot,
  paper-logged the registered arms at that moment's lines (Vercel's ticks are gated on their side;
  people were not). A named slot dispatched outside its window now skips with the reason, before
  the Neon probe; `force=true` is the one explicit override (it already bypassed the built-today
  probe) and `manual` stays the ungated preview that logs nothing. Before/after on the data: no
  logged arm row came from an out-of-gate dispatch (the only dispatch-event card run since
  ARMS_START was the Vercel tick, run 38463679608). Tests: `tests/test_ci_slots.py`.

- **2026-10-14 UTC (A VISITOR NEVER SEES THE OWNER'S CAP SLOT BEFORE KICKOFF).** Step 2 of the
  2026-10-14 programme. `signalGate.gateGame` rewrote only the action sentence and the "bet logged"
  chip; the "cap slot N" and "past the 5-bet cap · paper only" chips and the early-season clause
  "real money needs 2" still reached visitors, naming which games the owner's stake would take
  (v1.4/v1.7). Before kickoff a visitor now gets `capRank` null and `overCap` false, and the
  early-season sentence reads "a rating needs 2"; after kickoff the ledger shows the ticket anyway,
  so the slot shows too. The owner's view is unchanged; the rating, rank, our number, the gap and
  the kill line stay public before kickoff exactly as all season. Unit tests in
  `lib/signalGate.test.ts`; the visitor e2e on the board and the game page asserts none of the
  three strings renders.

- **2026-10-14 UTC (NO DOLLARS ARE PUBLIC: THE BANKROLL CURVE CARRIES UNITS ONLY).** Step 1 of the
  2026-10-14 programme. `/results` passed the bankroll curve into the client `BetLedger`, and every
  point carried a `usd` value (the starting bankroll compounded by the unit size), so each visitor's
  page payload held dollar amounts although the chart has drawn units only since 2026-09-28. The
  curve is now `{week, units}`; `bankrollCurve(picks)` takes no bankroll; the Results page no longer
  reads `bankrollEnv`. The game page still hands the unit size only to the signed-in log form (a
  server component; nothing reaches a visitor). The signed-out e2e test now asserts the page carries
  no `"usd"` key and no dollar figure in its text.

- **2026-10-14 UTC (WEATHER CAPTURE: A NULL WIND HOUR IS UNKNOWN; A 4XX IS RETRIED IN HALVES).** Step 4
  of the 2026-10-14 programme (the whole-system review; Tate's approval of all 17 steps the same
  day; plan file `pasted-content-id-a68f`). Two edge cases #374 left: a forecast block whose
  kickoff hour carries no wind value was stored as a fresh row with `wind_mph` NULL -- read as calm,
  counted as "forecast this build", and newer than any valid forecast on file; and a non-429 4xx from
  Open-Meteo escaped as a raw `HTTPError`, which `wx_paper.capture`'s halving retry does not catch,
  so one bad request cost a build both weather arms. Now a null-wind hour stores nothing and its
  games read UNKNOWN by id (an older valid forecast stays the newest), and every 4xx raises
  `WeatherUnavailable` (not retried, but handled). Before/after on the data: the 10-13 build stored 23
  of 23 outdoor rows with a wind value, so no stored row changes. The 10 mph rule, the arms, the
  windows and grading are untouched. Tests: `test_wx_paper` (null hour, older forecast survives, no
  NULL row), `test_weather_source` (404 → `WeatherUnavailable`, one call).

## 2026-10-13

- **2026-10-13 UTC (WEATHER CAPTURE BATCHED; A MISSING FORECAST IS UNKNOWN, NEVER CALM).** Tate's
  approval of the fix to the Tuesday finding (26 forecasts stored, 31 lost to seven Open-Meteo
  timeouts and the 180 s cap; a game without a forecast read as "not windy" and never appeared in the
  arm summary). `wx_paper.capture` now sends the outdoor venues of each UTC day in one Open-Meteo
  multi-location request (at most 25 venues a request; `sources/weather.py::fetch_hourly_series_batch`,
  the body is a JSON array in request order, each block checked within 0.5 degrees of the venue
  asked for or discarded); a failed request is retried in halves down to single venues (each venue
  asked at most once per level), the 180 s budget is checked before every request, and a venue whose
  forecast never arrives stores NOTHING. Every build now reports: the capture line (requests, stored,
  domes, failed, unavailable, past the cap) and, per arm, priced games split into a forecast from
  this build, one carried from an earlier build (with the oldest age in hours), domes, and UNKNOWN
  (no forecast) named by game id. Unchanged on purpose: the 10 mph sustained-wind rule, the selection rules,
  the windows, grading, history, and `newest()` carrying an older build's forecast (its age is now
  reported; capping it would be a rule change). `tests/test_weather_batch.py` (parsing: order,
  single-point dict body, short or displaced blocks, failed request) and `tests/test_wx_paper.py`
  (one request per day matched to its venue; a partial body counts unknown; a failed batch splits
  4 -> 2 -> 1; no request past the budget; the per-venue and batched paths store identical rows on
  the same synthetic slate; the arm accounting). Forecast freshness, measured: the runner's
  timeouts were against Open-Meteo's forecast endpoint, which answered the Mac in under a second
  the same day; the model is `icon_seamless` as before. First denser build: Friday 10-16.

- **2026-10-13 UTC (ARMS 1-3 CLOCKS STARTED: ARMS_START = THE TUE_PM CARD).** Tate's approval of the
  one-line change the protocol had been waiting for (p1.1, roadmap v1.5/v1.8): the first card built on
  the leak-fixed model ran 2026-10-13 (run 38463679608, 23 min, all six arms logged their lines;
  `cards.id` 29, built 20:51:39.533351 UTC). `beatvegas/protocol.py::ARMS_START` holds that instant;
  the position reader counts rows placed at or after it (one H-ARM-1HO row at the build; the
  2026-10-09 rows, ten per model arm, stay development evidence). No rule, threshold, grading
  method or record changed; the weather and 60+ arms keep their own backstop starts. Verified
  after the merge by a `study.yml` `protocol_position` dispatch. Same build: the weather capture
  stored 26 forecasts and lost 31 to Open-Meteo timeouts and the 180 s cap (investigated,
  unchanged; a game without a forecast is treated as not windy, which the arm cannot tell from
  calm -- a fix proposal is with Tate).

- **2026-10-13 UTC (EVIDENCE RULES IN THE BRIEF).** From the usage review of the same day (an
  unsupported count of scoreless halves Tate had to ask for repeatedly; a "failed cron" that was
  a hand dispatch from another session). Analysis Rules: every number carries the query, script
  or run id that produced it and its row count, an inference is labelled, a count Tate cannot
  re-run is not stated. The GHA-cron gotcha: check `gh run list --event workflow_dispatch` before
  calling a job missed. Neighbouring lines tightened; the brief stays at 398 lines. The private
  skill `bv-weekly-review` (the long report v2.1 stopped) is retired to `~/.claude/skills/_retired/`;
  `bv-monday-read` builds the one-page Monday read with a `[Qn]` appendix behind every number.
- **2026-10-13 UTC (CATCH-UP TICKS FOR THE NO-DEADLINE JOBS; ROADMAP v2.2).** From the usage
  review of the same day (jobs that missed a whole window were re-run by hand) and Tate's call:
  only jobs with no deadline get an automatic second chance. `web/vercel.json` gains grade at 20Z
  daily, Sunday at 23Z (the window now closes 8pm ET) and pricing-monday at 18Z (window to 3pm
  ET); `suppressedBy` (unchanged) lets each dispatch only when no run since the window opened
  succeeded. No catch-up for a card build or a close poll: a late card would log arm picks
  outside their registered window, a close poll is useless after kickoff; the board's dispatch
  and health banners still show those misses. Tests in `web/lib/cronJobs.test.ts` (both DST
  regimes, suppressed after a success, dispatched after a failure or nothing). Nothing about an
  arm, the judge, the protocol or money changed.
- **2026-10-13 UTC (THE PUSH/MERGE GATE AND THE PRODUCTION SMOKE CHECK).** From the usage report
  of the same day (masked test runs and a red suite pushed; stacked PRs merged into the wrong
  base) and Tate's call for a hard block. `scripts/hooks/pre_bash.sh` (PreToolUse, Bash) refuses
  `git push` unless the full suite is green on that exact tree (the `on_stop` stamp, now shared
  through `scripts/hooks/_suite.sh`, or a run inside the hook) and the branch adds no
  skip/xfail/only to a test; refuses `gh pr merge` unless `gh pr checks` shows web, python and e2e
  all passing; refuses a test run piped into tail/head/grep without `pipefail` or followed by
  `|| true`. `post_edit.sh` refuses an edit that adds a skip, xfail or `.only` to a test.
  `scripts/hooks/classify_bash.py` decides (stdlib, tested in `tests/test_hooks.py` against a
  stubbed suite and a stubbed `gh`). `web/scripts/smoke.mjs` is the post-deploy check `bv-ship`
  runs: pages 200 signed out, the first board game 200, every `next.config.ts` moved route 308 to
  its destination, `/api/health` ok, the season's records CSV non-empty. Nothing about an arm,
  the judge, the card, grading, the ledger or the site changed.

## 2026-10-12

- **2026-10-12 UTC (THE MONDAY PRICING REPORT; pv1 FROZEN; FORWARD FROM 2026-10-13).** Tate's
  approval of items 2 and 3 as one PR. `.github/workflows/pricing_monday.yml` (dispatch only,
  read-only, the report on the run's Summary page and the `pricing-report` artifact) is
  dispatched by the Vercel `pricing-monday` entries at 12Z with a 15Z retry (6am-noon ET window;
  the route re-dispatches only after a failed run). No GitHub cron: a scheduled Neon job needs a
  health contract, which reaches into the site's health list; `gh workflow run` is the fallback.
  `pricing.FORWARD_CUTOFF` = 2026-10-13: every earlier state is development evidence, printed
  apart; the cumulative verdict (insufficient below 40 forward opportunities; strengthening /
  weakening / inconclusive from the toward-Hard-Rock share's 90% Wilson bounds and the close EV
  interval, thresholds in `docs/PRICING_RESEARCH.md`) reads forward opportunities only. `pv1`'s
  constants are pinned by `tests/test_pricing.py`; any change is `pv2`. `data/fl_app_checks.csv`
  holds Tate's Florida screenshots; a state rises to tier 2 only on an exact match of game,
  market, line, prices and a capture within ten minutes; mismatch and ambiguous stay unverified,
  unreadable rows are counted and skipped. Nothing about an arm, the judge, the card, grading,
  the ledger or the site's pages changed (the cron table gained one job; the owner-only trigger
  gauge follows from it).

## 2026-10-11

- **2026-10-11 UTC (H-PRICE-HR READ 1: FIVE FEED OBSERVATIONS IN SIX WEEKS, NONE VERIFIED).**
  `study.yml` run 38179348954 at b04ae60, the first pricing read on 2026 weeks 1-6 (identical to
  the local reproduction): first-half 931 Hard Rock states on 358 games, mean EV −4.15%, 38/21/11
  above 0/+1%/+2% at the point estimate and **3 flags** at the lower bound of the half-point mass;
  full-game totals 1,485 states, 59/31/16, **2 flags**; moneylines within ±200, 73 states, 1 positive,
  **0 flags** (121 lopsided states not compared; the unrestricted pass had produced 18 longshot
  flags at +275 to +1100, the de-vig's favourite-longshot bias, fixed before the rule froze). Five
  opportunities, all tier 0 (feed observations, unverified for Florida), 1-4 realized; in the three
  first-half cases the market never moved; one full-game case moved toward Hard Rock. Development
  evidence: the bar was chosen after Step 0 on these same weeks; the forward weeks are the test.
  `docs/PRICING_RESEARCH.md` holds the tables. Lesson: the table's sampling error halves the
  candidate count; calibrating it is the next modelling task.

- **2026-10-11 UTC (H-PRICE-HR REGISTERED: HARD ROCK AGAINST THE MARKET, RULE pv1).** The pricing
  research runs (Tate's approval: the independent, read-only exploratory study only). Row before
  code: exploratory, no alpha, read at 2026-12-07 and January; `beatvegas/pricing.py` holds the
  frozen rule (main quote only; reference = median of 3+ other centred books confirmed at the
  capture minute, Fliff and the consensus row excluded; totals converted through `hp1` within 1.5
  pts; a flag is EV >= +2% at the LOWER bound of the table's integer masses; moneylines compared
  without conversion; spreads refused for want of a spread table; one opportunity per game-side).
  Every flag carries an evidence tier (0 feed observation, 1 fresh stamp and re-seen, 2 Florida
  screenshot, 3 ticket); tiers 0-1 are never called available. `scripts/pricing_check.py` on
  `study.yml` writes `reports/pricing_check_*.{md,json,csv}`; `docs/PRICING_RESEARCH.md` is the
  doc. Dispatch only: a Monday schedule is a separate automation decision. Nothing an arm, the
  judge, the card, grading, the ledger or the site reads changed. Correction to the same day's
  audit: the parser discards extra point pairs only when the feed sends several, which it did zero
  times in the recent card and Sunday runs; the alternate ladder is a separate feed market
  (`alternate_totals_h1`, a credit an event) that was never requested, so nothing is being thrown
  away today, and capturing it is a credit decision for Tate.

- **2026-10-11 UTC (CAPTURE STEP 1: THE FEED'S STAMPS AND EVENT IDS, A 6-HOUR SATURDAY LOOK-AHEAD,
  THE HARD ROCK KEY PROBE).** The first build of the pricing-inefficiency programme (Tate's approval
  2026-10-11; `docs/program/CAPTURE_DESIGN_2026-10.md`, corrected). Three nullable columns on
  `odds_snapshots`: `event_id` (the feed's key), `feed_updated_at` (The Odds API's `last_update` at
  FIRST capture of a price state, the PROVIDER's last observation, never overwritten) and
  `feed_reseen_at` (the newest provider stamp seen while the price stayed unchanged); rows written
  before the columns keep `feed_updated_at` NULL for good. Both pollers write them
  (`beatvegas/snapshots_provenance.py`: a missing stamp is NULL, a stamp more than ten minutes
  ahead of our clock is reported and kept). `lines_watch.yml` reads 360 minutes ahead on Saturday
  ticks (14Z Saturday to 05Z Sunday, chosen by the resolve step from the clock, so the pre-check
  and the poll cannot disagree) and 120 on weeknights; the judge's 2-hour window is untouched.
  Scheduler fact: of the last 40 `lines_watch` runs, 28 were Vercel dispatches and 12 GitHub
  schedule runs; both write rows. **The Florida key probe** (`scripts/probe_hr_keys.py`, run
  2026-10-11 21:25 UTC, 16 credits measured: 1 bulk `us2` call + 15 per-event calls at 1 each
  despite two markets): the `us2` region returned `rebet`, `ballybet`, `betparx`, `espnbet`,
  `courtside`, `hardrockbet` and `betanysports`; **`hardrockbet_fl` appeared in no response**,
  neither in bulk nor in 15 explicit `bookmakers=hardrockbet,hardrockbet_fl` requests (57
  Hard Rock full-game totals, 0 Florida rows, 0 first-half totals yet on a Sunday night). So the
  feed offers one Hard Rock key, which its bookmaker table calls the Indiana book "currently same
  odds as several other states"; whether the Florida app shows those numbers cannot be settled
  from the feed, only from Tate's screenshots or a ticket. The provider's stamp sat 54 seconds
  before our capture on every row of the probe. Nothing about an arm, the judge, the protocol,
  the ledger, grading or the site changed; no history was bought.

- **2026-10-11 UTC (H-LIT-COX READ: NOT MET, FINAL).** `study.yml` run 38170624665 at afbf045, the
  one dispatch: on 2019-2025 trophy games the favourite that had won the last three meetings went
  72-75-4 (147 graded of 529, 49.0%), p 0.818 against 52.38%, Holm-adjusted 1.000, units −9.55 at
  −110; final, since a raw p above 5% cannot pass at any Holm step. All four looks run (Arscott, TV,
  Bennett, Cox) read NOT MET; the family table over the four JSON reports prints 1.000 for each;
  Coleman and Salaga stay parked (roadmap v2.1). Descriptive only: every trophy favourite 51.2%
  on 512, the G5-vs-G5 underdog 50.3% on 195, the streak underdog 36.2% on 47; 2022 was 7-16.
  The registry row is tested-null; `docs/LITERATURE.md` holds the table. CFBD calls left 73,780.

- **2026-10-11 UTC (ROADMAP v2.1: THE ALIGNMENT CALLS, THE JANUARY TEMPLATE).** The evening Q&A after
  the October review, logged as one versioned amendment (`docs/ROADMAP_2026.md` v2.1) with the
  templates in `docs/program/JANUARY_2027_REVIEW.md`: one Monday sitting on a one-page read (arms
  first; the long weekly report stops; light read 10-12, first full read 10-19); two decision reads,
  2026-12-07 (mid-point, none) and 2027-01-25 (final); the 2027 default drafted (+1.5%, two-season
  clocks, capture-based arms first; a 2026 pass = $10 live validation only); Kalshi account only on
  a January H-VENUE-1 read of about 1 pt EV best-of-two over 100+ games on fee-inclusive prices;
  CFBD Tier 1 on 11-06, Odds API 20K, Actions cap $20; after 10-19 one late cron per job and the
  post-mortem tables stop; HR rung drift accepted; Cox now, Coleman and Salaga parked; weather
  backfill on Mon-Wed; friends get one plain message; 2026 success keeps the bar with the
  research-year deliverables beside it. Tate's deep-research Kalshi report filed as
  `docs/external/2026-10-11-chatgpt-deep-research-kalshi-cfb.md` (review §F4b points at it; Group
  2 answer 5 annotated with the later decision). The brief: v2.1, four stale open items cut.
  Docs only.

- **2026-10-11 UTC (H-ARM-FGU WEEK-6 SELECT REPLAYED: THE BUILD REPRODUCES EXACTLY).** The reassessment
  had flagged a gap (a reconstruction found 11 qualifiers at a 0.70 bar against 10 logged, with
  Kansas State and Ohio State "below the bar" and Arkansas State, Troy and Western Kentucky
  "unlogged"). Read-only replay against Neon as of the one build that logged the arm,
  `cards` 28 (fri_pm, 2026-10-09 20:17:48 UTC; the sat_am build never wrote a card row, run
  38049849474 timed out): Hard Rock `full_game_total` newest snapshot per game captured before the
  build, centred at −160, unplayed games only, `bv_fg_v1` predictions (refit 9, 2026-10-07, untouched
  since) → universe 50, k = 10, bar 0.48, the same ten games in the same order as `cap_rank` 1-10
  and the ten rows' frozen `bar` / `universe_n`; the run log printed "universe 50, bar 0.48, 10
  qualify, +10 logged". Kansas State (0.64) and Ohio State (0.48, a tie at the bar, which qualifies)
  were above the real bar. Troy (kick 10-07), Western Kentucky and Arkansas State (both 10-08) had
  kicked off before the build, so they could not be in the universe; counting them is what pushed
  the reconstruction's bar to 0.70. No defect, no row touched. The arm's first read stays
  2026-10-19.

- **2026-10-11 UTC (H-VENUE-1 FIRST DEVELOPMENT READ, AND THE FEE QUESTION).** `venue_check` run
  38149958361 on week 6 (53 graded games with a Hard Rock and a Kalshi full-game total and 3+ books
  inside the judge's window): both venues sit the same distance from the field's median (0.33 vs
  0.35 pts, about 25% a point or more off), but the judge reads Kalshi's price about 4 points of EV
  better on every under (−1.13% vs −5.16%, Kalshi better on 100% of games) and on 89% of overs
  (−0.78% vs −3.63%). Same line distance, better price on every game, a gap the size of Kalshi's
  7% taker fee (review §F: −110 to −121 all-in): the likely reading is that the feed's `us_ex` price
  is fee-exclusive, not that Kalshi is softer. The January registered read states whether the price
  includes the fee before any claim; the registry row is unchanged (its result cell is January's).

- **2026-10-11 UTC (THE 10-11 REFIT CONFIRMED; #362 MERGED).** `sunday.yml` run 38166029060 wrote
  `model_runs` 10 (`gbm_v1`, 2003-2025, "weekly refit", 19:19 UTC) and 11 (`bv_fg_v1` shadow refit,
  19:20 UTC): the leak-fixed model's first card is Tuesday 10-13, which starts arms 1-3's clocks
  (protocol p1.1). The weather step of that run failed (`need_capture`/`need_score` true, pace ok);
  read at the light read. PR #362 (the Hard Rock off-market capture design note) merged at ae610a9;
  the `roadmap-v2` and `capture-design` worktrees removed. The Vercel `sslmode` warning (pg v9)
  is an open nit, moved here from the brief: set `sslmode=verify-full` explicitly on `DATABASE_URL`.

- **2026-10-11 UTC (H-LIT-COX REGISTERED: THE STREAK FAVOURITE IN TROPHY GAMES).** The fourth
  literature look (roadmap v1.3; v2.1's "Cox runs now, Coleman and Salaga parked"). Tate's call on
  the rule: of Cox's three results the one tested is the favourite that won the last three meetings
  (56.6% on 454 in the paper, its only result significant at 5%); the rivalry-favourite fade and
  the non-P5 underdog are reported as descriptive numbers only. The row before the code: 2019-2025
  regular-season FBS-vs-FBS games whose pair is one of the 112 trophy pairs frozen 2026-10-09
  (`data/trophy_games.json`); favourite by the median CFBD closing spread (pick'em dropped); prior
  meetings from CFBD `/teams/matchup` (new `CFBDClient.matchup`, one call a pair), any season type
  and any year, ties skipped, fewer than three decided meetings dropped; graded on the final margin.
  `literature_look --row H-LIT-COX` (`beatvegas/backtest/literature.py::cox_rows`); the family
  stays m = 6, Holm 5%, outside the ledger. One dispatch after the merge; the results PR writes
  `docs/LITERATURE.md`.

- **2026-10-11 UTC (H-VENUE-1 REGISTERED: HARD ROCK AGAINST KALSHI ON CAPTURED DATA).** Roadmap v2.0
  decision 5 (Kalshi is measured before anything is built). The row before the script: on every
  graded 2026 game with a Hard Rock and a Kalshi full-game total inside the judge's 2-hour window
  and three other books, `scripts/venue_check.py` (study.yml) reads each venue's offset from the
  other books' median, the judge's EV of both sides at each venue's own close and price (the judge
  counts neither venue), realized units, and per side the better of the two venues. Exploratory,
  accruing (39 games at registration, week 6; the full-game close polls started 2026-10-06);
  development reads on Mondays, the registered read at the January review. No account, no
  capture, no credits. Kalshi's reported line is one rung of its ladder: a rung 1.5+ points off
  the other books has no reading and is counted (`far_lines`).
- **2026-10-11 UTC (THE CAPTURE DESIGN NOTE).** `docs/program/CAPTURE_DESIGN_2026-10.md`: Tate's
  call for the next build (roadmap v2.0 decision 6) scoped to two nullable columns on
  `odds_snapshots` (`event_id`, `book_updated_at`, both already in the feed's rows and dropped at
  insert) plus a 6-hour Saturday lookahead for the close poll (120 → 360 minutes on Saturday ticks
  only, about +180 credits a Saturday). The judge's 2-hour window, the arms and the protocol are
  untouched. PR Wednesday after Tuesday's card; first denser Saturday 2026-10-17.

- **2026-10-11 UTC (THE PRICE-CLV COLUMN GOES).** `clv_prob` never read the ticket's price or bet
  time (every pick on a game carried the same number: the market's own no-vig move from each
  book's first to last quote), so the ledger CSV drops it (31 → 30 columns) and the code that
  consumed it goes with the Monday review it fed: `lib/decision-quality.ts`, its test and
  `DecisionsStrip`. The sign pin in `lib/clvDirection.test.ts` keeps Tate's six week-2 tickets
  without the deleted module. The DB column stays (migrations are additive) and `picks.py` still
  writes it; nothing on the site reads it. Tate's call: drop the column and the dead code.

- **2026-10-11 UTC (THE DISPLAYED CLOSE NEVER COUNTS HARD ROCK).** The October review found that
  the stored `clv` on every pick (the ledger's "line value" column) used a close that was the
  median of EVERY book's last centred quote, Hard Rock and Fliff included. Hard Rock's late quotes
  are alternate rungs priced −140 to −160, which pass the centred filter and sit 1-1.5 points under
  the market, so the "close" leaned toward the under on exactly the tickets Hard Rock had moved
  against. Fix: `lines.closing_before_kickoff` counts only the judge's books
  (`lines.CLOSE_EXCLUDED_BOOKS` = Hard Rock, Fliff, the feed's consensus row; `consensus.py` now
  reads the same set); a game only Hard Rock priced has no close. `book_closing_before_kickoff`
  (one book's own close, the closing PRICE) is unchanged. `grade.yml` gains a `regrade` input
  (`pick.py --regrade`, forces the probe) for the one-time recompute; the before/after per ticket is
  in PR #357's body. The arms read `ev_cons`, so no clock moves. Tate's call: fix now, show the table.
- **2026-10-11 UTC (H-JUDGE AND H-WX-HIST READ, ONE LOOK EACH).** Re-dispatched after #347 fixed the
  market-name bug that had emptied their line-value readings (Tate's call: dispatch both).
  **H-JUDGE** (run 38147535009): does the judge's line value predict returns? First half 2023-25,
  3,664 bets: mean predicted −4.47% against realized −4.48%; slope 0.48 (−0.14 to 1.15), intercept
  −2.33%; the top quintile (predicted +2.7%) realized +0.35% (−5.97 to +6.48). The sign is right on
  average; the slope sits below one with an interval spanning 0 and 1, so a +3% reading has
  realized about +0.4% in this sample. **H-WX-HIST** (run 38147537131): windy (10+ mph, 72-hour
  forecast) first-half unders read −3.56% line value against calm −4.82% (the market moves about 1.3
  points of EV toward the under before kickoff, short of the vig) and 90-95-2 against the close;
  full game 94-92-4. Not an edge at the close; the pre-close move is what H-ARM-WX1H measures
  forward. Both exploratory; nothing adopted; the rows carry the numbers.
- **2026-10-11 UTC (THE DEAD CODE GOES; ROADMAP v2.0 CUT LIST, PART 1).** Deleted, each with its tests:
  the offline backtest engine (`backtest/engine.py`, `bv_engine.py`) and its tools (`scripts/backtest.py`,
  `validate_engine.py`, `retrain.py`, `rank_factors.py`, `inspect_combo.py`, `explain_pbp.py`,
  `factors/evaluate.py`, `factors/inspect.py`); the four finished gate WORKFLOWS (`residual_gate.yml`,
  `level_anchor_gate.yml`, `intercept_gate.yml`, `inseason_gate.yml`) plus `post-lines.yml` and
  `fg_shadow.yml` (Sunday runs both steps); the closed studies' scripts and modules (`two_sided_study`,
  `weather_style_study`, `hr_lag_study`, `stopping_rule_candidates`); and six scripts nothing called
  (`backfill_bv_line`, `backfill_context`, `deploy_neon_games`, `purge_demo_rows`, `weekly_report`).
  Kept, found live during the cut: the four gate SCRIPTS (`scripts/residual_gate.py` and siblings are
  imported by `protocol_position`, `fg_position`, `challenger_position`, `blend_gate`,
  `sharp_book_probe`, `stopping_rule_position`), `bv_adjust` (the only writer of a table the site
  reads), `elo_line` (a feature input), `BREAKEVEN` moved into `backtest/residual_gate.py`. Git
  history keeps every verdict's code at the SHA its doc names. 1,645 tests pass. Part 2 (GitHub cron
  backups) is its own PR; the residual engine's no-op card step, the margin model, the DraftKings
  first-try poller and the post-mortem tables wait for the first Monday read (10-19).

- **2026-10-11 UTC (THE SITE IS A PUBLIC RECORD AND NOTHING MORE; ROADMAP v2.0).** Gone: the
  board's answer bar, the My-teams chip (only the Hard Rock chip remains; `?mine=1` still parses),
  the Monday review's breakdown, decisions strip and factor read on Results, and the signed-in
  research section on How it works (live-season strip, flags, method fold, line study). Kept, on
  Tate's call: the owner's pick list with its edit/delete controls (the only place a pending real
  ticket is edited before kickoff) and the ops and build warnings (the failure surface). The banner
  names the owner's real bets a personal stake, recorded separately and never evidence. e2e: five
  tests removed, two retitled, `FEATURE_PARITY.md` matched; 241 passed on the fixture lane.

- **2026-10-11 UTC (ROADMAP v2.0).** The October review's sixteen decisions logged as one versioned
  amendment at the bottom of `docs/ROADMAP_2026.md` (objective = personal proof at Hard Rock; the
  site a public record only; every arm, the judge and the protocol frozen to the January review;
  +3% one-season target for 2026; Kalshi measured first on captured data; Hard Rock off-market
  capture next; the personal ledger continues, labelled a personal stake; the cut list; the
  measurement fixes; bookkeeping). Body edits: the three literature nulls read REJECTED in the
  hypothesis ledger (deferred since v1.5); `docs/PROTOCOL_2026.md` reads 8 betting slots (v1.8);
  the brief says the pause switch is off and the personal ledger ON. No code changed.

- **2026-10-11 UTC (THE COMPLETE REASSESSMENT; `docs/program/REVIEW_2026-10.md`).** Tate asked for a
  ground-up review of mission, strategy, hypotheses, results, data, infrastructure and business,
  as an independent researcher, with questions grouped and answered before any change. Read-only:
  live Neon reads, three repo sweeps, five Kalshi research lanes, his own Kalshi report
  reconciled. Nothing in the repo or the database changed during the review.
  - **What the evidence said:** every ledger (real, paper, every arm, the retired over arms)
    reads −3% to −6% against the consensus close — the vig; real money 12-14, −1.43u on 26
    tickets, 12 unjudgeable (`stale_close`); six of eight arms are unders variants and three ride
    a model that is worse than the market on 2026 data; the two structural arms (slots 4-5) have
    no design; stored `clv` is a median that includes Hard Rock's own late alternates and
    `clv_prob` never reads the ticket's price; the stop rule was replaced twice then dropped; the
    backtest is not the rule that is bet; ~$50/month but 87 scripts, 20 workflows, 30 tables,
    20K doc lines and 17 incidents since 09-01. Kalshi: lawful from Florida today, not a softer
    price (−110 to −121 all-in as a taker, a mirror of the books), unique for line shopping, no
    winner limits and a free maker side on 1H totals; its data terms keep its prices off the site.
  - **Tate's calls (sixteen, Part 2 of the review doc):** the objective is personal proof at Hard
    Rock; every arm runs unchanged to January (readings only); +3% one-season target stays for
    2026, re-decided in January; Kalshi is measured first on data already in `odds_snapshots`;
    the next build is Hard Rock off-market capture; the personal ledger continues and the site's
    mission line is scoped to promoted rules; the site is a public record and nothing more; the
    cut list is accepted (offline backtest engine + four finished gate workflows + orphan
    scripts, post-mortem tables and factor ledger, GitHub cron backups, owner-only site
    sections); one committed review doc under `docs/program/`. Roadmap v2.0 follows as its own PR.
  - The 2026-10-09 strategic review (topics 1-3 closed) was committed verbatim as Part 1; it had
    lived untracked in the `strategy-review` worktree.

## 2026-10-10

- **2026-10-10 UTC (H-ARM-HT1H COLLECTOR).** `beatvegas/ht_paper.py` logs the arm from every
  decision build, in its own savepoint after the weather arms (`scripts/build_card.py`).
  - **Rule:** the consensus full-game total is the median of each counted book's newest centred
    `full_game_total` quote at or before the build, on the judge's books (`consensus.EXCLUDED_BOOKS`)
    and at least `consensus.MIN_BOOKS`. At 60.0 or more, a game gets a paper first-half UNDER at
    Hard Rock's centred main line and under price, once per game, inside the paper window.
  - **Cost:** it reads only the snapshots on file, with no model and no network call, so it adds
    nothing to the card's clock.
  - **Registry:** `protocol.ARMS` slot 8, with `HT_ARM_START` as its clock backstop.
    `protocol_position.py` reads the arm from `ARMS`. The card summary gains its line.

- **2026-10-10 UTC (H-ARM-HT1H REGISTERED, ROADMAP v1.8).** Tate asked whether games with higher
  totals had done better.
  - **The answer:** yes in 2023-25. First-half unders at the real consensus close went 154-110-4
    (58.3%, n 268) where the full-game total was 60 or more (`docs/POST_MORTEM.md`). The pattern
    was found by slicing after the fact, and 2026 is too thin to say.
  - **Tate's calls:**
    - test it forward as a paper arm: first-half UNDERS on every game whose consensus full-game
      total at the build is 60.0 or more, at Hard Rock's price;
    - the consensus uses the judge's books: every centred book except Hard Rock, Fliff and the
      synthetic consensus, at least 3;
    - ledger slot 8, with its clock starting at its first eligible build (it reads no model);
    - the cap on paper arms rises from 7 to 8.
  - **Order:** the row comes before the collector (`beatvegas/ht_paper.py`, its own PR). The
    literature-nulls amendment moves to v1.9.

- **2026-10-10 UTC (H-MODEL-FIX NOT MET; MODEL WORK STOPS).** One `study.yml` dispatch
  (run 38070611660, branch `model/fix-2026-10` at 1e6bce5; `docs/MODEL_FIX.md`).
  - **Result:** with the four fixes, the champion's first-half number was less accurate:
    - Δ|err| +0.163 [+0.025, +0.294] against the +0.10 margin, over 760 games graded at a real
      consensus 1H close;
    - worse in 2025 (8.85 → 9.02) and in 2026 (7.98 → 8.10);
    - more often 6+ points from the close (19 games against 8).
  - **The live champion is level with the close** on those games (8.69 against 8.72).
  - **Disclosed after the run:** the incumbent's 2025 test games saw the 2025 bowls (week-ordered,
    as live trains). The candidate's deficit was larger on the games the bowls could not touch, so
    the flaw does not explain the verdict.
  - **Tate's calls:**
    - model work stops and the live model stays;
    - arms 1-3 start their clocks at the 2026-10-13 card on the 2026-10-11 refit;
    - PR #351 keeps the study re-runnable with every switch off live, and states early stopping as
      `'auto'` (sklearn's default, unchanged);
    - each refit records the trees it grew in `model_runs.metrics`;
    - next comes the 60+ first-half-unders arm, triggered on the judge's books.

- **2026-10-10 UTC (H-MODEL-FIX REGISTERED).** After the 2003+ switch, the champion's number
  tracked a raw early-season scoring projection (week 6: correlation 0.76, was 0.26; Georgia @
  Alabama 34.8 against Hard Rock's 25.5). Four defects were found read-only:
  - every bowl game (836, 2003-25) is filed as week 1, so the week-ordered season-to-date means
    let a bowl result into every later regular-season mean of its own season;
  - pre-2015 seasons lack most richer inputs;
  - sklearn's `early_stopping='auto'` switched on silently above 10,000 rows;
  - early averages carry no shrinkage.

  Tate's calls: fix the model first, then market rules; test the four fixes together against the
  live champion and adopt on a pass; start the arms' clocks as soon as possible (if the fix lands
  after Tuesday's card, the arms restart free before the first Monday read). The row comes before
  the script (`scripts/model_fix_study.py`).

- **2026-10-10 UTC (THE BOARD OPENS TO VISITORS, ROADMAP v1.7).** Tate's friends opened the site
  and saw an empty board. Every pre-kickoff rating read "Rating publishes at kickoff." (the
  2026-10-07 publication rule, `lib/signalGate.ts`), under two build warnings left by the failed
  `sat_am` build.
  - **Tate's calls:**
    - a visitor sees the board and game page as the owner does, ratings before kickoff included,
      in paper wording ("Paper signal", never "Bet one unit");
    - the owner's "bet logged" chip stays his until kickoff;
    - "Florida, 21+" goes on the site banner;
    - the build warnings ("card built Nh ago", "build did not run") are owner-only;
    - ship as soon as CI passes.
  - **Unchanged:** the bet ledger, `/records` and both CSVs keep withholding a game until kickoff.
  - **Code:** `signalGate.gateGame` no longer blanks a game, so `HIDDEN_ACTION`, `hidesSignal` and
    `HomeGame.signalHidden` are gone.
  - **Roadmap:** this is v1.7; the literature-nulls proposal for the 10-12 review becomes v1.8.

- **2026-10-10 UTC (THE SATURDAY CARD TIMED OUT; THE WEATHER CAPTURE IS SCOPED AND CAPPED).** The
  `sat_am` build (`card.yml` run 38049849474, dispatched 11:50Z) was cancelled at the job's 30-minute
  limit with no card written. Its build step ran 18+ minutes; Friday's, the last build before #345,
  took 4 seconds.
  - **Cause:** #345's `wx_paper.capture` fetched an Open-Meteo forecast for every game of the week, all
    divisions (254 games, 245 venue-day calls, each with a 60 s timeout and the four-try retry ladder),
    one after another inside the card's database transaction. The arms' savepoint catches errors, not
    slowness, so the timeout lost the whole build, the other arms' rows included. The run's output was
    still buffered when it was cancelled, so its log showed none of the build step.
  - **Effect:** week 6 has no `sat_am` card; the board and real-money verdicts stayed on Friday's card.
    The two weather arms, whose backstop clock began 2026-10-10 00:00Z, logged nothing for week 6, and
    first-log-wins means nothing is backfilled. Arms 1-3 had logged the week's games at Friday's build.
  - **Fix (#348, Tate's choice of four):**
    - the capture fetches only the games either weather arm can log (`wx_paper.arm_game_ids`: the
      card's Hard Rock first-half items plus the week's Hard Rock full-game totals; 57 games and 55
      calls in week 6), earliest kickoff first;
    - each call is capped at 10 s and 2 tries, the whole capture at 180 s; a game past the cap
      counts as failed, and the card summary names it;
    - a timing line goes to stderr unbuffered, and `card.yml` sets `PYTHONUNBUFFERED=1`.
  - **Docs:** the registry rows H-ARM-WX1H / H-ARM-WXFG and `docs/PROTOCOL_2026.md` carry a dated
    implementation note (Tate's call); which games qualify is unchanged.
  - **Measured from this Mac** against the live API on week 6's 45 remaining priced games: 44 calls in
    30 s, none failed. Tuesday's `tue_pm` build is the first production proof; a manual dispatch runs
    `--no-paper` and skips the capture.
  - **Open (Tate's call):** whether the weather arms' lost first Saturday needs a protocol note.

## 2026-10-06

- **2026-10-09 UTC (H-WX-HIST / H-JUDGE FIRST RUNS READ NO LINE VALUE: A MARKET-NAME BUG).** `study.yml`
  runs 37996581552 (weather) and 37996591672 (judge) at `59c0037` completed, but every line-value
  reading was excluded (`outside_table`; 3,804 first-half bets in the judge check, every weather cell):
  `early_close.records` passed the WAGER market ('1H') where the judge's half-point table is keyed by
  the SNAPSHOT market ('1H_total'). No line-value number was produced, so none was seen. The weather
  look's record against the close does not use the table and ran correctly: first half windy 90-95-2
  (48.6%, Wilson 41.5-55.8%, p 0.862), calm 517-511-23 (50.3%); full game windy 94-92-4 (50.5%), calm
  522-523-13. The fix passes the snapshot market, both reports now count exclusions by reason, and
  `tests/test_early_close.py` runs one game through the real table. The re-run repeats the close
  records identically and adds the line-value half.

- **2026-10-09 UTC (THE WEATHER ARMS, ROADMAP v1.6).** Strategic review topic 3: Tate asked for the correct
  weather test instead of a verdict. The legacy weather inputs left the model as a leak (#344); weather as
  an edge now runs as its own tests.
  - **Two forward paper arms under p1.1**, ledger slots 6 and 7 (4-5 stay reserved for derivative
    consistency and stale lines): H-ARM-WX1H (first-half unders) and H-ARM-WXFG (full-game unders) on
    every outdoor game whose newest build-time forecast has a sustained kickoff-hour wind of 10+ mph, at
    Hard Rock's price, uncapped, no model read. `beatvegas/wx_paper.py`; the build fetches forecasts into
    the new `build_forecasts` table (Open-Meteo forecast API, `icon_seamless`), kept out of
    `weather_obs` because that table's backfill deletes and rewrites rows by lead.
  - **Sizing (counts only, no outcomes):** about 95 priced outdoor games a season had a 10+ mph forecast
    72 h out in 2024-25, about 6 a week; 186 of them have both a 48-hour first-half line and a close (the
    history look's universe).
  - **Correction recorded:** only R09 (1H gust × style) was a weather null; R06 was rejected on blast
    radius, not signal.
  - Also on 2026-10-09: the 2023-25 pace re-pull (enrich_tempo run 37992138665) rewrote every row as of
    the Sunday before its week (6,310 rows, all Sunday-dated).

- **2026-10-09 UTC (TWO EXPLORATORY LOOKS REGISTERED: H-WX-HIST, H-JUDGE).** Strategic review topic 3,
  Tate's calls. Rows first, scripts in the same PR, each read once through `study.yml` after merge.
  - **H-WX-HIST** (`scripts/weather_history_look.py`): 2024-25 outdoor FBS games, the decision-safe
    72-hour forecast, windy at 10+ mph against calm. Line value of the under at the early consensus
    line against the close (first half), and the under's record against the closing line (both
    markets), plus wind bands.
  - **H-JUDGE** (`scripts/judge_check.py`): does `ev_cons` predict returns? Both sides of every
    2023-25 first-half game at the early line, -110: predicted EV beside realized units, by quintile,
    and the slope of realized on predicted, with week-resampled intervals.
  - Both read spent 2023-25 data, so both are exploratory; the shared frame is
    `beatvegas/backtest/early_close.py` (bowls keyed apart from week 1).

- **2026-10-09 UTC (THE LEAK-FIXED MODEL).** Strategic review topic 3, Tate's calls. The model under
  the arms had information from after the game in its training rows; each fix below is pinned by
  `tests/test_trophy_games.py`.
  - **Pace:** the 2023-25 `team_tempo` rows were pulled as of each week's median kickoff date
    (2025's rows are dated the Saturday of the game week), so midweek teams carried their own game.
    `backfill_enrichment.py` now reads the Sunday before the week's first regular-season kickoff
    (Eastern), as `sunday.yml` does live; `enrich_tempo.yml` re-pulls 2023-25 after merge.
  - **Weather:** `wx_temp`, `wx_wind`, `wx_precip` leave `BV_FEATURE_COLS`
    (`features.LEAKY_WEATHER_COLS`): kickoff observations on the old clock for 2023-25 only, while
    live reads a six-day forecast. `wx_dome` stays. Weather as an edge gets its own tests
    (history look, Salaga, two forward arms at 10+ mph; registry rows follow).
  - **Rivalry:** "met in 8+ distinct seasons across the dataset" counted future meetings; it is
    now the named trophy games, frozen from Wikipedia revision 1379225783 into
    `data/trophy_games.json` (112 FBS pairs; `scripts/build_trophy_games.py`). Counting only
    earlier meetings would have flagged nothing before 2011, since games start in 2003.
  - **Conference:** read from each game's own conference fields (realignment honoured: Texas Big
    12 through 2023, SEC from 2024; none missing on 17,632 FBS-vs-FBS games); two independents
    no longer count as a conference game.
  - **Kept, Tate's call:** same-season talent and roster experience, returning production,
    prior-season PPA/success (their risk is CFBD revising numbers, not after-game information).
  - 58 → 55 model inputs. Sunday's refit trains the leak-fixed model; the first card on it starts
    the arms' clocks (`protocol.ARMS_START` + `cards.id`, a follow-up PR).

- **2026-10-09 UTC (STRATEGIC REVIEW; ARMS PAUSED, PROTOCOL p1.1, ROADMAP v1.5).** Tate opened an
  evidence-first review of the whole project (one topic at a time; its record lands as one docs PR
  when the review ends).
  - **Topic 1 (goals):** proof is the goal, at small stakes on Hard Rock only (bankroll under $1K);
    proof = an arm passes its line-value test, then 2027 real tickets; two seasons fine; the
    personal ledger stays; the stop rule is set in January.
  - **Topic 2 (the odds):** every pick with a closing reading averages about −5% EV against the
    consensus close (real n 9, paper n 27, overs n 27): the vig and nothing else. Tate's and my
    estimate: about 1 in 10 that a strategy earns the proof by the end of 2027.
  - **Topic 3 (the test):** the protocol is sound; +3% is the smallest edge it can find in one
    season. Verified: CFBD files bowls as week 1, so the bowl season would enter as one week; one
    ungradable pick freezes its week. **Tate's calls:** fix the model's training leaks now (pace,
    weather, same-season roster and talent, rivalry and conference flags; inputs with no clean
    history come back to him one by one) and **pause the three arms' clocks before any completed
    week**: they start at the first card on the leak-fixed model. A restart before any read is
    free; after one it spends the slot. Bookkeeping fixes and four side readings queued as PRs.
  - **This PR:** `protocol.ARMS_START = None` (paused), `PROTOCOL_VERSION = "p1.1"`,
    `protocol_position` reads PAUSED with the logged count; `PROTOCOL_2026.md`, the three
    `H-ARM-*` rows and `H-PROGRAM-2026` amended; roadmap v1.5. The literature-ledger question
    deferred to Monday is renumbered v1.6.

- **2026-10-09 UTC (WEATHER PROMOTE REFUSED; INVERTED GUSTS NOW BLANKED).** Run 37833098273's
  fetch hit its 350-minute cap at 01:26Z. Its staging file was saved (1.06 MiB): 4,610 of
  10,097 planned ERA5 games (2013 to mid-2019) and every CFBD season.
  - **The refusal:** the promote's `--check` refused all 37,577 rows. 37 ERA5 hours had a gust
    more than 0.5 mph below the wind (median 1.2, max 8.1). There were no out-of-range values,
    and ERA5 vs CFBD agreed to 2.0 °F, 7.0% humidity and 2.8 mph wind. `weather_actuals` holds
    nothing yet.
  - **Tate's call:** blank those gusts (`null_inverted_gusts`) and promote the rest. The real
    staging file now passes `--check` with 37 gusts blanked.
  - **The fetch:** resumed fetch-only (run 37870394348, `promote=false`).
  - **Deferred:** the roadmap ledger edit for the three literature nulls goes to Monday's review
    (v1.5, Tate).

- **2026-10-09 UTC (THREE LITERATURE LOOKS: ALL NOT MET).** One `study.yml` dispatch each, at
  `4345320`, judged on the median CFBD close. `docs/LITERATURE.md` "Results" has the tables.
  - **H-LIT-ARSCOTT** (run 37863814444): 113-106-3, 51.6%, p 0.618.
  - **H-LIT-TV** (run 37864047692): 1249-1136-30, 52.4%, p 0.513.
  - **H-LIT-BENNETT** (run 37864196666): 28-32-1, 46.7%, p 0.845.
  - **Holm (m = 6):** every adjusted p is 1.000. The verdicts are final: a raw p above 5% cannot
    pass at any Holm step, whatever Coleman, Cox and Salaga show.
  - **No paper arm is licensed.** The rows are `tested-null`, and a second run is refused (exit
    2).
  - **Descriptive only:** the 1.75 Arscott cut (32-20-1, n 52) and Bennett faded-away (11-4-1)
    were never tests. They are not candidates without their own row.
  - **Not changed:** the roadmap's hypothesis ledger still lists the six looks under NEEDS MORE
    EVIDENCE. Moving three to REJECTED is a versioned amendment, so it is Tate's call.

- **2026-10-08 (THE LITERATURE LOOK SCRIPT).** `scripts/literature_look.py` +
  `beatvegas/backtest/literature.py` run H-LIT-ARSCOTT, H-LIT-TV and H-LIT-BENNETT, one
  `study.yml` dispatch each, on CFBD data only (`/games`, `/lines`, `/games/media`,
  `/rankings`; the two new client calls are `game_media` and `rankings`). It refuses a row that
  is not runnable, quotes the criterion verbatim, and `--holm` builds the family table (m = 6).
  - **Tate's call:** Bennett's first game is the first game PLAYED; a cancelled or postponed
    opener is skipped.
  - **Probe before the code (about 20 CFBD calls):**
    - CFBD's providers change by era. 2013-16 has `consensus` (spread, no total) beside
      `teamrankings` and `numberfire`, two near-identical feeds. Books arrive in 2018, and they
      agree tightly from then on.
    - No look reads a 2013-16 spread. TV's 2013-16 totals come from those two feeds.
    - `/games` returns FCS openers.
    - The final AP poll is one postseason release, and its first 10 places can include a tie.

- **2026-10-08 (THREE LITERATURE LOOKS PRE-REGISTERED: H-LIT-ARSCOTT, H-LIT-TV, H-LIT-BENNETT).**
  Roadmap step 5, part two. Three of the six v1.3 looks are now rows in `docs/HYPOTHESES.md`;
  no script exists yet. Tate's calls:
  - **The line:** each game's median close across CFBD's providers, re-fetched by the script.
    The provider stored in `games` changes by era (TeamRankings 2013-16, consensus 2017-22, one
    book 2023-25).
  - **The test:** one-sided exact binomial against 52.38%, pushes dropped. Holm at 5% with
    m = 6 fixed; a look not yet run counts as p = 1. Each look runs once its script merges.
  - **Scope:** regular season only.
  - **Arscott:** the working paper's formula and σ; spread-0 games are excluded.
  - **National TV:** any TV outlet that is exactly ABC, CBS, NBC, FOX or ESPN qualifies.
  - **Bennett:** first games of 2018-2025, since the paper's 2008-2016 may name first-game
    seasons; the team's literal first game; a game between two prior top-10 teams is dropped.
  - Coleman (full text), Cox (which rules) and Salaga (the weather backfill) still wait.

- **2026-10-08 (WEEKNIGHT CLOSES CONFIRMED).** The first Thursday ticks (shipped 2026-10-06) closed every
  Thursday game inside its windows: 4 of 4 with first-half closes (2 h) and full-game total,
  spread and moneyline closes (3 h). The first spread and moneyline capture (thu_pm refresh,
  9 credits): 1,241 spread rows and 1,187 moneyline rows from 24 books on 56 games.

- **2026-10-08 (THE FIRST ARMS REGISTER: H-ARM-1HU, H-ARM-1HO, H-ARM-FGU).** Roadmap step 6, Tate's calls.
  - **The rows:** three pre-registered rows under protocol p1, ledger slots 1-3 at 0.5% each
    (7 of 10 remain). The rows were committed before any collector.
  - **Arm 1** (first-half unders) counts every qualifier at the per-slate bar, uncapped and whatever
    the money-path flags. Its paper picks carry the new `manual_picks.arm`.
  - **Arm 2** (first-half overs) is the bottom-20% mirror with the gap below zero, logged by the new
    `beatvegas/arm_paper.py`.
  - **Arm 3** (full-game unders) is H-FG-P's rule without its cap, plus gap above zero.
  - **Clocks:** they start at the fri_pm build of 2026-10-09.
  - **Retired:** H-NEGGAP-P and H-FG-P.
  - **Exclusions:** an unpriced paper pick is now excluded as `no_price`.
  - **Monday read:** `scripts/protocol_position.py`, through `study.yml`.

- **2026-10-08 (REAL MONEY RESUMES AS A PERSONAL LEDGER; ROADMAP v1.4).** Tate kept the 7 paper
  arms as planned and resumed real-money first-half unders beside them.
  - **What is bet:** the old rule (BET at the per-slate bar, the top 5 a week by gap, every
    money-path check), $10 flat.
  - **Never evidence:** the protocol reads only an arm's own paper picks, so no real ticket is an
    observation, and every real bet has its paper twin.
  - **No stop rule**, to season end. A promotion's $10 live validation stays a separate track.
  - **The switch:** `rule_paused` set off at 20:00 UTC (it had been on since 2026-10-07 21:40 UTC).
    Tickets 102 and 103 hold 2 of week 6's 5 slots.
  - **The site:**
    - The banner names both tracks.
    - Signed in, a BET inside the cap reads "Bet one unit", past it "Paper signal" (the cap now
      also counts tickets on games that kicked off, mirroring `card.py`'s `prior_bet_game_ids`).
    - The answer bar reads "U of 5 bets placed — L left this week".
    - A visitor never sees bet wording (`signalGate.gateGame`).
    - Results shows line value vs the consensus close (`ev_cons`) per ticket.
  - **The card build:** `card.py`'s BET sentence is "Bet one unit" again.

- **2026-10-08 (OBSERVED WEATHER FOR THE HISTORY LOOKS: `weather_actuals`).** Roadmap v1.3's
  Salaga look needs 2016-2025 observed weather; we held 2023+.
  - **Tate's calls:**
    - ERA5 (Open-Meteo archive, `models=era5`) as the data, with CFBD's `/games/weather` beside
      it as a cross-check.
    - Every played FBS-vs-FBS game 2013-2026.
    - A new study-only table.
  - **What it stores:** ERA5 is one row per hour from one hour before the kickoff hour to four
    after; CFBD is one reading per game.
  - **Nothing reads it but the look.** `tests/test_weather_actuals.py` pins that, so the
    champion (`weather`) and the frozen studies (`weather_obs`) cannot move.
  - **Running it:** `weather_actuals.yml` stages, checks and promotes, and resumes across the two
    UTC days a full ERA5 pass needs.
  - **Checked:** the CFBD Starter Pack has no weather at all; CFBD's endpoint covered 60 of 60 and
    54 of 54 probed games; one live ERA5 call returned every variable for a 2016 game.
  - **First dispatch (run 37780538551):** CFBD staged 9,917 of 10,097 games. ERA5 was refused by
    the coordinate guard on two real Sydney venues: ANZ Stadium (2016 Hawai'i vs California) and
    Allianz Stadium (2017 Rice vs Stanford). Tate's call: allow-list both at their published
    coordinates (`etl/venues.py::VERIFIED_VENUES`, ±0.01°); the guard stays strict for every other
    venue.
  - **Second dispatch (37782514919):** about 2.6 games a minute (Open-Meteo throttles GitHub's
    shared runner addresses per request). It reached the 350-minute limit with 859 games staged
    (925 done keys) and an empty log, because Python buffered its prints.
  - **Tate's call:** fetch one call per venue-season (about 1,700 requests for the range) and set
    `PYTHONUNBUFFERED`. #331 had already made a cut-off run resumable.
  - **The queue:** the run held `neon-writers` from 13:12 to 19:02Z, and the 16:00Z grade backup
    waited 90 minutes behind it. Tate's call: split the workflow into plan / fetch / promote, with
    only plan and promote in the queue; the fetch job holds no `DATABASE_URL`.
    - `test_every_neon_writer_shares_the_concurrency_group` now checks every job that can reach
      Neon, whether it joins the queue at workflow or job level.

- **2026-10-08 (THE LITERATURE, VERIFIED; ROADMAP v1.3).** Roadmap step 5, part one: a six-lane
  research run checked every paper the deep-research report cited (`docs/LITERATURE.md`; lanes and
  sources in the gitignored `research/swarm/2026-10-08-literature-step5/`).
  - **The papers:** all 11 exist, but the report misdescribes most of them.
    - Arscott bets full-game OVERS at the close (1996-2017, 56% on 691, p 0.08), not team totals.
    - Coleman's effect is the home favourite against a visitor that came one zone EAST (2004-2011,
      ~55%).
    - Cox's only 5% result is a streak favourite.
    - Bennett is 2008-2016, n 83.
    - Salaga & Howley is a real college weather study (2012-2015, observed weather).
  - **Tate's calls:** six history looks, one look each on the post-sample years, Holm at 5% outside
    the K = 10 ledger.
    - National TV = ABC, CBS, NBC, FOX, ESPN (not ESPN2).
    - Rivalry = trophy games.
    - Coleman's cutoff comes from his full text.
    - Salaga waits for a 2016-22 weather backfill.
    - Team totals and full-game weather are added as tracked candidates (amendment v1.3).
  - **Doc corrections:** `DATA_STACK_REVIEW` called Arscott "team totals"; `EXTERNAL_REVIEW`'s
    source list now has full citations.

- **2026-10-07 (CAPTURE: FULL-GAME SPREADS + MONEYLINES).** Roadmap step 4, part one, Tate's calls
  on the credit math (plan `~/.claude/plans/pasted-content-id-3a47-session-handoff-shiny-bunny.md`).
  - **What gets captured:** every Odds API full-game pull (Sunday opener, card-day refresh, every
    Saturday and weeknight close tick) asks for `totals,spreads,h2h` on `us,us2,us_ex`, 9 credits
    for the whole slate.
  - **New rows:** each book's spread and moneyline are written as their own `odds_snapshots` rows
    (`full_game_spread`: line = the home point; `full_game_ml`: line NULL) with the new
    `home_price` / `away_price` columns.
  - **What stays unchanged:** the `full_game_total` rows keep their own `spread` column, so every
    existing reader is unchanged; each reader filters on `market` (checked reader by reader).
  - **Change detection:** a price move on either side writes a new row, and a standing quote
    stamps `last_seen_at` so it can grade as the close.
  - **Credits:** +200 a week, +860 a month, about 3,300 a month of 20K in all. The weeknight tick
    count is an estimate; the pull now prints `credits: ... spent= remaining=`.
  - **Not done here:** no site display (capture only). The judge still grades totals only; a
    spread needs a margin table in a later engine version.
  - **Next:** the `H-MKT-PROBE` (5 games, `us,us2`, Saturday 10-10 morning, ≤ 50 credits) is the
    second part.

- **2026-10-07 (THE TEST: STATISTICAL PROTOCOL p1).** Roadmap step 3 (`docs/PROTOCOL_2026.md`,
  `H-PROGRAM-2026`, amendment v1.2), Tate's calls: Wald SPRT per arm on line value at Hard Rock's
  price, H0 0 vs H1 +3% EV, alpha 0.5% (5% / K = 10, never recycled), beta 0.20, spread 0.06 per bet,
  at least 30 readings over 3+ weeks; promote → $10 live validation, the sequential lower bound
  stops an arm as NEEDS MORE EVIDENCE, timeout 200 readings or season end. The first simulation
  showed a shared Saturday move would leak the budget (1–5.5% false promotion), so WEEK-SHOCK was
  registered and run (study.yml 37712076009): the week move is 0.005 (2023–25, 42 weeks, to 0.007)
  and 0.012 (2026, 6 weeks, to 0.020); full game not measurable yet. Tate chose the WEEKLY-average
  design (assume 0.02): no-edge false promotion ≤ 0.08% everywhere measured; a real +3% edge found
  57% (8 bets/wk) to 80% (15/wk) of the time this season; a −5% arm stops in 3–4 weeks. Shadow
  engines left the alpha budget (exploratory). "Two seasons" = the unchanged rule passes again in 2027.

- **2026-10-07 (THE JUDGE: CONSENSUS ENGINE cv1).** Roadmap step 2, specified by Tate (amendment
  v1.1, `docs/CONSENSUS.md`): EV per unit of each wager at its own line and price against the median
  de-vigged close of every centred book except Hard Rock and Fliff, books within 1.5 points, closes
  confirmed inside 2 hours, at least 3 books. Lines are converted through a frozen half-point table
  (`data/halfpoint_hp1.json`, 2013–25 FBS games, built on the runner, study.yml run 37702656840):
  first-half key numbers 24 (8.9%), 31 (7.7%), 34, 27, 28, 21. `picks.grade_pick` writes nine
  `cons_*`/`ev_*` columns on both pick tables; grade.yml back-fills rows graded earlier. Development
  read (CONS-DEV, run 37703161461): the paper and real unders sat at about −5% EV at the close (the
  vig; P(win) ~0.51), EV varies about 4 points per bet, and most rows without a reading are weeks 2–4
  stale closes (0/31, 0/34, 3/16, then 13/15 in week 5). Nothing live changed; the protocol is next.

- **2026-10-07 (1b: THE SITE IS A RESEARCH LAB; THE REAL-MONEY SWITCH IS ON).** The real-money
  switch (`app_settings.rule_paused`) was thrown at 21:40 UTC on Tate's call, written through
  Neon's HTTPS endpoint (campus filters 5432) exactly as `scripts/rule_pause.py` writes it, and read
  back; `/api/health` reports `rulePaused: true`. The site then became the research lab
  (`docs/ROADMAP_2026.md`): a full-width banner under the header on every page (Tate's wording); a
  visitor sees no pre-kickoff signal — `lib/signalGate.ts` strips rating, rank, our number, gap,
  kill line, factor read and the logged chip from the board and game page, blanks our number and
  rank on `/records` and its CSV, and withholds pre-kickoff rows from the Results ledger and
  `/api/bets`; hidden rows lose their order too (a day sorts by kickoff, not score). The owner
  sees everything. "Bet one unit" became "Paper signal" in the action sentence and its mirrors
  (`edge.ts`, `card.py`, the e2e fixture); the board's old pause box folded into the banner.

- **2026-10-07 (THE RESET: ROADMAP 2026 v1; REAL MONEY PAUSED).** Tate reset the project after a
  ground-up review and twelve rounds of questions plus an outside critique (plan file
  `~/.claude/plans/pasted-content-id-83e1-session-handoff-optimized-lampson.md`): Beat Vegas is a
  potential business that follows the evidence to the market with the most defensible edge, not a
  1H-unders system; 2026 is the research year. `docs/ROADMAP_2026.md` v1 governs from here, changed
  only by versioned amendment. Real money paused until a strategy passes a pre-registered sequential
  test on EV at the wager's exact terms against the median-of-books de-vigged close (≤2 h), built
  for +3% EV inside a 5% family-wise budget held as a fixed ledger (K = 10, 0.5% each, never
  recycled); promotion → $10 flat live validation; up to 7 uncapped paper arms; every confirmatory
  clock starts after the Statistical Protocol is registered and simulated. H-STOP-2 closed
  inconclusive (profit n=10, LLR −0.26; line value n=9, LLR +0.73; tickets 102 and 103, placed
  2026-10-06, grade but feed no clock). H-NEGGAP-P, H-FG-P, H-PCT-TIE, H-TIMING, H-CLOSE-W
  superseded (their rows are development evidence); H-MARGIN closed, the Pick'em dropped. Option 2's
  program budget is replaced for the betting arms; the shadow engines' 1.67% shares stay until the
  protocol decides. `docs/BETTING_POLICY.md` gains the pause; the brief is rewritten once around
  the roadmap with Tate's mission line. Nothing in code changed; the site work is the next PR (1b).

- **2026-10-07 (CFBD STARTER PACK WALKTHROUGH + BRIEF REFRESH).** All 14 notebooks of the licensed
  Starter Pack (2026 preseason edition, gitignored at `research/cfbd_pack/`) run as shipped with
  Tate, in its own venv; notes in `docs/CFBD_PACK.md`. Five defects found and checked on scratchpad
  copies (00's explosiveness definition, 05 predicts a home win for every game, 07's home-oriented
  field position and 116 impossible drive totals, 04's within-four radar scaling, 10's
  mis-specified least squares — harmless on 2025). Findings: the pack's PPA is on the pre-September
  scale; on 2025, weeks 1-7 first-half scoring correlates 0.14 with week 8+ first-half totals and
  ridge opponent adjustment adds nothing (a prior for H-RIDGE-F); explosiveness is nearly
  independent of EPA and success. Proposed, not registered: H-BOOM-R, H-FHDRIVE. Open: whether the
  pack may ever feed the engine (licence). Nothing in the system changed.

- **2026-10-07 (H-MARGIN RUN: THE MARKET IS CLEARLY CLOSER).** `bv_margin_v1` (the champion's 58
  market-blind inputs, target home minus away, 2003+) against the Vegas closing spread, one run
  (study.yml 37670166376, frame `23cb43a0a69c29aa`): MAE 13.16 vs 11.76 over 1,058 games of 2025 and
  2026 (+1.40, 95% +1.04 to +1.77; both seasons alone exclude zero), straight-up 71.6% vs 74.9%, ATS
  49.1%. Exploratory, licenses nothing; the Pick'em entry stands (Tate). `docs/MARGIN.md`.

- **2026-10-07 (H-MARGIN REGISTERED, BEFORE ANY SCRIPT).** For the CFBD Model Pick'em (Tate: enter
  it), which scores full-game margins the system never had: a market-blind margin regressor on the
  champion's inputs, 2003+, every FBS-vs-FBS game, `bv_margin_v1` (never a champion read). Tate's
  calls: exploratory measurement that licenses nothing, and entry does not depend on the backtest;
  the report states MAE / MSE / straight-up / ATS beside the Vegas closing spread. Submission by API
  once Tate creates the Pick'em account and credential.

- **2026-10-07 (SITE: RESPONSIBLE-GAMBLING FOOTER + PUBLIC MODEL ACCURACY).** Tate's product calls
  (`docs/program/PRODUCT_OPTIONS.md`, Option A): the footer on every page now reads "This site
  rates bets. It never places one. Not betting advice. 21+, Florida, Hard Rock Bet. Past results do
  not predict future results. Gambling problem? 1-833-PLAYWISE." How it works' "What we don't know"
  shows, in public, our number's and Hard Rock's average first-half miss over this season's graded
  games, the same games for both (`lib/postmortem.ts::loadModelAccuracy`, newest live post-mortem
  run; season to date at merge: 8.34 vs 8.22 over 213 games), and its sentence follows the numbers.
  Each game counts at the number published that week, across model changes. The helpline is
  Florida's 1-833-PLAYWISE everywhere (How it works had the national 1-800-GAMBLER; Tate's call).

- **2026-10-07 (PROGRAM BUDGET: OPTION 2).** Tate's call (`docs/program/FP_BUDGET_OPTIONS.md`): the
  rows whose pass unlocks a promotion share one 5% budget, 1.67% each: H-PCT-TIE (now 0.417%
  per arm-clock, A = 5.257, B = −1.605), H-SHADOW-F and H-INSEASON-T (their per-comparison split
  written in their engine PRs before they log). All three were amended before any observation;
  none has a collector or engine yet. H-NEGGAP-P, H-FG-P and H6 keep 5% each as findings that
  license nothing; H-STOP-2, H-TIMING and H-CLOSE-W stay outside. `docs/HYPOTHESES.md` gains a
  "Program budget" list that `tests/test_hypotheses_registry.py` reads.

- **2026-10-07 (TWO DECISION MEMOS).** `docs/program/FP_BUDGET_OPTIONS.md`: three ways to split the
  program-wide false-positive budget Tate approved on 2026-10-06 (one 10% cap; tighten only rows
  whose pass unlocks a promotion; keep 5% each and require a repeat), with each row's threshold
  and expected picks to a pass. `docs/program/PRODUCT_OPTIONS.md`: site only, site + free Sunday
  email, or that plus a written 2027 paid-tier gate, built from the teardown, legal memo and
  knowledge base on file. Nothing decided; each choice lands as its own PR.

- **2026-10-07 (OM: THE OFF-MARKET GATE IS RETIRED).** Tate's call on `ASSUMPTIONS` row 8: the
  "Hard Rock more than 0.5 pts below the market → WATCH" gate is gone from `card.py::is_bet`,
  `verdict.ts`, `edge.ts` and `pickRules.serverVerdict` (and the e2e fixture's port; fixture game
  900004 now reads `no_fair_price`). It never blocked a game alone live (`GATES.md`, H4G). The
  gate he set first: retiring it must not change the paper ledger H-STOP-2 reads. It cannot, by
  construction — `qualifies` is `in_band` alone — and a test now pins that; Neon showed 8 paper
  picks tagged `off_market` (weeks 2-4), none since the clock started in week 5. Those rows keep
  their tag and their label. `HR_OFF_MARKET_PTS` stays in `score.py` for the post-mortem's
  `hr_vs_market` bands and the GATES study only; `tests/test_gate_parity.py` guards that no gate
  reads it on either side.

- **2026-10-07 (PR A: TATE'S 29 ASSUMPTION VERDICTS; H-CLOSE-W; 295 NOT 296).** `docs/ASSUMPTIONS.md`
  v2 carries Tate's verdict on every row (Q&A that day): keep all but two; **retire** the
  off-market blocker (its own gated PR, OM); **test** the 2 h close window as H-CLOSE-W, a
  pre-registered sensitivity read with Tate's criterion verbatim (`docs/HYPOTHESES.md`). Stale
  H-TOP3 / H-SHARE references fixed (both withdrawn in #301). The gap ≥ 1.75 real-close cohort
  read 295 in `RANKING_AND_TRUST` and 296 in `POST_MORTEM`: the post-mortem doc was the 09-07
  snapshot from a run no longer stored, and the three stored runs since all give 295
  (165-127-3, +23.00u). Tate's call: regenerate it (`study.yml` gained `post_mortem`, dry-run
  only, read-only; run 37636301161) and freeze the 295 game ids
  (`tests/fixtures/gap175_real_cohort_2023_25.json`) with a docs-parity test on both docs. The
  regenerated doc grades 3,596 historical games (3,601 on 09-07); "followed the system" is
  unchanged (169, 101-65-3P).

- **2026-10-07 (M2: LIVE FRESHNESS + REFRESH PRICE).** The live price check accepted any pre-kickoff
  Hard Rock snapshot, so a Tuesday quote passed on Saturday. Tate's calls: a live real BET needs the
  quote SEEN within `HR_PRICE_MAX_AGE_H` (6 h) of now (max(captured_at, last_seen_at), the M1B
  reading), refused as `PRICE STALE`; the form then offers **Refresh price** → authed
  `POST /api/price-refresh` → `lines_watch.yml market=1h_game` → `poll_lines.py --game-id`
  (one event, 1 credit, `--max-credits-per-run 2`). Nothing was ported to TypeScript and
  `ODDS_API_KEY` stays off Vercel. The route refuses an unknown or kicked-off game, a price already
  fresh, a credit gauge under 300, and a second request within 10 min (claimed atomically in
  `app_settings` `price_refresh_<gameId>`, released if the dispatch fails). Tate confirms the
  dispatch token's scope (`OPS_ACCOUNTS.md` item 3).

- **2026-10-07 (M1B: BACKDATED INTEGRITY).** A ticket logged more than 30 min after it was written
  used to skip the price check entirely (the card's kill price, or none when the card did not rate
  it BET; typing a bet time 31 min back was enough). Tate's calls (ASSUMPTIONS row 18): the
  evaluator's `as_of_bet_time` mode now reads the market as it stood at the bet time
  (`getLineCheck(season, "1h", undefined, asOf)`: snapshots captured at or before it), recomputes
  the kill price from it, refuses when Hard Rock's quote was last SEEN more than
  `HR_PRICE_MAX_AGE_H` = 6 h before the bet, and refuses a new late log the card in force did not
  rate BET (`NOT A BET THEN`). "Seen" is max(captured_at, last_seen_at): an unchanged poll writes no
  row and only stamps `last_seen_at` on the newest one, so a later sighting proves the quote was in
  force at the bet. An edit keeps its frozen verdict, so the price check also closes M1A's no-card
  gap for PATCH.

- **2026-10-07 (M1A: TICKET AND PAPER-STREAM INTEGRITY).** The system review found PATCH re-checked
  nothing: a ticket logged at a passing price could be edited to a worse one, cleared to no price,
  restaked, or flipped to a bonus bet (freeing a cap slot, booking a loss as 0); paper rows could be
  edited or deleted before kickoff; and a hand-logged paper pick (site, API or `pick.py add`) took a
  game's one slot on H-STOP-2's ledger before the build reached it. Tate's calls (ASSUMPTIONS rows
  15, 16, 19, 29): one evaluator for POST and PATCH (`web/lib/ticketPolicy.ts`, mode passed in
  explicitly); a changed price is re-judged at the time the ticket was written against its frozen
  verdict; an omitted price keeps the stored one and an explicit null is refused; the bonus flag
  moved onto the log form and is not editable; paper is build-only (`PAPER IS BUILD-ONLY`,
  `PAPER IS FROZEN`, `pick.py add` removed). Neon check that day: all 76 paper picks for 2026
  carry a `blocker`, so no hand-logged paper was ever written. The 10u edit cap stays (row 14).
  Backdated pricing (M1B) and the 6 h live-price limit (M2) follow as their own PRs.

- **2026-10-07 (LIVE SWITCH: CHAMPION TRAINS ON 2003+).** Tate's calls after H-HIST: switch now,
  start year 2003 (all three floors tied on accuracy; the tie-break did not look at betting
  records), keep H-STOP-2 running with before/after reporting, move the full-game shadow too.
  `score.CHAMPION_TRAIN_MIN_SEASON = 2003`, read by `weekly_update.py` and `fg_shadow.py` only;
  `features.CFBD_TOTALS_FROM = 2013` keeps the unpriced seasons as training rows while every
  scored row still needs a total (`rows_to_keep`); `score_slate` fits with `drop_all_nan=True`
  (a no-op on 2023+); the factor-board anchors and the serve-skew guard stay on 2023+. Every
  other frame (grading, factor ledger, research tools) stays at `FRAME_MIN_SEASON` 2023. Week 6
  re-scored the same night (`rescore.yml`), then the FG shadow.

- **2026-10-07 (H-HIST MET; H-ELO-F NULL).** One look each. H-HIST (run 37567344521): all three
  longer windows beat the 2023+ champion on accuracy by ~0.42 pts a game (Holm p 0.002 each),
  pooled MAE 9.17 → 8.74 / 8.75 / 8.76 against the consensus close's 8.73; units not worse
  (intervals span zero). H-ELO-F (run 37566955440): Δ|err| −0.019 [−0.087, +0.050], not met.
  Nothing live changed; raising `FRAME_MIN_SEASON` is Tate's call in its own PR.

- **2026-10-07 (H-HIST FIRST DISPATCH CRASHED BEFORE ANY NUMBER).** `study.yml` run 37566306294
  built the 2003-2026 study frame (17,447 rows) and crashed in the first fit: HGB refuses an
  all-NaN column, and a fold trained on 2003 alone has no talent input (the known HGB gotcha).
  Nothing was computed or read. Fix: `fit_bv_regressor(drop_all_nan=True)` for the history arms
  only (an all-empty column offers no split, so it is the same model); the incumbent keeps the
  live path. Noted in the H-HIST row before the re-dispatch; not a look.

- **2026-10-06 (H-HIST / H-ELO-F MACHINERY — PR H4).** `build_feature_frame(require_total=False)`
  keeps rows without a full-game total for the STUDY frame only (proxy line NaN instead of
  raising); the frame now carries `home_pregame_elo` / `away_pregame_elo` (never in
  FEATURE_COLS). `bv_line_for_slate(feature_cols=...)` lets a study arm add inputs (default =
  the champion's, byte-identical, tested). Arms: `model/train_windows.py` (`hist_2003`,
  `hist_2010`, `hist_2015`, and `champion_2023`, the incumbent as live trains it) and
  `model/elo_line.py` (`elo_2023`). `harness_report --frame-min-season all
  --keep-rows-without-total` lowers the study frame and pins the incumbent to 2023+;
  `HarnessSpec` records both knobs; every report now carries per-season frame coverage (rows,
  rows without a total, NaN shares, Elo coverage). Criteria `backtest/history_f.py` reuse the
  H-WEPA-F per-arm test. One dispatch per row follows the merge.

- **2026-10-06 (THE FIVE CODE-LESS ARMS, Tate's calls).** H-TOP3, H-MOVE and H-SHARE withdrawn
  before any observation (`superseded`, reasons in each row: no power at this volume; a test
  window already read; a gate judged only on spent 2023-25 data). H-PCT-TIE kept and folded: it
  is the margin-above-the-bar ranking test Tate approved after the review. H-TIMING kept as a
  no-bet measurement. Collectors for the two kept rows are later PRs.
- **2026-10-06 (WEEKNIGHT CLOSES).** Two weeks of GitHub weeknight close crons captured nothing
  (all 20 runs fired after kickoff or overnight), so Thursday/Friday games had no 1H close
  inside H-STOP-2's 2 h window and no full-game close inside 3 h. Tate's call: a Vercel
  `close-weeknight` job, Tue–Fri 6pm–midnight ET, hourly (24 entries, 22Z–03Z, both DST
  regimes), the same `lines_watch.yml market=1h_close` dispatch as Saturday (1H per game + the
  full-game bulk call); a tick with no Hard Rock game in the next 120 min stops at the free
  `/events` pre-check. GitHub's crons stay as backup. The id is short because
  `last_dispatch_<id>` must fit `app_settings.key` (32 chars).
- **2026-10-06 (REVIEW QUICK FIXES, Tate's calls).** The neggap paper arms now run inside a
  savepoint like H-FG-P (a database error in them could have discarded the whole card at commit).
  Doc drift: BETTING_POLICY's score, Watch and kill-number passages and README described the
  retired constant 1.75 bar (now the per-slate bar; the kill price is `BET_MIN_EV`, not "2% of
  vig"); SYSTEM_REVIEW_2026-10-04 §1's "2015-25 regressor" corrected to 2023-25; ASSUMPTIONS
  marks the full-game rows as run. Registry: H-PCT, H-PCT-U, H-STOP-2, H-NEGGAP-P were running
  but read `pre-registered` -> `live-tracking` (they run as clocks, never through the harness;
  the harness smoke-run test now names H-HIST); H-FG-U-R relabelled a **post-hoc positive**
  (row + `FG_MARKET.md`, whose "no verdict" paragraph is marked superseded); the blank line that
  split the full-game table and the `--row <id>` placeholders fixed.

- **2026-10-06 (HISTORY LOADED; H-HIST AMENDED BEFORE ANY LOOK).** `migrate.yml` added the
  Elo columns; the 2003 probe (`history_load.yml` run 37561721141) stored 699 FBS games, all with
  a first-half total and pregame Elo, 632 with a known venue, and **0 with a full-game total**:
  CFBD's free `/lines` has no totals before 2013 (2013: 702 of 813). The frame drops rows
  without a total although the regressor never reads it, so the 2003 and 2010 arms would both
  have started at 2013. Tate's call: a STUDY-only exception (`require_total=False`, PR H4); the
  live frame keeps its rule; written into H-HIST before any number was read. 2004-2022 loaded
  (run 37562361195: ~14,000 FBS games, totals from 2013 on). Elo onto 2023-26 (run 37562510742)
  went through the standard loader, which also writes CFBD's consensus full-game total: before,
  2,128 of 2,398 finished 2023-25 FBS games carried a total; after, all of them (source `cfbd`).
  The frame keeps only rows with a total, so the champion's 2023-25 training set grows **2,212
  → 2,343** from the week-7 refit (proved on `fg_shadow` run 37562628469, `model_runs` 7:
  train_window still 2023-2025, train_rows 2,343). Tate's call: keep it as a data repair (those
  games were excluded only for a missing total). Lesson: re-running the loader on a season the
  champion trains on is a training-data change, not a no-op.

- **2026-10-06 (HISTORY LOADER — PR H3).** `games.home_pregame_elo` / `away_pregame_elo`
  (CFBD `/games` pregame Elo; H-ELO-F's inputs, read by no champion code); `backfill.py
  --fbs-only` stores only FBS-vs-FBS games (`data/fbs_teams.json`, refuses a season the list
  lacks); an unknown venue id is stored NULL instead of failing the `venues` FK; the loader
  prints per-season Elo coverage. `history_load.yml` (dispatch-only, `neon-writers`, inputs via
  `env:`) runs it. Tate's calls: load right after merge, probe 2003 first, then 2004-2022, and
  prove the floor in production by re-running `fg_shadow` (its `model_runs.train_window` must
  still read 2023-2025).

- **2026-10-06 (FRAME FLOOR — PR H2, no behaviour change).** Before any 2003-2022 history is
  loaded for H-HIST / H-ELO-F: `features.FRAME_MIN_SEASON = 2023` floors every feature frame's
  games and its situational columns (rest days and the cross-season revenge/rivalry flags would
  otherwise read older games); a study opts out with `build_feature_frame(min_season=None)`.
  The site lists no season before `SITE_MIN_SEASON` (records seasons, the all-season 1H share);
  the e2e fixture now carries a 2005 game and the records spec failed with the floor removed.
  `data/fbs_teams.json` (+ web mirror) extended to 2003-2014 from CFBD `/teams/fbs` (12 calls,
  117-128 teams a season; 2015-26 byte-identical). A past season's `backfill.py` load no longer
  rewrites `teams.conference` (live rows read today's membership).
- **2026-10-06 (H-HIST / H-ELO-F REGISTERED — PR H1).** The system review found the live champion
  trains on 2023-25 only (`model_runs` 5: 2,212 rows) because Neon's `games` begins in 2023;
  earlier docs call it a "2015-25 regressor" from the June demo-DB era. Tate's calls: use every
  season we can, but test first; history from the free CFBD API into Neon (2003+; the Starter
  Pack, bought the same night, stays a local cross-check in gitignored `research/cfbd_pack/`);
  judged on 2025 + 2026 to date; pass = more accurate AND no worse units; the Elo arm on the
  champion's own window. Rows written before any script or load; the champion is pinned at
  2023 (PR H2) before history lands (PR H3); arms + one dispatch each (PR H4).

- **2026-10-06 (H-FG-P COLLECTOR — PR5a #293, PR5b).** Program PR5 in two PRs, both Tate's
  calls. **#293**: an allow-list (`score.CHAMPION_READ_VERSIONS` = `gbm_v1`, `derived_lines`,
  mirrored in `web/lib/model.ts`) at every "the model's line" read (board universe, pick-log
  freeze, `_model_row`, health's Sunday count, the card's frozen vectors). Behaviour unchanged
  (Neon held only those versions); the e2e fixture now carries a newer `bv_fg_v1` row per game
  and the lane failed 31 tests with the TS guards removed. **PR5b**: `scripts/fg_shadow.py`
  (`bv_fg_v1` predictions + a `fg shadow refit` model_runs row, no GameRecords; `sunday.yml`
  continue-on-error after the champion, `fg_shadow.yml` by hand), `beatvegas/fg_paper.py`
  (`FG_COLLECT=1`, the champion's bar-then-cap-5 rule on the full-game gap, held slots, paper
  windows, a savepoint around it), `stopping.FG` + `fg_position` (profit σ 0.913; line-value σ
  `None` until the first two Saturdays, the clock reports "not started"), `fg_position.py` (3 h
  window). Sandbox: the e2e fixture week built with and without the collector gave an identical
  card payload and champion paper picks; +5 `fg_under` rows, +0 on a second build. Week 6 is
  scored by hand so the arm collects from the Thursday 2026-10-08 build.

- **2026-10-06 (HOUSEKEEPING — #289 shipped, alerts, Dependabot, brief).** #289 (the rest of the
  Discord knowledge base) merged `cd9f75d`, deploy READY, health ok. Dependabot alerts 13
  (source-map-js) and 14 (sharp) patched by a lockfile-only PR inside the existing ranges; alert 12
  (braces, dev-only via eslint-config-next, no patched version) dismissed as tolerable risk, Tate's
  call. The three Dependabot PRs merge one at a time (#255 was superseded by #290: SQLAlchemy 2.1.3
  needs Python ≥ 3.11, so only the runner's `requirements/lock.txt` moves; the Mac's 3.9 venv stays
  on 2.0 under `requirements.txt`'s `>=2.0,<3`). The Paramount PDF moved from the repo root to the
  gitignored `research/`. The brief: where-we-are dated 10-06 with the deep program and the week-6
  card; honest status 10-10 (it still read 9-6); program PR5 (H-FG-P collector) and the 10-12
  review added to open items; the PR #247 sandbox item dropped (live builds have run since).
  Tate's calls for PR5: an allow-list of champion prediction versions at every model-line read,
  and week 6 scored by hand so H-FG-P collects from this week's Thursday build.

- **2026-10-06 (DISCORD CAPTURE COMPLETE — `docs/KNOWLEDGE.md`).** Seven public channels of the
  CFBD Discord captured in Tate's own signed-in session in the app's browser pane, one channel at a
  time at reader pace, back to 2025-08-01 or the channel's beginning: data-and-analytics 1,290,
  general 2,750, pick-em 650, projects-and-showcase 550, development 330, cfbfastr-questions 190,
  cfb-chat 19 messages (raw text gitignored under `research/discord/`). Every message read in
  full (two sittings by hand, the rest by research agents); ~120 entries curated into
  `docs/KNOWLEDGE.md` with 12 proposed registry rows (H-FPI-P, H-RIDGE-F, H-ELO-F, H-ERRBAND-P,
  H-SEGVETO-P, H-MKTPRIOR-F, H-PCAL-P, H-DESERVED-F, H-SPSNAP-F, H-SPARSE-F, H-FCS-F, an H-INJ
  data arm) — none registered. Headline: nobody in the CFB data community publishes first-half
  picks, a pre-registered criterion, an interval, a stopping rule or a book-specific close; the
  one other first-half model "barely breaks even"; Bill's own 2024 table shows the most accurate
  models were barely profitable and the most profitable were less accurate than the market. Not
  captured: `help-and-support` (a forum), `announcements` (read 2026-10-05), the patron
  `supporter-lounge` (role never synced). Discord drops the pane's session when the pane closes.

- **2026-10-06 (H-FG-U-R / H-FG-O-R RUN — `docs/FG_MARKET.md`).** One dispatch each on 2024-25
  (1,252 games at a real consensus full-game close inside 3 h). The full-game regressor is less
  accurate than the close (MAE 13.44 vs 12.68). **Overs: NOT MET on every reading** (lower bounds
  46.0% / 43.3%, 2025 units negative) — `tested-null`. **Unders: MET on Tate's ruling** — the row's
  "selected picks" was ambiguous between the qualifying set (138-107-5, 56.3%, lower bound 50.1%:
  fails) and the cap-5 set (78-44-2, 63.9%, lower bound 55.1%: passes, units positive both
  seasons); Tate ruled the same day that the champion's rule includes the weekly cap, so the
  capped set counts → `tested-positive`, licensing only H-FG-P, a 2026 paper arm of full-game
  unders (row registered in the same PR, family `fg-market-paper`; collector = PR5). The harness printed no verdict because no `--criterion` function was
  passed; the criterion was applied by hand to the runner's numbers, no re-dispatch.

- **2026-10-06 (H-FG-U-R / H-FG-O-R: data cell corrected before any look).** The rows named test
  seasons 2023-25; the frame begins in 2023, so 2023 has no prior training season and the first
  dispatches (`study.yml` runs 37495878846, 37495894548) returned NOT EVALUABLE with nothing graded
  and no number read. Tate's call: amend in place — test seasons 2024 and 2025, criterion "units > 0
  in BOTH seasons" — rather than new rows, because no observation preceded the edit. One dispatch
  each follows.

- **2026-10-06 (SHIPPED #279 `3cfe1f0`, #280 `272e6f8`, #281 `96a2506`, #282 `d269290`; the deep
  program approved).** Tate's brief: make Beat Vegas a true college-football betting system —
  six tracks (markets, CFBD catalogue, Discord knowledge base, Bill's business, assumptions audit,
  product thesis), one Monday program review, real money unchanged (1H unders, 5 flat units) for
  2026; plan file `pasted-content-id-35b3-session-handoff-iterative-rossum.md`. Track A shipped
  the same day: real Saturday full-game closes on the `lines_watch` ticks (`totals` x `us,us2`,
  2 credits a tick) and the 3 h window on `market_fg` (#279; 9 of 380 graded 2026 games had a
  snapshot inside 3 h before); registry rows H-FG-U-R / H-FG-O-R, pre-registered, one look each
  (#280); the market-aware harness — `beatvegas/markets.py`, `--market fg --side over`, the
  champion path byte-identical (#282). Track E: `docs/ASSUMPTIONS.md` v1, 28 live rules with
  their basis, and three doc defects fixed (#281). Deploys READY, health ok after each.

- **2026-10-06 (H-WEPA-F REGISTERED AND TESTED NULL — `docs/WEPA_F.md`).** The row (PR #278,
  commit `f9105bf`, before the script) pre-registered a 2025 retrospective arm: dated in-season
  WEPA from the 11 Patreon weekly files (561 games, z-scored within each file;
  `scripts/wepa_weekly_extract.py` → `data/wepa_2025_weekly_z.csv`, no raw value, no spread) as
  a walk-forward ridge correction to the champion's 2025 line, two sub-arms (`wepa_epa1`,
  `wepa_k4`; `beatvegas/backtest/wepa_f.py`), judged by `harness_report` on 622 games with a
  real consensus close. One dispatch (`study.yml` run 37491506377): **NOT MET** — Δ|err|
  −0.034 [−0.121, +0.050] and +0.008 [−0.109, +0.122], Holm p 0.91; both arms fixed the level
  (bias +0.53 → +0.04) and not the accuracy (MAE 9.11 / 9.15 vs 9.14; market 8.90); favourable
  line value negative for every arm. ARM P (the 2026 `bv_wepa_f` engine) is not licensed.
  Also 2026-10-06: #277 shipped (`bd74a70`); the deep-program plan approved (six tracks, one
  Monday program review; real money unchanged); PR #279 opened (Saturday full-game close capture
  + the 3 h window on `market_fg`).

- **2026-10-06 (ASSUMPTIONS LEDGER v1).** `docs/ASSUMPTIONS.md`: every live rule on the
  money path in one table — value, `file:line` (read in the code that day), basis (evidence /
  design / scope / registered / derived / display), the evidence or the reason, and the
  registered test that would move it, with a blank column for Tate's call. Two rows carry
  outcome evidence (the top-20% gap rule and the cap-5 ranking, both from the spent 2023-25
  set); the price gate has a live record (loss avoided); everything else is design or scope.
  A closing section names the inherited rules with no evidence and the paper rows that would
  test them (proposed: H-PRICE-F, H-CLOSE-W, H-EARLY-C, H-FG-U-R / H-FG-O-R; H-INJ named, not
  registered; H-TOP3 and H-PCT-TIE already registered). Three doc defects fixed: (1)
  `BETTING_POLICY.md` said Hard Rock rungs are "both sides no worse than −160" — the Hard Rock
  rule (`is_hr_rung`) is −140 or 2+ pts off the field, −160 is the general centred-quote rule;
  (2) `BETTING_POLICY.md` and (3) `EXTERNAL_REVIEW.md` each claimed a full-game backtest
  "found no edge" — no full-game-target study exists; the only full-game numbers are the
  post-mortem `fg` column (1H-selected picks graded as full-game unders). No code, constant,
  gate, workflow or registry criterion changed. `CLAUDE.md` Read-first names the ledger.

## 2026-10-05

- **2026-10-05 (ODDS API ON THE 20K PLAN; DATA STACK REVIEW).** Tate cancelled the 100K
  ($59) subscription and bought the 20K ($30) one; new key set in the `ODDS_API_KEY` secret
  (13:35Z) and local `config.yaml`; verified by a free `/v4/sports` read (20,000 remaining)
  and a zero-credit `lines_watch.yml` `1h_close` dispatch (run 37318117401).
  `config.example.yaml`, `README.md` and `docs/OPS_ACCOUNTS.md` item 3 updated; the
  CLAUDE.md open item closed. **Data stack review** written from a four-lane research swarm
  (`docs/DATA_STACK_REVIEW_2026-10-05.md`; lanes in `research/swarm/2026-10-05-data-stack/`,
  gitignored): keep the Odds API at 20K (nothing else sells Hard Rock 1H totals at <= $30;
  CFBD `/lines` and ESPN are full-game only); CFBD **Tier 1 ($1)** is the right tier (gating
  read from the API's source: Tier 1 = WEPA + weather + scoreboard; Tier 2 = live PBP only;
  Tier 3 = GraphQL + a weekly full-game, market-aware training CSV with nothing first-half;
  `/coaches`, `/drives`, `/games/teams` are free, correcting SYSTEM_REVIEW §7); do not buy
  public splits (no first-half splits exist anywhere; VSiN 2022-25 has the majority-handle
  side 51.2% on CFB totals). No published market-blind CFB totals model beats the close; the
  missing inputs are free (in-season opponent adjustment, decision-safe weather with a wind
  threshold, the discarded SP+/explosiveness columns, Elo/FPI/CORE). Seven decisions for Tate
  at the end of the doc, none acted on. Also fixed: `tests/test_coverage.py` pinned its clock
  (the seeded Saturday fell out of the 8-day look-back on 2026-10-05).

- **2026-10-05 (CFBD TIER 3 BOUGHT; TIER 3 REVIEW).** Tate bought Patreon Tier 3; CFBD matched
  it by email to the key issued to boomtatermac@gmail.com on 2026-06-02, which now carries
  Tier 3 (75,000 calls, WEPA/weather/scoreboard/live/GraphQL flags true) and sits in
  `config.yaml` and the `CFBD_API_KEY` secret (14:11Z); the FGCU Academic key is retired.
  Review written from four lanes (`docs/CFBD_TIER3_REVIEW_2026-10-05.md`; 57 calls): every
  useful dataset is Tier 1 — `/wepa/team/season` is the opponent-adjusted in-season input the
  model lacks (no week param, absent weeks 1-4, snapshot weekly); free `/game/box/advanced`
  splits EPA/success/explosiveness by quarter (a PBP-free route back to the 57 B-SERVE
  columns); SP+ `sos` and sub-ratings are null since 2019 (the PR6 `sp_sos` input is dead);
  **CFBD rewrote PPA history in Sept 2026** (turnover-on-downs fix, ~35-40% level shift on
  past seasons; our Sep 22 cache already post-fix, mean 2025 offense PPA 0.112 = live); the
  weekly Tier 3 CSV is full-game and market-aware (closing spread, no O/U, nothing 1H), not
  opened (patreon.com refused by both browsers). Discord: Sunday refresh 09-10:40 ET, SP+
  later, CSV afternoon; `/lines` close = last 5-min capture, no timestamps, DraftKings
  provider name duplicated until 09-25; new 2026 concurrency 429s; nobody there has 1H data.
  Four rows proposed (H-WEPA-F, H-FHBOX, H-ADJ-OWN, H-WX-VALID), none added; six decisions
  for Tate at the end of the doc. **Evening:** patreon.com is refused by both app browsers and
  the classifier refused a cookie-reading script, so Tate pulled the campaign himself with
  `gallery-dl --cookies-from-browser chrome` (one-time): all 34 posts read in full, and **all 18
  weekly CSVs** arrived — the 2025 weeks 5-15 files are frozen Sunday WEPA snapshots (561 games,
  536 with a real 1H close on file), a leak-free 2025 retrospective the endpoint cannot regenerate
  (pre-PPA-fix scale; standardise within season). Bill's own rule on every post: the spread is
  the OPENING line; games without a line at posting are dropped and re-posted mid-week. Also: `lines_watch.yml` dispatches 37318117401 and
  37318523335 proved the new Odds API key on the runner.

- **2026-10-05 (SHIPPED #276 → `d03fa17`, deploy `dpl_3GcyKVvmKV76FxKLj559ynjzCuGp` READY
  22:08Z).** CI was cancelled twice by a GitHub Actions incident (runner assignment delays from
  19:11Z; jobs queued 15 min and cancelled without a step) and passed on the third run at 22:04Z.
  Health ok, no warnings, four job verdicts ok; runtime errors: only the known `sslmode` warning;
  route sweep 8/8 200, 13/13 redirects 308; ledger 96 picks / 20 real matches Neon. No web files
  changed, so no screenshots. `gauges.cfbdCallsRemaining` 74,982 proves the runner is on the
  Tier 3 key (grade.yml 19:21Z).

## 2026-10-04

- **2026-10-04 (WEEK 5 REVIEWED — `reports/weekly/2026-w5.md`, gitignored; plan file
  `let-s-run-a-full-playful-russell.md`).** Real money **1-4, −3.13u** (season **10-10,
  −0.29u**, Wilson 29.9–70.1%): Washington @ USC u30.5 W; Florida @ Missouri u28.5, Kentucky @
  South Carolina u27.5, Penn State @ Northwestern u23.5 (all Tuesday tickets) and Alabama @
  Mississippi State u30.5 (Friday, gap 2.12 on a 2.12 bar, cap rank 5) L. Line value 0 / 0 /
  +1 / 0 / −1; price CLV −0.011; every card BET placed, nothing else; no rule loosened. Paper
  4-6, −2.66u (BET-rated 1-1, price-blocked 3-5; season price-blocked 14-20 vs BET-rated 7-4 —
  the price gate filters losers). **The slate went 33-20 under at Hard Rock's numbers and the
  under side sat below the bar**: gap < 1.75 went 26-13, gap ≥ 1.75 7-7, the qualifying set
  4-5; the gap-vs-residual correlation on main lines read +0.15 (wk 4) and +0.16 (wk 5) after
  −0.34 / −0.36 in weeks 2-3. B-SERVE fixed the level (bias +0.18, the book's) and not the
  accuracy (MAE 9.03 vs 8.39; qualifying games 8.74 vs 7.50); the model missed the four losers
  by 6.8 / 6.9 / 10.4 / 16.6 pts, Hard Rock by 1.5 / 2.5 / 7.5 / 14.5. **H-STOP-2** at n=10:
  profit LLR −0.26, line value LLR +0.73 (n=9; Penn State excluded — Friday-night close 227
  min out, the Vercel `lines-close` entries are Saturday-only). **H-NEGGAP-P** first week
  graded: `lt0` 5-11 −6.71u, `le175` 3-5, `le3` 2-4, all clocks running; the band went 12 under
  / 5 over on main lines. Ops: every job green; the close backup's first Saturday fired 14
  hourly dispatches and `close_coverage_pct` read **1.000 (53 of 53)**; weather 53/55; alternate
  share at `sat_am` 8 of 48; the Odds API counter reset on Oct 1 (99,940 remaining) — that is
  the monthly credit reset, not a bill: the dashboard (read 2026-10-04) shows the next invoice
  on Oct 6, so the downgrade must happen before then. **Decisions (Tate):** ledger confirmed;
  keep betting off the first BET-rated build; hold H-PCT as registered (a change would
  supersede H-STOP-2 at n=10); report + docs PR. Verdict: variance plus one marginal pick inside
  a model that is less accurate than the book; the registered clock is the arbiter. Proposed,
  not done: Friday-night `lines-close` entries; draft paper rows H-PCT-TIE and H-TIMING; the
  weekly review gains the gap-residual correlation and the qualifying-games MAE as standing
  lines. Housekeeping: `reports/neggap_*` gitignored (the position script writes there); the
  Friday write-up left uncommitted in worktree `neggap-card24` is committed as the first commit
  of this PR.

- **2026-10-04 (SHIPPED, afternoon: #269 tracking 14:44Z, #270 docs, #271 deps, #272 prisma —
  the week-6 stack's PR2 is live; CFBD and Odds API steps on hold).** `migrate.yml` was
  dispatched by Tate from the `tracking` ref (run 37210300461; the auto-mode classifier refuses
  a production-database write from the session) and all 11 new columns and 3 tables were read
  back on Neon before #269 merged (c3e8e0c, rebased over #268; 1,469 pytest / 544 vitest / 219
  e2e). **Finding:** a full `prisma db pull` is not the schema-change step the brief described —
  it introspects 22 models the app reads by raw SQL on purpose plus six `swfl_*` fishing tables
  that share the Neon database, and strips the schema comments; the four new columns were
  hand-added instead (#272) and the brief's rule now says so. #271 closed six of the seven
  Dependabot alerts that appeared when the repo went private (dev-only `brace-expansion`);
  `braces` has no upstream fix. Every deploy verified (health ok, routes 200/308); the new
  tables are empty until the next refit / sweep / card build. On hold at Tate's request: the
  Odds API 20K subscription (the 100K is due to cancel Oct 6 — Tuesday) and the CFBD Patreon
  tier (Tier 1 at $1 covers ~20 calls a day; the review doc said Tier 2 before the $1 tier
  was known).

- **2026-10-04 (SHIPPED: PR #267 docs 14:18Z, PR #268 classifier retired 14:26Z; REPO PRIVATE
  AGAIN; ACTIONS BUDGET SET).** #268: no classifier fit in `score_slate`, the "Model 1H"
  ledger and the Results row gone, `under_score` out of the records CSV, `verdict.ts` and
  `edge.ts` define "has a model" on `bvLine` alone, the factor ledger reads `market` result
  rows only; 1,444 pytest / 543 vitest / 219 e2e, production verified (health ok, overflow 0 at
  390 on every page). Left: `backtest/engine.py` still fits the classifier for four offline
  tools (open item). Tate put a card on GitHub and the repo went PRIVATE at 14:36Z (0 forks, 0
  stars while public; only collaborator Tate; no deploy keys or webhooks; no credential in any
  tracked file or in history; 2FA already on). The Actions budget read $0 with stop-usage on —
  the mechanism of the Sep 22 outage — and is now $10/month, stop-at-cap, alerts on (Tate's
  choice). Two medium Dependabot alerts (`brace-expansion`, build-time) wait for the next web PR.
  The Odds API (invoice Oct 6/7, 100K due to cancel, 20K to create → new key) and the CFBD
  Patreon tier (Tier 1 at $1 covers measured usage) are on hold at Tate's request.

- **2026-10-04 (FULL SYSTEM REVIEW — `docs/SYSTEM_REVIEW_2026-10-04.md`; every answer
  Tate's).** Prompted by the week-5 loss: "is the model actually getting sharper?" **It cannot
  be, by construction**: `score_slate` trains on seasons before the target only
  (`model/score.py`), so 2026 results never enter the fit; the Sunday refit is the same
  2015-25 regressor, and it moved in-season only when CFBD revised reference tables. The
  2026 factor screen (H-FACTOR-SCREEN, 212 Hard-Rock-priced games with frozen frames, 87
  comparisons, Bonferroni 0.00058) found no input predicting the residual against the close
  (best p 0.117) and the gap itself at rho −0.06, p 0.41; the 2023-25 buckets on record are
  quoted, not re-read. What has a live record: the price gate (paper price-blocked 14-20 vs
  BET-rated 7-4), the slate-bar universe fix (H-PCT-U), the close backup (53/53), the ledger
  itself. What does not: the model vs the book (MAE 9.03 vs 8.39), every situational and
  weather input (flat), the "overs" band (reversed), top-k concentration (top-3 by gap 5-7 vs
  top-5 9-11 live). Already fetched and discarded at zero cost: prior-season explosiveness,
  defensive success, SP+ special teams and strength of schedule. Not frozen anywhere: factor
  values on paper picks and card items; `model_version` has read `gbm_v1` through B-SERVE;
  `factor_ledger`, the post-mortem tables and `app_settings` are overwritten each run.
  **Decisions (Tate):** model improvements enter only as shadow arms beside the champion
  (H-SHADOW-F: the discarded CFBD inputs, legacy weather nulled; H-INSEASON-T: in-season
  training rows at w = 1 and 3); four paper rows (H-PCT-TIE, H-TIMING, H-MOVE, H-TOP3);
  retire the classifier; mirror the degraded hold on the web; delete the dead in-season
  challenger arms; freeze the factor vector and a refit id on every pick and card item; keep
  history instead of overwriting; store the Rotowire report and a poll log per build; buy
  CFBD Tier 2; Odds API down to 20K before its Oct 6 invoice; no public-betting purchase until H-MOVE says the move
  carries something. Week-6 money unchanged (≤5 × $10, every card BET, first BET-rated build).
  The stack and its dates are the brief's open item.

## 2026-10-02

- **2026-10-02 (WEEK 5 `fri_pm` CARD CLEAN, VERCEL-TRIGGERED; H-NEGGAP-P WRITES ITS FIRST
  ROWS — CARD 24).** Run 37058936969 (4 m 37 s, 56 credits; `last_dispatch_card-fri-pm` note
  `dispatched`, so Vercel fired it): 2 BET / 27 EDGE / 27 PASS, bar 2.12 = top 20% of 44
  priced games, 9 Hard Rock alternates ignored, 9 paper unders logged (the rest-of-week
  window), health ok. BETs: Washington @ USC u30.5 −115 (Tuesday's ticket) and Alabama @
  Mississippi State u30.5 −105 (gap 2.12, on the bar; ticket 100, logged 20:29Z, the week's
  fifth and last slot). Tuesday's Florida, Kentucky and Penn State tickets now read EDGE on
  price (Hard Rock −115/−120/−115 against kills −110/−115/−105); they stand as logged.
  **H-NEGGAP-P wrote 27 `challenger_picks` rows over 15 games** (`neggap_lt0` 15,
  `neggap_le175` 7, `neggap_le3` 5), recorded in `docs/NEGGAP_PAPER.md` before any kicked
  off. Thursday's card 23 (run 36919010718, 10 m 42 s, 56 credits: 2 / 26 / 30, bar 2.91 of
  45, 10 alternates, 0 paper — the 24 h window) was clean too; its Vercel tick at 21:01Z
  found the build (`already_ran`). **Measured 2026-10-01, nothing changed: Hard Rock's feed
  row drifts from its main line to an alternate rung as kickoff nears.** Over every
  pre-kickoff Hard Rock 1H snapshot of 2026 (a main row = both sides better than −140): the
  main-line share is 97% beyond 48 h, 87% at 12–48 h, 41% at 2–12 h, 31% inside 2 h; across
  535 consecutive-row pairs the feed went main→rung 142 times and rung→main 5, every
  main→rung with the line dropping 1–1.5 pts and the over juiced. That is the mechanism
  behind the 17-of-53 close coverage. Whether Hard Rock pulls its main 1H line late or The
  Odds API picks the wrong row of the ladder is not tellable from our side. Options put to
  Tate, simplest first: add `alternate_totals_h1` to the per-event call (2 credits an event,
  roughly doubles sweep cost, needs one 2-credit probe to confirm the ladder carries the
  main line), report it to The Odds API, accept it, a typed-in price at log time (breaks
  "the site never trusts the browser"), scrape Hard Rock (not recommended: geofenced,
  bot-walled, terms). No decision yet. The `bv-card-check` skill was updated the same day for
  the post-#260 board (answer bar + "Bar this week" sentence, the dispatch-gauge note, the
  real `manual_picks` column list).

## 2026-09-29

- **2026-09-29 (WEEK 5 `tue_pm` CARD CLEAN; THE CLOSE-POLL BACKUP PROVED BEFORE ITS FIRST
  SATURDAY; H-NEGGAP-P RECORDS CARD 22 — PR #262, merged and verified on production
  2026-09-30).** The first build on the B-SERVE model (run
  36627103104, card 22, 11 min, 55 credits): 4 BET / 24 EDGE / 27 PASS, bar 2.6 pts = top 20%
  of 46 priced games, 9 Hard Rock alternates ignored, health ok. All four BETs (Penn State @
  Northwestern u23.5, Florida @ Missouri u28.5, Kentucky @ South Carolina u27.5, Washington @
  USC u30.5) sit exactly at their kill price. **H-NEGGAP-P logged 0 rows** — the 09-28 entry
  below says "the 2026-09-29 `tue_pm` build is the first that logs", which overlooked the 48 h
  paper window (`ci.PAPER_WINDOW_HOURS`): a Tuesday build logs nothing for a Saturday slate.
  `docs/NEGGAP_PAPER.md` now records card 22 as the build that switched collection on, and
  keeps a "first build with rows" line for the `thu_pm` or `fri_pm` build (Tate's call: card 22
  now, first rows later). **The 17-of-53 close-coverage warning on the board is week 4**
  (Sat 09-26): 1H snapshots landed in three UTC hours (18Z, 21Z, 23Z) because only GitHub's
  cron existed; the Vercel `lines-close` backup (#242) merged 09-28 and has never run —
  `last_dispatch_lines-close` is null for that reason, not a fault. A hand dispatch of
  `lines_watch.yml` with `market=1h_close` (run 36633701647, 10 s, zero credits) proved the
  path: the resolve step took the market from the dispatch input, the free pre-check found 0
  events inside 120 min and every paid step was skipped. Three loose ends closed, each Tate's
  call: a **14Z Saturday `lines-close` entry** (10:00–10:59 EDT — without it a 15Z tick at
  11:59 plus runner start-up captures the noon slate at 12:0x, outside its 2-hour window; 9am
  EST from November, refused free; 15 entries 14Z–04Z); **`grade.yml`'s 16:00Z cron is
  Sun–Fri** (on Saturday it queued against the close poll in `neon-writers`, where a third
  arrival cancels the older pending run; Saturday's grade is 10:30Z plus the Vercel dispatch);
  the `HEALTH.md` runbook said "75-minute window" (120 since #249). Sat 2026-10-03 is the
  first live test of the backup: `last_dispatch_lines-close` advancing hourly and Sunday's
  grade lifting `close_coverage_pct` past 0.8.

## 2026-09-28

- **2026-09-28 (PUBLIC-SITE RESTRUCTURE BUILT — PR #260, merged and verified on production the
  same evening; one PR, per-page commits).** Tate's go the
  same evening as the review (PR #258). The site is now **Board / Results / How it works**:
  the Board keeps everything and gains a two-line strip; Results opens on the bet ledger (our
  bets in units, a "could plausibly be" interval, the units curve, every bet as logged, the
  CSV) with a three-row comparison; How it works holds the pitch, the Board key, the Hard Rock
  (Florida) note, the backtest headed "Backtest, 2023–25 (not money bet)", the gap ladder,
  what we don't know, ten terms (Plausibly in; Rank, Score, Line basis, Reference line, Kill
  line, Early season, Graded and pending out), the `/records` link and the helpline. **Owner-
  only behind the cookie** (`viewerIsAuthed()`): ops warnings, the My-teams chip, the pause
  reason, the Monday review (picks table with edit/delete, breakdown, decisions, factor read)
  and the model / full-game comparison rows on Results, the research section (live notes,
  flags, method fold) on How it works, the log control on the game page. Lock and Unlock moved
  to the footer beside "21+. Not financial advice." — which also ended the 87px phone header
  the layout spec had pinned as a known failure. `/proof` → `/results`, `/proof/records` →
  `/records`, `/glossary` → `/how-it-works#glossary` (thirteen 308s). **Board core fixes in
  `edge.ts` and `card.py` alike:** the row sentence names its basis ("the market line is 0.2
  above our number" when Hard Rock has no line; "sits on our number" instead of "0.0 below");
  the bar sentence is `Bar this week: 2.1 pts (top 20% of 41 priced games).`; "0 of 5 bets
  this week" and "Next update" replace slots and build. Decisions Tate made for the build:
  bar sentence shortened, one PR with one Vercel preview, Lock in the footer. Every
  FEATURE_PARITY line was kept, renamed or retired with its reason; the e2e fixture's port of
  the action templates changed in lockstep (`lib/e2eFixture.test.ts` holds them together).

- **2026-09-28 (PUBLIC-SITE REVIEW — what a stranger sees, and the structure if anyone could
  follow the picks; PR #258, merged 2026-09-28).** Tate walked the question "if Beat Vegas were a product anyone could open,
  how should the site be structured?" through four rounds of questions; the review and every
  decision are in `docs/superpowers/specs/2026-09-28-public-site-review.md`, the mockups (390 and
  1440 side by side, live numbers, a visitor / signed-in switch) at
  https://claude.ai/artifact/GRXmeADGb7PCGQRtfq4qRG. **Findings:** nothing on `/` says what the
  site is; `/results` and `/proof` headline the same record; the Monday-review tables, the ops
  warnings (with `docs/HEALTH.md` paths), "My teams", real dollars and an UNLOCK button all face
  visitors; two glossary terms describe a score no page shows. **Decisions (Tate):** audience is
  anyone, mostly US bettors; read-only "follow our picks", no sign-up yet; the Board's core is
  untouched and gets a two-line intro strip; Results and Track record merge into one Results page
  that opens on the ledger; a new **How it works** page takes the pitch, the Board legend, the
  Hard Rock (Florida) note, the backtest headed "Backtest, 2023–25 (not money bet)", the trust
  copy from 2026-09-08, nine terms (from 16) and a 21+ / not-advice line; ops warnings, My teams,
  the Monday tables and the research flags render only when signed in; "My money" → "Our bets";
  dollars leave the public site (units and ROI only); Unlock moves to the footer; `/proof` →
  `/results`, `/proof/records` → `/records`. Game page structure was out of scope (two owner-only
  fixes noted). **Nothing ships mid-season without a separate go**; the build plan waits.

- **2026-09-28 (WEEK-5 STACK CLEANUP, PR #249 — the `/code-review` + `/simplify` passes over
  #241-#247, applied; every fork Tate's call).** **Correctness:** `lines_watch.yml`'s free
  `/events` pre-check gated on 75 min while the poll looked 120 ahead, so a slot whose only
  kickoffs sat 76-119 min out was skipped by the very check #242 widened — one workflow env
  `CLOSE_LOOKAHEAD_MIN=120` is read by both steps (`test_workflows` pins it, `docs/HEALTH.md`
  regenerated). `scripts/neggap_position.py` accepted a close stamped AFTER kickoff while the
  champion's `stopping_rule_position.py` required it at or before — both now call
  `lines.close_in_window`. `challenger_position.py` read every graded `challenger_picks` row and
  negated clv with the under sign, so the H-NEGGAP-P over arms would have entered the H-INSEASON
  position with the wrong sign once graded — `load_observations`, `latest_build_context` and the
  row count filter on the H-INSEASON arms and `side='under'`. The log form's "Placed at" is
  BLANK by default (blank = now): pre-filling the mount time turned a form left open 31+ min
  into a backdated log judged by the card in force at mount time with no live price check. The
  ledger's late-log stamp uses `BACKDATE_MIN_MINUTES` (30), the threshold the server judges by.
  `vercel.json` gained a 04Z Sunday `lines-close` entry (11pm EST Saturday from November; 00:00
  EDT in summer, when the route refuses it as `wrong_day`) — **14 entries, 15Z Sat to 04Z Sun**.
  **Cleanup (no behaviour change):** `coverage.close_window_coverage` reads the priced games'
  1H rows once (was one COUNT per game, 57-72 round-trips per close run); `card.parse_kick` is
  the one kick parse (had four copies); `stopping.two_clocks` + `family_verdicts` replace the
  verbatim copies in `neggap_position`; `getLatestCard(season, week, asOf)` replaces
  `getCardAsOf`; the picks route runs `betAtCheck` right after the game load. **Skipped on
  purpose:** `side` through grading, the health check recomputing coverage, a sequence resync
  before the new `model_runs` writer (`init_db` already resyncs), `etLocalToUtc` in the DST gap
  hour (noted). Python 1,445 passed, web 539 vitest, tsc/eslint/prettier clean, no migrations.

- **2026-09-28 (THE WEEK-5 FIX STACK: SEVEN PRs #241-#247, ONE DAY, every fork Tate's call).**
  Plan file `pasted-content-id-74ed-how-did-functional-bee.md`. **Close poll (#242):** a Vercel
  `lines-close` job (`cronJobs.ts`, `everyTick` skips the already-ran probe; 13 once-a-day
  Saturday entries 15Z-03Z — the account is verified Hobby, each fires within its hour) dispatches
  `lines_watch.yml` with `market=1h_close`; the close look-ahead is **120 min** (ticks up to 119
  min apart still reach every kickoff inside the registered 2 h; 130 would not). GitHub's crons
  stay. **Coverage gauge (#243):** `beatvegas/coverage.py` → `close_coverage_pct` (written after
  each Saturday close poll and daily after grading), board warning under `CLOSE_COVERAGE_MIN =
  0.8` (parity-pinned with `health.py`), `lines_watch.close_window_coverage` judged on Saturday
  runs only; `counts.hr_priced` / `hr_alt` on the card. **Run log (#244):** every weekly refit
  writes a `model_runs` row (`weekly refit`: inputs, intercept, train/target rows, a data-only
  frame digest `frame_fingerprint.fingerprint_hash`, run id); `proof.ts` reads retrain's rows by
  content; `sunday.model_run_recorded`. **bet_at (#245):** `manual_picks.bet_at` (when the
  ticket was WRITTEN; `placed_at` stays the log time), the log form's "Placed at" field
  (`et.etLocalToUtc`, DST-safe), `pick.py add --bet-at`; a log more than 30 min after the bet is
  BACKDATED and judged by **the card in force at bet time** (`card.ts::getLatestCard(season, week, asOf)`,
  `pickRules.verdictAtBetTime`, that card's kill numbers, no live read — the money is on the
  table); `betAtCheck` refuses future / >7 d / post-kickoff; the ledger's hours-before-kickoff
  and the CSV (`bet_at_utc`, 31 columns) use the bet time. **H-NEGGAP-P (#246, #247):** paper
  OVERS on the negative-gap band, three nested arms (gap < 0 / ≤ −1.75 / ≤ −3) on Hard Rock's
  MAIN line in H-PCT-U's universe, one row per game per arm at Hard Rock's over price into
  `challenger_picks` (`side='over'`, never `manual_picks`), the champion's two clocks with the
  champion's sigmas (0.929 / 1.371) at 5% / 3 / 2 = 0.833% per arm-clock (A +4.5643 / B −1.6011),
  favourable line value for an over = **+(closing − bet)**; `NEGGAP_COLLECT=1` in `card.yml`, so
  **the 2026-09-29 `tue_pm` build is the first that logs** (write its `cards.id` into
  `docs/NEGGAP_PAPER.md`); grading is side-aware in one place (`grading.units_won(side)`,
  `picks.graded_pick_fields(side)`, `lines.book_closing_price_before_kickoff(side)`), the under
  path byte-identical; `challenger_picks.closing_captured_at` is new. A pass licenses nothing
  at real money. Migrations ran on each branch before its merge; production verified after
  each deploy (health ok, every route 200, shots metrics unchanged). **Two things not done:**
  the week-sandbox replay for #247 (this Mac's SQLite is a June snapshot — the first live
  build is the check, `bv-card-check` expects `neggap_*` rows) and Tate's two account tasks
  (Odds API 100K → 20K on Oct 6; CFBD Tier 2). **Pitfall, met twice today:** `pytest | tail -1`
  masks the exit code and let a red suite push once — check `$?` before pushing.

- **2026-09-28 (WEEK 4 REVIEWED — `reports/weekly/2026-w4.md`, gitignored).** Real money
  **3-2, +0.83u** (season **9-6, +2.84u**, Wilson 35.7–80.2%); every card BET placed, nothing
  else; first week every real ticket carries `price_provenance='logged'`. Paper 6-5, +0.41u on
  11 picks — only 11 because **H-PCT's slate bar was already live on every week-4 build** (bar
  4.9–5.5 vs the old 1.75; 6-11 qualifying per build vs 27-31) on the OLD model; H-STOP-2's
  observations start at the 2026-09-29 `tue_pm` build. Tickets 85/86 were bet Friday and logged
  Saturday (server stamped WATCH): repaired to BET + note by a guarded `_DATA_MIGRATIONS` entry,
  `placed_at` kept. **Week-5 refit is the first on the B-SERVE model** (run 36342602323: 58
  inputs, `serve-skew ... 0 column(s) NaN at serving`, mean bv_line 25.85 vs 24.41 in week 4,
  intercept −1.230); the refit writes no `model_runs` row. Model beat Hard Rock on the 43
  close-spread games (bias +0.50 vs −1.29, MAE 7.70 vs 7.83). **The "overs" band (H-NEGGAP)
  REVERSED: week 4 went 3 over / 9 under, cumulative 26 of 38** (Wilson 52.5–80.9) — and 23 of
  the 38 were Hard Rock ALTERNATE lines (2-4 pts under the field, over at −160..−325), the
  H-PCT-U feed defect; on main lines it is **10 of 15, 0 of 4 in week 4**. Measurement only;
  a draft paper-only row (H-NEGGAP-P, three arms, Bonferroni) sits in the report for Tate.
  **Ops finding: the Saturday close poll fires 3 of 18 GitHub cron slots** (5 in week 3), so
  Hard-Rock-priced games with any 1H snapshot inside the registered 2 h are wk2 25/72, wk3
  27/72, wk4 18/57; `lines_watch` health only judges runs that ran and the board's close gauge
  stays green on three sweeps. Fix chosen (Tate): a Vercel `lines-close` cron backup (14
  once-a-day Saturday entries — the account is verified **Hobby**: each entry fires once a day,
  within the hour) with `--kickoff-within-min 120`, GitHub crons kept. Everything else ran
  clean (all 40 recent runs green, Sunday's six contract facts ok, CFBD 1,808 / Odds 53,609).


## 2026-09-26

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


## 2026-09-25

- **2026-09-25 (HARD ROCK ALTERNATE LINES, PR #236, registry row H-PCT-U).** The Odds API
  sends Hard Rock alternate lines alone as its first-half total (Texas @ Tennessee: 30.5 at
  −160 against 27.5 in the app). The old −160 check missed 33 of them on 31 games.
  `devig.is_hr_rung` now flags a quote at −140 or worse, or 2+ points off the other books in
  the same sweep. The card and the board then show Hard Rock's last real line with its time
  (`hr_alt_line`), and it can never be bet. The 12 paper picks already logged on alternate
  lines stand as logged.


## 2026-09-23

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


## 2026-09-22

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


## 2026-09-20

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


## 2026-09-16

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


## 2026-09-15

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


## 2026-09-14

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


## 2026-09-13

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


## 2026-09-10

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


## 2026-09-09

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


## 2026-09-08

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


## 2026-09-06

- **2026-09-06 (post-mortem):** `scripts/post_mortem.py` (pure math in `beatvegas/postmortem.py`)
  regrades every rated game vs its outcome — the 2023-25 walk-forward ratings at the flat 0.52 AND
  the fair step proxy (FBS-only + all), plus the season's cards at Hard Rock's numbers — into
  `postmortem_runs/buckets/games` (last step of `grade.yml`) and `docs/POST_MORTEM.md`; the Results
  page renders the headline records, rating bands and change flags (`web/lib/postmortem.ts`).


## 2026-09-02

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


## 2026-09-01

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


## 2026-07-17

- **2026-07-17 (review closed):** the pre-season readiness review is fully worked
  off — blockers (PR #16), 13 should-fixes (PR #17), and the remainder (S8 strict
  pick matching, S15 postseason capture, S16 multiplier margin gate — fitted curve
  REVERTED to flat 0.52, S17-S19, S21-S22, nits). Accepted as-is: GHA cron lag
  (S20), sunday.yml DST double-fire (N12), plaintext local keys (N14), no login
  rate limit (store-less); N13 is moot since the push-notification layer was removed 2026-09-02. Since PR-1 data plumbing
  (2026-09) the Odds API bulk pull requests `totals,spreads` together (4-6 credits per slate), so each
  book's row carries its home spread; `Game.spread` is the run's cross-book median and Monday's CFBD
  upsert no longer clobbers Odds-API-sourced totals/spreads (`*_source` columns + `line_sources.py`).


## 2026-07

- **2026-07 (Hard Rock pivot, PRs #7-#9):** multi-book capture incl. Hard Rock via The Odds API (`hardrockbet`; the `hardrockbet_fl` key folds onto it at write time); web views `/preview`, `/line-check`, `/weekly-review`; both markets logged + graded (`manual_picks.market`, `market_fg` ledger). Before season: GH secrets set, `odds_api.regions: "us,us2"`. (The phone push-notification layer shipped here was removed 2026-09-02 — failure alerts are GitHub's failed-run email + the routines.)


## 2026-06

- **2026-06 (cloud + board):** Neon-writing jobs run in GitHub Actions, not launchd (campus network can't reach Neon:5432; DK 403s GHA IPs → CFBD `/lines` fallback). Derived-1H lines post to the board as "DERIVED · no model pick"; board query is season-scoped.


## 2026-05

- **2026-05 (opener capture):** Sunday DK full-game opener via free hidden API + gated spread-adjusted 1H multiplier (`data/multiplier.json`; absent = flat 0.52). Next.js on Vercel is the product (Streamlit removed).
