# Health contracts

What each scheduled job must leave behind, checked by the job itself as its last
step, written to one row the board reads. Code: `beatvegas/health.py` (the
contracts as data), `scripts/health_check.py` (the workflow step),
`web/lib/boardHealth.ts` (the banner and `/api/health`). No LLM, no texts: a
contract is a list of positive facts and a rule for turning misses into a word.

## Why

Eleven of the fourteen failures of 2026-08/09 were runs that exited green and
produced nothing -- a card build that died mid-sweep (2026-09-10), a grading job
that failed four runs straight while the board looked normal (2026-09-12/13),
a scoring run whose inputs were 57 columns of NaN (2026-09-22). GitHub's
failed-run email fires on none of those. The gauges in `beatvegas/ops.py`
(API budgets, last close, last completed grade, last dispatch) say whether the
system CAN keep running. A health contract asks the other question: did the run
that just finished DO what it was for?

## What a contract is

One per scheduled Neon-writing job -- `card`, `grade`, `sunday`,
`lines_watch` -- naming the workflow file, its window, the artifacts a run must
leave, the environment it is judged with, its checks and the failure modes on
record that each check would have caught.

A **check** is ONE POSITIVE FACT about this run, never the absence of an error:
"a `cards` row for this season and week was written after the run started and
carries this slot", "the `last_grade_completed_at` gauge moved after the run
started". Each check has a severity:

- `failed` -- the run did not do its job. The health step exits 1, so the run
  goes red and GitHub's failed-run email goes out.
- `degraded` -- the run did its job with something missing. Board-only.

A check that raises is reported as a miss with the exception's name in its
detail: a fact that cannot be established is not a positive fact.

## The verdict rule

`failed` if any failed-severity check misses; else `degraded` if any check
misses; else `ok`. A skipped run (`SKIPPED=true` -- a gate-skip tick, a probe
that found the work already done today, a no-week off-season tick) writes
nothing: it is not a run of the job, and the last real verdict stays on the
board.

## The gauge and the note

Each job writes `app_settings` row `last_health_<job>` (`ops.health_key`):
`value` is the verdict, `updated_at` the naive-UTC time it was written, and
`note` is at most 300 characters:

    run=<GITHUB_RUN_ID> event=<GITHUB_EVENT_NAME> slot=<slot> miss=<check id>(<detail>);<check id>(<detail>) info=k=v k=v

`run=` links the board to the Actions run; `event=` records the trigger
(`schedule` = GitHub's backup cron, `workflow_dispatch` = the Vercel cron or a
hand dispatch -- the runs API cannot tell those two apart, which is why the
`dispatch:<job>` gauge exists); `miss=` lists every missed check with its
detail; `info=` carries facts that are never a miss (`early_season_held=N`,
`bets=N`, `zero_halves_graded=N`, the enrichment step outcomes).

## How the board shows it

`web/lib/boardHealth.ts` reads the five keys (`HEALTH_GAUGE_PREFIX` +
`HEALTH_JOB_IDS`, parity-tested against `ops.HEALTH_PREFIX` / `ops.HEALTH_JOBS`)
into `Gauges.health[job] = { verdict, note, at }`. A `degraded` or `failed`
verdict becomes an `OpsBanner` line (`health:<job>`, failed sorted first) naming
the job, the ET time, the missed checks, this document's section for the job,
and the run link. `ok` is silent; a job with no row is unknown, not wrong.
`/api/health` exposes the same under `gauges.health`.

## Runbook

The first thing to open is always the run the note links to (`run=`); the
health step prints one line per check with its detail, and the step summary
carries `HEALTH: <verdict> <note>`.

### When card is degraded or failed

1. `card.row_this_run` missed -> the build never wrote a card. Open the run:
   did the `build` step run at all (a `gate`/`slot` skip should have set
   `SKIPPED`), did it die (traceback), or did the job time out? A timed-out
   job is reported `cancelled` and only runs its `always()` steps inside
   GitHub's grace window, so on a timeout THIS STEP MAY NEVER RUN -- the
   board's missed-build banner (`buildStatus`) is the check that always fires.
2. `card.sweep_reached_slate` missed -> the Odds API sweep stopped early
   (credit floor, per-run cap, 5xx). The card shipped degraded off the lines it
   reached; the sweep step's log names the error. Re-dispatch with `force=true`
   once the API is back.
3. `card.status_clean` missed -> a failed input (sweep, preview, pace) held
   games paper-only; the detail names the inputs. Same fix as 2.
4. `card.hr_priced_floor` missed -> Hard Rock has priced fewer than the floor.
   Early in the week this can be the market, not a bug: compare with the
   `hr_rows=` line of the sweep. If the sweep reports Hard Rock rows and the
   card does not, the book key or the sweep universe drifted.
5. `card.paper_logged_iff_window` missed -> qualifying games inside the slot's
   window have no paper pick (or a `manual` build logged some). Check the
   build log's "paper picks added" line and `manual_picks` for the game ids
   in the detail. Never backfill a paper pick by hand: the ledger is the
   stopping rule's observation set.

### When grade is degraded or failed

1. `grade.completed_this_run` missed -> one of the fatal grading steps
   (`grade.py`, `pick.py grade`, the consensus backfill "Line value at each
   pick's exact terms", `grade_records.py`) failed. Two of those used to be
   swallowed and now fail the run (final-2026 plan PR-02, 2026-10-19):
   challenger-arm grading inside `pick.py grade` (the champion ledger commits
   first, then an arm-grading exception propagates) and the judge's backfill
   step. The run is red; read that step's traceback. On CFBD 429/quota the scores fallback (ESPN)
   should still have landed finals -- check `grade.finals_landed`.
2. `grade.finals_landed` missed -> rated games kicked off > 18 h ago with no
   final. Both score sources failed or the games are genuinely late. The
   board's stale-results banner says the same thing; `backfill_scores_espn.py
   --days-back 4` by hand fixes a one-off.
3. `grade.records_graded` / `grade.picks_graded` missed -> played games with a
   first-half total whose record or pick is still ungraded. Usually the
   trust rule holding a 0-0 half without proof (`etl/first_half.py`): look at
   the game's line scores before touching anything. A proven 0-0 half is stored
   as `linescores_verified` (or `pbp`) and grades; a plain `linescores` 0 in a
   game that scored never does (`grading.ZERO_PROVEN_SOURCES`, 2026-10-15).

Stopped 2026-10-18 (final-2026 plan PR-09, decision D5): the daily run no longer
collects 1H play-by-play (`fh_team_game`), the SP+ factor chips or the
post-mortem tables, and no longer restores the CFBD reference cache that fed
them. CFBD drops to the free tier (1,000 calls a month) on 2026-11-05 and no
page or job reads those rows; the scripts stay, and so does `backfill.py`'s own
`/plays` call, the source of the 0-0 half proof. The checks
`grade.postmortem_written` and `grade.reference_cache_populated` went with
them; the 2026-09 failure modes below are kept as history.

### When sunday is degraded or failed

1. `sunday.fg_snapshot_today` missed -> no full-game capture today. Odds API
   outage or credits at zero; re-dispatch with `force=true` when it is back.
2. `sunday.predictions_today` missed -> the board was not scored today. Since
   B-SERVE (2026-09-22) `weekly_update.py` FAILS a scoring run whose target
   rows are mostly NaN on a training column; the step log names the columns.
   Do not lower the guard -- fix the frame.
3. `sunday.derived_lines_posted` missed -> `post_derived_lines.py` wrote no
   rows (it exits 1 on zero); the display-only derived lines are missing from
   the board, the model rows are fine.
3b. `sunday.model_run_recorded` missed -> the board was scored but the refit's
   run-log row (`model_runs`, note `weekly refit`: inputs, intercept, train
   rows, frame fingerprint) was not written; the step log carries
   `[model_runs] weekly refit NOT recorded: ...`. The predictions are fine; the
   record of what produced them is missing.
4. `sunday.pace_coverage` / `sunday.weather_coverage` missed -> TeamRankings or
   Open-Meteo was down (both steps are `continue-on-error`). The week scored
   with pace/weather NaN for the uncovered teams; re-run the enrichment step
   by hand when the source is back, then `weekly_update.py`.
5. `sunday.reference_cache_populated` -> as grade.

### The full-game close step (since 2026-10-06)

The `1h_close` run also calls `scripts/poll_full_game.py --markets totals,spreads,h2h --regions
us,us2,us_ex --kickoff-within-min 180 --allow-empty` after a successful 1H close poll: one bulk
Odds API call (9 credits a tick since 2026-10-07: three markets over three regions) captures or
re-seens (`last_seen_at`) every book's full-game total, spread and moneyline for games kicking
off inside `REAL_FG_CLOSE_WINDOW_H` (3 h). It exists so the full-game reference ledger
(`results.model_version='market_fg'`, `scripts/grade.py::_closings_fg`, now windowed at 3 h)
and the H-FG-U-R / H-FG-O-R retrospectives grade at a REAL close -- before this, 9 of 380 graded
2026 games had a full-game snapshot inside 3 h. The step is `continue-on-error` and carries no
contract check (2026-10-14: the Saturday close-coverage gauge covers the 1H side; a full-game
check is not planned while the judge's full-game reads are secondary).

### When monday is degraded (or failed)

1. `monday.positions_written` missed (FAILED, email) -> the Monday run did not leave one
   `arm_positions` row per registered hypothesis (the six arms from `scripts/protocol_position.py
   --write`, which also writes the exploratory H-ARM-EVP row; H-PRICE-HR from `scripts/pricing_check.py
   --write`). Read the run log for the step that
   failed; re-run with `gh workflow run pricing_monday.yml --ref main` -- a second run on the same
   Monday rewrites the same rows (unique on hypothesis + read date), nothing double-counts. Until it
   lands, the Research page shows the previous read with its date and the board's health banner
   names this check; past eight days the cards read "outdated".
2. `monday.pricing_report_written` missed -> `pricing_check.py` wrote no report file; the positions
   may still be fine. Same re-run.

### When lines_watch is degraded

1. `lines_watch.close_polled` missed -> the close poll found events in its
   `CLOSE_LOOKAHEAD_MIN` window (360 minutes on Saturday ticks whose UTC hour is divisible by
   3 since 2026-10-18, 120 on the others and on weeknights) and polled none of them (credit
   floor, API error). The
   next slot re-covers each game; if it repeats, check Odds credits.
2. `lines_watch.hr_rows_touched` missed -> events were polled and no Hard Rock
   1H row was written or re-seen: the `hardrockbet` key drifted or Hard Rock
   has stopped posting the market. `sources/odds.py` and the `hr_rows=` line.
3. `lines_watch.fg_close_polled` missed -> the close poll found events but the full-game
   close step (`poll_full_game.py`, continue-on-error) left no status file, said it was
   incomplete (`reason`: `credit_floor`, `db_unreachable`, `no_match`), or wrote and re-saw
   no `full_game_total` row since the run began. The two full-game arms then read
   `stale_close`; read that step's log and the Odds credits.
4. `lines_watch.close_gauge_written` missed -> `poll_lines.py` polled events
   but did not write `last_close_capture_at`; the gauge write is best-effort
   (`ops.record_gauge` never raises), so the log carries `[ops] gauge ... not
   recorded`.
5. `lines_watch.close_window_coverage` missed (Saturday runs only) -> fewer
   than 80% of that Saturday's kicked-off Hard-Rock-priced games had a
   first-half snapshot inside the 2-hour close window: the close slots are not
   firing (GitHub fired 3 of 18 in 2026 week 4). Check `last_dispatch_lines-close`
   is advancing hourly (the Vercel backup, `web/vercel.json`), then GitHub's
   cron. The same share is the board's `close_coverage` gauge all week.

There is no failed-severity check here: a slot that fires and polls nothing
is normal (the free `/events` pre-check skips most of them), a run that never
fired cannot email, and a dead week of close slots is what the board's `close`
gauge warning covers.

### When weekly is degraded or failed

The Sunday report (since 2026-10-20, final-2026 plan D4) writes `docs/reads/<season>-wNN.md`, commits it
to main and opens the week's issue; every check is `failed` severity, so a red run emails. Read the run's
`HEALTH:` line, then:

1. `weekly.report_written` -> `scripts/weekly_report.py` raised before writing the page (its traceback is
   in the "Write the report" step; a database read is the usual cause). Fix it, then dispatch
   `weekly_report.yml` by hand; nothing else depends on the page.
2. `weekly.committed` -> the push to main lost three rebase races or was refused. The page is still in the
   run's `weekly-report-<run id>` artifact; dispatch again (an unchanged page commits nothing).
3. `weekly.issue_opened` -> `gh issue create` failed (permissions or the API). The page is committed;
   dispatch again and the rerun comments on the week's issue if one exists.

A dispatch with `dry_run` writes the page as an artifact and no verdict.

### When archive is degraded or failed

The archive queue (since 2026-10-20, final-2026 plan PR-C10) runs `auto` daily at 07Z; it spends only in the
last four days before the credit reset. Read the run's `HEALTH:` line and its `archive-<run id>` artifact
(`archive_status.json`: window, live balance, allowance, each item's state), then:

1. `archive.ran` -> the auto step raised before writing its status (the traceback is in "Run the archive
   command"; an Odds API error or a database read). Credits do not roll over: inside the window, fix and
   dispatch `archive.yml` with item `auto` the same day.
2. `archive.within_allowance` -> it spent outside the window, or more than the allowance it computed. Stop
   the schedule (disable the workflow), read `odds_spend` for job `archive`, and check the balance against the
   recurring need before anything else runs.
3. `archive.items_ok` (degraded) -> one item raised and the queue went on. Its message is in the status file;
   the item resumes where it stopped on the next run (bought waves are read back from the ledger).

### When digest is degraded or failed

The digest (since 2026-10-20, final-2026 plan D4) is the one job whose red run is the point: it fails,
and GitHub emails, when anything below misses. Every check is `failed` severity; it is silent only
when all hold. Read the run's `HEALTH:` line, then:

1. `digest.jobs_fresh` -> a job wrote no verdict within its cadence (card 96 h, grade 30 h, sunday,
   monday, lines_watch 8 days): its cron and its Vercel tick both missed, or GitHub refused the run.
   `gh run list --workflow <file>` (a hand run from another session counts); re-dispatch it.
2. `digest.jobs_not_failed` -> a job's newest verdict is `failed` and the run behind it was not a
   cancelled one that a later success superseded. Open that job's runbook above.
3. `digest.grade_recent` -> grading has not completed in 30 h: `grade.yml` (the four-hour guard skips
   a hand run inside four hours of a graded one).
4. `digest.saturday_closes` -> the last Saturday's close coverage is under 90% or the gauge does not
   name it: the Saturday close poll missed games (lines_watch runbook). Not read on Saturday itself
   (to Sunday 08Z), while the close polls are still rewriting the gauge.
5. `digest.odds_budget` -> the balance no longer covers the recurring need to the reset above the floor:
   `python scripts/credit_plan.py report`; stop optional pulls before closes are at risk.
6. `digest.cfbd_calls` -> 300 or fewer CFBD calls left (the free tier is 1,000 a month from Nov 5): a hand
   season reload or a leak; nothing optional should call CFBD.
7. `digest.positions_fresh` -> no Monday read in 8 days: `gh workflow run pricing_monday.yml --ref main`.
8. `digest.arms_logging` -> on a Sunday or Monday, no registered arm logged a paper pick in 7 days: the
   card builds ran without logging (card runbook, `card.paper_logged_iff_window`).
9. `digest.ledger_matches_gauge` -> the balance fell by more than the `odds_spend` ledger explains: a
   caller is spending outside the client (`tests/test_odds_spend_ledger.py` should have caught it).

## The grace-window caveat

The health step runs on `always()`, so it reports on a red run too. It cannot
report on a run GitHub cancelled: a job timeout only lets `always()` steps run
inside a short grace window, and a runner lost mid-job runs nothing. For the
card that case is covered by the board's missed-build banner; for grade by
the stale-results banner and the `dispatch:grade` gauge; for sunday by the
Sunday probe writing no prediction row (the next tick scores).

## Regenerating the block below

    PYTHONPATH=. python -m beatvegas.health --render-md docs/HEALTH.md

`tests/test_docs_parity.py` fails when the block and `render_contracts()`
disagree.

<!-- contracts:begin -->
<!-- Generated by `python -m beatvegas.health --render-md docs/HEALTH.md`. Do not edit by hand. -->

Parameters: `HR_PRICED_FLOOR = 10`, `STALE_AFTER_HOURS = 18`, `PACE_COVERAGE_MIN = 0.8`, `WX_COVERAGE_MIN = 0.8`, `CLOSE_COVERAGE_MIN = 0.8`, `REFERENCE_CACHE_MIN_BYTES = 1024`

### card

- Workflow: `.github/workflows/card.yml`
- Window: tue_pm / thu_pm / fri_pm 3:45-5:15pm ET, sat_am 7:45-9:15am ET (beatvegas/ci.py)
- Artifacts: `cards row`, `manual_picks paper rows (scheduled slots)`, `odds_snapshots 1H sweep`
- Inputs (env, beside `SKIPPED` and `RUN_STARTED_AT`): `SLOT`, `SEASON`, `WEEK`, `OUTCOME_SWEEP`, `OUTCOME_PREVIEW`, `OUTCOME_BUILD`

| Check | Severity | Positive fact |
|---|---|---|
| `card.row_this_run` | failed | a `cards` row for (SEASON, WEEK) with built_at >= RUN_STARTED_AT whose payload.slot == SLOT |
| `card.status_clean` | degraded | that row's payload.status is the slot's clean status (ci.CARD_STATUS_BY_SLOT) and payload.degraded is empty |
| `card.hr_priced_floor` | degraded | items with a Hard Rock 1H line >= HR_PRICED_FLOOR [10] |
| `card.paper_logged_iff_window` | degraded | scheduled slot: every qualifying item inside the slot's paper window has a paper pick; manual: zero paper picks placed since RUN_STARTED_AT |
| `card.sweep_reached_slate` | degraded | the sweep status file says complete and events_polled >= events_in_window (a missing file is a miss unless the sweep step was skipped) |

Failure modes on record:

- **2026-09-10** -- a mid-sweep Odds API 5xx killed the job before build_card ran: no card at all. The sweep now continues on error; a partial sweep ships the card degraded. Caught by: `card.row_this_run`, `card.status_clean`, `card.sweep_reached_slate`.
- **2026-09-21** -- the first build of the week (nothing cached, 57 fresh previews) hit the 15-minute job timeout; GitHub reported `cancelled` and no card shipped. The timeout is 30 now. A cancelled job only runs its always() steps inside GitHub's grace window, so this step may never run on a timeout -- the board's buildStatus (missed build) is the check that always fires. Caught by: `card.row_this_run`.
- **2026-09-13** -- the paper window gave each slot the gap to the next build, so Friday's three clean BETs were never logged and the Saturday build claimed the whole slate; and a `manual` refresh logging paper picks would freeze the week at that moment's lines. Caught by: `card.paper_logged_iff_window`.
- **2026-09-09** -- a Vercel tick outside its window, or a GitHub cron running the build instead of the Vercel dispatch: invisible in the runs API. The board's `dispatch:<job>` warning covers it; the note carries `event=` so the trigger is on record. Caught by: info only.
- **2026-09-20** -- `early_season` held 10 games on the Friday card (an FCS opener leaves a team at 1 FBS game). Correct behaviour, so it is info (`early_season_held=N`), never a miss. Caught by: info only.
- **2026-09-25** -- the Odds API served Hard Rock alternate lines (2-3 pts off the field at -145..-160) as its 1H total; 20 passed the general -160 price bar and 12 paper picks were logged on them. The card now keeps them out of every gate (`devig.is_hr_rung`); a count is info (`hr_alt_ignored=N`), never a miss. Caught by: info only.

### grade

- Workflow: `.github/workflows/grade.yml`
- Window: daily, 10:30Z cron plus the Vercel dispatch, and a 16:00Z cron Sun-Fri; skipped when a run completed in the last 4 h
- Artifacts: `games finals`, `results / manual_picks graded`, `game_records graded`, `last_grade_completed_at gauge`
- Inputs (env, beside `SKIPPED` and `RUN_STARTED_AT`): `SEASON`, `OUTCOME_BACKFILL`, `OUTCOME_ESPN`

| Check | Severity | Positive fact |
|---|---|---|
| `grade.completed_this_run` | failed | the `last_grade_completed_at` gauge was written after RUN_STARTED_AT (the fatal grading steps all ran) |
| `grade.finals_landed` | degraded | zero rated games (a game_records row) in SEASON with home_points NULL that kicked off more than STALE_AFTER_HOURS [18] hours ago -- the board's stale-results predicate |
| `grade.records_graded` | degraded | zero game_records in SEASON with graded_at NULL whose game has a first_half_total |
| `grade.picks_graded` | degraded | zero manual_picks in SEASON with graded false/NULL whose game has a first_half_total |

Failure modes on record:

- **2026-09-12** -- CFBD returned 429 on the first, unguarded call and grade.yml failed four runs straight; week 2 sat with finals for 14 of 303 games and 0 of 31 picks graded for two days. Caught by: `grade.completed_this_run`, `grade.finals_landed`, `grade.picks_graded`.
- **2026-09-16** -- the CFBD reference cache had saved an EMPTY payload all season (the first job of each ISO week made no CFBD calls), so every later run re-fetched ~22 reference calls against a 3,000-call month. (grade.yml stopped restoring the cache 2026-10-18, final-2026 PR-09; `sunday.reference_cache_populated` keeps the check.) Caught by: info only.
- **2026-09-22** -- the four-hour probe matched scope = 'live' while the rows are written as live_<season>, so it matched nothing and never skipped. The check compared the exact scope string. (The post-mortem step and its check were retired 2026-10-18, final-2026 PR-09; the probe reads the completed-grade gauge.) Caught by: info only.
- **2026-09-20** -- fifteen 0-0 first halves on file looked like the ESPN false zero and were all real (PR #176). Zero halves graded this run are counted as info (`zero_halves_graded=N`), never judged. Caught by: info only.
- **2026-10-15** -- the writer stored App State-Old Dominion's proven 0-0 half (full box reconciled, 2026-10-10) and the grader refused every line-score 0, so the record sat ungraded for five days. The writer now labels a proven scoreless half `linescores_verified` and the grader trusts that label and `pbp` only (`grading.ZERO_PROVEN_SOURCES`; tests/test_zero_half_parity.py). Caught by: `grade.records_graded`.

### sunday

- Workflow: `.github/workflows/sunday.yml`
- Window: Sunday 18:00Z / 19:00Z / 20:30Z crons plus the Vercel dispatch, 1-5pm ET; one Vercel catch-up at 23Z (window to 8pm ET, roadmap v2.2) dispatches only when no run since 1pm succeeded
- Artifacts: `odds_snapshots full_game_total`, `team_tempo (season, week)`, `weather rows`, `predictions (model + derived_lines)`
- Inputs (env, beside `SKIPPED` and `RUN_STARTED_AT`): `SEASON`, `WEEK`, `NEED_CAPTURE`, `NEED_SCORE`, `OUTCOME_PACE`, `OUTCOME_WEATHER`

| Check | Severity | Positive fact |
|---|---|---|
| `sunday.fg_snapshot_today` | failed | at least one odds_snapshots row with market full_game_total captured since ET midnight |
| `sunday.predictions_today` | failed | at least one predictions row for the week's games with model_version != derived_lines created since ET midnight |
| `sunday.derived_lines_posted` | degraded | at least one predictions row for the week's games with model_version == derived_lines created since ET midnight |
| `sunday.fg_shadow_scored` | degraded | at least one predictions row for the week's games with model_version == bv_fg_v1 (H-ARM-FGU's input, scripts/fg_shadow.py) created since ET midnight |
| `sunday.model_run_recorded` | degraded | a model_runs row noted `weekly refit` whose metrics name SEASON and WEEK, created since ET midnight (inputs, intercept, train rows, frame fingerprint) |
| `sunday.pace_coverage` | degraded | share of the week's FBS slate teams with a team_tempo(SEASON, WEEK) row carrying seconds_per_play >= PACE_COVERAGE_MIN [0.8] |
| `sunday.weather_coverage` | degraded | share of the week's FBS games with a weather row >= WX_COVERAGE_MIN [0.8] |
| `sunday.reference_cache_populated` | degraded | the five CFBD reference files for SEASON-1 exist in data/cache/ at > REFERENCE_CACHE_MIN_BYTES [1024] bytes |

Failure modes on record:

- **2026-09-22** -- B-SERVE: the live model scored every upcoming game with 57 of 115 inputs NaN. weekly_update.py now FAILS a scoring run whose target rows are >90% NaN on a column training has, which leaves no prediction row for the day. Caught by: `sunday.predictions_today`.
- **2026-09-13** -- four Sunday ticks each re-ran the whole job for one capture (~1,150 Open-Meteo calls). The need_capture / need_score probes fixed the spend; the checks read the day's facts, not this run's, so a correctly skipped tick still passes. Caught by: `sunday.fg_snapshot_today`, `sunday.predictions_today`.
- **2026-09-16** -- the CFBD reference cache saved an empty payload all season. Caught by: `sunday.reference_cache_populated`.
- **2026-09-28** -- the refit left no record of itself: confirming the week-5 refit ran on the corrected 58 inputs meant reading the run log, while model_runs held only retrain.py's June rows. Caught by: `sunday.model_run_recorded`.

### monday

- Workflow: `.github/workflows/pricing_monday.yml`
- Window: Monday: the Vercel `pricing-monday` tick at 12Z (15Z retry, 18Z catch-up; 6am-3pm ET) plus the 12:30Z GitHub backup cron; a second run on the same Monday rewrites the same arm_positions rows
- Artifacts: `arm_positions rows (one per registered hypothesis, this read date)`, `pricing-report artifact + run Summary`
- Inputs (env, beside `SKIPPED` and `RUN_STARTED_AT`): 

| Check | Severity | Positive fact |
|---|---|---|
| `monday.positions_written` | failed | one arm_positions row per registered hypothesis (protocol.ARMS + H-PRICE-HR + the exploratory H-ARM-EVP) with read_at >= RUN_STARTED_AT |
| `monday.pricing_report_written` | degraded | a reports/pricing_check_<stamp>.md written since RUN_STARTED_AT |

Failure modes on record:

- **2026-10-14** -- Before the stored positions existed, the arms' Monday read lived only in a study.yml artifact and the site could not show it; a failed or missing Monday run was invisible. The site, the Monday read and the January review now read the same arm_positions row, and this contract is how a missing read surfaces. Caught by: `monday.positions_written`.

### lines_watch

- Workflow: `.github/workflows/lines_watch.yml`
- Window: every 30 min in the kickoff windows (1h_close) plus one Vercel dispatch per UTC hour on Saturday; the free /events pre-check and the poll both look CLOSE_LOOKAHEAD_MIN ahead (360 min on Saturday ticks whose UTC hour is divisible by 3 since 2026-10-18, 120 on the others and on weeknights)
- Artifacts: `odds_snapshots 1H rows or last_seen_at stamps`, `last_close_capture_at gauge`
- Inputs (env, beside `SKIPPED` and `RUN_STARTED_AT`): `MARKET`, `OUTCOME_FG`

| Check | Severity | Positive fact |
|---|---|---|
| `lines_watch.close_polled` | degraded | the close status file exists and says events_polled > 0, or events_in_window == 0 |
| `lines_watch.hr_rows_touched` | degraded | when events were polled: an odds_snapshots row with book hardrockbet and market 1H_total has captured_at or last_seen_at >= RUN_STARTED_AT |
| `lines_watch.fg_close_polled` | degraded | when the close poll found events in its window and the full-game step ran: the full-game status file exists and says complete, and (if it found an event inside its own window) an odds_snapshots row with market full_game_total has captured_at or last_seen_at >= RUN_STARTED_AT |
| `lines_watch.close_gauge_written` | degraded | when events were polled: the `last_close_capture_at` gauge was written after RUN_STARTED_AT |
| `lines_watch.close_window_coverage` | degraded | on a Saturday (ET) run: share of that Saturday's kicked-off Hard-Rock-priced games with a 1H_total snapshot captured or re-seen inside REAL_1H_CLOSE_WINDOW_H of kickoff >= CLOSE_COVERAGE_MIN [0.8] |

Failure modes on record:

- **2026-08-28** -- GitHub's cron fired 2 of 19 scheduled close slots (and 3 of 18 Saturday slots in 2026 week 4, leaving 18 of 57 Hard-Rock-priced games with a close inside the window while the `close` gauge stayed fresh); since 2026-09-28 the Vercel `lines-close` dispatch is the cover, `close_window_coverage` and the board's `close_coverage` gauge are the alarm, and the board's `close` gauge (CLOSE_CAPTURE_MAX_AGE_H) still catches a dead week. No check here is failed-severity: the run that never fired cannot email. Caught by: `lines_watch.close_polled`, `lines_watch.close_gauge_written`, `lines_watch.close_window_coverage`.
- **2026-09-09** -- a Hard Rock book key drift would make a close poll write no hardrockbet row while spending every credit; poll_lines warns, this makes it a verdict. Caught by: `lines_watch.hr_rows_touched`.
- **2026-10-18** -- the full-game close step is continue-on-error and exits 0 on an empty or credit-floor-skipped pull, so a step that failed silently left every run green while the two full-game arms (H-ARM-FGU, H-ARM-WXFG) accumulated stale_close exclusions; the status file and the step outcome now make it a verdict (final-2026 plan PR-05). Caught by: `lines_watch.fg_close_polled`.

### digest

- Workflow: `.github/workflows/digest.yml`
- Window: daily: the Vercel `digest` tick (13Z EDT / 14Z EST, 8:00-10:59am ET) plus the 13:30Z GitHub backup cron; silent when every check passes, a failed run (GitHub's email) when any misses; skipped from three days after the season's last kickoff
- Artifacts: `last_health_digest gauge (the verdict and the misses)`
- Inputs (env, beside `SKIPPED` and `RUN_STARTED_AT`): 

| Check | Severity | Positive fact |
|---|---|---|
| `digest.jobs_fresh` | failed | every scheduled job's last_health_<job> gauge exists and was written within its cadence (card 96 h, grade 30 h, sunday / monday / lines_watch 8 d) |
| `digest.jobs_not_failed` | failed | no job's newest verdict is failed, unless its run was cancelled and a later run of the same workflow succeeded |
| `digest.grade_recent` | failed | last_grade_completed_at was written within the last 30 h |
| `digest.saturday_closes` | failed | the close-coverage gauge names the most recent in-season Saturday and reads 90% or more |
| `digest.odds_budget` | failed | the Odds API balance covers the recurring need to the reset above the floor (credit_plan.allowance >= 0) |
| `digest.cfbd_calls` | failed | more than 300 CFBD calls remain this month |
| `digest.positions_fresh` | failed | the newest arm_positions read is within the last 8 days |
| `digest.arms_logging` | failed | on Sundays and Mondays, the registered arms logged at least one paper pick in the last 7 days |
| `digest.ledger_matches_gauge` | failed | the odds_spend ledger accounts for the balance's fall since the last week (within max(25, 5%)) |

Failure modes on record:

- **2026-10-18** -- A hand grade dispatch was cancelled in the neon-writers queue; its health step wrote failed and the banner read FAILED for a day while nothing was missing. Nothing emailed and nothing distinguished it from a real failure. The digest reads the run's conclusion and excuses a cancelled run that a later success superseded. Caught by: `digest.jobs_not_failed`.
- **2026-09-22** -- GitHub's billing stop refused every job for hours; no run wrote a verdict, so no contract could fail and no email went out (the gauges simply stopped moving). A verdict past its cadence is now a miss. Caught by: `digest.jobs_fresh`, `digest.grade_recent`.

### weekly

- Workflow: `.github/workflows/weekly_report.yml`
- Window: Sunday: the Vercel `weekly-report` tick (15Z EDT / 16Z EST, 10:30am-12:59pm ET) plus the 16:30Z GitHub backup cron, which stands down when a report landed in the last 20 hours; a dry run writes no verdict
- Artifacts: `docs/reads/<season>-wNN.md committed to main`, `a GitHub issue 'Week N report — <status>' (a rerun comments on it)`
- Inputs (env, beside `SKIPPED` and `RUN_STARTED_AT`): `OUTCOME_REPORT`, `OUTCOME_COMMIT`, `OUTCOME_ISSUE`

| Check | Severity | Positive fact |
|---|---|---|
| `weekly.report_written` | failed | the report step wrote its page and its status file names it |
| `weekly.committed` | failed | the page was committed and pushed to main (or was already there unchanged) |
| `weekly.issue_opened` | failed | this week's issue was opened, or commented on for a rerun |

Failure modes on record:

- **2026-10-20** -- Before the report existed the week's record was rows in arm_positions and a chat skill someone had to run; a week nobody opened Claude left no record. The page and the issue are now the record, and a run that wrote neither fails. Caught by: `weekly.report_written`, `weekly.committed`, `weekly.issue_opened`.

### archive

- Workflow: `.github/workflows/archive.yml`
- Window: daily: the 07:00Z GitHub cron plus the Vercel `archive` entry (07Z); spends only inside the last 4 days before `odds_cycle_reset_at` once the last Saturday's closes are in; status, probes and dry runs write no verdict
- Artifacts: `research_snapshots rows (purpose archive_*, source historical), one odds_spend row per call`, `the run's archive_status.json (artifact): window, live balance, allowance, each item's state`
- Inputs (env, beside `SKIPPED` and `RUN_STARTED_AT`): `OUTCOME_ARCHIVE`

| Check | Severity | Positive fact |
|---|---|---|
| `archive.ran` | failed | the auto step finished and wrote its status file |
| `archive.within_allowance` | failed | spent nothing outside the window, and inside it no more than the controller's allowance |
| `archive.items_ok` | degraded | no archive item raised (one item's failure never stops the queue) |

Failure modes on record:

- **2026-10-20** -- Credits do not roll over: an archive window that passes unnoticed (a missed run, an item that raises) loses what the cycle had left, and a run that spends from a stale gauge can eat the recurring need. The auto run reads the live balance, and its verdict names what it spent against the allowance. Caught by: `archive.ran`, `archive.within_allowance`.

<!-- contracts:end -->
