"""Two-sided diagnostic: does a NEGATIVE gap carry over-side information?

The system bets 1H unders when Hard Rock's number sits >= BET_GAP_PTS above our
own. It never bets overs. Live week 2 showed the most-negative-gap quartile going
OVER 12 of 13 times, which is a hint at n=13, not a finding. This module measures
the mirror image of the under ladder on the real close: at each symmetric gap
band, how often the under (and so the over) landed, whether "follow the sign of
the gap" pays at -110, and whether the two sides are symmetric.

A REPORT, NOT A BET. Nothing here reaches the card, the board or the money path.
The decision rule (`verdict`) was written BEFORE the numbers were looked at and is
pinned by tests so it cannot be tuned to them afterwards.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from .censoring import wilson

# Symmetric bands around zero, mirroring the under ladder (1 / 1.75 / 3) on the
# over side. Label, lower (inclusive), upper (exclusive).
SIDE_BANDS: List[tuple] = [
    ("<= -3", -np.inf, -3.0),
    ("-3 .. -1.75", -3.0, -1.75),
    ("-1.75 .. -1", -1.75, -1.0),
    ("-1 .. 0", -1.0, 0.0),
    ("0 .. 1", 0.0, 1.0),
    ("1 .. 1.75", 1.0, 1.75),
    ("1.75 .. 3", 1.75, 3.0),
    (">= 3", 3.0, np.inf),
]
BREAKEVEN_110 = 110.0 / 210.0  # 52.38%: what a -110 bet must hit to break even
WIN_110 = 100.0 / 110.0  # units won on a -110 winner


def band_of(gap: Optional[float]) -> Optional[str]:
    """Mirror bands: the under ladder is lower-inclusive on the right (a gap of
    exactly 1.75 is in the bettable band), so the over side is upper-inclusive on
    the left (a gap of exactly -1.75 is in its mirror band)."""
    if gap is None or not np.isfinite(gap):
        return None
    if gap < 0:
        for label, lo, hi in SIDE_BANDS[:4]:
            if lo < gap <= hi:
                return label
        return None
    for label, lo, hi in SIDE_BANDS[4:]:
        if lo <= gap < hi:
            return label
    return None


def _decided(df: pd.DataFrame, gap_col: str, outcome_col: str) -> pd.DataFrame:
    d = df[[gap_col, outcome_col] + [c for c in ("season", "week") if c in df.columns]].copy()
    d[gap_col] = pd.to_numeric(d[gap_col], errors="coerce")
    d[outcome_col] = d[outcome_col].astype(str).str.lower()
    d = d[d[gap_col].notna() & d[outcome_col].isin(["under", "over", "push"])]
    return d


def follow_sign_units(gap: float, outcome: str) -> float:
    """Bet the side the gap points to (under when the line is above our number,
    over when it is below) at -110. A push returns the stake."""
    if outcome == "push" or gap == 0:
        return 0.0
    side = "under" if gap > 0 else "over"
    return WIN_110 if outcome == side else -1.0


def ladder(df: pd.DataFrame, gap_col: str, outcome_col: str) -> List[Dict[str, Any]]:
    """One row per symmetric gap band: counts, decided under rate with a Wilson
    interval, and what following the sign of the gap would have returned."""
    d = _decided(df, gap_col, outcome_col)
    d["band"] = d[gap_col].map(band_of)
    rows: List[Dict[str, Any]] = []
    for label, _, _ in SIDE_BANDS:
        g = d[d["band"] == label]
        u = int((g[outcome_col] == "under").sum())
        o = int((g[outcome_col] == "over").sum())
        p = int((g[outcome_col] == "push").sum())
        n_dec = u + o
        lo, hi = wilson(u, n_dec)
        units = float(sum(follow_sign_units(gp, oc) for gp, oc in zip(g[gap_col], g[outcome_col])))
        # the side the band points to, and how often it hit among decided games
        side = "under" if label.startswith(("0", "1", ">")) else "over"
        side_hits = u if side == "under" else o
        rows.append(
            {
                "band": label,
                "side": side,
                "n": int(len(g)),
                "under": u,
                "over": o,
                "push": p,
                "under_rate": (u / n_dec) if n_dec else None,
                "under_ci": (lo, hi),
                "side_rate": (side_hits / n_dec) if n_dec else None,
                "side_ci": wilson(side_hits, n_dec),
                "units_follow_sign": units,
                "roi_follow_sign": (units / len(g)) if len(g) else None,
            }
        )
    return rows


def symmetry(df: pd.DataFrame, gap_col: str, outcome_col: str, bar: float = 1.75) -> Dict[str, Any]:
    """The over rate where the gap is <= -bar against the under rate where it is
    >= +bar. A symmetric signal has both above break-even; the under-only
    system assumes the left side carries nothing."""
    d = _decided(df, gap_col, outcome_col)
    d = d[d[outcome_col] != "push"]
    neg = d[d[gap_col] <= -bar]
    pos = d[d[gap_col] >= bar]
    o = int((neg[outcome_col] == "over").sum())
    u = int((pos[outcome_col] == "under").sum())
    return {
        "bar": bar,
        "neg_n": int(len(neg)),
        "neg_over_rate": (o / len(neg)) if len(neg) else None,
        "neg_over_ci": wilson(o, len(neg)),
        "pos_n": int(len(pos)),
        "pos_under_rate": (u / len(pos)) if len(pos) else None,
        "pos_under_ci": wilson(u, len(pos)),
        "breakeven": BREAKEVEN_110,
    }


def per_group(
    df: pd.DataFrame, gap_col: str, outcome_col: str, group: str, bar: float = 1.75
) -> List[Dict[str, Any]]:
    """`symmetry` per season (or per week band), so a pooled rate cannot hide a
    sign that flips year to year."""
    out = []
    for key, g in df.groupby(group):
        s = symmetry(g, gap_col, outcome_col, bar)
        s[group] = key
        out.append(s)
    return out


def week_band(week: Optional[float]) -> Optional[str]:
    if week is None or not np.isfinite(week):
        return None
    w = int(week)
    if w <= 2:
        return "w1-2"
    if w <= 4:
        return "w3-4"
    if w <= 8:
        return "w5-8"
    if w <= 12:
        return "w9-12"
    return "w13+"


def _logit_slope(x: np.ndarray, y: np.ndarray) -> Optional[float]:
    """Slope of a logistic fit of y on x (Newton iterations, no dependencies).
    None when it cannot be fit (one class, or no spread in x)."""
    if len(x) < 10 or y.min() == y.max() or np.ptp(x) == 0:
        return None
    X = np.column_stack([np.ones_like(x), x])
    b = np.zeros(2)
    for _ in range(50):
        z = X @ b
        p = 1.0 / (1.0 + np.exp(-z))
        w = p * (1 - p)
        H = X.T @ (X * w[:, None]) + 1e-9 * np.eye(2)
        step = np.linalg.solve(H, X.T @ (y - p))
        b = b + step
        if np.max(np.abs(step)) < 1e-8:
            break
    return float(b[1])


def gap_slope(
    df: pd.DataFrame,
    gap_col: str,
    outcome_col: str,
    n_boot: int = 2000,
    seed: int = 7,
) -> Dict[str, Any]:
    """Does P(under) rise with the gap the same way on both sides of zero?
    Pooled slope with a bootstrap CI, and the slope fit on each half alone."""
    d = _decided(df, gap_col, outcome_col)
    d = d[d[outcome_col] != "push"]
    x = d[gap_col].to_numpy(float)
    y = (d[outcome_col] == "under").to_numpy(float)
    pooled = _logit_slope(x, y)
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(x), len(x))
        s = _logit_slope(x[idx], y[idx])
        if s is not None:
            boots.append(s)
    ci = (
        (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5)))
        if boots
        else (None, None)
    )
    neg = x < 0
    return {
        "n": int(len(x)),
        "slope": pooled,
        "slope_ci": ci,
        "n_boot": n_boot,
        "slope_negative_side": _logit_slope(x[neg], y[neg]),
        "slope_positive_side": _logit_slope(x[~neg], y[~neg]),
        "n_negative": int(neg.sum()),
        "n_positive": int((~neg).sum()),
    }


def verdict(
    sym: Dict[str, Any], seasons: Sequence[Dict[str, Any]], min_n: int = 100
) -> Dict[str, Any]:
    """PRE-REGISTERED. An over-side signal is claimed only when ALL hold on the
    real-close history: (1) n at gap <= -bar is at least `min_n`; (2) the over
    rate there beats the -110 break-even; (3) its Wilson lower bound clears 50%
    (a coin flip is excluded, not merely the point estimate); (4) the over rate
    is above 50% in at least two of the three seasons. Anything less is
    'no over-side finding' and the under-only architecture stands as is."""
    reasons: List[str] = []
    n = sym["neg_n"]
    rate = sym["neg_over_rate"]
    lo = sym["neg_over_ci"][0]
    if n < min_n:
        reasons.append(f"only {n} decided games at gap <= -{sym['bar']} (needs {min_n})")
    if rate is None or rate <= BREAKEVEN_110:
        reasons.append(
            f"over rate {100 * (rate or 0):.1f}% does not beat the -110 break-even {100 * BREAKEVEN_110:.2f}%"
        )
    if lo is None or lo <= 0.5:
        reasons.append(
            f"Wilson lower bound {100 * (lo or 0):.1f}% does not clear 50% — a coin flip is not excluded"
        )
    above = [s for s in seasons if s["neg_over_rate"] is not None and s["neg_over_rate"] > 0.5]
    if len(seasons) >= 2 and len(above) < 2:
        reasons.append(f"over rate above 50% in only {len(above)} of {len(seasons)} seasons")
    return {
        "over_side_signal": not reasons,
        "reasons": reasons,
        "rule": (
            "PRE-REGISTERED: n >= 100 at gap <= -1.75 on the real close, over rate above "
            "52.38%, Wilson lower bound above 50%, and over rate above 50% in 2 of 3 seasons. "
            "Written before the numbers were read; nothing here places a bet either way."
        ),
    }


def _pct(v: Optional[float]) -> str:
    return "—" if v is None else f"{100 * v:.1f}%"


def _slope(v: Optional[float]) -> str:
    return "—" if v is None else f"{v:+.4f}"


def _ci(ci) -> str:
    lo, hi = ci
    return "—" if lo is None else f"{100 * lo:.1f}–{100 * hi:.1f}%"


def render_markdown(r: Dict[str, Any]) -> str:
    v = r["verdict"]
    L = [
        "# Two-sided diagnostic — does a negative gap carry over-side information?",
        "",
        f"Real-close history `{r['hist_scope']}`, FBS vs FBS, decided games with a real captured "
        f"1H close: **{r['hist_n']} games**. Live `{r['live_scope']}`: **{r['live_n']}** Hard "
        f"Rock-priced, graded games. Measurement only — nothing here is a bet.",
        "",
        f"## Verdict: {'**OVER-SIDE SIGNAL DETECTED**' if v['over_side_signal'] else '**NO OVER-SIDE FINDING**'}",
        "",
    ]
    for why in v["reasons"] or ["every pre-registered criterion met"]:
        L.append(f"- {why}")
    L += ["", f"_{v['rule']}_", ""]

    def ladder_table(rows, title):
        out = [
            f"## {title}",
            "",
            "| gap band (line − our number) | side it points to | n | under | over | push | under rate (decided) | Wilson 95% | side hit rate | follow-the-sign units at −110 | ROI |",
            "|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for b in rows:
            roi = "—" if b["roi_follow_sign"] is None else f"{100 * b['roi_follow_sign']:+.1f}%"
            out.append(
                f"| {b['band']} | {b['side']} | {b['n']} | {b['under']} | {b['over']} | {b['push']} | "
                f"{_pct(b['under_rate'])} | {_ci(b['under_ci'])} | {_pct(b['side_rate'])} | "
                f"{b['units_follow_sign']:+.1f} | {roi} |"
            )
        return out + [""]

    L += ladder_table(r["hist_ladder"], "History 2023–25 at the real close, by symmetric gap band")
    s = r["hist_symmetry"]
    L += [
        f"### Symmetry at ±{s['bar']} (history)",
        "",
        f"- gap ≤ −{s['bar']}: **over {_pct(s['neg_over_rate'])}** on {s['neg_n']} decided games, Wilson {_ci(s['neg_over_ci'])}",
        f"- gap ≥ +{s['bar']}: **under {_pct(s['pos_under_rate'])}** on {s['pos_n']} decided games, Wilson {_ci(s['pos_under_ci'])}",
        f"- break-even at −110: {100 * s['breakeven']:.2f}%",
        "",
        "| season | n at gap ≤ −bar | over rate | Wilson | n at gap ≥ +bar | under rate | Wilson |",
        "|---|---|---|---|---|---|---|",
    ]
    for p in r["hist_per_season"]:
        L.append(
            f"| {p['season']} | {p['neg_n']} | {_pct(p['neg_over_rate'])} | {_ci(p['neg_over_ci'])} | "
            f"{p['pos_n']} | {_pct(p['pos_under_rate'])} | {_ci(p['pos_under_ci'])} |"
        )
    L += [
        "",
        "| week band | n at gap ≤ −bar | over rate | Wilson | n at gap ≥ +bar | under rate | Wilson |",
        "|---|---|---|---|---|---|---|",
    ]
    for p in r["hist_per_week_band"]:
        L.append(
            f"| {p['week_band']} | {p['neg_n']} | {_pct(p['neg_over_rate'])} | {_ci(p['neg_over_ci'])} | "
            f"{p['pos_n']} | {_pct(p['pos_under_rate'])} | {_ci(p['pos_under_ci'])} |"
        )
    g = r["hist_slope"]
    L += [
        "",
        "### Does P(under) rise with the gap the same way on both sides of zero?",
        "",
        f"- pooled logistic slope of under on gap: **{g['slope']:+.4f} per point**, bootstrap 95% CI "
        f"[{g['slope_ci'][0]:+.4f}, {g['slope_ci'][1]:+.4f}] ({g['n_boot']} resamples, n={g['n']})",
        f"- fit on the negative side alone (n={g['n_negative']}): {_slope(g['slope_negative_side'])}; "
        f"positive side alone (n={g['n_positive']}): {_slope(g['slope_positive_side'])}",
        "",
    ]
    L += ladder_table(
        r["live_ladder"],
        "Live 2026 at Hard Rock's number (weeks 1–2; small n, read as a picture only)",
    )
    s = r["live_symmetry"]
    L += [
        f"### Symmetry at ±{s['bar']} (live)",
        "",
        f"- gap ≤ −{s['bar']}: over {_pct(s['neg_over_rate'])} on {s['neg_n']} games, Wilson {_ci(s['neg_over_ci'])}",
        f"- gap ≥ +{s['bar']}: under {_pct(s['pos_under_rate'])} on {s['pos_n']} games, Wilson {_ci(s['pos_under_ci'])}",
        "",
        f"_generated {r['generated_at']}_",
        "",
    ]
    return "\n".join(L)
