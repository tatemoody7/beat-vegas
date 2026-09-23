# The measurement harness

`beatvegas/backtest/harness.py`, driven by `scripts/harness_report.py`, dispatched through
`study.yml`. One shape of question, answered the same way every time, for every future
model gate: given the champion's scorer and zero or more candidates with the SAME contract
(`(train_played, target) -> bv_line per target row`, the contract of
`model.bv_line.bv_line_for_slate`), how do they do on each held-out season?

It **measures**. It never chooses a threshold, a feature or a rule; it never edits
`beatvegas/model/score.py`, a `docs/HYPOTHESES.md` row or a database table, and it writes
no `model_runs` row. The registry criterion is quoted verbatim in the report and, where a
criterion FUNCTION is declared, applied — the verdict is a sentence, never a change.

## What it measures

Per test season, and pooled:

- **Walk-forward.** Each test season is scored by one model per arm fitted on every played
  prior season (`season < s`), which is how `score_slate` trains the live champion. The
  training pool is `training_frame(apply_min_games(frame, min_games_train))` — no trust
  filter, exactly the rows `score_slate` hands the model. The score pool is the test
  seasons' played rows at `min_games_score` whose 1H total is trusted
  (`grading.trusted_first_half_total`).
- **Real closes only.** A game is graded when a consensus 1H close exists inside exactly
  `lines.REAL_1H_CLOSE_WINDOW_H` (2 h) of kickoff (`snapshots.consensus_closes`). No proxy
  line — `proxy_line`, `line_flat`, `line_step`, `full_game_total` — is ever read; their
  presence in the graded frame is refused. A test season with zero real closes raises
  `GateNotEvaluable`: the report says NOT EVALUABLE, the script exits 0.
- **Accuracy.** MAE and bias per arm, bias in both signs labelled (`actual − pred` and
  `pred − actual`), beside the market's own MAE on the same rows.
- **Selection.** The champion's rule: the top `PCT_SHARE` (20%) of each season-week slate by
  gap (`model.score.slate_bar`, the k-th largest gap, k = max(1, round(0.2·N))); a gap ≤ 0
  never qualifies, ties at the bar all qualify, an empty slate takes `BET_GAP_PTS` as the
  fallback. The share clearing the retired constant bar is reported beside it. The weekly cap
  (`postmortem.weekly_cap`, top 5, ties by kickoff then game id) is applied to the qualifying
  subset.
- **Records.** W-L-P, hit rate, Wilson interval, units and ROI for `all` / `pct` / `cap`, the
  under at a flat price (default −110). Pushes are staked and excluded from the hit rate.
- **The money population.** Every record is split at `MIN_GAMES_FOR_REAL_MONEY` (2 games
  played by both teams) so the population real money may touch reads on its own.
- **The Hard Rock basis.** Where the book closed the game (2026+), the same rows are graded
  at Hard Rock's own strict-centred close (`snapshots.hr_closes`) and its own under price
  (`snapshots.hr_close_prices`; −110 when the close is unpriced), beside the consensus.
- **Line value.** For an arm's qualifying picks that have a decision line: favourable CLV =
  `−(close − bet)` (`harness.favourable_clv`, the one sign flip; +1.0 means the market came a
  point toward us), mean and paired bootstrap against zero, with `n_with_decision_line /
  n_picks` stated.
- **Comparisons.** Each candidate against the incumbent, paired on the game: Δ|err| (negative
  = more accurate), Δ err (a constant difference is flagged `deterministic`), Δ portfolio
  units per game; Holm across the candidates per family; deflated Sharpe per arm over its
  picks (n_trials = number of arms); PBO over the arms' per-game portfolio units when there
  are ≥ 2 candidates and ≥ 4 groups, else `None` with a note; pick-set overlap.

## What it refuses, and the exit codes

| Condition | Where | Result |
|---|---|---|
| `--row` not in `docs/HYPOTHESES.md` | `registry.require_runnable_row`, before any DB read | stderr + step-summary line, **exit 2** |
| row status not `pre-registered` / `exploratory` | same | exit 2 |
| row's criterion cell empty | same | exit 2 |
| `--candidate` / `--criterion` module not under `beatvegas.` | `harness_report.resolve_callable` | exit 2 |
| `--criterion` on an `exploratory` row | script and `harness.verdict` | exit 2 |
| `--decision-rule` not `consensus_as_of(<slot>)` with a slot in `ci.SLOT_GATE_ET` | `snapshots.parse_decision_rule` | exit 2 |
| `--frame` snapshot without `attrs["build"]`, cut coarser than the spec's finer knob, or a different `fbs_only` | `harness.load_frame` | exit 2 |
| `Grading.window_h` not exactly `REAL_1H_CLOSE_WINDOW_H` | `Grading.__post_init__` | `HarnessRefusal` |
| a proxy-derived column in the graded frame | `attach_closes` | `HarnessRefusal` |
| a scorer returning NaN or the wrong length | `walk_forward` | `ValueError` (a defect, the run fails red) |
| a test season with zero real closes | `attach_closes` | NOT EVALUABLE report, **exit 0** |
| database unreachable | `try_init_db` | one stderr line, exit 0 (the runner re-raises) |

## The two `min_games` knobs

`--min-games-train` and `--min-games-score` both default to **0**, matching the live board:
`scripts/weekly_update.py --min-games 0` builds the frame and `score_slate` derives its
training set from whatever frame it is handed, so the champion trains AND scores at 0. Every
backtest path before this harness used `build_feature_frame`'s own default of 2, which is why
a diagnostic could read 4 rows for a whole early season (CLAUDE.md gotcha). Both values are
printed in the report's spec block; the graded table is split at 2 games so the money
population is readable whatever the knobs say.

## The 2023-25 substitution

The purchased 2023-25 1H close history carries **zero `hardrockbet` rows** (Hard Rock the
book existed; the data set does not carry it). So on those seasons the **consensus close
defines the slate universe and stands in for Hard Rock's line** — a declared substitution
(Tate, 2026-09-23), stated in every report's data-basis block and caveats. On 2026 rows the
Hard Rock basis is reported beside it. Nothing here should be read as "what Hard Rock would
have offered"; it is what the market closed at.

## The Friday CLV clock

A candidate's bet line for CLV is the consensus 1H line as it stood when that week's `fri_pm`
build window OPENED — `ci.SLOT_GATE_ET["fri_pm"][0]`, 3:45pm ET on the most recent Friday on
or before the kickoff's ET date, converted to naive UTC (`snapshots.decision_instant`). The
instant must precede kickoff: a Thursday game against the Friday clock takes the previous
Friday (usually unposted, so no line), a Friday-noon kickoff takes none. Declared in the
report as `decision_rule="consensus_as_of(fri_pm)"`; `snapshots.decision_lines` reads every
book's last centred quote at or before the instant and takes the median
(`lines.consensus_as_of`, strict as-of — no fallback to later quotes). It exists only where
the snapshots do (2026+); the report says `n_with_decision_line / n_picks`, and selection
itself uses the close's gap on every season (the historical frame has no decision-time line).

## Running it

Registry row first, script second, ONE dispatch per row (docs/HYPOTHESES.md, "How to add a
row"). Locally (needs the database; refusals need only the registry file):

```bash
PYTHONPATH=. .venv/bin/python scripts/harness_report.py --row NOPE          # exit 2, no DB
PYTHONPATH=. .venv/bin/python scripts/harness_report.py --row H-NEGGAP-L    # live-tracking: exit 2
```

On the runner, which is where any number about the live model must come from
(CLAUDE.md, 2026-09-22; the campus network filters Neon's 5432 anyway):

```bash
gh workflow run study.yml --ref <branch> -f script=harness_report \
  -f args="--row H-X --test-seasons 2024 2025 2026"
gh run list --workflow=study.yml --limit 1
gh run download <run-id> -n study-harness_report -D reports/
```

Optional arguments: `--candidate beatvegas.x.y:fn --candidate-name plus1` (repeatable),
`--criterion beatvegas.x.y:fn` (pre-registered rows only; `fn(report) -> True | False |
None`), `--frame reports/frame_snapshot_<UTC>.pkl`, `--min-games-train`,
`--min-games-score`, `--decision-rule`, `--out`, `--all-divisions`. The args field is split
on whitespace only (`read -ra`), so parentheses need no quoting there.

The artifact holds `harness_<ROW>_<UTC>.md` (the report), `.json` (the full report dict),
`.csv` (one row per graded game: predictions, gaps, qualification, cap, outcome, units, the
Hard Rock basis, decision line, favourable CLV per arm) and `harness_<ROW>_<UTC>_frame.json`.

**No unattended iteration.** One dispatch per registered row. A second look at the same
seasons goes in the row's `comparisons run` cell, and a changed criterion is a new row.

## Reading the fingerprint

`<stem>_frame.json` is `etl.frame_fingerprint.fingerprint(frame)`: row count, rows by
season, platform / Python / scikit-learn / numpy / pandas versions, and per column the
non-null count, mean and std. It names WHICH snapshot of CFBD's reference tables the run was
judged on — the 2026-09-22 reconciliation (`docs/MODEL_LEVEL_2026.md`) found one frozen gate
giving two verdicts because two machines held June vs September reference data. To compare
two runs:

```python
import json
from beatvegas.etl.frame_fingerprint import diff_columns
a = json.load(open("reports/harness_H-X_20260924T150000Z_frame.json"))
b = json.load(open("reports/frame_snapshot_20260922T155600Z.json"))
for col, change in diff_columns(a, b).items():
    print(col, change)   # {"non_null": (u, v), "mean": (u, v), ...} or {"only_in": "a"|"b"}
```

`scripts/frame_snapshot.py` also pickles the frame with `attrs["build"]` (`fbs_only`,
`min_games`, `prior_weight`, `weather_lead`); `--frame` accepts such a pickle so a study can
be re-cut on exactly the runner's inputs.

## Consumers

- `scripts/harness_report.py` — the generic runner above.
- `scripts/intercept_gate.py`, `scripts/inseason_gate.py` — load their frame through
  `harness.load_frame` (gaining `--frame`); their evaluation code is unchanged.
- `scripts/level_anchor_gate.py::load_closes`, `scripts/residual_gate.py::load_closes` —
  one-line wrappers over `snapshots.kickoffs_for` + `snapshots.consensus_closes`.
- `beatvegas/backtest/neggap_level.py` imports `stats.wilson`, the repo's one Wilson, but is
  **not a harness consumer**: it measures stored card rows (H-NEGGAP-L), not walk-forward
  predictions, and has no incumbent-vs-candidate shape.

## Caveats printed on every report

1. One-shot: one look at the seasons named; add it to the row's `comparisons run` cell.
2. Consensus stands in for Hard Rock before 2026 (declared substitution).
3. The EV / price gate is NOT reproduced — `card.py::is_bet` needs both sides' closing
   prices at the book, which the historical close set does not carry.
4. Per-season folds, not the live weekly CFBD refresh.
5. CLV only where a decision line exists; selection uses the close's gap.
6. Both `min_games` knobs stated; the graded table is split at 2 games.
7. The feature frame drops played games whose 1H total equals the proxy line (a
   training-target rule in `build_feature_frame`); those games are absent from every count.
8. **2023-25 EXHAUSTED for rule selection — this run measures, nothing here may pick a
   threshold.**
