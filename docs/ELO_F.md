# H-ELO-F — CFBD pregame Elo as two extra inputs

**NOT MET (`study.yml` run 37566955440, 2026-10-07; one look, as registered).** Adding home and
away pregame Elo to the champion on its own 2023+ window changed its first-half error by −0.019
points a game [−0.087, +0.050], p 0.62 — indistinguishable from zero. Units per game +0.018
[−0.000, +0.036], p 0.06: not worse, not shown better. Elo does not enter the champion.

Registry: `docs/HYPOTHESES.md` H-ELO-F (family `elo-input`, one comparison).

## Provenance

- Live frame (2023+, rows need a total): 2,717 rows; 2025 trained on 2023-24, 2026 on 2023-25;
  749 games graded at a real consensus 1H close inside 2 h (622 / 127). Elo present on every row.
- Same grading and incumbent identity as production (`bv_line_for_slate`).

| Arm | 2025 MAE | 2026 MAE | Pooled MAE | market close |
|---|---|---|---|---|
| incumbent | 9.28 | 8.71 | 9.19 | 8.73 |
| + pregame Elo | 9.30 | 8.51 | 9.17 | |

## What it says

Elo, a full-game strength rating, adds nothing the champion's inputs do not already carry on a
2-3 season window. It was the free first test before a first-half opponent-adjusted rating study
(H-RIDGE-F, proposed): a null here lowers that study's prior but does not decide it, because a
first-half-specific rating measures something Elo does not. Note H-HIST: the bigger handicap was
training history, so any new input should be judged on the longer window if that is adopted.
