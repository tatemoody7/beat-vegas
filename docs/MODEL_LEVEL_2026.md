# The model's level in 2026 — the diagnosis, and the test it licenses

**Written 2026-09-20, BEFORE the gate was run.** Registry rows: **H-LEVEL** (the test) and
**R04** (`docs/LEVEL_ANCHOR.md`, the MAE question, rejected). The measurements below are
descriptive reads of data the project already holds; the confirmation set (2025) is
untouched and stays that way until the gate in H-LEVEL runs.

## The finding

Averaged over every Hard-Rock-priced, graded game:

| era | mean `bv_line` | mean market line | mean realized 1H |
|---|---|---|---|
| 2023-25 (real close, FBS) | 27.33 | 26.35 | **27.33** |
| 2026 (Hard Rock, weeks 1-3) | **24.81** | 27.30 | **29.35** |

In the seasons the rule was validated on, the model's average number **equalled the
average realized first half to the decimal**. In 2026 realized scoring is 2.0 points
higher and the market has moved 0.95 of the way with it — while **the model's own output
fell 2.5 points**. It moved the wrong way.

## What that does to the rule

The board spends `gap = line − bv_line` against a fixed `BET_GAP_PTS = 1.75`. A constant
level deficit is added to every gap, so the bar stops meaning what it was fitted to mean.

| cut | mean gap | share clearing 1.75 |
|---|---|---|
| 2023 | −1.23 | 16.8% |
| 2024 | −0.31 | 19.7% |
| 2025 | −1.39 | 10.0% |
| **2026 week 2** | **+2.21** | **51.0%** |
| **2026 week 3** | **+1.81** | **47.4%** |

**The rule was validated as "the top 20% by gap" and deployed as a constant 1.75 points.**
Those are the same rule only while the model's level is stable. It is not, so the live
gate now admits about half the board where the backtest admitted a sixth.

By spread band the deficit is present everywhere, not only in blowouts:

| band | share of set (hist → 2026) | model bias (hist → 2026) | clearing 1.75 (hist → 2026) |
|---|---|---|---|
| <14 | 73.4% → 54.7% | +0.01 → **−2.42** | 12.5% → 39.7% |
| 14-21 | 14.8% → 17.9% | +0.02 → **−5.82** | 20.9% → 47.4% |
| 21-28 | 7.9% → 13.2% | −0.41 → **−2.96** | 26.5% → 50.0% |
| 28+ | 3.8% → 14.2% | +0.47 → **−6.80** | 29.2% → **86.7%** |

Two things compound. The deficit is worst at 28+, and Hard Rock prices **14.2%** of its
board there against **3.8%** in the validation set — so the worst band is also four times
more of what we look at. At 28+, 87 of every 100 priced games now clear the bar.

## What this is NOT

- **Not early season.** In 2023-25 weeks 1-3 the model ran **+0.70** (high) and 20.4% of
  games cleared the bar — the most ordinary band in the history. The drift is not the
  calendar.
- **Not a league-wide scoring jump.** League-wide first halves in weeks 1-3 read 28.14 /
  27.21 / 27.88 / 28.44 for 2023-26: 2026 is up about half a point, not two and a half.
- **Not regression to the mean.** Both the model and the market show the mechanical
  pattern (large positive bias on low-scoring games, large negative on high) in *both*
  eras. The 2026 curve is the same shape shifted down against the market at every level.
- **Not the ranking.** A constant level deficit adds the same number to every gap, so the
  ORDER of the board is untouched. What breaks is the threshold, and the live ladder is
  consistent with that: the 3-5 and 5+ gap bands ran 69% and 57% under across weeks 2-3,
  which is roughly where a percentile-restored bar would sit.

## What it licenses

`docs/LEVEL_ANCHOR.md` (R04) tested the prior-season seed on **MAE**, found nothing at
weeks 1-2, and rejected it. Its own closing paragraph says the rest:

> "The seed reduces bv_line's level bias and tightens selection" is a *different
> hypothesis* from the one tested here, and it deserves its own pre-registration against
> the still-untouched 2025 set — judged on **bias and gate-crossing count**, with MAE
> demoted to context.

That is exactly the hypothesis the numbers above make urgent, the 2025 set is still
untouched, and `scripts/level_anchor_gate.py` already reports both quantities. **H-LEVEL**
is that pre-registration; its criterion was committed before the gate was run.

**A pass licenses a registered parallel paper arm and nothing more.** H-STOP is running on
the frozen rule, and changing selection mid-test would end that measurement rather than
inform it.

## Results — H-LEVEL FAILS. `PRIOR_SEASON_WEIGHT` stays 0.

Run 2026-09-20, `scripts/level_anchor_gate.py --train-seasons 2023 2024 --test-season
2025`, 744 test rows (622 with a real 1H close). Judged on the criterion committed
before the run: bias, the share clearing the bar, and monotonicity in `k`. MAE is
context.

| k | bias (weeks 3+, n=621) | mean gap | clears 1.75 | share |
|---|---|---|---|---|
| **0.0 (incumbent)** | **+1.24** | −2.17 | 74 | 11.9% |
| 0.5 | +1.21 | −2.15 | 79 | 12.7% |
| 1.0 | +1.19 | −2.12 | 70 | 11.3% |
| 2.0 | **+1.45** | −2.40 | 71 | 11.4% |
| 3.0 | +1.15 | −2.12 | 74 | 11.9% |

- **(a) bias fails.** The whole grid moves the bias by at most 0.09 points against an
  incumbent of +1.24, and it is **not monotone** — it rises to +1.45 at k=2 before
  falling again. Non-monotonicity is the R04 failure mode and it repeated here.
- **(b) selectivity fails.** The share clearing the bar starts at 11.9% and ends at
  11.9%, wandering 11.3-12.7% in between. It does not move toward the 15-20% band; at
  k=1 it moves away from it.
- MAE, as context, also adopts nothing: the script's own weeks-1-2 rule finds no CI
  excluding zero at any k.

**And the deeper reason it could never have passed: the problem is not in this test
set.** On 2025 the incumbent's bias is **+1.24 — the model reads HIGH**, the opposite
sign to 2026's −2.4 to −6.8. Only 96 of 744 test rows are weeks 1-2, and only **one**
of them carries a real close, so the bucket the seed targets is empty where selection
is measured. The seed fixes NaN early-season features; the 2026 deficit is present in
**every week and every spread band**, so it is a different fault.

## Found: the calibration intercept, not a feature

Run 2026-09-20 on the `min_games=0` frame the live board scores from. Three things
were checked in order and the first two came back clean.

**It is not a broken feature.** Comparing the 153 played 2026 week 1-3 rows against
the 143 equivalent 2025 rows, feature by feature: **no feature is entirely missing in
either season**, the largest NaN-rate shift is 7.7 points (`home_fh_off_redzone_td`),
and the largest level shift is 0.76 standard deviations (`wx_wind`). The weather
columns move 4.3 points of NaN rate, which kills that lead. The inputs are ordinary.

**It is not the training-set filter, though that filter really does differ.**
`scripts/weekly_update.py` builds the frame with `min_games=0` and hands it to
`score_slate`, which derives its training set from the frame it is given — so the live
board trains on a population that every backtest path (`backtest/engine.py`,
`scripts/backtest.py`, `validate_engine`, `retrain`, `residual_gate`, `weekly_report`,
all `min_games=2`) excludes. Holding the target fixed and varying only that filter
moves 2026 by **+1.72 pts** [+1.23, +2.22]... but **−0.37** on 2025 and **−0.27** on
2024. The sign flips, so it is an interaction, not the cause.

**It is the global intercept.** `bv_line_for_slate` adds
`bias_corrections(train)["global"]` to every prediction: the mean walk-forward
out-of-fold residual. With `min_train = 500` and three training seasons, only two
folds are scorable, so that mean is an average of **two season-level numbers**, then
extrapolated to a third:

| season | OOF correction it needed | n |
|---|---|---|
| 2024 | **−1.15** | 732 |
| 2025 | **−2.46** | 744 |
| **2026 (what it actually needed)** | **+1.09** | 153 |

The intercept applied to the live board is **−1.81**, the mean of the first two.
2026 needed **+1.09** — the opposite sign. The gap is **2.90 points, which is the
entire level deficit**:

| | bias on 2026 wk1-3 |
|---|---|
| raw model, before calibration | **−1.09** |
| after the −1.81 intercept | **−2.90** |

So the raw regressor is only a point low, and the step meant to remove bias adds
1.81 points of it. The same arithmetic explains the `min_games` result above: adding
2025 to the training window moves the intercept from −1.15 to −1.81, and that is most
of the 1.72-point shift.

It is not a coding error — the residual sign is right (`actual − pred`, added). It is a
**season-level effect estimated from two observations and extrapolated to a third**,
and the two it saw disagree with each other by 1.3 points. It could not have been
expected to transfer, and it did not.

The week-of-season explanation was tested and rejected: OOF residuals by band run
−1.62 / −1.05 / −1.76 / −2.44 for weeks 1-3 / 4-6 / 7-10 / 11+, so an early-season
slate is mis-corrected by only 0.19 points. The problem is the season, not the week.

## What this rules out, and what is left

The obvious, already-built remedy does not address the 2026 level deficit. That is a
useful negative: it redirects rather than closes.

**The 2026 drift cannot be studied on 2023-25 at all**, because the model is well
calibrated there (bias +1.24 on 2025, and its 2023-25 mean line equals the realized
mean to the decimal). That row-level feature comparison has since been run — see
"Found: the calibration intercept" above — and the inputs are clean. The fault is in
the calibration step, not in the data.

Until that is found, the honest position is the one the board already takes: the
**ranking** is unaffected by a level shift, the **threshold** is not, and H-STOP is
measuring the frozen rule. Nothing here licenses a change to live selection.

## H-INTERCEPT — the grid, declared before the run

H-INTERCEPT's criterion cell says the shrinkage grid is "declared in advance" without
stating it. **This is that declaration, committed before the gate was run** (Tate,
2026-09-20): the arms are the intercept scaled by

**λ ∈ {0, 0.25, 0.5, 0.75, 1.0}**, where λ=1 is the incumbent and λ=0 drops the intercept.

λ=1 reproduces `bv_line_for_slate` exactly rather than re-implementing it, so the
incumbent is an arm of the experiment. Each arm is a constant shift of one fitted model,
so the whole grid costs one fit per held-out season — and a constant shift cannot reorder
a board, which is why the ranking is untouched whatever the gate returns.

Two details of how the rule is read, also fixed before the run:

- **The mean across seasons is equal-weight.** The criterion says "the MEAN |level bias|
  across the three held-out seasons", and the question is whether a correction transfers
  *between* seasons; game-weighting would hand that question to 2025 (744 rows) over 2026
  (153).
- **`comparisons run` counts challenger-versus-incumbent tests**, so the grid is 4
  comparisons per season, not 5 — λ=1 is not compared against itself.

The gate is `scripts/intercept_gate.py` (`beatvegas/backtest/intercept.py` holds the
arithmetic and `_verdict` applies the registered rule verbatim). It is a report, not a CI
gate, and changing the intercept would mean editing `model/bv_line.py` in a PR that cites
the report.
