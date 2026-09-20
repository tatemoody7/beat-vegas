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

## What this rules out, and what is left

The obvious, already-built remedy does not address the 2026 level deficit. That is a
useful negative: it redirects rather than closes.

**The 2026 drift cannot be studied on 2023-25 at all**, because the model is well
calibrated there (bias +1.24 on 2025, and its 2023-25 mean line equals the realized
mean to the decimal). Whatever changed is specific to how 2026 rows are built or
scored, so the next step is a **row-level comparison of one team's 2026 feature vector
against the same team's 2025 vector**, looking for a feature that shifted meaning
rather than a modelling choice that needs tuning. Candidates in order: the season-to-date
block on partial 2026 data, the repaired weather columns (`wx_temp`/`wx_wind` changed
on every historical row on 2026-09-14, mean |Δtemp| 6.79°F, and both are model
features), and the FBS filter's 2026 team list.

Until that is found, the honest position is the one the board already takes: the
**ranking** is unaffected by a level shift, the **threshold** is not, and H-STOP is
measuring the frozen rule. Nothing here licenses a change to live selection.
