# H-HIST — training the champion on 2003+ instead of 2023-25

**MET (`study.yml` run 37567344521, 2026-10-07; one look, as registered).** All three longer
training windows (from 2003, 2010 and 2015) made the champion's first-half number more accurate
by about 0.42 points a game, with the interval well clear of zero, and none made its picks worse.
Pooled over 2025 and 2026 to date, the champion's error fell from 9.17 to about 8.75 points a
game, level with the market's own close (8.73). This licenses a **proposal** to raise the live
training window (its own PR, Tate's call, stating its effect on H-STOP-2). Nothing live has
changed.

Registry: `docs/HYPOTHESES.md` H-HIST (family `train-history`, Holm across 3 arms). The first
dispatch (run 37566306294) crashed before any number (an all-NaN column in an early fold; PR
#303); it is not a look.

## Provenance (Analysis Rules order)

- **Data**: the study frame built on the runner with `min_season=None, require_total=False`
  (fingerprint in the report; sklearn 1.9.1, python 3.11.16): 17,447 FBS-vs-FBS rows, 2003-2026.
  Training pool 16,950 played rows, of which **7,042 (2003-2012) have no full-game total** and
  enter only through the study-only exception (CFBD's free `/lines` has none before 2013).
  Score pool: 2025 (trained through 2024) and 2026 games played before the dispatch (trained
  through 2025); 749 graded at a real consensus 1H close inside 2 h (622 in 2025, 127 in 2026).
- **Inputs that do not exist in old seasons stay empty**: 2003 rows have 14 all-empty inputs
  (talent, roster, returning production, pace, weather), 2008-2012 have 10, 2014 has 8, 2016-20
  have 6 (pace, weather), 2024 none. Mean empty share per row: 36% (2003) → 7% (2024). Pregame
  Elo is complete in every season. History arms fit each slice on the inputs that have a value
  in it (an all-empty column offers no split).
- **Grading**: actual = the trusted first-half total; line = consensus `1H_total` close inside 2 h
  (Hard Rock's own close reported beside it in 2026); flat −110; no proxy row graded.
- **Incumbent**: the champion as live trains it (2023+), never trained on the history.

## Accuracy (the primary test)

| Arm | 2025 MAE | 2026 MAE | Pooled MAE | Pooled bias (pred − actual) | Δ\|err\| vs incumbent [95%] | Holm p |
|---|---|---|---|---|---|---|
| incumbent (2023+) | 9.27 | 8.71 | 9.17 | +0.95 | — | — |
| from 2003 | 8.90 | 7.99 | 8.74 | +0.07 | −0.43 [−0.63, −0.22] | 0.002 |
| from 2010 | 8.94 | 7.82 | 8.75 | −0.53 | −0.43 [−0.65, −0.20] | 0.002 |
| from 2015 | 8.92 | 7.97 | 8.76 | −0.01 | −0.42 [−0.61, −0.21] | 0.002 |
| market close | 8.90 | 7.87 | 8.73 | | | |

Part of the gain is level: the 2023+ incumbent ran 1.4 points high in 2025 and 1.2 low in 2026,
while the longer windows sit near zero. The rest is accuracy beyond level (the error fell more
than the bias alone explains).

## Picks (secondary, never gated)

Portfolio units per game vs the incumbent: +0.012 [−0.020, +0.042] (2003), +0.026 [−0.004,
+0.056] (2010), +0.021 [−0.009, +0.051] (2015) — not worse, and not shown better. Records under
the champion's rule, pooled, cap 5: incumbent 38-42 (−7.45u); from 2003 43-39 (+0.09u); from
2010 46-36 (+5.82u); from 2015 48-34 (+9.64u). These are 82-game records with intervals spanning
break-even; picking a floor by them would be choosing on noise after the fact.

## What this does and does not say

- It says the champion's training history, not its inputs, was its biggest accuracy handicap:
  with 13-23 seasons instead of 2-3 it reaches the market close's accuracy on these games.
- It does not say any floor is better than another (all three are within 0.01 MAE), and it does
  not say the picks will win; the betting results are not distinguishable from the incumbent's.
- 2025's closes were already read for rule selection; this row measured training data on them.

## Decision for Tate (registered consequences, nothing automatic)

Whether and when to raise `FRAME_MIN_SEASON` (and with which floor) is a separate PR. It changes
the model H-STOP-2's clocks measure mid-season; that PR must state how the clock treats it.
