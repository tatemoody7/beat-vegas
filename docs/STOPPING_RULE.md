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
| line value | favourable line value vs Hard Rock's strict close, points | mean 0 | **+0.50 pts/bet** (Tate's choice: below week 2's observed +0.61; the 4-pp-equivalent 1.13 would stop in a dozen bets) | 1.714 | same 25 picks |

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
