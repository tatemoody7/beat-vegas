# The H-INSEASON challenger family — prospective paper collection

Registry row **H-INSEASON-P**. Written before the first challenger pick was logged, per
the rule H-INSEASON's own row set. `docs/MODEL_LEVEL_2026.md` holds the developmental
result this follows from.

> **STATUS 2026-09-22 — WITHDRAWN BEFORE THE FIRST PICK. `challenger_picks` holds zero rows
> and stays that way.** The gate that would have licensed this family, H-INSEASON, is
> **tested-null on the run of record**: run on the data the live board is actually fitted on
> (the runner's September 2026 CFBD reference tables), every arm beats the incumbent on both
> primaries but the Holm-adjusted p is 0.056 against the row's 0.05. The earlier pass (0.004)
> came from a frame built on this Mac's June 2026 cache of the same tables; the two runs were
> reconciled the same day — same frame and same library reproduce to six decimals on both
> machines, and only the reference-data snapshot differs (`docs/MODEL_LEVEL_2026.md`,
> Reconciliation). Tate's disposition: the criterion is judged on the data the system uses.
> The table, the arm code and `scripts/challenger_position.py` remain for a future family
> that earns its own registry row; `scripts/build_card.py` writes no challenger row unless
> `CHALLENGER_COLLECT=1`, which no workflow sets. The `bv_intercept` backfill stands (it is a
> correct value on every row, −1.2360, and the H-NEGGAP-L arithmetic still reads it).

## What licensed this, and what did not

H-INSEASON passed its **developmental** gate. That gate's primary measure was level bias,
and **for this estimator that measure is partly mechanical**: the arm subtracts an estimate
of the season's own level error and is then judged on that error, so any running mean
converging to the season mean drives the metric toward zero whether or not one prediction
improves. The pass therefore establishes **no prospective betting value** and may not be
quoted as evidence that an in-season intercept improves the betting system.

The single thing it licenses is this: properly registered prospective paper collection.

**No k has been chosen, and none was chosen from that run** (Tate, 2026-09-20). All four
arms passed, the developmental gate contained no ranking rule, and picking the
best-looking arm out of the same 2024-26 data would be post-hoc. The four go forward
together.

## The arms — frozen

`c_t = (1 − w)·c_prior + w·c_season`, `w = n/(n + k)`, for **k ∈ {25, 50, 100, 200}**.

`c_prior` is `bias_corrections(train)["global"]`, what the champion applies. `c_season` is
`mean(actual − RAW pred)` over the season's games completed strictly before the build —
the raw, PRE-intercept prediction, because deriving it from a calibrated one would
re-apply `c_prior` scaled by `w`. At n=0 the weight is 0 and the arm IS the champion.

All four run on **identical decision-time snapshots**: the same card build, the same Hard
Rock lines and prices, the same gates, the same `BET_GAP_PTS`. The only thing that differs
between an arm and the champion is the intercept, and therefore the gap.

## What this never touches

- **Real-money selection.** Challenger picks are paper, always, with no exception.
- **H-STOP.** The champion's clock is completely unchanged. Challenger rows live in their
  own table (`challenger_picks`), not in `manual_picks`, so no query that feeds the
  bankroll, the 5-bet cap, Results or H-STOP's observation set can see them even by
  mistake.
- **The model.** `bias_corrections` and `BET_GAP_PTS` are not edited.

## Observations

One canonical observation per decision per arm: an arm's qualifying pick at the build that
qualified it, at the Hard Rock price available then, uncapped (paper), 1H unders. A game an
arm does not select produces no observation for that arm. The arms will select overlapping
but different sets, which is the point.

Collection starts at the first card build after this row merges.

**Data note (2026-09-22).** `Prediction.bv_intercept` is written only by `score_slate`, and a
scoring run rewrites only its target week, so every 2026 row scored before PR #201 merged
(weeks 1-4, 214 rows) carried NULL — and `completed_season_rows` requires the column, so the
arms would have logged nothing and `c_season` could only ever have seen week 5 on. Those
rows were backfilled with the season's one intercept, recomputed on the runner the way
`score_slate` computes it (`scripts/backfill_bv_intercept.py`, `backfill_intercept.yml`) and
required to match the value the runner demonstrably applied, **−1.2360**, within 0.001 before writing (the −1.8092 in `MODEL_LEVEL_2026.md` is a Mac-platform number; see its correction note). Only the
new column moved; `bv_line` is checksummed unchanged. The as-of rule is unaffected: it is
SQL on `start_date` and `first_half_total`, not on when the column was filled.

## The rule — two clocks per arm, Bonferroni across arms

Both clocks are **absolute** quantities, the same two the champion is measured on, so an
arm's numbers can be read beside H-STOP's directly. A paired champion-versus-arm comparison
on matched games is reported as a diagnostic and **decides nothing** — the arms select
different games, so pairing would discard most of the ledger.

| clock | quantity | H0 | H1 (frozen at registration) | sd |
|---|---|---|---|---|
| profit | units won per 1u risked at the actual price | mean 0 | **+0.0731 u/bet** | 0.924 |
| line value | favourable line value vs Hard Rock's strict close, points | mean 0 | **+0.50 pts/bet** | 1.714 |

The alternatives and standard deviations are **H-STOP's own, reused deliberately** rather
than re-derived, so the challenger and the champion are held to the same bar in the same
units. Line-value direction follows `grading.clv_under`: the stored difference is
`closing − bet`, and for an under a line that **falls** is favourable, so favourable line
value is the negated quantity. A "fix" to that sign is a bug.

**Error budget.** Total false-decision budget **5%**, split **/4 across the arms
(Bonferroni, 1.25% per arm)** and then **/2 across the two clocks**, so each arm-clock runs
at **α = 0.625%**. Power 80% (β = 0.20). SPRT bounds, from the same formula that produced
H-STOP's 3.466 / −1.584:

- **ln A = +4.8520**, **ln B = −1.6032**

**Decisions.**

- An arm **PASSES** only when **both** of its clocks cross `ln A`.
- An arm is **DROPPED** as soon as **either** clock crosses `ln B`.
- Until then it accrues. Weekly reporting is descriptive; the boundary is the only decision.

**Naming a k.** If exactly one arm passes, it may be named. **If more than one arm passes,
no k is chosen here** — choosing among passing arms requires its own registered row with
its own rule, written before that choice is read. This is the whole reason the family is
carried forward intact.

**Display.** The four are one **H-INSEASON challenger family**. Wherever a single
challenger must be named, it is the family, never one of its arms.

## Secondary — reported, never optimised

Prediction error (MAE), level bias, hit rate, selection share against the validated 15-20%
band, bias by week band, and the paired champion-versus-arm comparison on matched games.
None of these may move a boundary or select an arm. Level bias in particular is a
**diagnostic only here**, precisely because it is the measure the developmental phase
showed to be partly mechanical for this estimator.

## Honest limits, stated before any number

- A paper ledger accrues slowly. At four builds a week this may take most of a season to
  reach a boundary, and it may reach none.
- Bonferroni across four arms at 0.625% per clock is conservative by design; an arm that
  is genuinely better may still never cross.
- The arms are correlated — they differ only in how fast they trust the same in-season
  estimate — so four arms is nothing like four independent looks. The correction is applied
  anyway, because the alternative is choosing one arm on no prospective evidence.
