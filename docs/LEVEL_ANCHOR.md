# The prior-season level anchor — tested, not adopted

**Run 2026-09-13. `PRIOR_SEASON_WEIGHT` stays 0. The seeded code ships inert.**

Re-run it with:

```
python scripts/level_anchor_gate.py --train-seasons 2023 --test-season 2024
```

## The change

`etl/features._season_to_date` computes a team's form as an expanding mean over
its prior games **this season**. The `shift(1)` that makes it leak-free also
makes game 1 of every season NaN and game 2 a one-game mean, and that propagates
into `proj_1h_total` / `proj_1h_ratio`. 68 of the regressor's 115 features are
NaN at zero games played.

The change seeds that window with `k` synthetic games of the team's
**prior-season** mean, so game 1 reads the prior-season mean and the seed decays
as `k/(n+k)`. `k=0` reproduces the unseeded frame exactly, which makes the
incumbent an *arm of the experiment* rather than a rival code path.

## The rule, fixed before the run

- weeks 1-2 must **improve** — paired gain > 0 with a 95% CI excluding 0;
- weeks 3+ must be **non-inferior** — within 0.10 points of MAE;
- grid `k ∈ {0, 0.5, 1, 2, 3}`, declared in advance;
- tune on 2023 → 2024, **2025 held out entirely** as the confirmation set.

Every comparison is **paired** on the same games: both arms score the identical
slate, so the statistic is the per-game difference in absolute error, not two
MAEs with their own noise.

## What happened

**No adoption.** Weeks 1-2 — the bucket the change was built for — showed
nothing. Pooled over both tuning splits (n=180) the gains ran −0.019 to +0.131,
every interval spanning zero, and not monotone in `k`.

| bucket | n | k=0.5 | k=1 | k=2 | k=3 |
|---|---|---|---|---|---|
| weeks 1-2 (pooled) | 180 | +0.033 | −0.019 | −0.001 | +0.131 |
| weeks 3+ (2024) | 648 | +0.038 | **+0.064** | **+0.094** | **+0.117** |

Weeks 3+, which nobody was testing, improved monotonically with an interval
excluding zero at `k ≥ 1`. **The seed helps where a team already has *some*
data — ordinary shrinkage — not where it has none.**

## Why it has no purchase on weeks 1-2

**The NaNs are not INHERENTLY the problem.** `HistGradientBoostingRegressor`
handles missing values natively: it learns a routing direction for them at each
split. "No games played yet" is a usable *signal* to the tree, not an absence.
Replacing it with a noisy prior-season estimate trades one imperfect input for
another, and the two roughly cancel.

Stated no more strongly than the experiment supports: **this particular remedy
was not justified**. Native handling means early-season NaNs are not broken by
construction; it does not prove missingness costs nothing. Missingness can still
remove information, and it can still create a train/serve distribution shift.
What was tested, and failed, is the expanding-mean prior-season seed.

The premise this change was built on — 68 NaN features, therefore weeks 1-2 are
broken — conflated **missing** with **harmful**.

## Why MAE was close to the wrong question

The seed measurably lifts bv_line's **level**. On 2026 weeks 1-2, against a
realized mean of 26.90:

| k | 0 | 0.5 | 1 | 2 | 3 |
|---|---|---|---|---|---|
| predicted mean | 24.26 | 24.20 | 24.39 | 24.72 | **25.20** |

That recovers about a third of the bias, and MAE barely registers it — a
~1-point correction against ~11 points of per-game spread sits well under the
noise floor.

But this system does not spend MAE. It spends `gap = line − bv_line` against
`BET_GAP_PTS`, so a level shift changes **selection** even when accuracy is
flat. On the 23 of those 2026 games carrying a real captured 1H close, the count
clearing the bar fell **14 → 11** across the grid.

**Decision 2026-09-13: honour the pre-registered rule and adopt nothing.** The
rule existed precisely so that an unexpected result could not rewrite the
question after the fact. "The seed reduces bv_line's level bias and tightens
selection" is a *different hypothesis* from the one tested here, and it deserves
its own pre-registration against the still-untouched 2025 set — judged on
**bias and gate-crossing count**, with MAE demoted to context. The gate already
reports both, fixed before that question is asked.

## What shipped anyway

Two genuine defects surfaced on the way and are fixed on their own merits:

- **`_cached` served an empty payload as a permanent hit.**
  `data/cache/{sp,adv,talent,roster,returning}_2026.json` were all 2 bytes
  (`[]`), written 2026-06-03 before 2026 data existed, and there is no expiry —
  so any *local* 2026 feature build silently NaN'd eight more columns, with no
  error and no log line. (GHA runners start cold and refetch, which is exactly
  why it went unnoticed for three months.) An empty payload is now a miss, and
  an empty result is never written.
- **A season whose priors cannot be fetched now warns instead of killing the
  build.** `build_feature_frame` asks for a prior per season in the games table
  — including the current one, whose full-year aggregate does not exist yet.
  With the guard above, that hole would otherwise take down every feature build,
  trading a silent wrong answer for a loud useless one. Same trade
  `backfill.py` already makes for venues.
