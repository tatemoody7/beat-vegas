# The blend — what weight does the close deserve against our number?

**Verdict (pre-registered rule): BLEND WINS AT CLOSE.** Bucket weights: **NOT ADOPTED.**
Measurement only — nothing reads the result. Run 2026-09-15 with
`scripts/blend_gate.py --freeze` (GitHub Actions `study.yml`, the campus network filters
Neon's port 5432); arithmetic and both rules in `beatvegas/backtest/blend.py`, pinned by
`tests/test_blend.py`. Registry rows **H3A** and **H3B** in `docs/HYPOTHESES.md`.

The word is the rule's word. Read the margins before reading the word: the blend beats
the close by **0.020** and **0.006** points of MAE in the two held-out seasons, and both
paired intervals span zero. What the study settles is the *weight*, not a win.

## Why it was run

Every number this system owns is worse than the number on the screen: the residual gate
measured the 2025 close at MAE 8.73 against the incumbent's 9.23. The cheapest way to ask
what a market-blind number is still worth is one parameter — `line* = w·close +
(1−w)·bv_line` — fitted to predict the realized first half. If w lands near 1, `bv_line`
is decoration; if it lands near 0.5, the market is leaving something on the table. The
answer also prices the gap: the board spends `close − bv_line` against a 1.75-point bar,
and `close − line*` is `(1−w)` of that, so the fitted w says what a 1.75 gap is in raw
points.

## The rule, written before the numbers were read

**H3A (global w).** Grid w ∈ [0, 1] by 0.01. Fit on the training seasons by **MAE against
the realized 1H total** — never on ROI or hit rate — and report the held-out season for
**2023 → 2024** and **2023-24 → 2025** beside w = 1 (the close) and w = 0 (`bv_line`).
Ties go to the larger w. **BLEND WINS AT CLOSE** only if the blend's MAE is below both
arms in both held-out seasons; **CLOSE WINS** if the close is at or below the blend in
both; otherwise **NO STABLE WINNER**. Bias by season and spread bucket and gate crossings
at 1.75 are reported, never optimised. After both splits, one final w is fitted on all of
2023-25 and frozen in `data/blend.json`, **read by nothing**; only that value may ever be
applied prospectively.

**H3B (bucket w, its own family).** Per held-out season, per bucket (<14 / 14-21 / 21-28 /
28+ absolute spread): fit a bucket w on the training rows, then take the paired per-game
|error| difference against the global w on the test rows, one-sided paired bootstrap
(2,000 draws), **Holm across the four buckets within the season at 5%**. A bucket is
adopted only if it passes in **both** 2024 and 2025 with **n ≥ 150** test rows in each;
**28+ is never adopted on its own**.

"At close" is in the verdict word on purpose: the 2023-25 market input is the closing
line, which holds information that did not exist when a bet could be placed.

## The rows

The **stored walk-forward `bv_line`** in `postmortem_games` (scope `hist_2023_25`, FBS,
real captured close, graded first half): **1,902 games — 626 / 639 / 637** by season, the
same cut every other 2023-25 study has read (this is the sixth). A refit was tried first and
is kept as `--source refit`: the Neon feature frame starts at 2023, so nothing can predict
2023 walk-forward from it. That refit run did check the arms — on 2025 (n = 568) w = 1
reproduced the residual gate's close MAE **8.728** and w = 0 the incumbent's **9.225**.

## What it found

- **The market gets four fifths of the number.** w = 0.80 fitted on 2023, 0.77 fitted on
  2023-24, **0.80 frozen on all three seasons** (MAE 8.567 in sample). `bv_line` is worth
  about a fifth of a forecast.
- **Against the close the blend is a rounding error.** Held-out MAE 8.242 vs 8.262 (2024)
  and 8.697 vs 8.703 (2025); paired difference −0.020 (−0.058..+0.018) and −0.006
  (−0.056..+0.047). The rule's word is earned by the letter; the market is not beaten by
  any margin a bettor could use.
- **Against `bv_line` the blend is clearly better in 2025 and not in 2024.** −0.229
  (−0.401..−0.071) in 2025; −0.059 (−0.211..+0.086) in 2024. The 2025 gain is where
  `bv_line` runs +0.50 high while the close runs −0.89 low.
- **A 1.75 bar on the blended gap is an 8-point raw gap.** Raw-gap equivalent 8.8 pts
  (w = 0.80) and 7.6 pts (w = 0.77). Every game that cleared 1.75 on the raw gap — 126 in
  2024, 64 in 2025 — fails it on the blended gap. That is arithmetic, not a finding, and
  it is the honest scale of the current rule: a 1.75-point disagreement with the market is
  worth 0.35 points of forecast.
- **Bias is the close's, with the sign.** The close runs about −0.9 (too low) at <14 in
  both seasons and **+3.4 (too high) at 28+ in 2025**, where `bv_line` runs +4.5; at 28+
  in 2024 both run low. n at 28+ is 19 and 28.
- **No bucket earns its own weight.** The only candidate is 14-21 in 2024 (one-sided
  p 0.018, Holm 0.072, n = 92) and it does not repeat in 2025 (w = 1.00, p 0.500). At 28+
  the fitted bucket w flips 0.95 → 0.00 between seasons and the 2025 bucket weight is
  worse than the global one by a full point.
- **2026 at decision time, descriptive, 49 graded games** (last final build before
  kickoff, the cards' consensus, w = 0.80): MAE blend 7.319 / consensus 7.342 / bv 7.405;
  bias −1.08 / −0.57 / **−3.14**. Consistent with the week-2 read of `bv_line` running low.

### Walk-forward splits

| train → test | n train | n test | w | test MAE blend | close | bv | blend−close (paired 95%) | blend−bv (paired 95%) | bias blend / close / bv | clear 1.75 before → after | changed side | raw-gap equivalent of 1.75 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| [2023] → 2024 | 626 | 639 | 0.80 | 8.242 | 8.262 | 8.301 | -0.020 (-0.058..+0.018) | -0.059 (-0.211..+0.086) | -0.86 / -0.92 / -0.61 | 126 → 0 | 126 | 8.8 pts |
| [2023, 2024] → 2025 | 1265 | 637 | 0.77 | 8.697 | 8.703 | 8.926 | -0.006 (-0.056..+0.047) | -0.229 (-0.401..-0.071) | -0.57 / -0.89 / +0.50 | 64 → 0 | 64 | 7.6 pts |

### Bias and MAE by spread bucket (held-out seasons)

| test | bucket | n | bias close / bv / blend | MAE close / bv / blend |
|---|---|---|---|---|
| 2024 | <14 | 471 | -1.13 / -0.63 / -1.03 | 8.363 / 8.339 / 8.327 |
| 2024 | 14-21 | 92 | +0.01 / +0.21 / +0.05 | 8.253 / 8.837 / 8.359 |
| 2024 | 21-28 | 57 | -0.42 / -0.89 / -0.51 | 7.136 / 7.028 / 7.081 |
| 2024 | 28+ | 19 | -1.87 / -3.17 / -2.13 | 9.184 / 8.589 / 9.061 |
| 2025 | <14 | 473 | -1.01 / +0.55 / -0.65 | 8.609 / 8.793 / 8.591 |
| 2025 | 14-21 | 87 | -0.76 / +0.10 / -0.57 | 8.845 / 9.032 / 8.846 |
| 2025 | 21-28 | 49 | -2.38 / -1.50 / -2.18 | 9.597 / 9.635 / 9.527 |
| 2025 | 28+ | 28 | +3.36 / +4.47 / +3.61 | 8.286 / 9.602 / 8.576 |

### Bucket weights (H3B, own family): **BUCKET W: NOT ADOPTED**

- <14: not adopted (2024: n=471, Holm p=0.840; 2025: n=473, Holm p=1.0)
- 14-21: not adopted (2024: n=92, Holm p=0.072; 2025: n=87, Holm p=1.0)
- 21-28: not adopted (2024: n=57, Holm p=1.0; 2025: n=49, Holm p=1.0)
- 28+: not adopted (2024: n=19, Holm p=1.0; 2025: n=28, Holm p=1.0)

| test | bucket | n train | n test | w bucket | MAE bucket-w | MAE global-w | mean |err| diff (95%) | one-sided p | Holm p | passes |
|---|---|---|---|---|---|---|---|---|---|---|
| 2024 | <14 | 453 | 471 | 0.66 | 8.318 | 8.327 | -0.009 (-0.041..+0.023) | 0.280 | 0.840 | no |
| 2024 | 14-21 | 103 | 92 | 0.90 | 8.306 | 8.359 | -0.053 (-0.103..-0.003) | 0.018 | 0.072 | no |
| 2024 | 21-28 | 45 | 57 | 1.00 | 7.136 | 7.081 | +0.055 (-0.061..+0.181) | 0.832 | 1.000 | no |
| 2024 | 28+ | 25 | 19 | 0.95 | 9.153 | 9.061 | +0.093 (-0.149..+0.334) | 0.775 | 1.000 | no |
| 2025 | <14 | 924 | 473 | 0.62 | 8.598 | 8.591 | +0.007 (-0.033..+0.047) | 0.625 | 1.000 | no |
| 2025 | 14-21 | 195 | 87 | 1.00 | 8.845 | 8.846 | -0.001 (-0.129..+0.126) | 0.500 | 1.000 | no |
| 2025 | 21-28 | 102 | 49 | 0.89 | 9.563 | 9.527 | +0.037 (-0.055..+0.128) | 0.800 | 1.000 | no |
| 2025 | 28+ | 44 | 28 | 0.00 | 9.602 | 8.576 | +1.026 (+0.281..+1.745) | 0.997 | 1.000 | no |

## What this licenses, and what it does not

**It licenses a number:** w = 0.80, frozen, in `data/blend.json`, and the statement that a
1.75-point gap is about a fifth of a point of forecast. Any future use — a blended gap on
the board, a rescaled bar — is a **separate, registered, prospective** test on 2026
decision-time snapshots, and this row does not authorise it. The frozen w is the only
weight that may be carried into such a test.

**It does not license** calling the market beaten (the paired difference to the close
spans zero twice), changing `BET_GAP_PTS`, or a spread-bucket weight (H3B is
`tested-null`). It does not speak to decision time at all: the 2023-25 input is the close.

## Reproduce

```
gh workflow run study.yml -f script=blend_gate -f args="--freeze --out reports/blend"
PYTHONPATH=. python scripts/blend_gate.py --freeze --out reports/blend            # off campus
PYTHONPATH=. python scripts/blend_gate.py --source refit --out reports/blend       # arms check
```

Reads Neon; writes `reports/blend_<UTC>.{md,json,csv}` (gitignored) and, with `--freeze`
and both splits evaluated, `data/blend.json`; exits 0 whatever the numbers say.
