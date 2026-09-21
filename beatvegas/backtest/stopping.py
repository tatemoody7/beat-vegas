"""The stopping rule -- when does the paper record of the 1.75 rule end the test?

Pure arithmetic (docs/HYPOTHESES.md row H-STOP; docs/STOPPING_RULE.md). Two
confirmatory clocks, either can stop the test, with the TOTAL false-stop budget split
equally between them so the joint rate equals the stated target:

  profit  X_i = units won per 1 unit risked at each bet's ACTUAL price
          H0: E[X] = 0 (break-even at the prices paid, by construction)
          H1: E[X] = mu1 = edge / break-even   (a hit rate `edge` above break-even b
              pays (b + edge)/b - 1 per unit)
  clv     Y_i = favourable line value vs Hard Rock's strict close, in points
          H0: E[Y] = 0
          H1: E[Y] = the line shift worth `edge` of win probability at the outcome
              density's peak: edge * sigma_outcome * sqrt(2*pi)

Hit rate is REPORTED beside them and stops nothing. One canonical observation per
decision = the locked paper pick; a real ticket attaches as adherence, never a row.

Two designs, chosen once at registration and never mixed:

  fixed-n     ONE test, at the pre-registered n, with an ordinary band. Before n the
              position is printed with the words "not a test".
  sequential  Wald's SPRT for a normal mean with known sigma against the FROZEN mu1:
              LLR_n = (mu1/sigma^2) * sum(x) - n * mu1^2 / (2 sigma^2), stop when
              LLR >= A = ln((1-beta)/alpha) (success) or LLR <= B = ln(beta/(1-alpha))
              (failure -> real money pauses). Sequentially valid by construction; an
              ordinary confidence band is NEVER inspected for a crossing under this
              design, and running_position refuses to emit one.

The alternative effect sizes are frozen at registration from the 2026 weeks 1-2 ledger
and do not drift with later prices.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from scipy import stats

CLOCKS = ("profit", "clv")
PAPER_PER_SEASON = 300  # ~25 qualifying paper decisions a week x 12-13 weeks


# ---------------------------------------------------------------- effect sizes


def edge_to_units(edge: float, breakeven: float) -> float:
    """Profit per 1u risked when the hit rate sits `edge` above break-even `breakeven`
    (the price-implied probability). (b + e)/b - 1 = e/b."""
    if not 0 < breakeven < 1:
        raise ValueError("breakeven must be a probability")
    return edge / breakeven


def edge_to_points(edge: float, sigma_outcome: float) -> float:
    """The line shift, in points, worth `edge` of win probability at the peak of a
    normal outcome density with sd `sigma_outcome` (P changes phi(0)/sigma per pt)."""
    return edge * sigma_outcome * math.sqrt(2 * math.pi)


def breakeven_from_prices(prices: Sequence[int]) -> float:
    """Mean price-implied probability over American prices."""
    ps = []
    for p in prices:
        p = int(p)
        ps.append((-p) / (-p + 100) if p < 0 else 100 / (p + 100))
    if not ps:
        raise ValueError("no prices")
    return float(np.mean(ps))


# ---------------------------------------------------------------- fixed-n


def fixed_n(mu1: float, sigma: float, alpha: float, power: float) -> int:
    """Two-sided test of mean 0 against |mean| = mu1 at level alpha and the given power."""
    if mu1 <= 0 or sigma <= 0:
        raise ValueError("mu1 and sigma must be positive")
    z_a = stats.norm.ppf(1 - alpha / 2)
    z_b = stats.norm.ppf(power)
    return int(math.ceil(((z_a + z_b) * sigma / mu1) ** 2))


def fixed_band(sigma: float, alpha: float, n: int) -> float:
    """Half-width of the two-sided band on the mean at the registered n."""
    return float(stats.norm.ppf(1 - alpha / 2) * sigma / math.sqrt(n))


# ---------------------------------------------------------------- SPRT


def sprt_bounds(alpha: float, beta: float) -> Dict[str, float]:
    return {"A": math.log((1 - beta) / alpha), "B": math.log(beta / (1 - alpha))}


def sprt_llr(x: Sequence[float], mu1: float, sigma: float) -> np.ndarray:
    """Cumulative log-likelihood ratio path of H1: mean mu1 against H0: mean 0."""
    xs = np.asarray(x, float)
    return (mu1 / sigma**2) * np.cumsum(xs) - np.arange(1, len(xs) + 1) * mu1**2 / (2 * sigma**2)


def sprt_expected_n(mu1: float, sigma: float, alpha: float, beta: float) -> Dict[str, float]:
    """Wald's approximations to the expected sample size under H0, H1 and the
    midpoint (zero drift)."""
    b = sprt_bounds(alpha, beta)
    A, B = b["A"], b["B"]
    drift1 = mu1**2 / (2 * sigma**2)
    e_h1 = ((1 - beta) * A + beta * B) / drift1
    e_h0 = (alpha * A + (1 - alpha) * B) / (-drift1)
    var_inc = mu1**2 / sigma**2
    e_mid = (-A * B) / var_inc
    return {"under_h0": float(e_h0), "under_h1": float(e_h1), "at_midpoint": float(e_mid)}


# ---------------------------------------------------------------- candidates


def candidate_table(
    breakeven: float,
    sigma_units: float,
    sigma_clv: float,
    sigma_outcome: float,
    edge: float = 0.04,
    alphas: Sequence[float] = (0.05, 0.10),
    power: float = 0.80,
    clv_mu1s: Optional[Sequence[float]] = None,
) -> Dict[str, Any]:
    """Every candidate design for both clocks, with the frozen effect sizes. The
    line-value clock is shown at several alternatives: the edge-equivalent shift
    (edge * sigma_outcome * sqrt(2 pi)) is a large move for a market whose Hard Rock
    lines mostly do not move, so smaller ones are offered beside it."""
    mu_profit = edge_to_units(edge, breakeven)
    mu_clv_edge = edge_to_points(edge, sigma_outcome)
    clv_alts = list(clv_mu1s) if clv_mu1s else [mu_clv_edge, 0.5, 0.25]
    mu = {"profit": mu_profit, "clv": mu_clv_edge}
    sig = {"profit": sigma_units, "clv": sigma_clv}
    rows: List[Dict[str, Any]] = []
    for alpha_total in alphas:
        a = alpha_total / len(CLOCKS)  # equal split so the joint false-stop rate is alpha_total
        for clock in CLOCKS:
            alts = [mu_profit] if clock == "profit" else clv_alts
            for m1 in alts:
                n = fixed_n(m1, sig[clock], a, power)
                rows.append(
                    {
                        "design": "fixed-n",
                        "alpha_total": alpha_total,
                        "alpha_clock": a,
                        "power": power,
                        "clock": clock,
                        "mu1": m1,
                        "sigma": sig[clock],
                        "n": n,
                        "band": fixed_band(sig[clock], a, n),
                        "seasons": n / PAPER_PER_SEASON,
                    }
                )
                e = sprt_expected_n(m1, sig[clock], a, 1 - power)
                rows.append(
                    {
                        "design": "sprt",
                        "alpha_total": alpha_total,
                        "alpha_clock": a,
                        "power": power,
                        "clock": clock,
                        "mu1": m1,
                        "sigma": sig[clock],
                        "bounds": sprt_bounds(a, 1 - power),
                        "expected_n": e,
                        "seasons": {k: v / PAPER_PER_SEASON for k, v in e.items()},
                    }
                )
    return {
        "inputs": {
            "breakeven": breakeven,
            "sigma_units": sigma_units,
            "sigma_clv": sigma_clv,
            "sigma_outcome": sigma_outcome,
            "edge": edge,
            "power": power,
            "paper_per_season": PAPER_PER_SEASON,
        },
        "mu1": mu,
        "rows": rows,
    }


# ---------------------------------------------------------------- the running test


def running_position(
    units: Sequence[float],
    clv: Sequence[float],
    design: str,
    mu1: Dict[str, float],
    sigma: Dict[str, float],
    alpha_clock: float,
    power: float = 0.80,
    n_fixed: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    """Where the test stands. `design` is "fixed-n" or "sprt", chosen at registration.

    fixed-n: nothing is a test before the registered n; at n the FIRST n observations
    are tested once. sprt: the LLR path against the frozen mu1 and the Wald bounds;
    the first crossing stops. No bootstrap band exists in this module -- under a
    sequential design there is nothing to peek at.
    """
    if design not in ("fixed-n", "sprt"):
        raise ValueError("design must be 'fixed-n' or 'sprt'")
    out: Dict[str, Any] = {"design": design, "clocks": {}}
    series = {"profit": np.asarray(units, float), "clv": np.asarray(clv, float)}
    for clock in CLOCKS:
        x = series[clock]
        x = x[~np.isnan(x)]
        n = int(len(x))
        c: Dict[str, Any] = {"n": n, "mean": float(x.mean()) if n else None}
        if design == "fixed-n":
            need = int(
                (n_fixed or {}).get(clock) or fixed_n(mu1[clock], sigma[clock], alpha_clock, power)
            )
            c["n_registered"] = need
            if n < need:
                c["status"] = "not a test"
                c["verdict"] = None
            else:
                first = x[:need]
                band = fixed_band(sigma[clock], alpha_clock, need)
                m = float(first.mean())
                c["band"] = band
                c["mean_at_n"] = m
                c["status"] = "tested once at the registered n"
                c["verdict"] = "success" if m > band else "failure" if m < -band else "inconclusive"
        else:
            bounds = sprt_bounds(alpha_clock, 1 - power)
            c["bounds"] = bounds
            if n == 0:
                c["status"] = "no observations"
                c["verdict"] = None
                c["llr"] = None
            else:
                path = sprt_llr(x, mu1[clock], sigma[clock])
                hit_a = np.nonzero(path >= bounds["A"])[0]
                hit_b = np.nonzero(path <= bounds["B"])[0]
                first_a = int(hit_a[0]) + 1 if len(hit_a) else None
                first_b = int(hit_b[0]) + 1 if len(hit_b) else None
                c["llr"] = float(path[-1])
                if first_a is not None and (first_b is None or first_a < first_b):
                    c["status"], c["verdict"], c["stopped_at"] = "stopped", "success", first_a
                elif first_b is not None:
                    c["status"], c["verdict"], c["stopped_at"] = "stopped", "failure", first_b
                else:
                    c["status"], c["verdict"] = "running", None
        out["clocks"][clock] = c
    verdicts = [c.get("verdict") for c in out["clocks"].values()]
    out["real_money"] = "PAUSE" if "failure" in verdicts else "unchanged"
    return out


# ---------------------------------------------------------------- markdown


def render_candidates(t: Dict[str, Any]) -> str:
    i = t["inputs"]
    L = [
        "# Stopping-rule candidates",
        "",
        f"Inputs (frozen at registration): break-even at the mean paper price {i['breakeven']:.4f}; "
        f"sd of units per bet {i['sigma_units']:.3f}; sd of favourable line value {i['sigma_clv']:.3f} pts; "
        f"outcome sd {i['sigma_outcome']:.2f} pts; alternative = a {100 * i['edge']:.0f}-pp edge; power "
        f"{100 * i['power']:.0f}%; ~{i['paper_per_season']} paper decisions a season.",
        "",
        f"Alternative effect sizes: profit clock mu1 = {t['mu1']['profit']:+.4f} u/bet; "
        f"line-value clock mu1 = {t['mu1']['clv']:+.3f} pts/bet.",
        "",
        "| total false-stop | per clock | clock | mu1 | design | n (fixed) or expected n (H0 / H1 / midpoint) | band or bounds | seasons |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in t["rows"]:
        if r["design"] == "fixed-n":
            L.append(
                f"| {100 * r['alpha_total']:.0f}% | {100 * r['alpha_clock']:.1f}% | {r['clock']} | {r['mu1']:+.3f} | fixed-n | "
                f"**{r['n']}** | ±{r['band']:.3f} | {r['seasons']:.1f} |"
            )
        else:
            e, s = r["expected_n"], r["seasons"]
            L.append(
                f"| {100 * r['alpha_total']:.0f}% | {100 * r['alpha_clock']:.1f}% | {r['clock']} | {r['mu1']:+.3f} | SPRT | "
                f"{e['under_h0']:.0f} / {e['under_h1']:.0f} / {e['at_midpoint']:.0f} | "
                f"A {r['bounds']['A']:.2f}, B {r['bounds']['B']:.2f} | {s['under_h0']:.1f} / {s['under_h1']:.1f} / {s['at_midpoint']:.1f} |"
            )
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- the registered rule

# Chosen by Tate on 2026-09-15 from the candidate table, before any week-3 decision
# had graded. These values do not drift: the ledger inputs are the 2026 weeks 1-2
# paper picks as read that day. docs/STOPPING_RULE.md and tests/test_docs_parity.py
# quote them from here.
REGISTERED: Dict[str, Any] = {
    "registered_on": "2026-09-15",
    "design": "sprt",
    "alpha_total": 0.05,
    "alpha_clock": 0.025,
    "power": 0.80,
    "edge": 0.04,
    "breakeven": 0.5475,  # mean price-implied probability, 2026 wk 1-2 paper picks (n 25)
    "sigma": {"profit": 0.924, "clv": 1.714},  # sample sds, same 25 picks
    "mu1": {"profit": round(0.04 / 0.5475, 4), "clv": 0.50},  # 0.0731 u/bet; 0.50 pts
    "start": {"season": 2026, "week": 3},
    "unit": "1u = one unit risked; the paper ledger stakes 1u flat",
    "observation": "the locked paper pick (manual_picks.is_paper, market 1H) -- one per decision",
    "on_failure": "real money pauses (scripts/rule_pause.py on) and the rule is reviewed",
    "on_success": "nothing automatic; a finding for Tate",
}


def registered_position(units: Sequence[float], clv: Sequence[float]) -> Dict[str, Any]:
    """running_position under the registered design and constants."""
    r = REGISTERED
    out = running_position(
        units, clv, r["design"], r["mu1"], r["sigma"], r["alpha_clock"], r["power"]
    )
    out["registered"] = {k: v for k, v in r.items() if k != "unit"}
    return out


def render_position(pos: Dict[str, Any]) -> str:
    r = pos.get("registered", REGISTERED)
    L = [
        "# Stopping rule — running position",
        "",
        f"Design {r['design'].upper()}, total false-stop {100 * r['alpha_total']:.0f}% ({100 * r['alpha_clock']:.1f}% per "
        f"clock), power {100 * r['power']:.0f}%, registered {r['registered_on']}. Observations: locked paper "
        f"picks from {r['start']['season']} week {r['start']['week']} onward.",
        "",
        "| clock | n | mean | LLR | bounds A / B | status | verdict |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, c in pos["clocks"].items():
        b = c.get("bounds", {})
        mean = "—" if c["mean"] is None else "{:+.3f}".format(c["mean"])
        llr = "—" if c.get("llr") is None else "{:+.3f}".format(c["llr"])
        L.append(
            f"| {name} | {c['n']} | {mean} | {llr} | {b.get('A', 0):.2f} / {b.get('B', 0):.2f} | "
            f"{c['status']} | {c['verdict'] or '—'} |"
        )
    L += ["", f"Real money: **{pos['real_money']}**.", ""]
    return "\n".join(L)


# --- The H-INSEASON challenger family (registry row H-INSEASON-P) -------------
#
# A SEPARATE dict from REGISTERED above, deliberately. H-STOP measures the
# champion and must not move; this measures four challenger arms and shares only
# the generic machinery. The alternatives and sds ARE H-STOP's, reused so the
# challenger is held to the champion's bar in the champion's units.
#
# The error budget is the one difference that matters: 5% total, split /4 across
# the arms (Bonferroni) and then /2 across the two clocks, so each arm-clock runs
# at 0.625% -- against H-STOP's 2.5%, because H-STOP tests one ledger and this
# tests four correlated ones.
#
# docs/INSEASON_PAPER.md quotes these; tests/test_docs_parity.py pins it.
CHALLENGER: Dict[str, Any] = {
    "registered_on": "2026-09-20",
    "design": "sprt",
    "arms": ["k25", "k50", "k100", "k200"],
    "alpha_total": 0.05,
    "multiplicity": "bonferroni",
    "alpha_arm": 0.05 / 4,  # 1.25% per arm
    "alpha_clock": 0.05 / 4 / 2,  # 0.625% per arm-clock
    "power": 0.80,
    "sigma": REGISTERED["sigma"],
    "mu1": REGISTERED["mu1"],
    "unit": "1u = one unit risked; every challenger observation stakes 1u flat",
    "observation": "one qualifying pick per arm per game (challenger_picks) -- never manual_picks",
    "pass": "BOTH clocks cross A",
    "drop": "EITHER clock crosses B",
    "on_pass": (
        "if exactly one arm passes it may be named; if more than one does, no k is chosen "
        "here and that choice needs its own registered row"
    ),
    "touches": "nothing live -- no real-money selection, no model edit, H-STOP unchanged",
}


def challenger_position(arms: Dict[str, Dict[str, Sequence[float]]]) -> Dict[str, Any]:
    """The running position of every arm, under the challenger's own budget.

    `arms` maps an arm label to {"units": [...], "clv": [...]} in placed order,
    where clv is ALREADY the favourable direction (see grading.clv_under: the
    stored value is closing - bet, and for an under a falling line is good).
    """
    c = CHALLENGER
    out = {
        "registered": {k: v for k, v in c.items() if k != "unit"},
        "arms": {
            label: running_position(
                obs.get("units", []),
                obs.get("clv", []),
                c["design"],
                c["mu1"],
                c["sigma"],
                c["alpha_clock"],
                c["power"],
            )
            for label, obs in sorted(arms.items())
        },
    }
    for pos in out["arms"].values():
        clocks = pos.get("clocks", {})
        verdicts = {k: v.get("verdict") for k, v in clocks.items()}
        passed = verdicts and all(v == "SUCCESS" for v in verdicts.values())
        dropped = any(v == "FAILURE" for v in verdicts.values())
        pos["family_verdict"] = "PASS" if passed else ("DROPPED" if dropped else "accruing")
    passers = [a for a, p in out["arms"].items() if p["family_verdict"] == "PASS"]
    out["passers"] = passers
    out["may_name_k"] = len(passers) == 1
    return out
