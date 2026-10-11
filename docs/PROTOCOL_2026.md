# The 2026 Statistical Protocol — `p1.1`

**Status: frozen on Tate's approval of the simulated numbers below (2026-10-07); amended `p1.1`
on 2026-10-09 (roadmap v1.5: the three arms' clocks paused before any completed week, and the
restart rule below). Registry row `H-PROGRAM-2026`.** Every confirmatory arm of the 2026 research program (`docs/ROADMAP_2026.md`)
is one test under this protocol, registered as its own row before it logs anything; every
confirmatory clock starts at the first eligible build after that row exists. Everything logged
before is development evidence. Code: `beatvegas/protocol.py` (the test),
`scripts/protocol_sim.py` (the simulation), `scripts/week_shock_study.py` (WEEK-SHOCK). A change
to any rule here is a new protocol version and a roadmap amendment, never an edit.

## The test

| Rule | Value | Basis |
|---|---|---|
| Observation | **one completed week**: the mean `ev_cons` of the arm's readings that week (`docs/CONSENSUS.md`) | bets in a week share the Saturday move (WEEK-SHOCK, below) |
| Price | Hard Rock's price, the one the paper pick logs | Tate: promotion licenses *his* $10 at Hard Rock; the customer's best-price scoreboard is tracked beside, not tested |
| Hypotheses | H0 mean EV 0 vs H1 mean EV **+0.03** | roadmap: the economically meaningful edge |
| Test | Wald SPRT on a normal mean; a week of n readings has variance 0.02² + 0.06²/n | spread 0.06 per bet (measured 0.04–0.05; conservative); week move 0.02 (top of 2026's interval) |
| Error | alpha **0.005** per arm, beta 0.20 | fixed ledger: 5% family-wise across at most **K = 10** confirmatory tests, never recycled |
| Guard | no decision before **30 readings over 3+ weeks** | no single slate decides an arm |
| PROMOTE | LLR ≥ ln(0.8/0.005) = 5.075 → **$10 live validation** at the arm's own weekly volume | roadmap |
| STOP | LLR ≤ ln(0.2/0.995) = −1.604 → **NEEDS MORE EVIDENCE** (stopped: no +3% edge) | Tate: the sequential lower bound; a thin real edge can stop here and is not called negative |
| TIMEOUT | 200 readings or the season's end → **NEEDS MORE EVIDENCE** (timed out) | roadmap; may restart in 2027 as a new test with new alpha |
| Exclusions | a pick with no reading (`cons_excluded`) is not an observation; every exclusion is counted and reported beside the arm | `docs/CONSENSUS.md` |
| Reading cadence | the Monday program review reads each arm over completed weeks | roadmap |

Every ending spends the arm's 0.5%. **Restarts (p1.1, 2026-10-09):** abandoning a test and
restarting it is an ending, and spends the slot, once any completed week of it has been read; a
restart before any completed week is free, because no result has been looked at. A new arm enters only while ledger slots remain (10 in total
for 2026, 8 betting slots at a time since roadmap v1.8). Correlated arms (the first-half unders and their over mirror
read the same slates) need no adjustment: the ledger is a Bonferroni split, valid under any
dependence.

**"The edge shows in two seasons"** (the 2027 business gate, defined now, before any 2027 data): a
rule promoted in 2026 is re-registered **unchanged** for 2027 with fresh alpha and must pass this
same test again on 2027 games at Hard Rock's price.

## WEEK-SHOCK — how much of line value a week shares

`study.yml` run 37712076009 (registry row WEEK-SHOCK, exploratory, read once). For every FBS game
with an opener and a close on file, a standard bet — the under at the median opening line of the
counted books, priced −110 — read by the consensus engine against the close; split into a week
component and a game component (one-way random effects, weeks resampled for the interval).

| market | era | games | weeks | mean EV | total spread | **week move (95% interval)** | game spread | share of variance from the week |
|---|---|---|---|---|---|---|---|---|
| first half | 2023–25 | 1,855 | 42 | −0.044 | 0.049 | **0.005 (0.000–0.007)** | 0.049 | 1.0% |
| first half | 2026 | 131 | 6 | −0.037 | 0.050 | **0.012 (0.000–0.020)** | 0.049 | 5.6% |
| full game | 2023–25 | 1,894 | 41 | −0.045 | 0.008 | not measurable | 0.008 | — |
| full game | 2026 | 4 | 2 | — | — | not measurable | — | — |

The week-wide move is small. The protocol assumes 0.02, the top of 2026's interval. **The full
game cannot be measured yet:** the 2023–25 history has no separate full-game opener (a spread of
0.008 means opener equals close), and 2026's full-game closes mostly fell outside the 2-hour
window before the weeknight and Saturday full-game close capture (2026-10-06). The full-game arm
is tested under the same assumed 0.02; WEEK-SHOCK is re-read for the full game once it has six
weeks of in-window closes, and if that read exceeds 0.02 the full-game arm's design is amended
before its next Monday reading.

## What the simulation says (`scripts/protocol_sim.py`, 20,000 arms per world, true spread 0.05)

| bets a week | true week move | true mean EV | promoted | stopped | timed out | weeks to an ending |
|---|---|---|---|---|---|---|
| 8 | 0.012 | −0.05 (where today's picks sit) | 0.0% | 100% | 0% | 4.0 |
| 8 | 0.012 | 0.00 (no edge) | **0.01%** | 96.4% | 3.6% | 5.0 |
| 8 | 0.012 | +0.01 | 0.3% | 64.3% | 35.5% | 7.2 |
| 8 | 0.012 | **+0.03** | **56.2%** | 1.1% | 42.6% | 8.6 |
| 8 | 0.012 | +0.05 | 99.9% | 0.0% | 0.1% | 4.9 |
| 15 | 0.012 | −0.05 | 0.0% | 100% | 0% | 3.0 |
| 15 | 0.012 | 0.00 (no edge) | **0.00%** | 99.1% | 0.9% | 3.8 |
| 15 | 0.012 | +0.01 | 0.4% | 72.6% | 27.0% | 6.4 |
| 15 | 0.012 | **+0.03** | **80.1%** | 0.8% | 19.1% | 7.5 |
| 15 | 0.012 | +0.05 | 100% | 0.0% | 0.0% | 3.8 |

At the top of the measured range (week move 0.02) a no-edge arm is promoted 0.03% (8 a week) or
0.08% (15 a week) of the time — inside its 0.5% everywhere — and a real +3% edge 57% / 75%. The
full table (both spreads, week moves 0 / 0.005 / 0.012 / 0.02, five true edges, two volumes) is
the script's output; it is deterministic.

**What this means for the season:** an arm sitting where today's paper unders sit (about −5% at
the close) is stopped within 3–4 weeks of going live. A real +3% edge is found more often than not,
but not reliably, before the bowls; a thinner edge mostly times out. "One promoted edge by January"
is therefore a demanding objective, and a clean "not yet" is a likely and acceptable outcome.

## Before any arm goes live (roadmap step 6)

Each arm's registry row names: this protocol (`p1`, amended `p1.1`), its ledger slot and 0.5%, its exact
selection rule, its market and side, the first eligible build, and its expected weekly volume.
Its position is reported every Monday from `beatvegas.protocol.position` over its completed weeks.

## The registered arms (2026-10-08, Tate's calls)

The first three arms registered before any collector logged, each with its own ledger slot (rows in
`docs/HYPOTHESES.md`; `beatvegas/protocol.py::ARMS`). The builds tag their picks from the **fri_pm
card of 2026-10-09** on.

**Clocks paused (p1.1, roadmap v1.5, Tate 2026-10-09, before any completed week).** The October
2026 strategic review (topic 3) found information from after the game
in the model's training inputs (pace, weather, same-season roster and talent, the rivalry and
conference flags). The model under the three arms is re-fitted without those leaks first. Each
arm's clock starts at the **first card built on the leak-fixed model**; its `cards.id` and time are
written here and into `beatvegas/protocol.py::ARMS_START` when it runs. Every pick the arms log
until then is development evidence, like every row before 2026-10-09. No week has been read, so
the restart spends no alpha; the selection rules, slots and test are otherwise unchanged.

| Arm | Slot | Rule (every qualifier, uncapped) | Where its picks live |
|---|---|---|---|
| H-ARM-1HU | 1 | First-half UNDER on every game at or above the per-slate bar (gap above zero), whatever the money-path flags | `manual_picks`, `is_paper`, `arm = 'H-ARM-1HU'` (written by `scripts/build_card.py::log_paper_picks`) |
| H-ARM-1HO | 2 | First-half OVER on every game at or below the slate floor (the k-th smallest gap, k = max(1, round(0.2N))) with the gap below zero, at Hard Rock's over price | `challenger_picks`, `arm = 'H-ARM-1HO'` (`beatvegas/arm_paper.py`) |
| H-ARM-FGU | 3 | Full-game UNDER on every game at or above the full-game slate bar (gap above zero), H-FG-P's universe without its cap | `challenger_picks`, `arm = 'H-ARM-FGU'` (`beatvegas/fg_paper.py`, `cap=None`) |

**The weather arms (roadmap v1.6, Tate 2026-10-09), ledger slots 6 and 7.** Registered under
p1.1 with the same test; they read no model, so the pause above does not apply, and each clock
starts at its first eligible build after the rows merged (`protocol.WX_ARMS_START` is the backstop;
`protocol.arm_start` gives each arm's start).

| Arm | Slot | Rule (every qualifier, uncapped) | Where its picks live |
|---|---|---|---|
| H-ARM-WX1H | 6 | First-half UNDER on every outdoor game whose newest build-time forecast has a sustained kickoff-hour wind of 10+ mph, at Hard Rock's centred main line and under price | `challenger_picks`, `arm = 'H-ARM-WX1H'` (`beatvegas/wx_paper.py`) |
| H-ARM-WXFG | 7 | Full-game UNDER on the same games, at Hard Rock's newest centred full-game total and under price | `challenger_picks`, `arm = 'H-ARM-WXFG'` (`beatvegas/wx_paper.py`) |

- **The forecast:** each decision build fetches the kickoff-hour forecast of the week's games not
  yet kicked off (Open-Meteo forecast API, model `icon_seamless`) into `build_forecasts`, which
  nothing else reads; a game qualifies on its newest forecast fetched at or before the build.
  IMPLEMENTATION NOTE 2026-10-10, before any number was read: the first build on this code
  (`sat_am`, run 38049849474) fetched all 254 of the week's games and timed the card job out, so
  a build now fetches only the games an arm can log (Hard Rock-priced; `wx_paper.arm_game_ids`),
  10 s a call, 2 tries, 180 s in all. The rule is unchanged.

**The high-total arm (roadmap v1.8, Tate 2026-10-10), ledger slot 8.** Registered under p1.1
with the same test. It reads no model, so the pause above does not apply, and its clock starts at
its first eligible build after its collector merges (`protocol.HT_ARM_START` is the backstop).

| Arm | Slot | Rule (every qualifier, uncapped) | Where its picks live |
|---|---|---|---|
| H-ARM-HT1H | 8 | First-half UNDER on every game whose consensus full-game total at the build is 60.0 or more (the median of each counted book's newest centred quote at or before the build, at least 3 books, the judge's book set), at Hard Rock's centred main line and under price | `challenger_picks`, `arm = 'H-ARM-HT1H'` (`beatvegas/ht_paper.py`, its collector PR) |

- **The development collectors retired** when these started: H-NEGGAP-P (`NEGGAP_COLLECT`) and
  H-FG-P (`FG_COLLECT`) are no longer switched on by `card.yml`.
- **Exclusions:** a paper pick without a Hard Rock price is now excluded by name (`no_price`,
  `beatvegas/consensus.py`), so nothing is a silent gap.
- **The Monday read:** `scripts/protocol_position.py`, through `study.yml` (`script =
  protocol_position`), reports each arm's state, readings, weeks, LLR, mean EV and exclusions by
  reason over its completed weeks.
- **Tate's personal real-money ledger** (roadmap v1.4) is never an observation for any arm.

