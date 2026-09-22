# The stopping rule — when does the paper record end the test?

**Registered 2026-09-15, before any week-3 decision had graded.** Design **SPRT**
(Wald's sequential probability ratio test), **total false-stop 5%, 2.5% per clock**,
power 80%. Two clocks, either can stop it. **A failure boundary pauses real money
immediately** (`scripts/rule_pause.py on`); **a success boundary changes nothing** — it
is a finding for Tate. Constants live in `beatvegas/backtest/stopping.py::REGISTERED`;
`tests/test_docs_parity.py` pins this page to them. Registry row **H-STOP**.

## What is being tested

The rule: **gap ≥ 1.75 at Hard Rock's number**, as the card logs it — every qualifying
game, on paper, one flat unit, **uncapped** (capped-5 is a diagnostic in docs only). The
scoreboard is the paper ledger because five real bets a week cannot settle anything
(W2); ~300 locked paper decisions a season can.

**One canonical observation per decision = the locked paper pick** (`manual_picks`,
`is_paper`, market 1H) from **2026 week 3** onward, cumulative across seasons, in the
order placed. A real ticket on the same game attaches to that observation as adherence
(placed / not / against) and is never a second row; a real ticket with no paper
counterpart is an off-rule bet and counts only in the adherence view.

**1u = one unit risked.** The paper ledger stakes 1u flat; `units` is profit on that unit
at the bet's own price, so break-even is 0 by construction. Hit rate is reported beside
the clocks and stops nothing.

## The two clocks

| clock | observation | H0 | H1 (frozen) | sd (frozen) | source of the frozen values |
|---|---|---|---|---|---|
| profit | units won per 1u risked at the actual price | mean 0 | **+0.0731 u/bet** = a 4-pp edge over a break-even of 0.5475 (edge ÷ break-even) | 0.924 | 2026 weeks 1-2 paper picks, n 25, read 2026-09-15 |
| line value | favourable line value vs the centred consensus close (the code, `picks.grade_pick`, never graded against Hard Rock's own rung; this cell said otherwise until 2026-09-22), points | mean 0 | **+0.50 pts/bet** (Tate's choice: below week 2's observed +0.61; the 4-pp-equivalent 1.13 would stop in a dozen bets) | 1.714 | same 25 picks |

Both alternatives are **frozen**. They do not move with later prices or later
volatility; if the ledger's character changes, that is a new registered row.

## The boundaries

For a normal mean with known sd, `LLR_n = (μ₁/σ²)·Σx − n·μ₁²/(2σ²)`. Stop when
**LLR ≥ A = ln((1−β)/α) = 3.466** (success) or **LLR ≤ B = ln(β/(1−α)) = -1.584**
(failure), with α = 0.025 per clock and β = 0.20.

Expected observations to a stop (Wald's approximations, PAPER_PER_SEASON ≈ 300):

| clock | no edge (H0) | the edge (H1) | midpoint |
|---|---|---|---|
| profit | 466 (~1.6 seasons) | 785 (~2.6) | 877 (~2.9) |
| line value | 34 | 58 | 65 |

The joint false-stop rate is the stated 5% because each clock runs at 2.5%; a stop on
either clock is a stop.

## What a stop does

- **Failure on either clock → real money pauses.** `scripts/rule_pause.py on --note "…"`
  throws the switch; `POST /api/picks` and `pick.py add` refuse every real-money
  first-half pick (`RULE PAUSED`), paper continues, and nothing resumes real money until
  the rule has been reviewed and Tate clears the switch. The paper ledger keeps
  accruing — the test is on paper; the pause is about money.
- **Success on either clock → nothing automatic.** Stakes stay 5 × 1u. Any change to
  stake, cap or rule is a separate registered decision.
- **While unresolved:** stakes and weekly exposure fixed and small; never raised on
  short-term performance.

## Sequential validity, enforced

Under this design there is **no confidence band to look at**. `running_position`
computes the LLR path and the Wald bounds and nothing else; the module contains no
bootstrap and refuses any design name but the registered two. Weekly runs of
`scripts/stopping_rule_position.py` are legitimate looks because the boundaries are
sequential by construction — that is the point of choosing SPRT over a fixed n.

## The candidate table Tate chose from (frozen inputs, 2026-09-15)

| total false-stop | per clock | clock | mu1 | design | n (fixed) or expected n (H0 / H1 / midpoint) | band or bounds | seasons |
|---|---|---|---|---|---|---|---|
| 5% | 2.5% | profit | +0.073 | fixed-n | **1521** | ±0.053 | 5.1 |
| 5% | 2.5% | profit | +0.073 | SPRT | 466 / 786 / 878 | A 3.47, B -1.58 | 1.6 / 2.6 / 2.9 |
| 5% | 2.5% | clv | +1.129 | fixed-n | **22** | ±0.819 | 0.1 |
| 5% | 2.5% | clv | +1.129 | SPRT | 7 / 11 / 13 | A 3.47, B -1.58 | 0.0 / 0.0 / 0.0 |
| 5% | 2.5% | clv | +0.500 | fixed-n | **112** | ±0.363 | 0.4 |
| 5% | 2.5% | clv | +0.500 | SPRT | 34 / 58 / 65 | A 3.47, B -1.58 | 0.1 / 0.2 / 0.2 |
| 5% | 2.5% | clv | +0.250 | fixed-n | **447** | ±0.182 | 1.5 |
| 5% | 2.5% | clv | +0.250 | SPRT | 137 / 231 / 258 | A 3.47, B -1.58 | 0.5 / 0.8 / 0.9 |
| 10% | 5.0% | profit | +0.073 | fixed-n | **1256** | ±0.051 | 4.2 |
| 10% | 5.0% | profit | +0.073 | SPRT | 429 / 610 / 691 | A 2.77, B -1.56 | 1.4 / 2.0 / 2.3 |
| 10% | 5.0% | clv | +1.129 | fixed-n | **19** | ±0.771 | 0.1 |
| 10% | 5.0% | clv | +1.129 | SPRT | 6 / 9 / 10 | A 2.77, B -1.56 | 0.0 / 0.0 / 0.0 |
| 10% | 5.0% | clv | +0.500 | fixed-n | **93** | ±0.348 | 0.3 |
| 10% | 5.0% | clv | +0.500 | SPRT | 32 / 45 / 51 | A 2.77, B -1.56 | 0.1 / 0.1 / 0.2 |
| 10% | 5.0% | clv | +0.250 | fixed-n | **369** | ±0.175 | 1.2 |
| 10% | 5.0% | clv | +0.250 | SPRT | 126 / 179 / 203 | A 2.77, B -1.56 | 0.4 / 0.6 / 0.7 |

## Reproduce

```
PYTHONPATH=. python scripts/stopping_rule_candidates.py --breakeven 0.5475 --sd-units 0.924 --sd-clv 1.714 --sigma-outcome 11.26
PYTHONPATH=. python scripts/stopping_rule_position.py --out reports/stopping      # weekly; GHA study.yml when on campus
```

## Clock 1 closed — 2026-09-22, n = 30, no boundary crossed. Superseded.

Position at close: profit LLR −0.44, line-value LLR −0.51 against +3.466 / −1.584. Neither
boundary. The clock did not decide anything; it was **superseded** because the champion it
measured changes at the week-5 refit (B-SERVE: 57 inputs the model never saw missing in
training were missing on every row it scored, worth about two points of level) and its
constant 1.75 bar is replaced by a per-slate percentile (H-PCT). The 30 observations stay in
`manual_picks` as history and are never mixed into Clock 2. Registry rows H-STOP and R10 are
`rejected` with that sentence.

Two defects in this page's own registration, corrected below rather than edited above: the
line-value cell named Hard Rock's strict close while the code graded against the centred
consensus; and the frozen sd 1.714 was week 2's value alone — week 3 read 0.984.

## Clock 2 — H-STOP-2, registered 2026-09-22, before its first observation

**What is tested:** the H-PCT rule — the top 20% of the slate by gap (`slate_bar`), on the
corrected model — every qualifying game, on paper, one flat unit, uncapped, from the first
card build on the corrected model (week 5, the 2026-09-29 `tue_pm` build) onward. One
canonical observation per decision, in placed order; real tickets attach as adherence.

**Design:** SPRT, total false-stop 5% (2.5% per clock), power 80%, bounds
**A = +3.466 / B = −1.584** — unchanged.

| clock | observation | H0 | H1 (frozen) | sd (frozen, treated as known) |
|---|---|---|---|---|
| profit | units won per 1u risked at the pick's own price; **priced picks only** | mean 0 | **per pick: μ₁ᵢ = 0.04 / bᵢ**, bᵢ = the pick's break-even implied by its price (a 4-pp edge over that price's break-even; at −110 this is +0.0731, at −180 +0.0622) | **0.929** |
| line value | favourable line value = −(consensus close − bet), **consensus close inside `REAL_1H_CLOSE_WINDOW_H` (2 h) of kickoff**; a pick with no close inside the window is excluded and counted; **unpriced picks are included** | mean 0 | **+0.50 pts** (carried over) | **1.371** |

Both sds are the sample sds of the **55 graded 2026 paper picks as stored on 2026-09-22**
(weeks 2-3; week 2 alone 0.924 / 1.714, week 3 alone 0.944 / 0.984). They are not
re-estimated during the test. σ-as-known is a stated limitation of the SPRT here, as is the
within-week dependence of picks that share one fitted model.

**LLR with a per-pick alternative:** `LLR_n = Σᵢ (μ₁ᵢ·xᵢ − μ₁ᵢ²/2) / σ²`. At a constant price
this reduces to the Clock-1 formula.

**What a stop does:** unchanged — failure on either clock pauses real money
(`scripts/rule_pause.py on`); success on either is a finding for Tate and changes no stake.

Constants: `beatvegas/backtest/stopping.py::REGISTERED_2`; the weekly position is
`scripts/stopping_rule_position.py --clock 2`. Registry row **H-STOP-2**.
