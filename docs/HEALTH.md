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

`web/lib/boardHealth.ts` reads the four keys (`HEALTH_GAUGE_PREFIX` +
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
   (`grade.py`, `pick.py grade`, `grade_records.py`) failed. The run is red;
   read that step's traceback. On CFBD 429/quota the scores fallback (ESPN)
   should still have landed finals -- check `grade.finals_landed`.
2. `grade.finals_landed` missed -> rated games kicked off > 18 h ago with no
   final. Both score sources failed or the games are genuinely late. The
   board's stale-results banner says the same thing; `backfill_scores_espn.py
   --days-back 4` by hand fixes a one-off.
3. `grade.records_graded` / `grade.picks_graded` missed -> played games with a
   first-half total whose record or pick is still ungraded. Usually the
   trust rule holding a 0-0 half without proof (`etl/first_half.py`): look at
   the game's line scores before touching anything.
4. `grade.postmortem_written` missed -> `post_mortem.py --write` did not write
   the live scope this run; it is `continue-on-error`, so the run is green.
   Re-run it by hand or re-dispatch `grade.yml`.
5. `grade.reference_cache_populated` missed -> the CFBD reference files for the
   prior season are absent or empty in `data/cache/`. The feature build
   fetched nothing (quota, 429) or the weekly cache key is holding an empty
   payload; `docs/OPS_ACCOUNTS.md` for the CFBD tier.

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
4. `sunday.pace_coverage` / `sunday.weather_coverage` missed -> TeamRankings or
   Open-Meteo was down (both steps are `continue-on-error`). The week scored
   with pace/weather NaN for the uncovered teams; re-run the enrichment step
   by hand when the source is back, then `weekly_update.py`.
5. `sunday.reference_cache_populated` -> as grade.

### When lines_watch is degraded

1. `lines_watch.close_polled` missed -> the close poll found events in its
   75-minute window and polled none of them (credit floor, API error). The
   next slot re-covers each game; if it repeats, check Odds credits.
2. `lines_watch.hr_rows_touched` missed -> events were polled and no Hard Rock
   1H row was written or re-seen: the `hardrockbet` key drifted or Hard Rock
   has stopped posting the market. `sources/odds.py` and the `hr_rows=` line.
3. `lines_watch.close_gauge_written` missed -> `poll_lines.py` polled events
   but did not write `last_close_capture_at`; the gauge write is best-effort
   (`ops.record_gauge` never raises), so the log carries `[ops] gauge ... not
   recorded`.

There is no failed-severity check here: a slot that fires and polls nothing
is normal (the free `/events` pre-check skips most of them), and a dead run
of close slots is what the board's `close` gauge warning covers.

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

Parameters: `HR_PRICED_FLOOR = 10`, `STALE_AFTER_HOURS = 18`, `PACE_COVERAGE_MIN = 0.8`, `WX_COVERAGE_MIN = 0.8`, `REFERENCE_CACHE_MIN_BYTES = 1024`

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
- Window: daily, 10:30Z and 16:00Z crons plus the Vercel dispatch; skipped when a run completed in the last 4 h
- Artifacts: `games finals`, `results / manual_picks graded`, `game_records graded`, `postmortem_runs live_<season>`, `last_grade_completed_at gauge`
- Inputs (env, beside `SKIPPED` and `RUN_STARTED_AT`): `SEASON`, `OUTCOME_BACKFILL`, `OUTCOME_ESPN`, `OUTCOME_PBP`, `OUTCOME_LEDGER`, `OUTCOME_PM`

| Check | Severity | Positive fact |
|---|---|---|
| `grade.completed_this_run` | failed | the `last_grade_completed_at` gauge was written after RUN_STARTED_AT (the fatal grading steps all ran) |
| `grade.finals_landed` | degraded | zero rated games (a game_records row) in SEASON with home_points NULL that kicked off more than STALE_AFTER_HOURS [18] hours ago -- the board's stale-results predicate |
| `grade.records_graded` | degraded | zero game_records in SEASON with graded_at NULL whose game has a first_half_total |
| `grade.picks_graded` | degraded | zero manual_picks in SEASON with graded false/NULL whose game has a first_half_total |
| `grade.postmortem_written` | degraded | a postmortem_runs row with scope == live_<SEASON> and computed_at >= RUN_STARTED_AT |
| `grade.reference_cache_populated` | degraded | the five CFBD reference files (sp/talent/roster/returning/adv) for SEASON-1 exist in data/cache/ at > REFERENCE_CACHE_MIN_BYTES [1024] bytes |

Failure modes on record:

- **2026-09-12** -- CFBD returned 429 on the first, unguarded call and grade.yml failed four runs straight; week 2 sat with finals for 14 of 303 games and 0 of 31 picks graded for two days. Caught by: `grade.completed_this_run`, `grade.finals_landed`, `grade.picks_graded`.
- **2026-09-16** -- the CFBD reference cache had saved an EMPTY payload all season (the first job of each ISO week made no CFBD calls), so every later run re-fetched ~22 reference calls against a 3,000-call month. Caught by: `grade.reference_cache_populated`.
- **2026-09-22** -- the four-hour probe matched scope = 'live' while the rows are written as live_<season>, so it matched nothing and never skipped. The check compares the exact scope string. Caught by: `grade.postmortem_written`.
- **2026-09-20** -- fifteen 0-0 first halves on file looked like the ESPN false zero and were all real (PR #176). Zero halves graded this run are counted as info (`zero_halves_graded=N`), never judged. Caught by: info only.

### sunday

- Workflow: `.github/workflows/sunday.yml`
- Window: Sunday 18:00Z / 19:00Z / 20:30Z crons plus the Vercel dispatch, 1-5pm ET
- Artifacts: `odds_snapshots full_game_total`, `team_tempo (season, week)`, `weather rows`, `predictions (model + derived_lines)`
- Inputs (env, beside `SKIPPED` and `RUN_STARTED_AT`): `SEASON`, `WEEK`, `NEED_CAPTURE`, `NEED_SCORE`, `OUTCOME_PACE`, `OUTCOME_WEATHER`

| Check | Severity | Positive fact |
|---|---|---|
| `sunday.fg_snapshot_today` | failed | at least one odds_snapshots row with market full_game_total captured since ET midnight |
| `sunday.predictions_today` | failed | at least one predictions row for the week's games with model_version != derived_lines created since ET midnight |
| `sunday.derived_lines_posted` | degraded | at least one predictions row for the week's games with model_version == derived_lines created since ET midnight |
| `sunday.pace_coverage` | degraded | share of the week's FBS slate teams with a team_tempo(SEASON, WEEK) row carrying seconds_per_play >= PACE_COVERAGE_MIN [0.8] |
| `sunday.weather_coverage` | degraded | share of the week's FBS games with a weather row >= WX_COVERAGE_MIN [0.8] |
| `sunday.reference_cache_populated` | degraded | the five CFBD reference files for SEASON-1 exist in data/cache/ at > REFERENCE_CACHE_MIN_BYTES [1024] bytes |

Failure modes on record:

- **2026-09-22** -- B-SERVE: the live model scored every upcoming game with 57 of 115 inputs NaN. weekly_update.py now FAILS a scoring run whose target rows are >90% NaN on a column training has, which leaves no prediction row for the day. Caught by: `sunday.predictions_today`.
- **2026-09-13** -- four Sunday ticks each re-ran the whole job for one capture (~1,150 Open-Meteo calls). The need_capture / need_score probes fixed the spend; the checks read the day's facts, not this run's, so a correctly skipped tick still passes. Caught by: `sunday.fg_snapshot_today`, `sunday.predictions_today`.
- **2026-09-16** -- the CFBD reference cache saved an empty payload all season. Caught by: `sunday.reference_cache_populated`.

### lines_watch

- Workflow: `.github/workflows/lines_watch.yml`
- Window: every 30 min in the kickoff windows (1h_close); the free /events pre-check skips a slot with nothing kicking off in 75 min
- Artifacts: `odds_snapshots 1H rows or last_seen_at stamps`, `last_close_capture_at gauge`
- Inputs (env, beside `SKIPPED` and `RUN_STARTED_AT`): `MARKET`

| Check | Severity | Positive fact |
|---|---|---|
| `lines_watch.close_polled` | degraded | the close status file exists and says events_polled > 0, or events_in_window == 0 |
| `lines_watch.hr_rows_touched` | degraded | when events were polled: an odds_snapshots row with book hardrockbet and market 1H_total has captured_at or last_seen_at >= RUN_STARTED_AT |
| `lines_watch.close_gauge_written` | degraded | when events were polled: the `last_close_capture_at` gauge was written after RUN_STARTED_AT |

Failure modes on record:

- **2026-08-28** -- GitHub's cron fired 2 of 19 scheduled close slots; a dead run of them is what the board's `close` gauge warning (CLOSE_CAPTURE_MAX_AGE_H) covers, which is why no check here is failed-severity. Caught by: `lines_watch.close_polled`, `lines_watch.close_gauge_written`.
- **2026-09-09** -- a Hard Rock book key drift would make a close poll write no hardrockbet row while spending every credit; poll_lines warns, this makes it a verdict. Caught by: `lines_watch.hr_rows_touched`.

<!-- contracts:end -->
