"""Factor credibility ledger — the honest, real-line scoreboard per factor.

A factor's track record is a Beta-binomial posterior over its 1H-under hit rate
when it's "green". The prior is centered at the -110 breakeven (0.524) with ~20
pseudo-games of weight, so:

  * absent evidence, every factor is assumed worthless (no free promotions);
  * small samples cannot clear the promotion bar (the prior pulls them back),
    which is exactly the multiple-comparisons safeguard — we test ~dozens of
    factors continuously, and shrinkage stops the lucky ones from sneaking up;
  * a factor earns its tier only when real games move the posterior.

Display shows the posterior mean, the 95% credible interval, and n, loudly.
Promotion uses a stricter one-sided test: P(true rate > breakeven) >= 0.95 AND
n >= 25. Decay is symmetric — a once-hot factor cools when its recent window
drops back below breakeven.
"""

from __future__ import annotations

from typing import Dict

import pandas as pd
from scipy.stats import beta

# Prior: mean 10.5/20 = 0.525 (≈ breakeven), strength ~20 pseudo-games.
PRIOR_A = 10.5
PRIOR_B = 9.5
BREAKEVEN = 0.524  # -110 break-even win rate

PROMOTE_N = 25  # minimum real games before a factor can promote
PROMOTE_CONF = 0.95  # required P(true rate > breakeven)
MIN_RECENT = 10  # minimum recent games before a cooling flag is trusted


def beta_posterior(hits: int, n: int) -> Dict:
    """Posterior summary for `hits` 1H-under wins out of `n` green-state games."""
    a = PRIOR_A + hits
    b = PRIOR_B + (n - hits)
    return {
        "n": n,
        "hits": hits,
        "mean": a / (a + b),
        "lo": float(beta.ppf(0.025, a, b)),  # 95% credible interval (display)
        "hi": float(beta.ppf(0.975, a, b)),
        "p_beat": float(1.0 - beta.cdf(BREAKEVEN, a, b)),  # P(true rate > breakeven)
    }


def is_promoted(hits: int, n: int) -> bool:
    """True when the factor has earned its standing on real lines."""
    if n < PROMOTE_N:
        return False
    return beta_posterior(hits, n)["p_beat"] >= PROMOTE_CONF


def is_cooling(recent_hits: int, recent_n: int, alltime_mean: float) -> bool:
    """True when a factor that looks like an edge all-time has gone cold lately.

    Guards against over-reading a short cold streak via MIN_RECENT.
    """
    if recent_n < MIN_RECENT:
        return False
    if alltime_mean <= BREAKEVEN:
        return False  # not an edge to begin with — nothing to cool from
    return beta_posterior(recent_hits, recent_n)["mean"] < BREAKEVEN


def green_mask(values: pd.Series, direction: int, binary: bool) -> pd.Series:
    """Which games are in this factor's 'green' (most under-favorable) state.

    Binary factors are green when active. Continuous factors are green in the top
    under-favorable third (signed by `direction`). Factors with no pre-registered
    direction (hypotheses) are never green — we won't grade what we won't assert.
    """
    if binary:
        return values.fillna(0).astype(float) != 0
    if direction == 0:
        return pd.Series(False, index=values.index)
    signed = direction * values.astype(float)
    cutoff = signed.quantile(2.0 / 3.0)
    return signed >= cutoff


def tier_from_evidence(base_tier: int, hits: int, n: int) -> int:
    """Displayed tier = the better of our base belief and earned real-line standing.

    A speculative (Tier-3) factor rises to Tier 1 only once the ledger promotes it;
    a factor never drops below its registry base tier on thin data.
    """
    return 1 if is_promoted(hits, n) else base_tier


def ledger_row(
    factor: str, base_tier: int, hits: int, n: int, recent_hits: int, recent_n: int
) -> Dict:
    """Assemble one FactorLedger row from green-state counts (all-time + recent)."""
    post = beta_posterior(hits, n)
    recent_mean = beta_posterior(recent_hits, recent_n)["mean"] if recent_n else None
    return {
        "factor": factor,
        "n": n,
        "hits": hits,
        "post_mean": round(post["mean"], 4),
        "post_lo": round(post["lo"], 4),
        "post_hi": round(post["hi"], 4),
        "tier": tier_from_evidence(base_tier, hits, n),
        "recent_n": recent_n,
        "recent_mean": round(recent_mean, 4) if recent_mean is not None else None,
        "drift_flag": is_cooling(recent_hits, recent_n, post["mean"]),
    }


RECENT_WINDOW = 40  # trailing green-state games used for decay detection


def grade_ledger(df: pd.DataFrame, outcomes: Dict[int, int], recent_window: int = RECENT_WINDOW):
    """Accumulate the ledger from a frame of REAL-LINE graded games.

    df: feature frame restricted to games with a real 1H line + result. Must have
        an 'id' column and an 'order' column (sortable; higher = more recent).
    outcomes: {game_id: 1 if the 1H under cashed else 0}.
    Returns a FactorLedger row per board factor that had >=1 green-state game.
    """
    from .board import BOARD_FACTOR_NAMES
    from .registry import factor_by_name

    rows = []
    df = df.sort_values("order")
    for name in BOARD_FACTOR_NAMES:
        if name not in df.columns:
            continue
        factor = factor_by_name(name)
        if factor is None:
            continue
        green = green_mask(df[name], factor.direction, factor.binary)
        gdf = df[green]
        if gdf.empty:
            continue
        gids = [int(i) for i in gdf["id"].tolist()]
        n = len(gids)
        hits = sum(int(outcomes.get(i, 0)) for i in gids)
        recent_ids = gids[-recent_window:]
        recent_n = len(recent_ids)
        recent_hits = sum(int(outcomes.get(i, 0)) for i in recent_ids)
        rows.append(ledger_row(name, factor.tier, hits, n, recent_hits, recent_n))
    return rows


def load_ledger(session) -> Dict[str, Dict]:
    """Read the persisted ledger into the dict shape build_factor_board wants."""
    from ..db.models import FactorLedger

    out: Dict[str, Dict] = {}
    for r in session.query(FactorLedger).all():
        out[r.factor] = {
            "n": r.n,
            "hits": r.hits,
            "mean": r.post_mean,
            "lo": r.post_lo,
            "hi": r.post_hi,
            "cooling": bool(r.drift_flag),
        }
    return out
