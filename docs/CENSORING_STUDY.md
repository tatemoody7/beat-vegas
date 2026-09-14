# Does censoring leave information the price has not absorbed?

**Run 2026-09-14. Verdict: DO NOT BUILD.** Re-run with
`python scripts/censoring_study.py`.

The two-team probabilistic engine was going to be a multi-day build. This is the
half-day measurement that decided whether it was worth starting. It was not.

## The question, stated so it can be answered

The mechanism was never in doubt, so "is censoring real?" was the wrong
question. The right one is **does censoring leave information in the outcomes
that the price has not already absorbed?** — and the way to answer it is to
control for the book's own de-vigged probability and ask whether spread still
predicts anything.

## Pushes first, because they can invalidate everything else

A two-way de-vig returns `fair_over + fair_under = 1`, which implicitly assumes
no push. Comparing that against a raw Under percentage with pushes still in the
denominator compares two different quantities, and the error is silent.

| line type | n | share | pushes | push rate |
|---|---|---|---|---|
| half-point | 1,390 | 73% | 0 | 0% |
| **integer** | **512** | **27%** | 29 | **5.66%** |

Under rate is **48.74% counting pushes, 49.49% among decided games**. That
0.75 pp gap is the same order as the effect being hunted — left alone it would
have been an error the size of the signal.

The resolution is clean. On an integer line a push **voids** the bet, so the
book's two prices effectively price `{under | decided}` against
`{over | decided}`; a two-way de-vig therefore already yields
conditional-on-decided probabilities. Everything below conditions on non-push
and reports the push rate separately.

## Test 2 — the gate

1,873 decided games with a real captured 1H close and a centred de-vigged
closing price (median 7 books per game).

- market mean P(under) **50.06%** against realized **49.49%** — a gap of
  **0.57 pp**
- Brier **0.2500**, identical to a flat coin flip, which is what a correctly
  centred line looks like
- **spread coefficient +0.00369 per point, bootstrap 95% CI
  [−0.0083, +0.0157] — includes zero**

Three independent reads, all the same:

**The sign is not stable.**

| season | n | spread coef |
|---|---|---|
| 2023 | 617 | +0.00574 |
| 2024 | 630 | **−0.00378** |
| 2025 | 626 | +0.00927 |

**It does not survive out of sample.** Fit on 2023–24, the coefficient is
+0.00073 — the two training seasons cancel. Applied blind to 2025 it improves
Brier from 0.25040 to 0.25029: an improvement in the fourth decimal place.

**And it would not pay even if it were real.** Taken at face value the
coefficient moves P(under) by **+1.94 pp across the entire 7-to-28 spread
range**, against a **2.38 pp** vig hurdle at −110.

The bucket view says the same thing in a form you can eyeball — the differences
are not merely small, they are non-monotone, with adjacent buckets swinging
13 points in opposite directions on 135 and 62 games:

| bucket | n | realized | implied | diff |
|---|---|---|---|---|
| <7 | 936 | 48.7% | 50.1% | −1.4 pp |
| 7–14 | 484 | 50.0% | 50.1% | −0.1 pp |
| 14–21 | 256 | 52.7% | 50.1% | +2.7 pp |
| 21–28 | 135 | 43.7% | 49.9% | **−6.2 pp** |
| 28+ | 62 | 56.5% | 49.8% | **+6.7 pp** |

Every Wilson interval spans the implied value.

## Test 1 — the mechanism is real, and that is the point

This is a diagnostic, not a market test: a 1H total plus a full-game spread does
not uniquely determine the market's implied zero mass without a distributional
assumption. It cannot show the market is wrong, in either direction.

| bucket | n | dog shutout | Wilson 95% | fav shutout | dog mean | fav mean |
|---|---|---|---|---|---|---|
| <7 | 952 | 8.6% | 7.0–10.6% | 4.3% | 12.4 | 14.6 |
| 7–14 | 493 | 12.0% | 9.4–15.1% | 3.7% | 10.4 | 17.1 |
| 14–21 | 257 | 16.3% | 12.3–21.4% | 1.6% | 8.1 | 19.0 |
| 21–28 | 135 | 17.0% | 11.6–24.3% | 0.0% | 8.3 | 21.1 |
| 28+ | 65 | **23.1%** | 14.5–34.6% | **0.0%** | 5.3 | 23.5 |

Monotone, large, and exactly as asymmetric as the theory says. **So the finding
is not "there is no censoring." It is: the censoring is real, strong and
monotone — and the market prices it correctly.** That is a much more useful
result than a null, and it is the one that closes the question.

**A correction worth recording.** The plan quoted a 37.6% underdog shutout rate
at 28+. On the real-close cut it is **23.1%**. The higher figure came from the
full 3,601-row population including the 1,699 games no book priced — which are
not a random sample, they are the games nobody wanted to price. Another
instance of the standing rule: split on `line_real` before concluding anything.

## What this does and does not close

**Closed:** the censoring-specific engine. There is no evidence of exploitable
residual information in spread, and the point estimate is below the vig hurdle
even if real.

**Not closed:** whether the market errs on some *other* conditioning variable —
weather, pace, travel, rest. This tested spread because spread is what the
censoring argument predicts. A different hypothesis needs its own
pre-registration and its own out-of-sample test.

**Kept:** the scoring machinery. `brier`, `log_loss`, `brier_multi`, `wilson`
and `reliability` did not exist anywhere in this repo before — the only model
probability, `score.py`'s `predict_proba`, is uncalibrated and is squashed into
a 0–100 display score without ever being scored. They are written
three-outcome-aware so a future engine emitting P(under)/P(push)/P(over) can be
graded by the same functions, and so that its numbers are comparable to these.

**One design call this validates anyway.** The underdog's first-half score is
extremely lumpy — 7 (16.5%), 10 (13.1%), 0 (11.6%), 14 (11.3%), 3 (10.7%)
account for 63% of games. Any future scoring model must be **discrete**. A
continuous positive distribution would misfit that support and could not state
a push probability at all.
