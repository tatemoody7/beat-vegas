# H-MARGIN: a market-blind margin model for the CFBD Model Pick'em

**Verdict (2026-10-07, one run): the model misses the final margin by about 1.4 points more than
the Vegas closing spread (13.2 vs 11.8), in both test seasons, and it is a coin flip against the
spread (49%).** That is the expected result for a model that never sees the market and was built on
first-half inputs. It changes nothing: H-MARGIN is an exploratory measurement that licenses nothing,
and entering the Pick'em does not depend on it (Tate, 2026-10-07). The Pick'em itself is the honest
external test from here.

## What was measured

- **Model** `bv_margin_v1` (`beatvegas/model/margin_line.py`): the champion's 58 market-blind inputs
  (`BV_FEATURE_COLS`: no spread, no market column), the same HGB and walk-forward global intercept;
  target home points minus away points; trained on every played FBS-vs-FBS season before the test
  season, from 2003 (`CHAMPION_TRAIN_MIN_SEASON`); every game with both final scores, no first-half
  result required.
- **Benchmark** the Vegas closing spread: `games.spread`, CFBD's home-relative line (negative = home
  favored), effectively the close for a played game; implied home margin = −spread. Never an input.
- **Tests** 2025 (trained 2003-24) and 2026 games played before the run (trained 2003-25), games with a
  closing spread. One fit per test season, as the champion trains.
- **Run** `study.yml` run 37670166376 (`scripts/margin_backtest.py`), frame fingerprint
  `23cb43a0a69c29aa`, computed 2026-10-07T18:57Z on the runner.

## Results

| test | n | train | model MAE | Vegas MAE | MAE diff, model − Vegas (95%) | model MSE | Vegas MSE | model straight-up | Vegas straight-up | model ATS |
|---|---|---|---|---|---|---|---|---|---|---|
| 2025 | 790 | 2003-2024 | 13.13 | 11.85 | +1.28 (+0.85 to +1.70) | 276.5 | 227.1 | 70.1% (66.8–73.2) | 72.8% (69.6–75.8) | 48.7% (45.2–52.2) |
| 2026 | 268 | 2003-2025 | 13.26 | 11.51 | +1.75 (+0.92 to +2.60) | 277.7 | 219.0 | 76.1% (70.7–80.8) | 81.3% (76.2–85.5) | 50.2% (44.2–56.2) |
| pooled | 1,058 | | 13.16 | 11.76 | +1.40 (+1.04 to +1.77) | 276.8 | 225.0 | 71.6% (68.9–74.3) | 74.9% (72.2–77.4) | 49.1% (46.1–52.1) |

Intervals: Wilson 95% for the percentages, a paired bootstrap (2,000 resamples) for the MAE
difference. Straight-up skips a predicted or actual tie; ATS skips a push and a game where the model
equals the spread. Per-game rows are in the run's artifact (`margin_backtest_*_games.csv`).

## Reading it

- **The market is more accurate, clearly.** The interval on the MAE difference sits wholly above zero
  in both seasons; this is not noise.
- **Against the spread it carries nothing**: 49.1% on 1,058 games, interval 46–52%. The model's
  disagreements with the spread are not information about who covers.
- **For scale on the Pick'em:** CFBD's own pack model finished #2 in the 2024 contest at 12.07 MAE
  (`docs/CFBD_CATALOGUE.md`). At about 13.2 this model would sit below the leaders. The leaderboard is
  scored relative to the Vegas close, so a public number this far behind it is what an honest
  first entry looks like.
- **Why it is behind, without testing it:** the inputs were chosen for first-half totals (pace,
  first-half scoring, weather), not for who wins by how much. Margin-specific inputs (efficiency
  differentials, points per drive) were offered on 2026-10-07 and Tate chose the champion's inputs for
  simplicity. Improving the margin would be its own registered row, not a change to this one.

## What comes next (Tate's calls already made)

1. The weekly scorer stores `bv_margin_v1` predictions for every FBS-vs-FBS game (never a champion read).
2. Automatic submission to the Pick'em by its API before the first kickoff, once Tate creates the
   account and credential.
