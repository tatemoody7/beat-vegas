"""Post-mortem math: every rated game vs its outcome, under two proxy lines.

Pure and DB-free so it is unit-tested; `scripts/post_mortem.py` does the I/O.

Two scopes:
- hist_2023_25: the walk-forward gbm_v1 ratings (predictions rows), regraded
  side by side at the flat 0.52 proxy they were rated against and at the fair
  step proxy (data/multiplier.json). The step column is the honest one.
- live_<season>: the built cards (Hard Rock price reads) graded at Hard Rock's
  own number, the consensus number and the consensus close.

Conventions: pushes are excluded from the hit rate but count as staked (ROI =
units / n). Every bucket carries a Wilson interval and the factor ledger's
Beta posterior (p_beat = P(true rate > 52.4%)) so small buckets read small.
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy import stats

from .card import KEY_NUMBERS_1H, hook_side
from .etl.fbs import FbsMap
from .etl.proxy_line import DEFAULT_SHARE, proxy_total
from .factors.ledger import BREAKEVEN, beta_posterior
from .grading import trusted_first_half_total, under_result, units_won
from .model import score as _score

BET_GAP_PTS = float(getattr(_score, "BET_GAP_PTS", 1.75))
STRONG_GAP_PTS = float(getattr(_score, "STRONG_GAP_PTS", 3.0))
WATCH_GAP_PTS = float(getattr(_score, "WATCH_GAP_PTS", 1.0))
MODEL_BET_THRESHOLD = int(getattr(_score, "MODEL_BET_THRESHOLD", 53))
HR_OFF_MARKET_PTS = float(getattr(_score, "HR_OFF_MARKET_PTS", 0.5))
EV_FLOOR = float(getattr(_score, "EV_FLOOR", -0.05))
PRICE_EDGE_EV = 0.005  # card.py / lineCheck.ts "pos" verdict
WEEKLY_CAP = 5

HIST_SCOPE = "hist_2023_25"
RULES = ("all", "gap175", "gap300", "score53", "both", "cap5", "top20")
LIVE_RULES = ("all_hr", "bet", "price_read", "gap175", "qualifying")
KEY_NUMBERS = KEY_NUMBERS_1H  # one tuple with card.py so both ledgers read alike
SIGMA_1H = 11.9  # per-game 1H-total noise, pts (validate_engine)

_INF = float("inf")
# (lo inclusive, hi exclusive, label)
GAP_BANDS = [
    (-_INF, 0, "<0"),
    (0, 1, "0–1"),
    (1, 1.75, "1–1.75"),
    (1.75, 3, "1.75–3"),
    (3, _INF, "3+"),
]
SCORE_BANDS = [(-_INF, 47, "<47"), (47, 53, "47–52"), (53, 60, "53–59"), (60, _INF, "60+")]
SPREAD_BANDS = [(0, 7, "≤7"), (7, 14, "7–14"), (14, 21, "14–21"), (21, _INF, "21+")]
TOTAL_BANDS = [(-_INF, 45, "<45"), (45, 52, "45–52"), (52, 60, "52–60"), (60, _INF, "60+")]
PACE_BANDS = [(-_INF, 24, "<24 fast"), (24, 27, "24–27"), (27, 30, "27–30"), (30, _INF, "30+ slow")]
WIND_BANDS = [(-_INF, 10, "<10"), (10, 15, "10–15"), (15, _INF, "15+")]
TEMP_BANDS = [(-_INF, 40, "<40"), (40, 60, "40–60"), (60, 80, "60–80"), (80, _INF, "80+")]
WEEK_BANDS = [
    (-_INF, 3, "1–2"),
    (3, 7, "3–6"),
    (7, 11, "7–10"),
    (11, 16, "11–15"),
    (16, _INF, "post"),
]
KEY_DIST_BANDS = [
    (0, 0.25, "0"),
    (0.25, 0.75, "0.5"),
    (0.75, 1.25, "1"),
    (1.25, 1.75, "1.5"),
    (1.75, _INF, "2+"),
]
EV_BANDS = [
    (-_INF, EV_FLOOR, "neg"),
    (EV_FLOOR, PRICE_EDGE_EV, "fair"),
    (PRICE_EDGE_EV, _INF, "pos"),
]

# Ordered bucket labels per dimension (for bucket_order); quantile dims sort by label.
_ORDER: Dict[str, List[str]] = {
    "gap_band": [b[2] for b in GAP_BANDS],
    "score_band": [b[2] for b in SCORE_BANDS],
    "spread_band": [b[2] for b in SPREAD_BANDS],
    "total_band": [b[2] for b in TOTAL_BANDS],
    "pace_band": [b[2] for b in PACE_BANDS],
    "wind_band": ["dome"] + [b[2] for b in WIND_BANDS],
    "temp_band": [b[2] for b in TEMP_BANDS],
    "week_band": [b[2] for b in WEEK_BANDS],
    "key_dist": [b[2] for b in KEY_DIST_BANDS],
    "hook_side": ["key+0.5", "key−0.5", "on_key", "other"],
    "line_frac": ["whole", "half"],
    "division": ["fbs", "fbs_v_fcs", "non_fbs"],
    "neutral": ["home", "neutral"],
    "kick_window": ["noon", "afternoon", "evening", "night"],
    # Hard Rock minus the other books' median, banded on HR_OFF_MARKET_PTS.
    # Exactly-on-the-market is its own band: it is the modal case.
    "hr_vs_market": ["HR ≤ -0.5", "HR -0.5..0", "HR = market", "HR 0..+0.5", "HR ≥ +0.5"],
    "ev_band": [b[2] for b in EV_BANDS],
    "tier": ["BET", "EDGE", "PASS"],
    # paper-ledger gate (live): what blocked a real bet on each rated game
    "blocker": [
        "none",
        "price",
        "off_market",
        "no_fair_price",
        "qb_out",
        "cap",
        "gap",
        "no_hr_line",
        "no_model",
    ],
    # which 1H engine wrote the stored prediction (factors_json.engine); rows
    # written before the field existed carry none and fall out of the split
    "engine": ["bv_line", "residual"],
}

HIST_DIMENSIONS = (
    "gap_band",
    "score_band",
    "season",
    "week_band",
    "spread_band",
    "total_band",
    "pace_band",
    "wind_band",
    "temp_band",
    "division",
    "neutral",
    "kick_window",
    "line_frac",
    "key_dist",
    "hook_side",
    "off_ppa_q",
    "def_ppa_q",
    "fh_pf_q",
)
LIVE_DIMENSIONS = (
    "hr_vs_market",
    "tier",
    "blocker",
    "engine",
    "ev_band",
    "week_band",
    "spread_band",
    "total_band",
    "hook_side",
)

CONTRAST_FEATURES = (
    "spread_abs",
    "full_game_total",
    "line",
    "bv_line",
    "gap",
    "under_score",
    "pace_spp",
    "pace_plays",
    "wx_temp",
    "wx_wind",
    "dome",
    "off_ppa",
    "def_ppa",
    "fh_pf_sum",
    "fh_pa_sum",
    "fh_off_epa_mean",
    "fh_off_success_mean",
    "returning_pct",
    "neutral_site",
    "week",
    "kick_hour_et",
    "line_frac_half",
)


# ---------------------------------------------------------------- small helpers


def _num(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def parse_pace(s: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
    """'27.3s/play · 149 plays' -> (27.3, 149.0); anything else -> (None, None)."""
    if not s or not isinstance(s, str):
        return (None, None)
    m_spp = re.search(r"([\d.]+)\s*s/play", s)
    m_pl = re.search(r"(\d+)\s*plays", s)
    return (
        float(m_spp.group(1)) if m_spp else None,
        float(m_pl.group(1)) if m_pl else None,
    )


def parse_weather(s: Optional[str]) -> Dict[str, Optional[float]]:
    """Score.py's display string back to numbers. 'Dome' -> dome=1, rest unknown;
    a string without a rain token means precipitation was zero, not unknown."""
    out: Dict[str, Optional[float]] = {
        "wx_temp": None,
        "wx_wind": None,
        "wx_precip": None,
        "dome": None,
    }
    if not s or not isinstance(s, str):
        return out
    if s.strip().lower() == "dome":
        out["dome"] = 1.0
        return out
    m_t = re.search(r"(-?[\d.]+)\s*°F", s)
    m_w = re.search(r"wind\s*([\d.]+)\s*mph", s)
    m_r = re.search(r"([\d.]+)\s*in\s*rain", s)
    out["wx_temp"] = float(m_t.group(1)) if m_t else None
    out["wx_wind"] = float(m_w.group(1)) if m_w else None
    out["wx_precip"] = float(m_r.group(1)) if m_r else 0.0
    out["dome"] = 0.0
    return out


def _parse_returning(s: Any) -> Optional[float]:
    if not s or not isinstance(s, str):
        return None
    vals = [float(x) for x in re.findall(r"([\d.]+)%", s)]
    return sum(vals) / len(vals) if vals else None


def division_of(season: int, home: str, away: str, fbs: FbsMap) -> Optional[str]:
    teams = fbs.get(int(season)) if season is not None else None
    if teams is None:
        return None
    h, a = home in teams, away in teams
    if h and a:
        return "fbs"
    if h or a:
        return "fbs_v_fcs"
    return "non_fbs"


def proxy_lines(
    full_total: Optional[float], spread: Optional[float], step_coeffs: Optional[Dict]
) -> Tuple[Optional[float], Optional[float]]:
    """(flat 0.52 line, fair step line) for a game; step None when no coeffs."""
    full = _num(full_total)
    if full is None:
        return (None, None)
    flat = proxy_total(full, ratio=DEFAULT_SHARE)
    step = proxy_total(full, _num(spread), coeffs=step_coeffs) if step_coeffs else None
    return (flat, step)


def regrade(
    fh: Optional[float], line: Optional[float], price: int = -110
) -> Tuple[Optional[str], Optional[float]]:
    f, ln = _num(fh), _num(line)
    if f is None or ln is None:
        return (None, None)
    return (under_result(f, ln), units_won(f, ln, price))


_EPS = 1e-9


def hr_vs_market_band(diff: Optional[float]) -> Optional[str]:
    """Five bands on Hard Rock's line minus the other books' median, with
    HR_OFF_MARKET_PTS as the threshold: <= -0.5, (-0.5, 0), exactly 0,
    (0, +0.5), >= +0.5. Float noise around 0 and the thresholds reads as the
    exact value (lines are half points)."""
    v = _num(diff)
    if v is None:
        return None
    if v <= -HR_OFF_MARKET_PTS + _EPS:
        return "HR ≤ -0.5"
    if v >= HR_OFF_MARKET_PTS - _EPS:
        return "HR ≥ +0.5"
    if abs(v) < _EPS:
        return "HR = market"
    return "HR -0.5..0" if v < 0 else "HR 0..+0.5"


def hr_vs_market(hr_line: Optional[float], market_line: Optional[float]) -> Optional[str]:
    """Where Hard Rock's number sits vs the consensus (hr_vs_market_band of the
    difference); None without both lines."""
    h, m = _num(hr_line), _num(market_line)
    if h is None or m is None:
        return None
    return hr_vs_market_band(h - m)


def _kick_hour_et(start: Any) -> Optional[float]:
    if start is None:
        return None
    try:
        ts = pd.Timestamp(start)
    except (TypeError, ValueError):
        return None
    if pd.isna(ts):
        return None
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    # games.start_date is naive UTC; CFB season is on daylight time.
    return float((ts.hour - 4) % 24 + ts.minute / 60.0)


def run_id_for(now: datetime) -> str:
    return now.strftime("pm-%Y%m%dT%H%M%SZ")


# ---------------------------------------------------------------- frames


def _loads(s: Any) -> Dict:
    if isinstance(s, dict):
        return s
    if not s:
        return {}
    try:
        d = json.loads(s)
    except (TypeError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def engine_of(factors_json: Any) -> Optional[str]:
    """The 1H engine tag a stored prediction carries (`factors_json.engine`:
    'bv_line' | 'residual'); None for rows written before the field existed,
    or for anything that is not a JSON object."""
    d = factors_json if isinstance(factors_json, dict) else _loads(factors_json)
    e = d.get("engine") if isinstance(d, dict) else None
    return e if isinstance(e, str) and e else None


def created_order(row: Any) -> Tuple[int, datetime]:
    """Sort key for 'newest row wins' scans of `predictions`: oldest first, with
    a NULL created_at as the OLDEST row. Postgres sorts NULL last under ORDER BY
    ASC, which would let a legacy untagged row win as 'newest'."""
    ts = getattr(row, "created_at", None)
    return (0, datetime.min) if ts is None else (1, ts)


def _mean2(a: Any, b: Any) -> Optional[float]:
    x, y = _num(a), _num(b)
    vals = [v for v in (x, y) if v is not None]
    return sum(vals) / len(vals) if vals else None


def _sum2(a: Any, b: Any) -> Optional[float]:
    x, y = _num(a), _num(b)
    if x is None or y is None:
        return None
    return x + y


def build_hist_frame(
    preds: Iterable[Dict], step_coeffs: Optional[Dict], fbs: FbsMap
) -> pd.DataFrame:
    """One row per stored prediction with both proxy lines, both gradings and the
    covariates the contrasts use. Drops untrusted 1H totals and rows with no
    model line; counts live in `df.attrs['dropped']`."""
    rows: List[Dict] = []
    dropped: Dict[str, int] = {}

    def _drop(reason: str) -> None:
        dropped[reason] = dropped.get(reason, 0) + 1

    for p in preds:
        fh = trusted_first_half_total(
            _num(p.get("first_half_total")),
            _num(p.get("home_points")),
            _num(p.get("away_points")),
            p.get("first_half_source"),
        )
        if fh is None:
            _drop("untrusted_fh" if p.get("first_half_total") is not None else "no_fh")
            continue
        bv = _num(p.get("bv_line"))
        if bv is None:
            _drop("no_bv_line")
            continue
        f = _loads(p.get("factors_json"))
        spp, plays = parse_pace(f.get("pace"))
        wx = parse_weather(f.get("weather"))
        # numeric fallbacks (weather / team_tempo tables) when the string lacks them
        if wx["wx_temp"] is None:
            wx["wx_temp"] = _num(p.get("wx_temp"))
        if wx["wx_wind"] is None:
            wx["wx_wind"] = _num(p.get("wx_wind"))
        if wx["dome"] is None:
            wx["dome"] = _num(p.get("wx_dome"))
        if spp is None:
            spp = _num(p.get("tempo_spp"))
        full = _num(p.get("full_game_total"))
        spread = _num(p.get("spread"))
        flat_proxy, step_line = proxy_lines(full, spread, step_coeffs)
        line_flat = _num(p.get("line_used"))
        if line_flat is None:
            line_flat = flat_proxy
        o_flat, u_flat = regrade(fh, line_flat)
        o_step, u_step = regrade(fh, step_line)
        line_real = _num(p.get("close_line"))  # real pre-kickoff consensus 1H close, if captured
        o_real, u_real = regrade(fh, line_real)
        # Same pick, FULL-GAME under at the real pre-kick full-game close (2026-09-07):
        # selection stays the 1H gap (gap_fg = gap_real); the outcome is the whole game.
        pts = _sum2(p.get("home_points"), p.get("away_points"))
        line_fg = _num(p.get("fg_close"))
        o_fg, u_fg = regrade(pts, line_fg) if line_real is not None else (None, None)
        season = int(p["season"])
        rows.append(
            {
                "game_id": int(p["game_id"]),
                "season": season,
                "week": _num(p.get("week")),
                "home_team": p.get("home_team"),
                "away_team": p.get("away_team"),
                "division": division_of(season, p.get("home_team"), p.get("away_team"), fbs),
                "fh": float(fh),
                "bv_line": bv,
                "under_score": _num(p.get("under_score")),
                "spread": spread,
                "spread_abs": abs(spread) if spread is not None else None,
                "full_game_total": full,
                "neutral_site": bool(p.get("neutral_site"))
                if p.get("neutral_site") is not None
                else None,
                "pace_spp": spp,
                "pace_plays": plays,
                "wx_temp": wx["wx_temp"],
                "wx_wind": wx["wx_wind"],
                "wx_precip": wx["wx_precip"],
                "dome": wx["dome"],
                "off_ppa": _num(f.get("off_ppa")),
                "def_ppa": _num(f.get("def_ppa")),
                "fh_pf_sum": _sum2(f.get("fh_home_pf"), f.get("fh_away_pf")),
                "fh_pa_sum": _sum2(f.get("fh_home_pa"), f.get("fh_away_pa")),
                "fh_off_epa_mean": _mean2(f.get("fh_off_epa_home"), f.get("fh_off_epa_away")),
                "fh_off_success_mean": _mean2(
                    f.get("fh_off_success_home"), f.get("fh_off_success_away")
                ),
                "returning_pct": _parse_returning(f.get("returning")),
                "kick_hour_et": _kick_hour_et(p.get("start_date")),
                "line_flat": line_flat,
                "line_step": step_line,
                "gap_flat": round(line_flat - bv, 2) if line_flat is not None else None,
                "gap_step": round(step_line - bv, 2) if step_line is not None else None,
                "outcome_flat": o_flat,
                "outcome_step": o_step,
                "units_flat": u_flat,
                "units_step": u_step,
                "line_real": line_real,
                "gap_real": round(line_real - bv, 2) if line_real is not None else None,
                "outcome_real": o_real,
                "units_real": u_real,
                "pts": pts,
                "line_fg": line_fg,
                "gap_fg": round(line_real - bv, 2)
                if (line_real is not None and line_fg is not None)
                else None,
                "outcome_fg": o_fg,
                "units_fg": u_fg,
                "resid": float(fh) - bv,
            }
        )
    df = pd.DataFrame(rows)
    df.attrs["dropped"] = dropped
    return df


def live_blocker(it: Dict) -> str:
    """The paper-ledger gate for a card item: 'cap' beyond the weekly cap; the
    gate that blocked a qualifying game ('none' = it was a BET); otherwise the
    card's own blocker ('no_hr_line', 'gap', 'no_model', ...)."""
    if it.get("over_cap"):
        return "cap"
    if it.get("qualifies"):
        return it.get("paper_blocker") or "none"
    b = it.get("blocker")
    if b:
        return str(b)
    return "no_model" if _num(it.get("bv_line")) is None else "gap"


def build_live_frame(
    items: Iterable[Dict],
    games: Dict[int, Dict],
    closes: Dict[int, float],
    hr_closes: Optional[Dict[int, float]] = None,
    engines: Optional[Dict[int, Optional[str]]] = None,
) -> pd.DataFrame:
    """Card items (the live ratings) graded at Hard Rock's number, the consensus
    number, the consensus close and (when captured) Hard Rock's own pre-kick
    close. Ungraded games keep fh=None. `hr_closes`: game_id -> Hard Rock's
    pre-kickoff 1H close from the per-game close polls. `engines`: game_id ->
    the engine tag of the stored prediction (engine_of), an added split on top
    of the model_version tag, which stays as it is."""
    hr_closes = hr_closes or {}
    engines = engines or {}
    rows: List[Dict] = []
    for it in items:
        gid = int(it["game_id"])
        g = games.get(gid, {}) or {}
        fh = trusted_first_half_total(
            _num(g.get("first_half_total")),
            _num(g.get("home_points")),
            _num(g.get("away_points")),
            g.get("first_half_source"),
        )
        hr_line, market_line = _num(it.get("hr_line")), _num(it.get("market_line"))
        hr_price = it.get("hr_price")
        price = int(hr_price) if hr_price is not None else -110
        close = _num(closes.get(gid))
        hr_close = _num(hr_closes.get(gid))
        hr_open = _num(it.get("hr_open"))
        o_hr, u_hr = regrade(fh, hr_line, price)
        o_mk, u_mk = regrade(fh, market_line)
        o_cl, u_cl = regrade(fh, close)
        o_hc, u_hc = regrade(fh, hr_close, price)
        spread = _num(g.get("spread"))
        full = _num(g.get("full_game_total"))
        rows.append(
            {
                "game_id": gid,
                "season": g.get("season"),
                "week": _num(g.get("week")),
                "home_team": it.get("home"),
                "away_team": it.get("away"),
                "kick": it.get("kick"),
                "fh": float(fh) if fh is not None else None,
                "tier": it.get("tier"),
                "blocker": it.get("blocker"),
                "ev": _num(it.get("ev")),
                "gap": _num(it.get("gap")),
                "bv_line": _num(it.get("bv_line")),
                "hr_line": hr_line,
                "hr_price": price if hr_line is not None else None,
                "market_line": market_line,
                "close_line": close,
                "derived_line": _num(g.get("derived_line")),
                "spread": spread,
                "spread_abs": abs(spread) if spread is not None else None,
                "full_game_total": full,
                "fh_share": (float(fh) / full) if (fh is not None and full) else None,
                "outcome_hr": o_hr,
                "units_hr": u_hr,
                "outcome_market": o_mk,
                "units_market": u_mk,
                "outcome_close": o_cl,
                "units_close": u_cl,
                # Hard Rock minus the OTHER books' median, straight off the
                # card. Cards built before 2026-09-07 carry no such field, and
                # the old fallback (hr_line - market_line) is a DIFFERENT
                # quantity — that median includes Hard Rock itself — so banding
                # them together would mix two definitions in one set of buckets.
                # They get None instead: the dimension covers only the weeks
                # from the cutover on.
                "hr_vs_market": (
                    hr_vs_market_band(it["hr_vs_market"])
                    if _num(it.get("hr_vs_market")) is not None
                    else None
                ),
                # Hard Rock's own opener -> pre-kick close (the number you bet)
                "hr_open": hr_open,
                "hr_close": hr_close,
                "hr_move": (hr_close - hr_open)
                if hr_close is not None and hr_open is not None
                else None,
                "outcome_hr_close": o_hc,
                "units_hr_close": u_hc,
                # paper ledger
                "qualifies": bool(it.get("qualifies")),
                "over_cap": bool(it.get("over_cap")),
                "cap_rank": _num(it.get("cap_rank")),
                "blocker_dim": live_blocker(it),
                "engine": engines.get(gid),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- rules


def weekly_cap(
    df: pd.DataFrame,
    gap_col: str,
    cap: int = WEEKLY_CAP,
    min_gap: float = BET_GAP_PTS,
    tie_cols: Optional[Sequence[str]] = None,
) -> pd.Series:
    """Per (season, week): the top `cap` games by gap among gap >= min_gap.
    Ties: `tie_cols` ascending, default lower game_id. Deterministic. Hist rows
    have no ev; mirrors card.apply_weekly_cap minus ev (under_score is never a
    tie-break). The residual gate passes [kickoff, game_id] so both engines are
    ranked the way the card ranks them."""
    mask = pd.Series(False, index=df.index)
    if df.empty or gap_col not in df:
        return mask
    elig = df[df[gap_col].notna() & (df[gap_col] >= min_gap)]
    if elig.empty:
        return mask
    ties = list(tie_cols) if tie_cols else ["game_id"]
    elig = elig.sort_values([gap_col] + ties, ascending=[False] + [True] * len(ties))
    keep = elig.groupby(["season", "week"], sort=False, dropna=False).head(cap)
    mask.loc[keep.index] = True
    return mask


def _top20(df: pd.DataFrame, gap_col: str) -> pd.Series:
    mask = pd.Series(False, index=df.index)
    for _, grp in df.groupby("season"):
        g = grp[gap_col].dropna()
        if g.empty:
            continue
        cut = g.quantile(0.8)
        mask.loc[g[g >= cut].index] = True
    return mask


def rule_masks(df: pd.DataFrame, proxy: str) -> Dict[str, pd.Series]:
    gap_col = f"gap_{proxy}"
    gap = df[gap_col] if gap_col in df else pd.Series(np.nan, index=df.index)
    score = df["under_score"] if "under_score" in df else pd.Series(np.nan, index=df.index)
    gap175 = gap.notna() & (gap >= BET_GAP_PTS)
    score53 = score.notna() & (score >= MODEL_BET_THRESHOLD)
    return {
        "all": pd.Series(True, index=df.index),
        "gap175": gap175,
        "gap300": gap.notna() & (gap >= STRONG_GAP_PTS),
        "score53": score53,
        "both": gap175 & score53,
        "cap5": weekly_cap(df, gap_col),
        "top20": _top20(df, gap_col),
    }


def live_rule_masks(df: pd.DataFrame) -> Dict[str, pd.Series]:
    tier = df["tier"] if "tier" in df else pd.Series(None, index=df.index, dtype=object)
    ev = (
        pd.to_numeric(df["ev"], errors="coerce")
        if "ev" in df
        else pd.Series(np.nan, index=df.index)
    )
    gap = (
        pd.to_numeric(df["gap"], errors="coerce")
        if "gap" in df
        else pd.Series(np.nan, index=df.index)
    )
    hr = df["hr_line"].notna() if "hr_line" in df else pd.Series(False, index=df.index)
    if "qualifies" in df:
        qualifying = df["qualifies"].fillna(False).astype(bool)
    else:
        qualifying = hr & gap.notna() & (gap >= BET_GAP_PTS)
    return {
        "all_hr": hr,
        "bet": tier == "BET",
        "price_read": tier.isin(["BET", "EDGE"]) | (ev.notna() & (ev >= PRICE_EDGE_EV)),
        "gap175": gap.notna() & (gap >= BET_GAP_PTS),
        # the paper ledger's population: Hard Rock's 1H line >= 1.75 above ours, any gate
        "qualifying": qualifying,
    }


# ---------------------------------------------------------------- bands


def band_label(value: Any, bands: Sequence[Tuple[float, float, str]]) -> Optional[str]:
    v = _num(value)
    if v is None:
        return None
    for lo, hi, label in bands:
        if lo <= v < hi:
            return label
    return None


def quantile_bands(series: pd.Series, q: int = 4) -> List[Tuple[float, float, str]]:
    """Equal-count bands with the cutpoints in the label, e.g. 'Q2 (0.28–0.34)'."""
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty or s.nunique() < q:
        return []
    edges = [float(s.quantile(i / q)) for i in range(q + 1)]
    bands = []
    for i in range(q):
        lo = -_INF if i == 0 else edges[i]
        hi = _INF if i == q - 1 else edges[i + 1]
        bands.append((lo, hi, f"Q{i + 1} ({edges[i]:.2f}–{edges[i + 1]:.2f})"))
    return bands


def _kick_window(h: Any) -> Optional[str]:
    v = _num(h)
    if v is None:
        return None
    if v <= 12.75:
        return "noon"
    if v < 17:
        return "afternoon"
    if v < 20:
        return "evening"
    return "night"


def _key_dist(line: Any) -> Optional[str]:
    v = _num(line)
    if v is None:
        return None
    return band_label(min(abs(v - k) for k in KEY_NUMBERS), KEY_DIST_BANDS)


_hook_side = hook_side  # same chip as the live card (beatvegas/card.py)


def assign_dimensions(df: pd.DataFrame, proxy: str) -> pd.DataFrame:
    """Add the *_band / categorical columns bucket_rows groups by."""
    out = df.copy()
    line_col, gap_col = f"line_{proxy}", f"gap_{proxy}"
    if gap_col in out:
        out["gap_band"] = out[gap_col].map(lambda v: band_label(v, GAP_BANDS))
    if "under_score" in out:
        out["score_band"] = out["under_score"].map(lambda v: band_label(v, SCORE_BANDS))
    if "season" in out:
        out["season"] = out["season"].map(lambda v: str(int(v)) if _num(v) is not None else None)
    if "week" in out:
        out["week_band"] = out["week"].map(lambda v: band_label(v, WEEK_BANDS))
    if "spread_abs" in out:
        out["spread_band"] = out["spread_abs"].map(lambda v: band_label(v, SPREAD_BANDS))
    if "full_game_total" in out:
        out["total_band"] = out["full_game_total"].map(lambda v: band_label(v, TOTAL_BANDS))
    if "pace_spp" in out:
        out["pace_band"] = out["pace_spp"].map(lambda v: band_label(v, PACE_BANDS))
    if "wx_wind" in out:
        dome = out["dome"] if "dome" in out else pd.Series(None, index=out.index, dtype=object)
        out["wind_band"] = [
            "dome" if _num(d) == 1.0 else band_label(w, WIND_BANDS)
            for d, w in zip(dome, out["wx_wind"])
        ]
    if "wx_temp" in out:
        out["temp_band"] = out["wx_temp"].map(lambda v: band_label(v, TEMP_BANDS))
    if "neutral_site" in out:
        out["neutral"] = out["neutral_site"].map(
            lambda v: (
                None
                if v is None or (isinstance(v, float) and math.isnan(v))
                else ("neutral" if v else "home")
            )
        )
    if "kick_hour_et" in out:
        out["kick_window"] = out["kick_hour_et"].map(_kick_window)
    if line_col in out:
        out["line"] = out[line_col]
        out["line_frac"] = out[line_col].map(
            lambda v: None if _num(v) is None else ("half" if abs(v % 1 - 0.5) < 1e-9 else "whole")
        )
        out["line_frac_half"] = out["line_frac"].map(
            lambda v: None if v is None else (1.0 if v == "half" else 0.0)
        )
        out["key_dist"] = out[line_col].map(_key_dist)
        out["hook_side"] = out[line_col].map(_hook_side)
    if gap_col in out:
        out["gap"] = out[gap_col]
    for col, dim in (("off_ppa", "off_ppa_q"), ("def_ppa", "def_ppa_q"), ("fh_pf_sum", "fh_pf_q")):
        if col in out:
            bands = quantile_bands(out[col])
            out[dim] = out[col].map(lambda v, b=bands: band_label(v, b)) if bands else None
    if "ev" in out:
        out["ev_band"] = out["ev"].map(lambda v: band_label(v, EV_BANDS))
    if "blocker_dim" in out:
        out["blocker"] = out["blocker_dim"]
    if proxy == "hr" and "hr_line" in out and "hook_side" not in out:
        out["key_dist"] = out["hr_line"].map(_key_dist)
        out["hook_side"] = out["hr_line"].map(_hook_side)
    return out


# ---------------------------------------------------------------- statistics


def wilson_ci(hits: int, n: int, z: float = 1.96) -> Tuple[Optional[float], Optional[float]]:
    if not n:
        return (None, None)
    p = hits / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def tally(outcomes: pd.Series, units: pd.Series) -> Dict[str, Any]:
    o = pd.Series(list(outcomes), dtype=object)
    u = pd.to_numeric(pd.Series(list(units)), errors="coerce").fillna(0.0)
    n = int(len(o))
    unders = int((o == "under").sum())
    overs = int((o == "over").sum())
    pushes = int((o == "push").sum())
    decided = unders + overs
    lo, hi = wilson_ci(unders, decided)
    post = beta_posterior(unders, decided) if decided else None
    return {
        "n": n,
        "unders": unders,
        "overs": overs,
        "pushes": pushes,
        "under_pct": (unders / decided) if decided else None,
        "units": float(u.sum()) if n else 0.0,
        "roi": (float(u.sum()) / n) if n else None,
        "ci_lo": lo,
        "ci_hi": hi,
        "post_mean": post["mean"] if post else None,
        "p_beat": post["p_beat"] if post else None,
    }


def _order(dim: str, bucket: str, i: int) -> int:
    labels = _ORDER.get(dim)
    if labels and bucket in labels:
        return labels.index(bucket)
    return i


def bucket_rows(
    df: pd.DataFrame,
    *,
    run_id: str,
    computed_at: str,
    scope: str,
    segment: str,
    proxy: str,
    selection_masks: Dict[str, pd.Series],
    outcome_col: str,
    units_col: str,
    dimensions: Sequence[str],
) -> List[Dict]:
    """Tidy rows: one headline ('all'/'all') per selection plus one per
    dimension bucket. Buckets with no graded games are skipped."""
    ids = {
        "run_id": run_id,
        "computed_at": computed_at,
        "scope": scope,
        "segment": segment,
        "proxy_kind": proxy,
    }
    out: List[Dict] = []
    for sel, mask in selection_masks.items():
        sub = df[mask.reindex(df.index, fill_value=False).astype(bool)]
        sub = sub[sub[outcome_col].notna()] if outcome_col in sub else sub.iloc[0:0]
        out.append(
            {
                **ids,
                "selection": sel,
                "dimension": "all",
                "bucket": "all",
                "bucket_order": 0,
                **tally(
                    sub[outcome_col] if not sub.empty else pd.Series([], dtype=object),
                    sub[units_col] if not sub.empty else pd.Series([], dtype=float),
                ),
            }
        )
        for dim in dimensions:
            if dim not in sub or sub.empty:
                continue
            groups = sub[sub[dim].notna()].groupby(dim, sort=True)
            for i, (bucket, grp) in enumerate(groups):
                if grp.empty:
                    continue
                out.append(
                    {
                        **ids,
                        "selection": sel,
                        "dimension": dim,
                        "bucket": str(bucket),
                        "bucket_order": _order(dim, str(bucket), i),
                        **tally(grp[outcome_col], grp[units_col]),
                    }
                )
    return out


def stress_rows(
    df: pd.DataFrame,
    mask: pd.Series,
    line_col: str,
    deltas: Sequence[float] = (-1.0, -0.5, 0.0, 0.5, 1.0),
    actual_col: str = "fh",
    **ids: Any,
) -> List[Dict]:
    """Hold the selection, shift the grading line by each delta, regrade
    `actual_col` (the 1H total, or `pts` for the full-game column)."""
    sub = df[mask.reindex(df.index, fill_value=False).astype(bool)]
    out: List[Dict] = []
    for d in deltas:
        graded = [
            regrade(fh, (ln + d) if _num(ln) is not None else None)
            for fh, ln in zip(sub[actual_col], sub[line_col])
        ]
        t = tally(
            pd.Series([g[0] for g in graded], dtype=object),
            pd.Series([g[1] for g in graded], dtype=float),
        )
        out.append(
            {
                **ids,
                "dimension": "line_stress",
                "bucket": f"{d:+.1f}",
                "bucket_order": int(round((d + 1.0) * 2)),
                "delta": d,
                **t,
            }
        )
    return out


def residual_by_band(df: pd.DataFrame, proxy: str, **ids: Any) -> List[Dict]:
    """mean(actual 1H − bv_line) per gap band: proxy-independent model check.
    stat_win = mean residual, stat_loss = its standard error."""
    d = assign_dimensions(df, proxy) if "gap_band" not in df else df
    out: List[Dict] = []
    for i, (bucket, grp) in enumerate(d[d["gap_band"].notna()].groupby("gap_band")):
        r = pd.to_numeric(grp["resid"], errors="coerce").dropna()
        if r.empty:
            continue
        se = float(r.std(ddof=1) / math.sqrt(len(r))) if len(r) > 1 else None
        out.append(
            {
                **ids,
                "dimension": "resid_by_gap",
                "bucket": str(bucket),
                "bucket_order": _order("gap_band", str(bucket), i),
                "n": int(len(r)),
                "unders": 0,
                "overs": 0,
                "pushes": 0,
                "under_pct": None,
                "units": 0.0,
                "roi": None,
                "ci_lo": None,
                "ci_hi": None,
                "post_mean": None,
                "p_beat": None,
                "stat_win": float(r.mean()),
                "stat_loss": se,
                "effect": None,
                "p_value": None,
                "q_value": None,
            }
        )
    return out


def bh_qvalues(pvals: Sequence[float]) -> List[float]:
    """Benjamini–Hochberg step-up q-values (NaN passes through)."""
    p = np.asarray([float(v) if v is not None else np.nan for v in pvals], dtype=float)
    q = np.full_like(p, np.nan)
    idx = np.where(~np.isnan(p))[0]
    m = len(idx)
    if m == 0:
        return q.tolist()
    order = idx[np.argsort(p[idx])]
    ranked = p[order] * m / np.arange(1, m + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    q[order] = np.minimum(ranked, 1.0)
    return q.tolist()


def contrast_rows(
    df: pd.DataFrame,
    mask: pd.Series,
    outcome_col: str,
    features: Sequence[str] = CONTRAST_FEATURES,
    **ids: Any,
) -> List[Dict]:
    """Wins (under) vs losses (over) on the selected rows, one row per feature:
    means, Cohen's d (pooled sd), Mann–Whitney p, BH q within this table."""
    sub = df[mask.reindex(df.index, fill_value=False).astype(bool)]
    wins = sub[sub[outcome_col] == "under"]
    losses = sub[sub[outcome_col] == "over"]
    rows: List[Dict] = []
    pvals: List[float] = []
    for f in features:
        if f not in sub:
            continue
        w = pd.to_numeric(wins[f], errors="coerce").dropna()
        lo = pd.to_numeric(losses[f], errors="coerce").dropna()
        if len(w) < 2 or len(lo) < 2:
            continue
        sw, sl = float(w.std(ddof=1)), float(lo.std(ddof=1))
        pooled = math.sqrt(((len(w) - 1) * sw**2 + (len(lo) - 1) * sl**2) / (len(w) + len(lo) - 2))
        effect = float((w.mean() - lo.mean()) / pooled) if pooled > 0 else 0.0
        if pooled > 0:
            try:
                p = float(stats.mannwhitneyu(w, lo, alternative="two-sided").pvalue)
            except ValueError:
                p = 1.0
        else:
            p = 1.0
        pvals.append(p)
        rows.append(
            {
                **ids,
                "dimension": "wl_contrast",
                "bucket": f,
                "bucket_order": len(rows),
                "n": int(len(w) + len(lo)),
                "unders": int(len(w)),
                "overs": int(len(lo)),
                "pushes": 0,
                "under_pct": None,
                "units": 0.0,
                "roi": None,
                "ci_lo": None,
                "ci_hi": None,
                "post_mean": None,
                "p_beat": None,
                "stat_win": float(w.mean()),
                "stat_loss": float(lo.mean()),
                "med_win": float(w.median()),
                "med_loss": float(lo.median()),
                "effect": effect,
                "p_value": p,
                "q_value": None,
            }
        )
    for r, q in zip(rows, bh_qvalues(pvals)):
        r["q_value"] = None if (q is None or (isinstance(q, float) and math.isnan(q))) else float(q)
    return rows


def gap_logit(df: pd.DataFrame, mask: pd.Series, proxy: str) -> Optional[Dict[str, Any]]:
    """Does the gap keep its coefficient once spread and total are controlled?
    Standardized logistic coefficients (sklearn, light L2). None if too few rows."""
    try:
        from sklearn.linear_model import LogisticRegression
    except ImportError:  # pragma: no cover
        return None
    sub = df[mask.reindex(df.index, fill_value=False).astype(bool)]
    cols = [f"gap_{proxy}", "spread_abs", "full_game_total"]
    if "wx_wind" in sub and sub["wx_wind"].notna().sum() >= 100:
        cols.append("wx_wind")
    d = sub[cols + [f"outcome_{proxy}"]].copy()
    d = d[d[f"outcome_{proxy}"].isin(["under", "over"])]
    for c in cols:
        d[c] = pd.to_numeric(d[c], errors="coerce")
        d[c] = d[c].fillna(d[c].median())
    d = d.dropna()
    if len(d) < 100 or d[f"outcome_{proxy}"].nunique() < 2:
        return None
    x = d[cols].to_numpy(dtype=float)
    x = (x - x.mean(axis=0)) / np.where(x.std(axis=0) == 0, 1.0, x.std(axis=0))
    y = (d[f"outcome_{proxy}"] == "under").to_numpy(dtype=int)
    m = LogisticRegression(C=10.0, max_iter=1000).fit(x, y)
    return {"n": int(len(d)), "coef": {c: float(b) for c, b in zip(cols, m.coef_[0])}}


def overfit_summary(returns_by_config: Dict[str, Sequence[float]], headline: str) -> Dict[str, Any]:
    from .backtest.overfit import deflated_sharpe_ratio, sharpe_ratio, sr_variance_across_configs

    configs = {k: list(v) for k, v in returns_by_config.items() if len(v) > 1}
    if headline not in configs:
        return {"headline": headline, "dsr": None, "n_trials": len(configs), "sharpe": {}}
    var = sr_variance_across_configs(list(configs.values()))
    dsr = deflated_sharpe_ratio(configs[headline], n_trials=max(2, len(configs)), sr_variance=var)
    return {
        "headline": headline,
        "n_trials": len(configs),
        "dsr": None if (dsr is None or math.isnan(dsr)) else float(dsr),
        "sharpe": {k: float(sharpe_ratio(v)) for k, v in configs.items()},
    }


# ---------------------------------------------------------------- flags


def _find(
    buckets: Sequence[Dict],
    dimension: str,
    bucket: str,
    *,
    segment: str = "fbs_only",
    proxy: str = "step",
    selection: str = "all",
) -> Optional[Dict]:
    for b in buckets:
        if (
            b.get("dimension") == dimension
            and b.get("bucket") == bucket
            and b.get("selection") == selection
            and b.get("segment") == segment
            and b.get("proxy_kind") == proxy
        ):
            return b
    return None


def _pct(b: Optional[Dict]) -> Optional[float]:
    return None if b is None else b.get("under_pct")


def _fmt_pct(v: Optional[float]) -> str:
    return "—" if v is None else f"{100 * v:.1f}%"


def _flag(code: str, severity: str, text: str, **evidence: Any) -> Dict:
    return {"code": code, "severity": severity, "text": text, "evidence": evidence}


def derive_flags(buckets: Sequence[Dict], contrasts: Sequence[Dict], n_tests: int) -> List[Dict]:
    """Testable statements about the scoring system, judged on the buckets.
    Severity: change (evidence says act), watch (suggestive), ok (holds up)."""
    flags: List[Dict] = []
    seg, prx = "fbs_only", "step"
    # fall back to whatever segment/proxy exists if the primary is absent
    if not any(b.get("segment") == seg and b.get("proxy_kind") == prx for b in buckets):
        for b in buckets:
            if b.get("dimension") == "gap_band":
                seg, prx = b.get("segment"), b.get("proxy_kind")
                break

    s60, s47 = (
        _find(buckets, "score_band", "60+", segment=seg, proxy=prx),
        _find(buckets, "score_band", "<47", segment=seg, proxy=prx),
    )
    if s60 and s47 and _pct(s60) is not None and _pct(s47) is not None:
        if _pct(s60) <= _pct(s47) + 0.01:
            flags.append(
                _flag(
                    "score_gate",
                    "change",
                    f"The old classifier score does not separate outcomes ({_fmt_pct(_pct(s60))} at 60+ vs {_fmt_pct(_pct(s47))} below 47). It is no longer shown on the site.",
                    score60=_pct(s60),
                    n60=s60["n"],
                    score_lt47=_pct(s47),
                    n47=s47["n"],
                )
            )
        else:
            flags.append(
                _flag(
                    "score_gate",
                    "ok",
                    f"The old classifier score at 60+ hits {_fmt_pct(_pct(s60))} vs {_fmt_pct(_pct(s47))} below 47.",
                    score60=_pct(s60),
                    n60=s60["n"],
                    score_lt47=_pct(s47),
                    n47=s47["n"],
                )
            )

    g175, g3, gneg, gdip = (
        _find(buckets, "gap_band", lbl, segment=seg, proxy=prx)
        for lbl in ("1.75–3", "3+", "<0", "1–1.75")
    )
    if g175 and gneg and _pct(g175) is not None and _pct(gneg) is not None:
        lo175 = g175.get("ci_lo") or 0.0
        lo3 = (g3.get("ci_lo") if g3 else None) or 0.0
        discriminates = (
            _pct(g175) > _pct(gneg)
            and lo175 > 0.45
            and (g3 is None or (_pct(g3) or 0) > _pct(gneg))
            and lo3 > 0.45
            if g3
            else _pct(g175) > _pct(gneg)
        )
        head = _find(buckets, "all", "all", segment=seg, proxy=prx, selection="cap5") or _find(
            buckets, "all", "all", segment=seg, proxy=prx, selection="gap175"
        )
        beats = head is not None and _pct(head) is not None and _pct(head) >= BREAKEVEN
        text = (
            f"Gap discriminates ({_fmt_pct(_pct(g175))} at {BET_GAP_PTS:g}–{STRONG_GAP_PTS:g}, {_fmt_pct(_pct(g3))} at {STRONG_GAP_PTS:g}+, vs {_fmt_pct(_pct(gneg))} below 0); keep the {BET_GAP_PTS:g} gap bar as a ranking rule."
            if discriminates
            else f"Gap bands do not separate cleanly ({_fmt_pct(_pct(g175))} at {BET_GAP_PTS:g}–{STRONG_GAP_PTS:g} vs {_fmt_pct(_pct(gneg))} below 0)."
        )
        if head is not None:
            text += (
                f" Followed-the-system hit rate against the estimated line is {_fmt_pct(_pct(head))} (n {head['n']}), "
                + (
                    "at or above breakeven."
                    if beats
                    else "below the 52.4% breakeven: no ROI edge against a fair proxy; the flat-0.52 result is an artefact."
                )
            )
        flags.append(
            _flag(
                "gap_gate",
                "ok" if (discriminates and beats) else "watch",
                text,
                gap175=_pct(g175),
                n175=g175["n"],
                gap3=_pct(g3) if g3 else None,
                gap_neg=_pct(gneg),
                headline=_pct(head) if head else None,
                headline_n=head["n"] if head else None,
            )
        )
    if gdip and g175 and _pct(gdip) is not None and _pct(g175) is not None:
        diff = _pct(g175) - _pct(gdip)
        se = math.sqrt(
            _pct(g175) * (1 - _pct(g175)) / max(1, g175["unders"] + g175["overs"])
            + _pct(gdip) * (1 - _pct(gdip)) / max(1, gdip["unders"] + gdip["overs"])
        )
        flags.append(
            _flag(
                "gap_dip",
                "watch" if diff > 2 * se else "ok",
                f"{WATCH_GAP_PTS:g}–{BET_GAP_PTS:g} band hits {_fmt_pct(_pct(gdip))} vs {_fmt_pct(_pct(g175))} at {BET_GAP_PTS:g}–{STRONG_GAP_PTS:g} (difference {100 * diff:+.1f} pts, about {diff / se if se else 0:.1f} SE). "
                + (
                    "A real step at the cut would be unusual; treat as noise until real lines say otherwise."
                    if diff > 2 * se
                    else f"Within noise: {BET_GAP_PTS:g} is a ranking convenience, not where an edge starts."
                ),
                dip=_pct(gdip),
                n_dip=gdip["n"],
                gap175=_pct(g175),
            )
        )
    if g3 and g175 and _pct(g3) is not None and _pct(g175) is not None:
        flags.append(
            _flag(
                "strong_label",
                "ok" if _pct(g3) <= _pct(g175) + 0.02 else "watch",
                f"Gap {STRONG_GAP_PTS:g}+ hits {_fmt_pct(_pct(g3))} vs {_fmt_pct(_pct(g175))} for {BET_GAP_PTS:g}–{STRONG_GAP_PTS:g}: "
                + (
                    "no extra hit rate; keep 3.0 as a sort label only."
                    if _pct(g3) <= _pct(g175) + 0.02
                    else "some extra hit rate; worth re-checking on real lines."
                ),
                gap3=_pct(g3),
                n3=g3["n"],
                gap175=_pct(g175),
            )
        )

    fbs_b, non_b = (
        _find(buckets, "division", "fbs", segment="all", proxy=prx),
        _find(buckets, "division", "non_fbs", segment="all", proxy=prx),
    )
    if fbs_b and non_b and _pct(fbs_b) is not None and _pct(non_b) is not None:
        d = _pct(non_b) - _pct(fbs_b)
        flags.append(
            _flag(
                "division",
                "ok",
                f"Non-FBS games hit {_fmt_pct(_pct(non_b))} vs {_fmt_pct(_pct(fbs_b))} FBS-vs-FBS ({100 * d:+.1f} pts). "
                + (
                    "Confirms keeping the engine FBS-only."
                    if abs(d) > 0.03
                    else "Little difference under the fair proxy."
                ),
                fbs=_pct(fbs_b),
                non_fbs=_pct(non_b),
            )
        )

    early, late = (
        _find(buckets, "week_band", "3–6", segment=seg, proxy=prx),
        _find(buckets, "week_band", "7–10", segment=seg, proxy=prx),
    )
    if early and late and _pct(early) is not None and _pct(late) is not None and early["n"] >= 100:
        d = _pct(late) - _pct(early)
        flags.append(
            _flag(
                "early_season",
                "watch" if d > 0.03 else "ok",
                f"Weeks 3–6 hit {_fmt_pct(_pct(early))} vs {_fmt_pct(_pct(late))} in weeks 7–10. "
                + (
                    "Early-season gaps look weaker; consider discounting them or raising the games-played minimum."
                    if d > 0.03
                    else "No early-season penalty needed."
                ),
                early=_pct(early),
                n_early=early["n"],
                late=_pct(late),
            )
        )

    for c in contrasts:
        q, d = c.get("q_value"), c.get("effect")
        if q is None or d is None:
            continue
        if q < 0.10 and abs(d) >= 0.2 and c.get("unders", 0) >= 30 and c.get("overs", 0) >= 30:
            flags.append(
                _flag(
                    f"contrast_{c['bucket']}",
                    "watch",
                    f"Wins and losses differ on {c['bucket']}: wins average {c['stat_win']:.2f}, losses {c['stat_loss']:.2f} (d={d:+.2f}, q={q:.2f}, n {c['unders']}/{c['overs']}). A hypothesis to test on real 2026 lines, not a rule.",
                    feature=c["bucket"],
                    effect=d,
                    q=q,
                    n_win=c["unders"],
                    n_loss=c["overs"],
                    segment=c.get("segment"),
                    proxy=c.get("proxy_kind"),
                    selection=c.get("selection"),
                )
            )

    hi_hr = next(
        (
            b
            for b in buckets
            if b.get("dimension") == "hr_vs_market"
            and b.get("bucket") == "HR higher"
            and b.get("proxy_kind") == "hr"
        ),
        None,
    )
    hi_cl = next(
        (
            b
            for b in buckets
            if b.get("dimension") == "hr_vs_market"
            and b.get("bucket") == "HR higher"
            and b.get("proxy_kind") == "market_close"
        ),
        None,
    )
    if hi_hr and hi_cl and hi_hr.get("n"):
        flags.append(
            _flag(
                "hr_off_market",
                "watch",
                f"When Hard Rock sits above the market, the under at its number went {hi_hr['unders']}-{hi_hr['overs']} vs {hi_cl['unders']}-{hi_cl['overs']} at the consensus close (n {hi_hr['n']}). Counts only; too few games for a rate.",
                n=hi_hr["n"],
                hr_unders=hi_hr["unders"],
                close_unders=hi_cl["unders"],
            )
        )
    flags.append(
        _flag(
            "multiple_comparisons",
            "ok",
            f"{n_tests} comparisons were run, so about {max(1, round(0.05 * n_tests))} would look meaningful by luck alone. Only differences that clear that bar by a wide margin are flagged.",
            n_tests=n_tests,
        )
    )
    return flags


# ---------------------------------------------------------------- report


def _ci_text(b: Dict) -> str:
    if b.get("ci_lo") is None:
        return "—"
    return f"{100 * b['ci_lo']:.1f}–{100 * b['ci_hi']:.1f}%"


def _row(b: Dict, label: Optional[str] = None) -> str:
    units = b.get("units") or 0.0
    roi = "—" if b.get("roi") is None else f"{100 * b['roi']:+.1f}%"
    pb = "—" if b.get("p_beat") is None else f"{b['p_beat']:.2f}"
    return (
        f"| {label or b.get('bucket')} | {b.get('n', 0)} | {b.get('unders', 0)}-{b.get('overs', 0)}"
        f"{('-' + str(b['pushes']) + 'P') if b.get('pushes') else ''} | {_fmt_pct(b.get('under_pct'))} | {_ci_text(b)} | {pb} | {units:+.1f} | {roi} |"
    )


_HEAD = "| Bucket | n | W-L(-P) | Under % | 95% CI | P(>52.4%) | Units | ROI |\n|---|---|---|---|---|---|---|---|"

RULE_LABEL = {
    "cap5": "Followed the system (≤5/wk by gap, gap ≥ 1.75)",
    "gap175": "Every gap ≥ 1.75",
    "gap300": "Every gap ≥ 3.0 (strong)",
    "top20": "Top 20% by gap, per season",
    "score53": "Every score ≥ 53",
    "both": "Gap ≥ 1.75 and score ≥ 53",
    "all": "Every rated game (blanket under)",
    "bet": "Card BET tier",
    "price_read": "Price read (Hard Rock pays ≥ fair)",
    "all_hr": "Every Hard Rock number (blanket under)",
    "qualifying": "Qualifying (Hard Rock gap ≥ 1.75, any gate — the paper ledger)",
}


# What each grading column's line actually is. Mirrors web/lib/postmortem.ts
# PROXY_LABEL; keep the two in sync. 'real' is NOT a Hard Rock number.
PROXY_LABEL = {
    "real": "us-region consensus close (no Hard Rock), ~30 min pre-kick",
    "fg": "full-game under at the us-region consensus full-game close",
    "step": "fair line",
    "flat": "old 0.52 line",
    "hr": "Hard Rock's number",
    "hr_close": "Hard Rock's pre-kick close",
    "market": "consensus at build",
    "market_close": "consensus close",
}


def _proxy_text(prx: str) -> str:
    label = PROXY_LABEL.get(prx)
    return f"{prx} · {label}" if label else prx


def _select(buckets: Sequence[Dict], **kw: Any) -> List[Dict]:
    out = [b for b in buckets if all(b.get(k) == v for k, v in kw.items())]
    return sorted(out, key=lambda b: (b.get("bucket_order", 0), str(b.get("bucket"))))


def render_markdown(
    runs: Sequence[Dict], buckets: Sequence[Dict], contrasts: Sequence[Dict]
) -> str:
    """The report body scripts/post_mortem.py writes to docs/POST_MORTEM.md."""
    lines: List[str] = ["# Beat Vegas Post-mortem: rated games vs outcomes", ""]
    lines.append(
        "Generated by `scripts/post_mortem.py`. Pushes are excluded from the hit rate and count as "
        "staked. Every percentage carries its n and a 95% Wilson interval; P(>52.4%) is the factor "
        "ledger's Beta posterior against the -110 breakeven. Separating a 55% bettor from breakeven "
        "takes about 2,300 bets, so these tables rule out large edges and find large mistakes, nothing finer."
    )
    lines.append("")
    for run in runs:
        scope = run.get("scope", "?")
        notes = run.get("notes") or {}
        lines.append(
            f"## Scope `{scope}` (computed {run.get('computed_at')}, {run.get('n_games', 0)} graded games)"
        )
        lines.append("")
        for cav in notes.get("caveats", []) or []:
            lines.append(f"- {cav}")
        if notes.get("caveats"):
            lines.append("")
        scope_b = [b for b in buckets if b.get("scope") == scope]
        if not scope_b:
            lines.append("_No graded games yet._")
            lines.append("")
            continue
        segments = sorted({b["segment"] for b in scope_b})
        proxies = sorted({b["proxy_kind"] for b in scope_b})
        lines.append("### Headline records")
        lines.append("")
        lines.append(
            "| Rule | Population | Graded at | n | W-L(-P) | Under % | 95% CI | P(>52.4%) | Units | ROI |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        for seg in segments:
            for prx in proxies:
                for b in _select(scope_b, segment=seg, proxy_kind=prx, dimension="all"):
                    r = _row(b, RULE_LABEL.get(b["selection"], b["selection"]))
                    lines.append(
                        r.replace(
                            f"| {RULE_LABEL.get(b['selection'], b['selection'])} |",
                            f"| {RULE_LABEL.get(b['selection'], b['selection'])} | {seg} | {_proxy_text(prx)} |",
                            1,
                        )
                    )
        lines.append("")
        for dim, title in (
            ("gap_band", "By gap band"),
            ("score_band", "By under_score band"),
            ("season", "By season"),
            ("week_band", "By week of season"),
            ("spread_band", "By spread"),
            ("total_band", "By full-game total"),
            ("pace_band", "By pace (sec/play)"),
            ("wind_band", "By wind"),
            ("division", "By division"),
            ("neutral", "Neutral site"),
            ("kick_window", "By kickoff window"),
            ("line_frac", "Line on a whole vs half number"),
            ("key_dist", "Distance of the line to 24/28/31"),
            ("hook_side", "Hook side vs key numbers"),
            ("off_ppa_q", "Combined offensive PPA (quartiles)"),
            ("def_ppa_q", "Combined defensive PPA (quartiles)"),
            ("fh_pf_q", "Prior-season 1H points for, both teams (quartiles)"),
            ("hr_vs_market", "Hard Rock vs consensus"),
            ("tier", "Card tier"),
            ("blocker", "Gate that blocked a real bet (paper ledger)"),
            ("ev_band", "Price read"),
            ("line_stress", "Line stress test (shift the grading line)"),
            ("resid_by_gap", "Model residual (actual − our line) by gap band"),
        ):
            rows_any = [b for b in scope_b if b.get("dimension") == dim]
            if not rows_any:
                continue
            lines.append(f"### {title}")
            lines.append("")
            for seg in segments:
                for prx in proxies:
                    sels = sorted(
                        {
                            b["selection"]
                            for b in rows_any
                            if b["segment"] == seg and b["proxy_kind"] == prx
                        }
                    )
                    for sel in sels:
                        rows = _select(rows_any, segment=seg, proxy_kind=prx, selection=sel)
                        if not rows:
                            continue
                        lines.append(
                            f"**{RULE_LABEL.get(sel, sel)} · {seg} · graded at {_proxy_text(prx)}**"
                        )
                        lines.append("")
                        if dim == "resid_by_gap":
                            lines.append(
                                "| Gap band | n | Mean residual (pts) | SE |\n|---|---|---|---|"
                            )
                            for b in rows:
                                se_txt = (
                                    "—" if b.get("stat_loss") is None else f"{b['stat_loss']:.2f}"
                                )
                                lines.append(
                                    f"| {b['bucket']} | {b['n']} | {b['stat_win']:+.2f} | {se_txt} |"
                                )
                        else:
                            lines.append(_HEAD)
                            for b in rows:
                                lines.append(_row(b))
                        lines.append("")
        scope_c = [c for c in contrasts if c.get("scope") == scope]
        if scope_c:
            lines.append("### Wins vs losses (hypothetical bets)")
            lines.append("")
            keys = sorted({(c["segment"], c["proxy_kind"], c["selection"]) for c in scope_c})
            for seg, prx, sel in keys:
                rows = sorted(
                    [
                        c
                        for c in scope_c
                        if (c["segment"], c["proxy_kind"], c["selection"]) == (seg, prx, sel)
                    ],
                    key=lambda c: -abs(c.get("effect") or 0),
                )
                big = max(rows, key=lambda c: c.get("n", 0))
                lines.append(
                    f"**{RULE_LABEL.get(sel, sel)} · {seg} · graded at {prx}** (up to {big['unders']} wins, {big['overs']} losses; n varies by feature coverage)"
                )
                lines.append("")
                lines.append(
                    "| Feature | n W/L | Wins mean | Losses mean | Wins median | Losses median | d | p | q | Read |\n|---|---|---|---|---|---|---|---|---|---|"
                )
                for c in rows:
                    q = c.get("q_value")
                    read = (
                        ("wins higher" if c["effect"] > 0 else "losses higher")
                        if (q is not None and q < 0.10 and abs(c["effect"]) >= 0.2)
                        else "noise"
                    )
                    lines.append(
                        f"| {c['bucket']} | {c['unders']}/{c['overs']} | {c['stat_win']:.2f} | {c['stat_loss']:.2f} | {c.get('med_win', float('nan')):.2f} | {c.get('med_loss', float('nan')):.2f} | {c['effect']:+.2f} | {c['p_value']:.3f} | {'—' if q is None else f'{q:.2f}'} | {read} |"
                    )
                lines.append("")
        flags = notes.get("flags") or []
        if flags:
            lines.append("### What to change")
            lines.append("")
            for f in flags:
                lines.append(f"- **{f['severity'].upper()} · {f['code']}** — {f['text']}")
            lines.append("")
        extra = notes.get("logit")
        if extra:
            lines.append("### Does the gap survive spread and total controls?")
            lines.append("")
            for k, v in extra.items():
                coefs = ", ".join(f"{c} {b:+.2f}" for c, b in v["coef"].items()) if v else "n/a"
                lines.append(
                    f"- {k}: standardized logistic coefficients ({v['n'] if v else 0} games): {coefs}"
                )
            lines.append("")
        of = notes.get("overfit")
        if of:
            lines.append("### Overfitting control")
            lines.append("")
            dsr = of.get("dsr")
            lines.append(
                f"- Deflated Sharpe of `{of.get('headline')}` against {of.get('n_trials')} tried configurations: "
                f"{'n/a' if dsr is None else f'{dsr:.2f}'} (≥ 0.95 would be significant)."
            )
            lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------- orchestrators


def _clean(v: Any) -> Any:
    """JSON/DB-safe scalar: NaN -> None, numpy -> python."""
    if v is None:
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        f = float(v)
        return None if math.isnan(f) else f
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    return v


def _game_rows(
    df: pd.DataFrame, *, run_id: str, scope: str, followed: pd.Series, rules: Dict[str, pd.Series]
) -> List[Dict]:
    rows: List[Dict] = []
    for idx, rec in df.iterrows():
        r = {k: _clean(v) for k, v in rec.items()}
        if r.get("week") is not None:
            r["week"] = int(r["week"])
        if r.get("season") is not None:
            r["season"] = int(float(r["season"]))
        r["run_id"] = run_id
        r["scope"] = scope
        r["followed_system"] = bool(followed.get(idx, False))
        r["rules_json"] = json.dumps({k: bool(m.get(idx, False)) for k, m in rules.items()})
        rows.append(r)
    return rows


def compute_hist(
    df: pd.DataFrame,
    *,
    run_id: str,
    computed_at: str,
    cap: int = WEEKLY_CAP,
    scope: str = HIST_SCOPE,
    proxies: Sequence[str] = ("flat", "step"),
    segments: Sequence[str] = ("fbs_only", "all"),
) -> Dict[str, Any]:
    """Everything the historical scope writes: buckets, contrasts, notes, games.
    A 'real' grading column (captured pre-kickoff 1H closes) is added whenever
    any row carries one; only those rows are graded in it."""
    n_real = int(df["line_real"].notna().sum()) if "line_real" in df else 0
    if n_real and "real" not in proxies:
        proxies = tuple(proxies) + ("real",)
    n_fg = int(df["outcome_fg"].notna().sum()) if "outcome_fg" in df else 0
    if n_fg and "fg" not in proxies:
        proxies = tuple(proxies) + ("fg",)
    buckets: List[Dict] = []
    contrasts: List[Dict] = []
    returns_by_config: Dict[str, List[float]] = {}
    logit: Dict[str, Any] = {}
    all_rules: Dict[str, pd.Series] = {}
    followed = pd.Series(False, index=df.index)
    for seg in segments:
        sub = df if seg == "all" else df[df["division"] == "fbs"]
        if sub.empty:
            continue
        for prx in proxies:
            ocol, ucol, lcol, gcol = f"outcome_{prx}", f"units_{prx}", f"line_{prx}", f"gap_{prx}"
            if ocol not in sub or sub[ocol].isna().all():
                continue
            d = assign_dimensions(sub, prx)
            masks = rule_masks(d, prx)
            masks["cap5"] = weekly_cap(d, gcol, cap=cap)
            ids = {
                "run_id": run_id,
                "computed_at": computed_at,
                "scope": scope,
                "segment": seg,
                "proxy_kind": prx,
            }
            buckets += bucket_rows(
                d,
                selection_masks=masks,
                outcome_col=ocol,
                units_col=ucol,
                dimensions=HIST_DIMENSIONS,
                proxy=prx,
                run_id=run_id,
                computed_at=computed_at,
                scope=scope,
                segment=seg,
            )
            actual_col = "pts" if prx == "fg" else "fh"
            for sel in ("cap5", "gap175"):
                buckets += stress_rows(
                    d, masks[sel], lcol, actual_col=actual_col, selection=sel, **ids
                )
                contrasts += contrast_rows(d, masks[sel], ocol, selection=sel, **ids)
            if prx != "fg":  # the residual check is a 1H-model check; the fg column shares it
                buckets += residual_by_band(d, prx, selection="all", **ids)
            for sel, m in masks.items():
                if sel == "all":
                    continue
                returns_by_config[f"{sel}/{prx}/{seg}"] = (
                    pd.to_numeric(d.loc[m, ucol], errors="coerce").dropna().tolist()
                )
            logit[f"{prx}/{seg}"] = gap_logit(d, masks["all"], prx)
            if seg == "all":
                for sel, m in masks.items():
                    all_rules[f"{sel}_{prx}"] = m
            if seg == "fbs_only" and prx == "step":
                followed = masks["cap5"].reindex(df.index, fill_value=False).astype(bool)
    n_tests = len(contrasts)
    flags = derive_flags(buckets, contrasts, n_tests)
    notes = {
        "flags": flags,
        "dropped": dict(df.attrs.get("dropped", {}) or {}),
        "n_tests": n_tests,
        "real_lines": {"n": n_real, "share": (n_real / len(df)) if len(df) else None},
        "fg_lines": {"n": n_fg, "share": (n_fg / len(df)) if len(df) else None},
        "logit": logit,
        "overfit": overfit_summary(returns_by_config, headline="cap5/step/fbs_only"),
        "caveats": [
            "Ratings are the stored walk-forward gbm_v1 rows (2023-25); every line is a proxy, not a real 1H market.",
            "'flat' grades at the 0.52 x full-game line the ratings were built on; 'step' grades at the fair spread-aware "
            "line (0.4975 / 0.5375 at spread 21+). The step column is the honest one.",
            "No Hard Rock prices existed historically, so the price, off-market and QB gates cannot be applied; "
            "'followed the system' is the gap gate plus the weekly cap of 5.",
            "About 2,300 bets separate a 55% bettor from breakeven at 80% power; this data cannot confirm a realistic edge.",
        ]
        + (
            [
                f"'real' grades at the us-region consensus first-half close (no Hard Rock: it did "
                f"not exist historically), captured once about 30 minutes before kickoff from The Odds "
                f"API history; {n_real} of {len(df)} rated games have one. Only those games appear in "
                f"the real column."
            ]
            if n_real
            else []
        )
        + (
            [
                f"'fg' grades the SAME picks (selected on the real 1H gap) as FULL-GAME unders at the captured "
                f"pre-kick full-game consensus close; {n_fg} of {len(df)} rated games have one."
            ]
            if n_fg
            else []
        ),
    }
    games = _game_rows(df, run_id=run_id, scope=scope, followed=followed, rules=all_rules)
    return {
        "scope": scope,
        "buckets": buckets,
        "contrasts": contrasts,
        "notes": notes,
        "games": games,
    }


def _mae(a: pd.Series, b: pd.Series) -> Optional[float]:
    d = (pd.to_numeric(a, errors="coerce") - pd.to_numeric(b, errors="coerce")).dropna()
    return float(d.abs().mean()) if len(d) else None


def compute_live(df: pd.DataFrame, *, season: int, run_id: str, computed_at: str) -> Dict[str, Any]:
    """Everything the live scope writes. Grades at Hard Rock's number ('hr'),
    the consensus at build time ('market') and the consensus close ('market_close')."""
    scope = f"live_{season}"
    d = assign_dimensions(df, "hr")
    masks = live_rule_masks(d)
    buckets: List[Dict] = []
    for kind, ocol, ucol in (
        ("hr", "outcome_hr", "units_hr"),
        ("hr_close", "outcome_hr_close", "units_hr_close"),
        ("market", "outcome_market", "units_market"),
        ("market_close", "outcome_close", "units_close"),
    ):
        if ocol not in d:
            continue
        buckets += bucket_rows(
            d,
            selection_masks=masks,
            outcome_col=ocol,
            units_col=ucol,
            dimensions=LIVE_DIMENSIONS,
            proxy=kind,
            run_id=run_id,
            computed_at=computed_at,
            scope=scope,
            segment="live",
        )
    graded = d[d["fh"].notna()] if "fh" in d else d.iloc[0:0]
    der = graded[graded["derived_line"].notna()] if "derived_line" in graded else graded.iloc[0:0]
    tot = (
        pd.to_numeric(graded["full_game_total"], errors="coerce")
        if "full_game_total" in graded
        else pd.Series(dtype=float)
    )
    fh = pd.to_numeric(graded["fh"], errors="coerce") if "fh" in graded else pd.Series(dtype=float)
    ok = tot.notna() & fh.notna() & (tot > 0)
    derived_note = {
        "n": int(len(der)),
        "mae": _mae(der["derived_line"], der["fh"]) if len(der) else None,
        "bias": float(
            (
                pd.to_numeric(der["fh"], errors="coerce")
                - pd.to_numeric(der["derived_line"], errors="coerce")
            ).mean()
        )
        if len(der)
        else None,
        "hr_mae": _mae(graded["hr_line"], graded["fh"]) if len(graded) else None,
        "market_mae": _mae(graded["market_line"], graded["fh"]) if len(graded) else None,
        "share": float(fh[ok].sum() / tot[ok].sum()) if ok.any() else None,
        "n_share": int(ok.sum()),
    }
    price_counts: Dict[str, Dict[str, int]] = {}
    if "ev_band" in graded and "outcome_hr" in graded:
        for band, grp in graded[graded["ev_band"].notna()].groupby("ev_band"):
            price_counts[str(band)] = {
                k: int((grp["outcome_hr"] == k).sum()) for k in ("under", "over", "push")
            }
    flags = derive_flags(buckets, [], 0)
    notes = {
        "flags": flags,
        "n_items": int(len(d)),
        "n_graded": int(len(graded)),
        "n_bets": int(masks["bet"].sum()),
        "n_price_reads": int(masks["price_read"].sum()),
        "derived_line": derived_note,
        "price_read_counts": price_counts,
        "landing": sorted(int(v) for v in fh.dropna().tolist()) if len(fh) else [],
        "n_qualifying": int(masks["qualifying"].sum()),
        "caveats": (
            [
                f"The {season} system has placed zero model bets so far (no model read in weeks 1-2 by design)."
            ]
            if int(masks["bet"].sum()) == 0
            else []
        )
        + [
            "'hr' grades the under at Hard Rock's own number and price when the card was built, "
            "'hr_close' at Hard Rock's own pre-kick close, 'market' at the consensus number at "
            "build time, 'market_close' at the consensus close.",
            "'Qualifying' is the paper ledger: every game whose Hard Rock 1H line sat >= 1.75 "
            "above ours, tagged by the gate that blocked a real bet (the 'blocker' dimension).",
            "Counts, not rates, until a bucket has 30 graded games.",
        ],
    }
    followed = masks["bet"].reindex(df.index, fill_value=False).astype(bool)
    games = _game_rows(df, run_id=run_id, scope=scope, followed=followed, rules=masks)
    return {"scope": scope, "buckets": buckets, "contrasts": [], "notes": notes, "games": games}
