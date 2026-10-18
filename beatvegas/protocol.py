"""The 2026 Statistical Protocol's test (docs/PROTOCOL_2026.md; docs/ROADMAP_2026.md v1.2).

Every confirmatory arm of the 2026 research program is one sequential test on
its line value: `ev_cons` per graded paper pick -- the EV per unit of the wager
at Hard Rock's price against the consensus close (beatvegas/consensus.py). A
pick with no reading (`cons_excluded` set) is not an observation; it is counted
as an exclusion.

The test, Tate's calls of 2026-10-07:

- H0: mean EV 0 (no edge) against H1: mean EV +0.03, Wald's SPRT on a normal
  mean, alpha 0.005 per arm (the fixed ledger: 5% family-wise across at most
  K = 10 confirmatory tests, never recycled), beta 0.20.
- **The observation is a WEEK**: the mean EV of the arm's readings that week.
  Bets in one week share the Saturday market move, so they are not independent;
  WEEK-SHOCK measured that shared move at 0.005 (2023-25, 42 weeks, interval to
  0.007) and 0.012 (2026, 6 weeks, interval to 0.020). A week's mean of n bets
  is treated as having variance SIGMA_WEEK^2 + SIGMA^2 / n with SIGMA_WEEK =
  0.02 (the top of 2026's interval) and SIGMA = 0.06 per bet (measured
  0.04-0.05). In the simulation this keeps a no-edge arm's false-promotion
  chance at or below 0.08% everywhere in the measured range.
- No decision before 30 readings spanning at least 3 different weeks.
- PROMOTE when the log-likelihood ratio reaches ln((1-beta)/alpha) -> $10 live
  validation. STOP when it falls to ln(beta/(1-alpha)) -- the evidence favours
  "no +3% edge" -- retired as NEEDS MORE EVIDENCE (a thin real edge can stop
  here; it is not called negative). TIMEOUT at 200 readings or the season's end,
  also NEEDS MORE EVIDENCE. Every ending spends the arm's alpha.
- Only COMPLETED weeks enter (the Monday review reads the week just graded).

Amended p1.1 (roadmap v1.5, Tate's calls of 2026-10-09, strategic review topic 3):

- The three arms' clocks are PAUSED before any completed week: the model under
  them is re-fitted without its training leaks first, and readings count only
  from the first card built on that model (ARMS_START is set then). Picks the
  arms log meanwhile are development evidence.
- Abandoning and restarting a test spends its alpha once any completed week of
  it has been read; a restart before any completed week is free (no result has
  been looked at).

Amended p1.3 (roadmap v2.6, Tate's calls of 2026-10-18, the final-2026 plan):

- The season ENDS after the Saturday 2026-11-28 slate (SEASON_LAST_KICKOFF, D1)
  and every arm is read for the last time on Monday 2026-11-30 (FINAL_READ_DATE,
  D4). A running arm times out at that read; nothing placed after the last
  kickoff is an observation. `season_over(now)` is the deterministic switch.

Pure: observations in, a position out. Tests pin the arithmetic; the simulation
(scripts/protocol_sim.py) gives the operating characteristics Tate approved.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

PROTOCOL_VERSION = "p1.3"
K_TESTS = 10
FAMILY_ALPHA = 0.05
ALPHA = FAMILY_ALPHA / K_TESTS  # 0.005 per confirmatory test
BETA = 0.20
MU0 = 0.0
MU1 = 0.03
SIGMA = 0.06  # per-bet spread of line value
SIGMA_WEEK = 0.02  # the week-wide move every bet in a week shares
MIN_OBS = 30  # readings
MIN_WEEKS = 3
MAX_OBS = 200  # readings

# The registered arms (docs/HYPOTHESES.md, Tate's calls of 2026-10-08). Each is
# one sequential test with its own 0.5% ledger slot; `table` + `arm` + `market`
# + `side` select its paper picks. The builds tag them from ARMS_TAGGED_FROM
# on; ARMS_START is the earliest placed_at that counts toward a clock. It was
# None while the clocks were paused (p1.1, 2026-10-09) and holds the first card
# built on the leak-fixed model since 2026-10-13.
ARM_1H_UNDER = "H-ARM-1HU"
ARM_1H_OVER = "H-ARM-1HO"
ARM_FG_UNDER = "H-ARM-FGU"
# The weather arms (Tate's calls of 2026-10-09, strategic review topic 3): a
# paper UNDER on every outdoor game whose newest build-time forecast has a
# sustained kickoff-hour wind of 10+ mph (beatvegas/wx_paper.py). They read no
# model, so the leak-fix pause does not apply to them.
ARM_WX_1H = "H-ARM-WX1H"
ARM_WX_FG = "H-ARM-WXFG"
# The high-total arm (Tate's calls of 2026-10-10, roadmap v1.8): a paper
# first-half UNDER on every game whose consensus full-game total at the build is
# 60.0 or more (beatvegas/ht_paper.py). It reads no model either.
ARM_HT_1H = "H-ARM-HT1H"
ARMS = {
    ARM_1H_UNDER: {"table": "manual_picks", "market": "1H", "side": "under", "slot": 1},
    ARM_1H_OVER: {"table": "challenger_picks", "market": "1H", "side": "over", "slot": 2},
    ARM_FG_UNDER: {"table": "challenger_picks", "market": "full", "side": "under", "slot": 3},
    ARM_WX_1H: {"table": "challenger_picks", "market": "1H", "side": "under", "slot": 6},
    ARM_WX_FG: {"table": "challenger_picks", "market": "full", "side": "under", "slot": 7},
    ARM_HT_1H: {"table": "challenger_picks", "market": "1H", "side": "under", "slot": 8},
}
ARMS_TAGGED_FROM = "2026-10-09T00:00:00"  # naive UTC; the first tagging build is fri_pm
# Set 2026-10-13 (Tate's approval): the first card built on the leak-fixed model,
# cards row for 2026 week 7, slot tue_pm, built_at 2026-10-13T20:51:39.533351 (naive UTC). Rows
# placed at or after this instant count; the 2026-10-09 rows stay development.
ARMS_START: Optional[str] = "2026-10-13T20:51:39.533351"
# The weather arms tag nothing before their rows merge, so this is a backstop:
# their clocks run from their first eligible build.
WX_ARMS_START = "2026-10-10T00:00:00"
# The same backstop for the high-total arm: nothing tags it before its collector
# merges, so its clock runs from its first eligible build.
HT_ARM_START = "2026-10-10T00:00:00"
ARM_STARTS: Dict[str, Optional[str]] = {
    ARM_1H_UNDER: ARMS_START,
    ARM_1H_OVER: ARMS_START,
    ARM_FG_UNDER: ARMS_START,
    ARM_WX_1H: WX_ARMS_START,
    ARM_WX_FG: WX_ARMS_START,
    ARM_HT_1H: HT_ARM_START,
}


def arm_start(arm: str) -> Optional[str]:
    """The earliest placed_at that counts toward `arm`'s clock; None = paused."""
    return ARM_STARTS[arm]


# The season's end (final-2026 plan, Tate 2026-10-18; roadmap v2.6, protocol p1.3).
# D1: paid operation ends after Sat 2026-11-28 (week 13); its last kickoff, naive UTC.
SEASON_LAST_KICKOFF = "2026-11-29T04:00:00"
# D4: the final read, the Monday after; it replaces 2027-01-25 and drops the 12-07 mid-point.
FINAL_READ_DATE = "2026-11-30"
# The read's instant: the Monday-noon-UTC clock of p1.2 R2 on that day.
FINAL_READ_AT = FINAL_READ_DATE + "T12:00:00"


def season_over(now: datetime) -> bool:
    """True from the final read's instant on (naive UTC, deterministic): every
    running arm times out there, and the Monday workflow needs no hand input."""
    return now >= datetime.fromisoformat(FINAL_READ_AT)


UPPER = math.log((1.0 - BETA) / ALPHA)  # promote
LOWER = math.log(BETA / (1.0 - ALPHA))  # stop

RUNNING = "running"
PROMOTE = "promote"
STOP = "stop"
TIMEOUT = "timeout"
PAUSED = "paused"


def week_variance(n: int, sigma: float = SIGMA, sigma_week: float = SIGMA_WEEK) -> float:
    """The assumed variance of one week's mean line value over n bets."""
    return sigma_week**2 + sigma**2 / n


def llr_week(mean_ev: float, n: int, mu0: float = MU0, mu1: float = MU1) -> float:
    """One week's contribution to the log-likelihood ratio, H1 over H0."""
    return (mu1 - mu0) / week_variance(n) * (mean_ev - (mu0 + mu1) / 2.0)


@dataclass
class Position:
    """Where an arm stands after its completed weeks."""

    state: str
    n: int  # readings
    weeks: int
    llr: float
    decided_at_week: Optional[object] = None  # the week the arm ended

    @property
    def can_decide(self) -> bool:
        return self.n >= MIN_OBS and self.weeks >= MIN_WEEKS


def weekly(observations: Iterable[Tuple[object, float]]) -> List[Tuple[object, int, float]]:
    """(week, n, mean ev) per week, in the order weeks first appear."""
    order: List[object] = []
    acc: dict = {}
    for week, ev in observations:
        if week not in acc:
            acc[week] = []
            order.append(week)
        acc[week].append(float(ev))
    return [(w, len(acc[w]), sum(acc[w]) / len(acc[w])) for w in order]


def position(observations: Iterable[Tuple[object, float]], season_over: bool = False) -> Position:
    """Run the test over an arm's (week, ev) readings from COMPLETED weeks.

    Weeks enter in order; after each, once MIN_OBS readings span MIN_WEEKS
    weeks, the first boundary crossed ends the arm. MAX_OBS readings, or
    `season_over`, end a still-running arm as TIMEOUT."""
    llr = 0.0
    n = 0
    k = 0
    for week, n_w, mean in weekly(observations):
        n += n_w
        k += 1
        llr += llr_week(mean, n_w)
        if n >= MIN_OBS and k >= MIN_WEEKS:
            if llr >= UPPER:
                return Position(PROMOTE, n, k, llr, week)
            if llr <= LOWER:
                return Position(STOP, n, k, llr, week)
        if n >= MAX_OBS:
            return Position(TIMEOUT, n, k, llr, week)
    if season_over:
        return Position(TIMEOUT, n, k, llr, None)
    return Position(RUNNING, n, k, llr, None)


def label(state: str) -> str:
    """The roadmap bucket an ending earns (docs/ROADMAP_2026.md)."""
    return {
        PROMOTE: "PROMOTED TO $10 LIVE VALIDATION",
        STOP: "NEEDS MORE EVIDENCE (stopped: no +3% edge)",
        TIMEOUT: "NEEDS MORE EVIDENCE (timed out)",
        RUNNING: "IN FORWARD TEST",
        PAUSED: "PAUSED (clock not started; development evidence)",
    }[state]


def observations_from_rows(rows: Sequence) -> Tuple[list, int]:
    """(week, ev_cons) readings from graded pick rows in grading order, and the
    count of rows excluded for want of a reading."""
    obs = []
    excluded = 0
    for r in rows:
        ev = getattr(r, "ev_cons", None)
        if ev is None:
            excluded += 1
            continue
        obs.append((getattr(r, "week", None), float(ev)))
    return obs, excluded


def simulate(
    true_mu: float,
    true_sigma: float,
    per_week: int,
    max_weeks: int,
    week_shock_sd: float = 0.0,
    reps: int = 20000,
    seed: int = 7,
) -> dict:
    """Operating characteristics of `position` in a simple world: each week
    brings `per_week` readings, each true_mu + a week-wide shock shared by that
    week + independent noise, total spread `true_sigma`. Vectorised over weeks
    (tests/test_protocol.py holds it equal to `position` path by path)."""
    import numpy as np

    rng = np.random.default_rng(seed)
    idio_sd = math.sqrt(max(true_sigma**2 - week_shock_sd**2, 0.0))
    weeks = min(max_weeks, math.ceil(MAX_OBS / per_week))
    shock = rng.normal(0.0, week_shock_sd, size=(reps, weeks)) if week_shock_sd > 0 else 0.0
    means = true_mu + shock + rng.normal(0.0, idio_sd / math.sqrt(per_week), size=(reps, weeks))
    llr = np.cumsum(llr_week(means, per_week), axis=1)
    k = np.arange(1, weeks + 1)
    ok = (k * per_week >= MIN_OBS) & (k >= MIN_WEEKS)
    up = (llr >= UPPER) & ok
    dn = (llr <= LOWER) & ok
    big = weeks + 10
    fu = np.where(up.any(1), up.argmax(1), big)
    fd = np.where(dn.any(1), dn.argmax(1), big)
    promote = fu < fd
    stop = fd < fu
    end_week = np.where(promote, fu, np.where(stop, fd, weeks - 1)) + 1
    return {
        "promote": float(promote.mean()),
        "stop": float(stop.mean()),
        "timeout": float(1.0 - promote.mean() - stop.mean()),
        "mean_weeks": float(end_week.mean()),
        "mean_bets": float((end_week * per_week).mean()),
        "max_weeks": int(weeks),
    }


def variance_components(groups: Sequence[Sequence[float]]) -> dict:
    """One-way random-effects split (method of moments, unbalanced groups):
    each observation = grand mean + group effect (sd `between`) + noise (sd
    `within`). Used by WEEK-SHOCK with one group per week: `between` is the
    week-wide shock every bet that week shares. Groups of one are dropped."""
    gs = [list(g) for g in groups if len(g) >= 2]
    k = len(gs)
    n_tot = sum(len(g) for g in gs)
    if k < 2 or n_tot <= k:
        return {"k": k, "n": n_tot, "between": None, "within": None, "icc": None, "total": None}
    grand = sum(sum(g) for g in gs) / n_tot
    means = [sum(g) / len(g) for g in gs]
    ssb = sum(len(g) * (m - grand) ** 2 for g, m in zip(gs, means))
    ssw = sum(sum((x - m) ** 2 for x in g) for g, m in zip(gs, means))
    msb = ssb / (k - 1)
    msw = ssw / (n_tot - k)
    n0 = (n_tot - sum(len(g) ** 2 for g in gs) / n_tot) / (k - 1)
    var_b = max(0.0, (msb - msw) / n0)
    total = sum((x - grand) ** 2 for g in gs for x in g) / (n_tot - 1)
    return {
        "k": k,
        "n": n_tot,
        "between": math.sqrt(var_b),
        "within": math.sqrt(msw),
        "icc": var_b / (var_b + msw) if (var_b + msw) > 0 else None,
        "total": math.sqrt(total),
        "mean": grand,
    }


def bootstrap_between(
    groups: Sequence[Sequence[float]], reps: int = 2000, seed: int = 7
) -> Tuple[float, float, float, float]:
    """Percentile interval (2.5, 5, 95, 97.5) for the between-group sd,
    resampling whole groups (weeks) with replacement."""
    import random

    rnd = random.Random(seed)
    gs = [list(g) for g in groups if len(g) >= 2]
    vals = []
    for _ in range(reps):
        sample = [gs[rnd.randrange(len(gs))] for _ in gs]
        b = variance_components(sample)["between"]
        if b is not None:
            vals.append(b)
    vals.sort()

    def q(p: float) -> float:
        return vals[min(len(vals) - 1, max(0, int(round(p * (len(vals) - 1)))))]

    return q(0.025), q(0.05), q(0.95), q(0.975)
