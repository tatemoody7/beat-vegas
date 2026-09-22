# The model's level in 2026 — the diagnosis, and the test it licenses

> **Platform correction (2026-09-22).** Every number in this document that depends on a
> fitted model — the incumbent intercept **−1.8092**, the per-fold 2024/2025 values −1.15 /
> −2.46, the raw-vs-calibrated bias split, and the H-INTERCEPT and H-INSEASON gate tables —
> was computed on this project's Mac (scikit-learn 1.6.1, Python 3.9). **The live board runs
> on the GitHub runner (scikit-learn 1.9.1, Python 3.11), and HistGradientBoosting output is
> not pinned across platforms.** On 2026-09-22 the runner recomputed the same 2,212 training
> rows to an intercept of **−1.2360**, and recomputing `bv_line_for_slate` for the 58 stored
> week-4 rows reproduced every one to 0.01 at that value (`backfill_intercept.yml` run
> 35746685925) — so **−1.236, not −1.81, is what the board applied**, and the 2026 level
> deficit attributable to the intercept is correspondingly smaller than the 2.90 points
> stated below. The qualitative findings (the prior-season intercept does not transfer; the
> in-season estimator's primary metric is partly mechanical) do not depend on which forest
> was fitted, but the figures do, and `intercept_gate.yml` had never actually run on the
> runner (a `from scripts.*` import failed there; fixed the same day). The runner's own gate
> table is to be appended below once the workflow has run; until then treat the numbers in
> this file as **Mac numbers**. Rows scored before `bv_intercept` existed were backfilled
> with −1.2360 (`scripts/backfill_bv_intercept.py`).


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

## H-INTERCEPT — result. NO ARM ADOPTED. The intercept stays as it is.

Run 2026-09-20, `scripts/intercept_gate.py` against Neon, `min_games=0`, FBS-vs-FBS,
2,000 bootstrap draws. Judged on the criterion committed before the run, applied verbatim
and **not edited**. `ADOPT: none`.

| season | test n | train n | intercept applied | priced |
|---|---|---|---|---|
| 2024 | 732 | 736 | **+0.0000 (no scorable fold)** | 623 |
| 2025 | 744 | 1,468 | −1.1508 | 622 |
| 2026 | 153 | 2,212 | −1.8092 | 61 |

Signed bias, prediction − actual:

| λ | 2024 | 2025 | 2026 | mean abs | worst |
|---|---|---|---|---|---|
| 0.0 (drop it) | +1.15 | +2.46 | −1.09 | **1.565** | 2.457 |
| 0.25 | +1.15 | +2.17 | −1.54 | 1.619 | 2.169 |
| 0.5 | +1.15 | +1.88 | −1.99 | 1.674 | **1.990** |
| 0.75 | +1.15 | +1.59 | −2.44 | 1.729 | 2.443 |
| 1.0 (incumbent) | +1.15 | +1.31 | −2.90 | 1.784 | 2.895 |

**Every challenger beats the incumbent on both aggregate measures.** λ=0 takes the mean
from 1.784 to 1.565 and λ=0.5 takes the worst season from 2.895 to 1.990. The row still
fails, on the per-season clause, for two independent reasons.

**(a) 2025 wants the OPPOSITE fix, at every λ.** The model reads 2.46 points HIGH on 2025
before calibration, so the correction it needs is the one the incumbent applies; shrinking
it monotonically makes 2025 worse (1.31 → 2.46) while making 2026 better (−2.90 → −1.09).
No constant multiplier can serve both. **That is the finding**: a season-level intercept
estimated from two observations does not transfer, because the two observations disagree
about its sign.

**(b) 2024 cannot discriminate at all, and that is about the test.** Its training window is
2023 alone, and `oof_residuals` needs a prior season inside the window (`min_train=500`),
so `bias_corrections` returns 0.0. Every arm predicts the same number there, every
bootstrap draw of the difference is exactly 0, and the interval is [0, 0] — which cannot
exclude zero. **The criterion's "in every season" clause is unsatisfiable on 2024 for a
reason that has nothing to do with the intercept.** The criterion was not amended to route
around it: a row is closed under the rule it was registered with. A future row testing
this estimator should hold out only seasons whose training window has a scorable fold.

### A third thing the run exposed: the CI clause is nearly vacuous here

**6 of the 12 challenger-season intervals have ZERO WIDTH.** Two arms differ by a
constant, so while a resampled bias keeps its sign the difference of absolute means is
that same constant in every replicate; width appears only where a resample can carry the
bias across zero. So "a paired bootstrap 95% CI excluding zero" is satisfied by
construction wherever the bias is comfortably away from zero. What decided every arm here
was the plain comparison — is this season's |bias| lower at all — and the interval added
nothing. A criterion testing a constant shift should say so rather than dress the
comparison in an interval.

### Secondary — reported, never optimised

| λ | 2024 share clearing 1.75 | 2025 | 2026 |
|---|---|---|---|
| 0.0 | 18.8% (117/623) | 7.2% (45/622) | 42.6% (26/61) |
| 0.5 | 18.8% | 8.8% | 47.5% |
| 1.0 (incumbent) | 18.8% | **11.9% (74/622)** | **60.7% (37/61)** |

Two things worth keeping. **2024 sits at 18.8% — inside the 15-20% band the rule was
validated on — with no intercept applied at all.** And **dropping the intercept does not
repair 2026's selection**: 42.6% is still roughly three times the validated band, so the
intercept is the largest single piece of the level deficit but not the whole of what moved
the bar. 2026 is 61 priced games in weeks 1-3, when first halves run hot in every season,
so that column is thin and seasonal both.

MAE is flat across the grid by construction (8.918 / 9.088-9.287 / 8.026-8.233): a level
shift of a point or two is nothing against ~9 points of per-game error, which is exactly
why this row was judged on bias.

### What it changes

Nothing. `bias_corrections` is untouched, `BET_GAP_PTS` is untouched, and a constant shift
cannot reorder a board, so the ranking never depended on this. H-STOP keeps measuring the
frozen rule.

What it redirects to is **H-INSEASON**, registered the same day in its own family: the
intercept is a season-level number estimated from prior seasons only, and `score_slate`
trains on `season < target_season` strictly, so 2026's own 153 graded games are used for
nothing — not the fit, not the intercept. Shrinking a number estimated from the wrong
seasons cannot fix it; re-estimating it from the right ones might.

## H-INSEASON — result. PASSED ITS DEVELOPMENTAL GATE *on June-2026 reference data*; TESTED-NULL on the run of record (see Reconciliation below). NOT a betting-value finding.

**What this result is, stated before any number** (Tate, 2026-09-20): H-INSEASON passed
its registered **developmental** gate. The primary level-bias metric is **partly mechanical
for this estimator**, so the pass does **not** establish prospective betting value, and
nothing below should be quoted as evidence that an in-season intercept improves the betting
system. The only thing it licenses is properly registered prospective paper collection.

Run 2026-09-20, `scripts/inseason_gate.py` against Neon, `min_games=0`, FBS-vs-FBS,
2,000 draws, α 0.05. Judged on the criterion frozen before the script existed.
`ADOPT: ['k25', 'k50', 'k100', 'k200']`. Reproduced identically from the previous
session's cached frame.

**As-of rule used: the week boundary** — a game in week *w* is scored from the completed
games of weeks < *w* only. Live, the window closes strictly before the build's timestamp;
the two differ only for a midweek build after a Thursday game of the same week.

| arm | 2024 | 2025 | 2026 | mean abs | worst | mean w |
|---|---|---|---|---|---|---|
| k25 | +0.37 | +0.28 | −1.78 | **0.810** | **1.776** | 0.73 |
| k50 | +0.45 | +0.38 | −2.00 | 0.944 | 2.003 | 0.65 |
| k100 | +0.55 | +0.51 | −2.26 | 1.106 | 2.257 | 0.55 |
| k200 | +0.67 | +0.66 | −2.49 | 1.275 | 2.486 | 0.43 |
| incumbent | +1.15 | +1.31 | −2.90 | 1.784 | 2.895 | 0.00 |

Every arm beats the incumbent on both aggregate measures with the interval entirely below
zero (k25: mean −0.974 [−1.016, −0.507], worst −1.119 [−1.244, −0.800]), no season is
entirely worse, and all four survive Holm at adjusted p = 0.0040.

### The caveat that matters more than the table

**The primary measure is close to self-fulfilling, and a pass on it is weaker evidence
than it looks.** The estimator subtracts an estimate of the season's own level error, and
the primary measure is that season's level error. Any estimator whose running mean
converges toward the season mean drives season-level bias toward zero — whether or not it
improves a single prediction. This is not leakage: the window is strictly prior, and a
week-8 game is corrected only by weeks 1-7. It is a measure that cannot fail.

MAE does not rescue it. It improves in all three seasons (8.918 → 8.840, 9.088 → 8.988,
8.233 → 8.094 at k25), but by **exactly the amount removing that much bias implies** — for
errors around 9 points, removing 1.5 points of level is worth about 0.07 of MAE. That is
the same fact restated, not corroboration.

**What the run does establish, and it is not nothing:** the season's level is estimable
from its own completed games early enough to be worth applying, and the correction is not
purely mechanical. If within-season bias were constant, the prefix mean would zero every
week band. It does not:

| arm | 2024 weeks 1-3 / 4-6 / 7-10 / 11+ | 2025 |
|---|---|---|
| incumbent | +1.01 / +0.02 / +0.97 / **+2.13** | +1.04 / +0.99 / +1.36 / +1.61 |
| k25 | −0.04 / −0.52 / +0.33 / **+1.22** | −0.05 / +0.20 / +0.36 / +0.46 |

2024's bias drifts within the season and the prefix mean lags it by design, leaving +1.22
at weeks 11+. So there is real within-season structure the estimator is only partly
tracking.

### The consequential number is selection

| arm | 2024 | 2025 | 2026 |
|---|---|---|---|
| incumbent | 18.8% | 11.9% | 60.7% |
| k25 | 24.6% | 18.2% | 49.2% |
| k200 | 22.5% | 16.4% | 55.7% |

The share clearing 1.75 becomes far more **uniform across seasons**, which is what a
level correction should do, and 2025 moves from 11.9% into the validated 15-20% band.
Two things temper it: 2024 moves above the band rather than into it, and **2026 is still
at 49.2%** against a band of 15-20%.

**2026 is where the estimator is weakest, for a structural reason.** The season is weeks
1-3 and nothing else, so week 1 — about a third of its 153 games — gets no in-season
evidence at all and takes the full −1.81 prior intercept. The in-season correction is
weakest exactly when a season is young, which is when the 2026 deficit bit hardest.

Worth putting beside it: on 2026 alone, **simply dropping the intercept beat every
in-season arm** (H-INTERCEPT's λ=0 gives −1.09 against k25's −1.78). The in-season blend
wins overall because it also fixes 2025 (+0.28 against λ=0's +2.46), which dropping the
intercept made worse.

### What it licenses, and what it does not

Under the registered rule: **a prospective paper arm, and nothing more.** Before that arm
logs its first pick it needs its own registry row with its own prospective validation or
stopping criterion. H-STOP is untouched and the champion's rule is never mixed with the
challenger's. Live selection does not change, `bias_corrections` is not edited, and
`BET_GAP_PTS` is not moved.

**No k is chosen, and none will be chosen from this run.** All four passed, the registered
gate contained no ranking rule, and picking the best-looking arm out of the same 2024-26
data that produced the table would be post-hoc. The four values go forward together as one
**H-INSEASON challenger family**; if a single challenger must be named anywhere for display,
it is the family, never one of its arms.

The declared limitation still stands: the bootstrap resamples games within a season and is
blind to between-season variation, the dominant uncertainty here. Three seasons, one of
them three weeks long, is thin — and these are **development** seasons, since 2026
motivated the hypothesis. Prospective evidence begins with decisions logged from here.

The prospective phase is deliberately judged on measures that are **not** mechanically tied
to the correction: paper profit at actually available prices and CLV against the closing
market, with prediction error and level bias demoted to secondary diagnostics. Its rule
lives in its own registry row, written before its first pick.

## Runner results (2026-09-22) — the same two gates on the platform that scores the board

Both gate workflows were dispatched on the GitHub runner the day the platform discrepancy
was found (`intercept_gate.yml` run 35747758294, `inseason_gate.yml` run 35747948770;
walk-forward, `min_games=0`, FBS-only, 2,000 draws, criteria unchanged). The runner's
incumbent intercept is **−1.2360** for 2026 and **−0.9927** for 2025 (Mac: −1.8092 /
−1.31 applied), and it reproduces the stored week-4 `bv_line` rows exactly, so these are
the production numbers.

**H-INTERCEPT on the runner — still NO ARM ADOPTED, for the same two reasons.**

| λ | 2024 | 2025 | 2026 | mean \|bias\| | worst |
|---|---|---|---|---|---|
| 0.0 | +0.99 | +1.48 | −1.01 | 1.159 | 1.475 |
| 0.25 | +0.99 | +1.23 | −1.32 | 1.179 | 1.319 |
| 0.5 | +0.99 | +0.98 | −1.63 | 1.200 | 1.628 |
| 0.75 | +0.99 | +0.73 | −1.94 | 1.220 | 1.937 |
| 1.0 (incumbent) | +0.99 | +0.48 | −2.25 | 1.240 | 2.246 |

2024 is structurally tied (no scorable fold) and 2025 wants the opposite fix at every λ.
The 2026 level deficit under the incumbent is **−2.25**, of which the intercept accounts
for 1.24 points (raw −1.01), not the 2.90 / 1.81 split the Mac run gave. The share of
priced 2026 games clearing the 1.75 bar is 49.2% under the incumbent and 36.1% with no
intercept (Mac: 60.7% / 42.6%).

**H-INSEASON on the runner — DOES NOT CLEAR THE REGISTERED CRITERION.** Every arm beats
the incumbent on mean and worst |bias| with the 95% interval entirely below zero, and no
season is worse — but the **Holm-adjusted p is 0.0560 on all four arms, against the
row's 0.05**. The Mac run read 0.0040. The estimator behaves the same way (mean |bias|
1.240 → 0.622 at k=25, worst 2.246 → 1.438, selection 2025 17.2 → 19.1%, 2026 49.2 →
44.3%); what changed is that the runner's incumbent is closer to the truth, so the
improvement is smaller and the multiplicity-corrected test lands on the wrong side of the
line.

| arm | 2024 | 2025 | 2026 | mean \|bias\| | worst | Holm p |
|---|---|---|---|---|---|---|
| k25 | +0.26 | +0.17 | −1.44 | 0.622 | 1.438 | 0.0560 |
| k50 | +0.33 | +0.21 | −1.60 | 0.716 | 1.604 | 0.0560 |
| k100 | +0.43 | +0.26 | −1.79 | 0.825 | 1.788 | 0.0560 |
| k200 | +0.54 | +0.31 | −1.95 | 0.935 | 1.953 | 0.0560 |
| incumbent | +0.99 | +0.48 | −2.25 | 1.240 | 2.246 | — |

This is the "partly mechanical" caveat above showing up in the arithmetic: the runner's
incumbent removes more of the level error on its own, so the estimator has less to
subtract. **Disposition (Tate, 2026-09-22): neither run is authoritative yet.** Two supposedly
equivalent runs of one frozen test disagree on pass/fail, and the source of the difference
(library, data, bootstrap, precision, configuration) is to be identified from inputs through
final statistics before the criterion is applied to the reconciled result. H-INSEASON's
status is unchanged meanwhile and H-INSEASON-P collection is paused before its first pick.

## Reconciliation (2026-09-22) — the two runs disagree because the DATA differs, not the code

Tate's direction was to reconcile the Mac and runner runs from inputs through final
statistics before either result is allowed to decide anything. Done the same afternoon,
read-only, by crossing the two frames with the two libraries:

- **Frames.** The Mac's frame was rebuilt fresh against Neon (`min_games=0`, 2,477 rows,
  identical ids to the runner's); the runner's frame was dumped by `scripts/frame_snapshot.py`
  (study.yml run 35750576666, Linux x86_64, Python 3.11, scikit-learn 1.9.1). **40 of 196
  columns differ**, every one a CFBD reference feature: advanced-stat PPA / explosiveness /
  success rate (all seasons, max |Δ| 0.25), roster experience and upperclass share (**every
  2023-25 row**, max |Δ| 1.0), returning-production PPA (2023 and 2025). Everything else —
  scores, lines, pace, weather, PBP aggregates — is byte-identical.
- **Why.** `season_stats._cached` has no expiry. This Mac's `data/cache/` holds the 2022-25
  reference files fetched **2026-06-02/03**; the runner's weekly ISO-week cache re-fetches
  them, and CFBD revised those tables between June and September. The registered "frozen"
  test therefore had un-frozen inputs, and which snapshot a run saw depended on the machine.
- **Libraries.** Homebrew Python 3.12 with the runner's exact pins (scikit-learn 1.9.1,
  numpy 2.4.6, pandas 2.3.3, scipy 1.17.1) beside this Mac's Python 3.9 / scikit-learn 1.6.1.
  OpenMP thread count (1 / 2 / 4) changes nothing on either.

| frame (reference-data snapshot) | library | intercept 2025 / 2026 | incumbent bias 2024 / 2025 / 2026 | k25 mean \|bias\| vs incumbent | Holm p (all four arms) | H-INSEASON |
|---|---|---|---|---|---|---|
| June cache (Mac) | 1.6.1 | −1.1508 / **−1.8092** | +1.15 / +1.31 / −2.90 | 0.810 vs 1.784 | **0.0040** | pass |
| June cache (Mac) | 1.9.1 | −1.0950 / −1.9117 | +1.09 / +1.62 / −2.99 | 0.831 vs 1.901 | **0.0040** | pass |
| September cache (runner) | 1.9.1 (runner itself) | −0.9927 / **−1.2360** | +0.99 / +0.48 / −2.25 | 0.622 vs 1.240 | **0.0560** | fail |
| September cache (runner) | 1.9.1 (Mac, runner's pins) | −0.9927 / −1.2360 (to 6 dp) | +0.99 / +0.48 / −2.25 | 0.622 vs 1.240 | **0.0560** | fail |
| September cache (runner) | 1.6.1 | −0.9052 / −1.1385 | +0.91 / +0.46 / −2.32 | 0.635 vs 1.231 | **0.0560** | fail |

**What this settles.**

1. **Platform is not a factor.** Given the runner's frame, a Mac running the runner's pins
   reproduces the runner to six decimals, and thread count is irrelevant. The earlier
   "Mac numbers vs runner numbers" framing in the correction note above was right about the
   symptom and wrong about the cause: the machines differed because their *caches* differed.
2. **The library version moves the intercept by ~0.1 and never the verdict.** Same frame,
   same verdict, under 1.6.1 and 1.9.1 alike.
3. **The reference-data snapshot moves the verdict.** With CFBD's June tables the frozen
   H-INSEASON gate passes at Holm 0.004 in both libraries; with its September tables it fails
   at 0.056 in both. The estimator's direction is the same on every row of the table (every
   arm beats the incumbent on both primaries); the size of the improvement is smaller on the
   September data because the incumbent's own bias is smaller there (2026 −2.25 vs −2.90).
4. **H-INTERCEPT is unaffected**: ADOPT none on every row of the table, for the same two
   reasons (2024 structurally tied; 2025 wants the opposite fix).

**What it implies for the process.** A registered run must pin its inputs. From here, every
`*_gate.yml` and `study.yml` run should write the frame fingerprint
(`scripts/frame_snapshot.py::fingerprint`) beside its report, and a registry result cell
should name the snapshot it was judged on. The live board's model also inherits this: it is
re-fitted each Sunday on whatever CFBD serves that week, so a CFBD revision of 2023-25
statistics changes the champion's number without any code change.

**Disposition (Tate, 2026-09-22): the criterion is applied to the September data — the tables the
runner refetches weekly and the live board is fitted on. H-INSEASON is `tested-null`; H-INSEASON-P is
withdrawn before its first pick, with zero rows ever logged. This Mac's June cache is refreshed so local
studies read the same tables as the runner, and every gate run now writes its frame fingerprint.**

## The serving skew (2026-09-22) — 57 inputs present on every training row, missing on every scored row

Found by the system review, after the reconciliation above. It is the most likely cause of
the deficit this document has been chasing, and it is a defect, not a modelling question
(registry row **B-SERVE**, `adopted`).

**Mechanism.** The first-half play-by-play season-to-date features (`FH_FACTOR_COLS`, 52
columns) and their five derived matchup columns (`mm_*`) are built in
`etl/fh_factors.py::fh_factor_frame` as a `shift(1).expanding().mean()` over `fh_team_game`
rows and then joined onto games **by the game's own id**. A played game has a play-by-play
row and receives its teams' prior-game means. An upcoming game has no play-by-play row yet,
so the join finds nothing and every one of the 57 columns is NaN — even though its teams'
prior games exist. In the historical seasons every row is played, so the training frame and
every backtest carry the columns on ~100% of rows.

| rows | NaN share on the 57 columns |
|---|---|
| 2026 week 4 (the 58 rows scored on 2026-09-20) | **100%** |
| 2026 weeks 2-3 (now played) | ~4-10% |
| 2023-25 weeks 4+ (training) | **0.0%** |

`HistGradientBoostingRegressor` learns a routing direction for missing values only from
missing values it sees in training; on a column it never saw missing, a NaN at prediction
time is sent to whichever child the implementation defaults to. The model has been scoring
every live game through 57 branches it never trained.

**Measured effect** (the runner's frame snapshot 2026-09-22T15:56Z, scikit-learn 1.9.1;
train `season < test`, the champion's own `bias_corrections`; the same played rows predicted
with the 57 columns present and then masked to NaN, exactly the serving condition):

| test rows | n | bias, columns present | bias, columns masked | mean shift | mean \|shift\| per game | MAE present → masked |
|---|---|---|---|---|---|---|
| 2026 weeks 2-3 | 104 | −2.52 | **−4.51** | **−1.99** | 2.85 | 8.29 → 8.20 |
| 2025 weeks 4+ | 601 | +0.57 | −0.73 | **−1.30** | 2.41 | 9.01 → 8.83 |
| 2024 weeks 4+ | 596 | +0.98 | −1.60 | **−2.58** | 3.39 | 9.08 → 8.89 |

Three things follow. The masked prediction is **1.3-2.6 points lower** in every season: that
is the size and sign of the 2026 level deficit, and it is not an intercept. The per-game
shift is **2.4-3.4 points**, so the skew reorders the board as well as lowering it — the
constant bar was firing on a reshuffled slate. And MAE is slightly **better without** the
columns in all three seasons, consistent with the 2026-09 ablation (9.22 with vs 9.18
without the PBP family): the features were noise in training and poison at serving.

**Why nothing caught it.** Every validation path scores played rows. The stored week-4
predictions reproduce exactly on today's frame (the verify run above) because today's frame
has the same NaNs. The intercept studies measured a real symptom on the correct data and
attributed it to calibration.

**The fix (next PR, effective at the week-5 refit):** the 57 columns leave `BV_FEATURE_COLS`
as `SERVE_UNAVAILABLE_COLS`; `weekly_update.py` prints a per-column NaN-share comparison of
the target rows against the training rows and fails if any column is >90% NaN on the target
and <10% on training — the guard for the class, not the instance. The level, the selection
share and the intercept are then re-derived on the runner and appended here. H-INTERCEPT and
H-INSEASON are not reopened: they studied a symptom.

## The corrected model on the intercept gate (2026-09-22, after B-SERVE)

Run under the runner's exact pins (scikit-learn 1.9.1, numpy 2.4.6) on this Mac against a
freshly refetched CFBD reference cache — the setup that reproduced the runner to six
decimals earlier the same day; the runner itself could not start jobs that afternoon
(GitHub Actions billing hold, `docs/OPS_ACCOUNTS.md`). `BV_FEATURE_COLS` without the 57
serve-unavailable columns:

| season | incumbent intercept | incumbent bias (played rows) | share clearing 1.75 |
|---|---|---|---|
| 2024 | +0.0000 (no scorable fold) | +0.91 (was +0.99) | 21.2% |
| 2025 | −0.9131 (was −0.9927) | +0.64 (was +0.48) | 17.8% |
| 2026 | −1.2341 (was −1.2360) | **−2.67 (was −2.25)** | 55.7% |

ADOPT: none, as before. **Read this correctly:** the gate scores PLAYED rows, where the 57
columns were always present, so it cannot see the serving gain. On played rows the model
without those columns sits 0.4 pts lower; at serving the OLD model sat ~2.0 pts lower than
its own played-row bias (the masking table above: −2.52 → −4.51), so the corrected model's
serving level is about **1.8 pts higher** than what the board carried all season — the
number the week-5 refit will show directly (`predictions.bv_line` for week 5 against Hard
Rock's mean). The share clearing 1.75 is now moot: H-PCT makes the bar a percentile.
