# Share engine — spec (decided 2026-09-13, spec written 2026-09-15, NOT built)

## What it is

A second first-half engine that **takes the market's full-game total and spread as
given** and predicts only how the first half splits from them — and emits a
**discrete** distribution over 1H totals, so P(under), P(push) and P(over) at any
posted number fall out of it. It runs beside the incumbent market-blind `bv_line`,
which stays **champion** until the challenger beats it under the rules below.

It exists because of three measured facts:

1. **The market's 1H line is centred**: over 1,902 real closes the median realized 1H
   total minus the posted line is **0.000**, and the blind under lands 49.5%
   ([1h-market-is-efficiently-priced]). The lever was never direction; it is *which*
   games, and by *how much*.
2. **`bv_line` runs low and blind to blowouts**: live 2026 bias −3.1 overall,
   **−10.2 on 28+ spreads** with an implied share of .46 against a realized .68
   (`RANKING_AND_TRUST.md` §10). `spread` is not in `FEATURE_COLS`; a market-blind
   regressor cannot know the game is a 30-point mismatch.
3. **`bv_sigma` is one number per slate** (11.26 on every 2026 row), so nothing in
   the current engine can be turned into a per-game probability, and `ev` is a
   price-shopping read, not wager EV (`RANKING_AND_TRUST.md` §8b). **A true EV gate
   needs a calibrated P(under).** This engine is the only thing on the roadmap that
   can supply one.

## What it is not

- Not a two-sided bet. `TWO_SIDED.md` found no over-side signal at the bar; the
  engine's outputs feed the **under** decision only until a separate pre-registered
  test says otherwise.
- Not the censoring engine. `CENSORING_STUDY.md` said DO NOT BUILD a spread-only
  correction to the *price*; this predicts the *split*, conditional on the market's
  own numbers, and is graded on proper scoring rules against the market's close.
- Not a replacement. The board keeps ranking on `bv_line`'s gap until promotion.

## Inputs (all as-of the decision time — `lines.as_of`, never `games.spread`)

- Market: full-game total and spread from the **consensus as of the build time**
  (`consensus_as_of`), never the mutable `games.spread` column
  ([as-of-reads]). The 1H posted line is **not** an input (it is what we grade against).
- Team style, season-to-date and prior-season, leak-free: 1H `pass_rate`,
  `explosive`, `success`, `epa` from `fh_team_game`; pace from `team_tempo`; the
  existing `BV_FEATURE_COLS` minus anything derived from a 1H line.
- Optional later: decision-safe weather (`weather_obs`, leads 24/72) — only if
  `WEATHER_STYLE.md` earns it.

## Output

A probability mass function over integer 1H totals **0..70** for the game
(the dog's 1H score is lumpy — 7/10/0/14/3 are 63% of outcomes — so a continuous
fit misfits the support; `CENSORING_STUDY.md` banked this). From it:
`P(under L)`, `P(push L)`, `P(over L)` for any posted `L`, the median as the
engine's "number", and the interval.

Candidate model families, to be compared under the same gate:
1. **Ordinal / multinomial gradient boosting** on the total directly.
2. **Two-team discrete** (home 1H points, away 1H points as separate discrete
   distributions with a copula or independence) — the censoring mechanism is
   real and monotone even though the market prices it; a two-team model represents
   it natively.
3. **Quantile regression** of the 1H total on the inputs, discretised.

## Promotion gate (pre-registered; the same eight criteria the external review listed)

Walk-forward by season (train ≤ 2023 → test 2024; train ≤ 2024 → test 2025), on
FBS-vs-FBS games with a **real captured 1H close**, decided games for hit rates
and three-outcome scoring for the distribution. Reuse `beatvegas/backtest/censoring.py`:
`brier_multi`, `log_loss`, `wilson`, `reliability` (quantile bins),
`calibration_intercept_slope`, `brier_delta_ci`.

The challenger earns its prospective paper arm (see the 2026-09-15 amendment below;
it is no longer promoted straight to *drive the gap*) only if **all** hold:

1. **Beats the market's own close on MAE** out of sample (the bar is **8.582**,
   the close's MAE on the real-close cut; `bv_line` does not clear it).
2. **Positive vig-free CLV** for the picks it would have made at the decision-time
   consensus, graded at the centred consensus close (never a single book's last quote
   — `HR_LAG.md`: the books diverge into kickoff).
3. **Profitable ROI after realistic prices** — Hard Rock's actual under price where
   captured, −110 otherwise, with the `centred_snaps(strict=True)` filter.
4. **Stability across seasons**: the same sign of edge in both test seasons.
5. **Stability after the 2023 timing regime**: no reliance on pre-2023 rows for the
   claim (the rule change cut plays; the engine must not learn a 2019 pace).
6. **Sensible calibration**: intercept ≈ 0 and slope ≈ 1 on the held-out season,
   and quantile-binned reliability with realized rates inside their Wilson intervals.
7. **Not one subgroup**: the edge does not vanish when the 28+ bucket, or any single
   week band, is removed.
8. **Survives ablation**: removing the market total and spread must *hurt* (they are
   the point of the engine); removing weather, if present, must not be what carries it.

Report as `docs/SHARE_ENGINE.md` with **bias, MAE, gate-crossings and blast radius**
side by side — MAE alone is near-blind to what a level shift does to selection
([level-anchor-not-adopted]).

## Amendment 2026-09-15 — what a pass licenses (Tate)

The eight criteria above are unchanged. What changed is what passing them earns.
`docs/HYPOTHESES.md` declares the 2023-25 real-close set **spent** — five studies had
read it before this spec was written — so a pass on that set is a look at in-sample data,
not fresh validation. **Passing all eight licenses a prospective paper arm, not
promotion**: the engine's picks are logged on paper beside the champion's, one canonical
observation per decision, under a stopping clock registered in its own row before the
first pick is logged. `engine: share` flips only after that arm clears its clock. A fail
on any criterion is a finding and changes nothing. Registry row **H-SHARE**.

## Blast radius on the board (measure before promotion)

The number of games whose Hard Rock gap crosses `BET_GAP_PTS` when `bv_line` is
replaced, and the number of real-money BETs that flip. The weather gate refused
activation at 31–62 crossings against a limit of 5 (`WEATHER.md`); the same discipline
applies. A promotion is a config flip (`engine:` in `config.yaml`, the residual
engine's precedent) executed **between weeks**, never on a build day.

## Build plan (sessions, not hours)

1. Data frame builder: as-of market + style + labels, walk-forward splits, tests.
2. Family 1 (ordinal boosting) end to end through the gate report.
3. Family 2 (two-team discrete) if family 1 fails the calibration criterion.
4. Gate report; Tate's promotion call; only then wire `engine: share`.

Nothing above changes week 3 or week 4. The champion is unchanged until the report exists.
