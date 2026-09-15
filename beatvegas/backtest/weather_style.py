"""Weather x offensive style: does DECISION-TIME weather predict market error?

The book prices wind. The question is not "does wind lower scoring" but: after
conditioning on the book's own de-vigged probability at its closing number, does
the forecast gust that existed 24 hours before kickoff still predict the under --
and does it do so differently for pass-heavy offences (the sharper hypothesis Tate
wants hunted; an external review named it as a candidate core layer).

Inputs are decision-safe by construction: `weather_obs` rows with `lead_hours = 24`
and `decision_safe = true` (the forecast that existed a day out, never the
near-kickoff series), and each offence's first-half pass rate / explosiveness as
the mean of its PRIOR games that season (leak-free). Usable sample: 2024-2025 only
-- fixed-lead wind/gust/precipitation begin with the 2024 season (docs/WEATHER.md).

The decision rule (`verdict`) was written before the numbers were read and is
pinned by tests. A REPORT, NOT A FEATURE: weather stays out of the model until a
separate pre-registered promotion test says otherwise.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from .censoring import wilson

GUST_BANDS = [
    ("< 10", 0, 10),
    ("10–15", 10, 15),
    ("15–20", 15, 20),
    ("20–25", 20, 25),
    ("25+", 25, np.inf),
]
VIG_HURDLE_PP = 2.38  # what a -110 bet must clear: 52.38% - 50%
STYLE_TOP_SHARE = 1 / 3  # "pass-heavy" = top third of as-of pass rate


def style_as_of(fh: pd.DataFrame, season: int, week: int, team: str) -> Dict[str, Optional[float]]:
    """Mean 1H pass rate / explosiveness of `team`'s offence over its PRIOR games
    that season (strictly earlier weeks). None when it has none."""
    g = fh[(fh["season"] == season) & (fh["off_team"] == team) & (fh["week"] < week)]
    if g.empty:
        return {"pass_rate": None, "explosive": None, "n_prior": 0}
    return {
        "pass_rate": float(pd.to_numeric(g["pass_rate"], errors="coerce").mean()),
        "explosive": float(pd.to_numeric(g["explosive"], errors="coerce").mean()),
        "n_prior": int(len(g)),
    }


def attach_style(games: pd.DataFrame, fh: pd.DataFrame) -> pd.DataFrame:
    """Per game: the two offences' as-of means, combined as the simple average
    (the total is both offences' points), plus the max (one air-raid team is
    enough to make wind matter)."""
    out = games.copy()
    pr, ex, nmin = [], [], []
    for r in out.itertuples(index=False):
        h = style_as_of(fh, int(r.season), int(r.week), r.home_team)
        a = style_as_of(fh, int(r.season), int(r.week), r.away_team)
        vals = [v for v in (h["pass_rate"], a["pass_rate"]) if v is not None]
        exs = [v for v in (h["explosive"], a["explosive"]) if v is not None]
        pr.append(float(np.mean(vals)) if len(vals) == 2 else None)
        ex.append(float(np.mean(exs)) if len(exs) == 2 else None)
        nmin.append(min(h["n_prior"], a["n_prior"]))
    out["pass_rate_asof"] = pr
    out["explosive_asof"] = ex
    out["style_n_prior_min"] = nmin
    return out


def flag_pass_heavy(df: pd.DataFrame, col: str = "pass_rate_asof") -> pd.DataFrame:
    """Top third of the as-of pass rate within the frame = pass-heavy. The cut is
    taken on the analysed sample and reported; it is a split, not a tuned threshold."""
    out = df.copy()
    v = pd.to_numeric(out[col], errors="coerce")
    cut = float(v.quantile(1 - STYLE_TOP_SHARE)) if v.notna().any() else np.nan
    out["pass_heavy"] = (v >= cut).astype(int)
    out.attrs["pass_heavy_cut"] = cut
    return out


def gust_band(g: Optional[float]) -> Optional[str]:
    if g is None or not np.isfinite(g):
        return None
    for label, lo, hi in GUST_BANDS:
        if lo <= g < hi:
            return label
    return None


def buckets(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Realized under rate against the book's implied, by gust band x style.
    Decided games only (a two-way de-vig carries no push mass)."""
    d = df[df["outcome"].isin(["under", "over"])].copy()
    d["band"] = d["gust"].map(gust_band)
    rows = []
    for style in (1, 0):
        for label, _, _ in GUST_BANDS:
            g = d[(d["band"] == label) & (d["pass_heavy"] == style)]
            n = int(len(g))
            u = int((g["outcome"] == "under").sum())
            lo, hi = wilson(u, n)
            rows.append(
                {
                    "style": "pass-heavy" if style else "other",
                    "band": label,
                    "n": n,
                    "realized_under": (u / n) if n else None,
                    "implied_under": float(g["fair_under"].mean()) if n else None,
                    "diff_pp": (100 * (u / n - g["fair_under"].mean())) if n else None,
                    "wilson": (lo, hi),
                }
            )
    return rows


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def _fit(offset: np.ndarray, X: np.ndarray, y: np.ndarray) -> Optional[np.ndarray]:
    """Logistic regression of y on X with a fixed offset (the book's logit,
    coefficient 1) and an intercept. Newton steps; None if it cannot fit."""
    if len(y) < 30 or y.min() == y.max():
        return None
    Z = np.column_stack([np.ones(len(y)), X])
    b = np.zeros(Z.shape[1])
    for _ in range(60):
        eta = offset + Z @ b
        p = 1 / (1 + np.exp(-eta))
        w = p * (1 - p)
        H = Z.T @ (Z * w[:, None]) + 1e-8 * np.eye(Z.shape[1])
        try:
            step = np.linalg.solve(H, Z.T @ (y - p))
        except np.linalg.LinAlgError:
            return None
        b = b + step
        if np.max(np.abs(step)) < 1e-9:
            break
    return b


def interaction_fit(df: pd.DataFrame, n_boot: int = 2000, seed: int = 7) -> Dict[str, Any]:
    """under ~ offset(logit fair_under) + gust/5 + pass_heavy + (gust/5 x pass_heavy).
    Coefficients with bootstrap CIs; the swing in P(under) for a pass-heavy game
    from the 10th to the 90th percentile of gust, in percentage points."""
    d = df[df["outcome"].isin(["under", "over"])].dropna(
        subset=["gust", "fair_under", "pass_heavy"]
    )
    y = (d["outcome"] == "under").to_numpy(float)
    off = _logit(d["fair_under"].to_numpy(float))
    g5 = d["gust"].to_numpy(float) / 5.0
    ph = d["pass_heavy"].to_numpy(float)
    X = np.column_stack([g5, ph, g5 * ph])
    b = _fit(off, X, y)
    names = ["intercept", "gust_per5", "pass_heavy", "gust_x_pass_heavy"]
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(y), len(y))
        bb = _fit(off[idx], X[idx], y[idx])
        if bb is not None:
            boots.append(bb)
    B = np.array(boots) if boots else np.empty((0, 4))
    ci = (
        {
            names[i]: (float(np.percentile(B[:, i], 2.5)), float(np.percentile(B[:, i], 97.5)))
            for i in range(4)
        }
        if len(B)
        else {}
    )
    coef = {names[i]: float(b[i]) for i in range(4)} if b is not None else {}
    swing = None
    if b is not None:
        p10, p90 = np.percentile(g5, [10, 90])
        base = float(np.median(off))

        def eta(g: float) -> float:  # a pass-heavy game at gust g (in 5-mph units)
            return base + b[0] + b[1] * g + b[2] + b[3] * g

        def pr(e: float) -> float:
            return 1 / (1 + np.exp(-e))

        swing = float(100 * (pr(eta(p90)) - pr(eta(p10))))
    return {
        "n": int(len(y)),
        "coef": coef,
        "ci": ci,
        "n_boot": n_boot,
        "swing_pp_pass_heavy_p10_to_p90_gust": swing,
        "gust_p10_p90_mph": (
            float(np.percentile(d["gust"], 10)),
            float(np.percentile(d["gust"], 90)),
        ),
    }


def per_season(df: pd.DataFrame) -> List[Dict[str, Any]]:
    out = []
    for season, g in df.groupby("season"):
        f = interaction_fit(g, n_boot=0)
        out.append({"season": int(season), "n": f["n"], "coef": f["coef"]})
    return out


def verdict(fit: Dict[str, Any], seasons: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """PRE-REGISTERED. A weather x style signal is claimed only when ALL hold:
    (1) the interaction coefficient's bootstrap CI excludes zero; (2) it carries
    the same sign in every season; (3) the implied swing for a pass-heavy game
    across the 10th-90th percentile of gust exceeds the 2.38 pp vig hurdle. The
    main gust effect is reported but is NOT the claim -- the book prices wind."""
    reasons: List[str] = []
    ci = fit.get("ci", {}).get("gust_x_pass_heavy")
    coef = fit.get("coef", {}).get("gust_x_pass_heavy")
    if not ci or coef is None:
        reasons.append("the interaction could not be fit")
    else:
        if ci[0] <= 0 <= ci[1]:
            reasons.append(f"interaction CI [{ci[0]:+.3f}, {ci[1]:+.3f}] includes zero")
        signs = {np.sign(s["coef"].get("gust_x_pass_heavy", 0)) for s in seasons if s["coef"]}
        if len(signs) > 1:
            reasons.append("the interaction changes sign across seasons")
    swing = fit.get("swing_pp_pass_heavy_p10_to_p90_gust")
    if swing is None or abs(swing) <= VIG_HURDLE_PP:
        reasons.append(
            f"swing {swing if swing is None else round(swing, 2)} pp across the gust range does not clear the {VIG_HURDLE_PP} pp hurdle"
        )
    return {
        "signal": not reasons,
        "reasons": reasons,
        "rule": (
            "PRE-REGISTERED: interaction (gust x pass-heavy) bootstrap CI excludes zero, same sign "
            "every season, and the pass-heavy swing across the p10-p90 gust range clears 2.38 pp. "
            "Written before the numbers were read. Weather stays out of the model regardless "
            "until a separate promotion test passes."
        ),
    }


def _pct(v):
    return "—" if v is None else f"{100 * v:.1f}%"


def _ci(ci):
    return "—" if not ci or ci[0] is None else f"{100 * ci[0]:.1f}–{100 * ci[1]:.1f}%"


def render_markdown(r: Dict[str, Any]) -> str:
    v = r["verdict"]
    f = r["fit"]
    L = [
        "# Weather × offensive style — does decision-time gust predict market error?",
        "",
        f"2024–25 FBS games with a real 1H close, a de-vigged closing price, and a decision-safe "
        f"lead-{r['lead_hours']} forecast (`weather_obs`, ICON): **{r['n']} decided outdoor games**. Pass-heavy = top third "
        f"of the two offences' mean as-of 1H pass rate (cut {r['pass_heavy_cut']:.3f}). Measurement only.",
        "",
        f"## Verdict: {'**SIGNAL DETECTED**' if v['signal'] else '**NO FINDING**'}",
        "",
    ]
    for why in v["reasons"] or ["every pre-registered criterion met"]:
        L.append(f"- {why}")
    L += [
        "",
        f"_{v['rule']}_",
        "",
        "## Realized under against the book's implied, by gust band × style",
        "",
        f"| style | gust (mph, lead {r['lead_hours']}) | n | realized under | implied | diff | Wilson 95% |",
        "|---|---|---|---|---|---|---|",
    ]
    for b in r["buckets"]:
        diff = "—" if b["diff_pp"] is None else f"{b['diff_pp']:+.1f} pp"
        L.append(
            f"| {b['style']} | {b['band']} | {b['n']} | {_pct(b['realized_under'])} | {_pct(b['implied_under'])} | {diff} | {_ci(b['wilson'])} |"
        )
    L += [
        "",
        "## The test: under ~ book's logit (offset) + gust/5 + pass-heavy + gust/5 × pass-heavy",
        "",
    ]
    for k in ("gust_per5", "pass_heavy", "gust_x_pass_heavy"):
        c = f["coef"].get(k)
        ci = f["ci"].get(k)
        L.append(
            f"- **{k}**: {'—' if c is None else f'{c:+.4f}'}"
            + (
                ""
                if not ci
                else f", bootstrap 95% CI [{ci[0]:+.4f}, {ci[1]:+.4f}] ({f['n_boot']} resamples)"
            )
        )
    sw = f.get("swing_pp_pass_heavy_p10_to_p90_gust")
    lo, hi = f["gust_p10_p90_mph"]
    L += [
        f"- for a pass-heavy game, moving gust from its 10th to its 90th percentile ({lo:.1f} → {hi:.1f} mph) shifts P(under) by "
        f"**{'—' if sw is None else f'{sw:+.2f} pp'}** against a **{VIG_HURDLE_PP} pp** vig hurdle",
        "",
        "| season | n | gust/5 | pass-heavy | gust × pass-heavy |",
        "|---|---|---|---|---|",
    ]
    for s in r["per_season"]:
        c = s["coef"]
        L.append(
            f"| {s['season']} | {s['n']} | {c.get('gust_per5', float('nan')):+.4f} | {c.get('pass_heavy', float('nan')):+.4f} | {c.get('gust_x_pass_heavy', float('nan')):+.4f} |"
        )
    L += ["", f"_generated {r['generated_at']}_", ""]
    return "\n".join(L)
