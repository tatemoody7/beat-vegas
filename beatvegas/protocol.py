"""The 2026 Statistical Protocol's test (docs/PROTOCOL_2026.md; docs/ROADMAP_2026.md v1.2).

Every confirmatory arm of the 2026 research program is one sequential test on
its stream of line-value observations: `ev_cons` per graded paper pick -- the
EV per unit of the wager at Hard Rock's price against the consensus close
(beatvegas/consensus.py). A pick with no reading (`cons_excluded` set) is not an
observation; it is counted as an exclusion.

The test (Wald's SPRT on a normal mean with a frozen spread), Tate's calls of
2026-10-07:

- H0: mean EV 0 (no edge) against H1: mean EV +0.03 (the economically meaningful
  edge the program is built to find).
- alpha 0.005 per arm (the fixed ledger: 5% family-wise across at most K = 10
  confirmatory tests, never recycled); beta 0.20.
- Assumed spread 0.06 per bet (measured 0.04-0.047 on development rows; the
  conservative value keeps a no-edge arm's false-promotion chance inside its
  0.5% even if the true spread is that wide).
- No decision before 30 observations spanning at least 3 different weeks (one
  Saturday's market-wide move cannot carry an arm across a boundary).
- PROMOTE when the log-likelihood ratio reaches ln((1-beta)/alpha); STOP when it
  falls to ln(beta/(1-alpha)) -- the evidence favours "no +3% edge" -- and the
  arm is retired as NEEDS MORE EVIDENCE (a thin real edge can stop here; it is
  not called negative). TIMEOUT at 200 observations or the season's end, also
  NEEDS MORE EVIDENCE. Every ending spends the arm's alpha.

Pure: observations in, a position out. Tests pin the arithmetic; the simulation
(scripts/protocol_sim.py) gives the operating characteristics Tate approved.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence, Tuple

PROTOCOL_VERSION = "p1"
K_TESTS = 10
FAMILY_ALPHA = 0.05
ALPHA = FAMILY_ALPHA / K_TESTS  # 0.005 per confirmatory test
BETA = 0.20
MU0 = 0.0
MU1 = 0.03
SIGMA = 0.06
MIN_OBS = 30
MIN_WEEKS = 3
MAX_OBS = 200

UPPER = math.log((1.0 - BETA) / ALPHA)  # promote
LOWER = math.log(BETA / (1.0 - ALPHA))  # stop

RUNNING = "running"
PROMOTE = "promote"
STOP = "stop"
TIMEOUT = "timeout"


def llr_step(ev: float, sigma: float = SIGMA, mu0: float = MU0, mu1: float = MU1) -> float:
    """One observation's contribution to the log-likelihood ratio, H1 over H0,
    for a normal mean with known spread."""
    return (mu1 - mu0) / sigma**2 * (ev - (mu0 + mu1) / 2.0)


@dataclass
class Position:
    """Where an arm stands after its observations, in order."""

    state: str
    n: int
    weeks: int
    llr: float
    decided_at: Optional[int] = None  # the observation count at which it ended

    @property
    def can_decide(self) -> bool:
        return self.n >= MIN_OBS and self.weeks >= MIN_WEEKS


def position(observations: Iterable[Tuple[object, float]], season_over: bool = False) -> Position:
    """Run the test over (week, ev) observations in the order they graded.

    The boundaries are checked after every observation once at least MIN_OBS
    observations span MIN_WEEKS distinct weeks; the first crossing ends the arm.
    `season_over` ends a still-running arm as TIMEOUT."""
    llr = 0.0
    seen_weeks: set = set()
    n = 0
    for week, ev in observations:
        n += 1
        seen_weeks.add(week)
        llr += llr_step(ev)
        if n >= MIN_OBS and len(seen_weeks) >= MIN_WEEKS:
            if llr >= UPPER:
                return Position(PROMOTE, n, len(seen_weeks), llr, n)
            if llr <= LOWER:
                return Position(STOP, n, len(seen_weeks), llr, n)
        if n >= MAX_OBS:
            return Position(TIMEOUT, n, len(seen_weeks), llr, n)
    state = TIMEOUT if season_over else RUNNING
    return Position(state, n, len(seen_weeks), llr, n if season_over else None)


def label(state: str) -> str:
    """The roadmap bucket an ending earns (docs/ROADMAP_2026.md)."""
    return {
        PROMOTE: "PROMOTED TO $10 LIVE VALIDATION",
        STOP: "NEEDS MORE EVIDENCE (stopped: no +3% edge)",
        TIMEOUT: "NEEDS MORE EVIDENCE (timed out)",
        RUNNING: "IN FORWARD TEST",
    }[state]


def observations_from_rows(rows: Sequence) -> Tuple[list, int]:
    """(week, ev_cons) observations from graded pick rows in grading order,
    and the count of rows excluded for want of a reading."""
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
    """Operating characteristics of `position` under a simple world: each week
    brings `per_week` observations; each is true_mu + a week-wide shock (shared
    by that week's bets: the Saturday market move) + independent noise, with the
    total spread `true_sigma`. Vectorised, but the same rule as `position`
    (tests/test_protocol.py holds them equal path by path)."""
    import numpy as np

    rng = np.random.default_rng(seed)
    n_max = min(MAX_OBS, per_week * max_weeks)
    idio_sd = math.sqrt(max(true_sigma**2 - week_shock_sd**2, 0.0))
    weeks_idx = np.arange(n_max) // per_week
    shocks = (
        rng.normal(0.0, week_shock_sd, size=(reps, max_weeks))
        if week_shock_sd > 0
        else np.zeros((reps, max_weeks))
    )
    x = true_mu + shocks[:, weeks_idx] + rng.normal(0.0, idio_sd, size=(reps, n_max))
    llr = np.cumsum(llr_step(x), axis=1)
    n = np.arange(1, n_max + 1)
    ok = (n >= MIN_OBS) & ((weeks_idx + 1) >= MIN_WEEKS)
    up = (llr >= UPPER) & ok
    dn = (llr <= LOWER) & ok
    big = n_max + 10
    fu = np.where(up.any(1), up.argmax(1), big)
    fd = np.where(dn.any(1), dn.argmax(1), big)
    promote = fu < fd
    stop = fd < fu
    end = np.where(promote, fu, np.where(stop, fd, n_max - 1)) + 1
    return {
        "promote": float(promote.mean()),
        "stop": float(stop.mean()),
        "timeout": float(1.0 - promote.mean() - stop.mean()),
        "mean_obs": float(end.mean()),
        "mean_weeks": float(np.ceil(end / per_week).mean()),
        "n_max": int(n_max),
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
