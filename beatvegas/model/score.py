"""Score upcoming games for first-half under value.

Walk-forward: train on all seasons before the target, predict the under
probability, and map it to an intuitive 0-100 "Under Score" where 50 = the
-110 breakeven (52.4%). Above 50 = the model leans under with positive expected
value; below 50 = lean over. Also assembles the per-game factor payload the
dashboard cards render.

Honest framing: the backtest showed only a small, unstable edge vs a proxy line,
so treat the score as the model's *relative lean*, not a guarantee.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

from ..backtest.engine import BREAKEVEN, _new_model
from ..db.models import Prediction
from ..db.store import init_db, session_scope
from ..etl.features import FEATURE_COLS, build_feature_frame
from ..etl.proxy_line import proxy_total
from .bv_line import bv_line_for_slate, residual_band

MODEL_VERSION = "gbm_v1"
MODEL_BET_THRESHOLD = 53          # under_score at/above this = the model "bets" it


def is_model_bet(under_score, threshold: int = MODEL_BET_THRESHOLD) -> bool:
    """Whether the model's score is a positive-EV under lean worth grading."""
    return under_score is not None and under_score >= threshold


def under_score(prob: float) -> int:
    """Map under probability to 0-100, anchored at breakeven=50.

    Gentle slope (x200) keeps scores in a believable band given the edge is
    small — we don't want a marginal lean reading as a near-certain '98'."""
    score = round(50 + (prob - BREAKEVEN) * 200)
    return max(1, min(99, int(score)))


def _pace_str(row: pd.Series) -> Optional[str]:
    spp = row.get("combined_sec_play")
    plays = row.get("combined_plays")
    if spp is None or pd.isna(spp):
        return None
    s = f"{spp:.1f}s/play"
    if plays is not None and not pd.isna(plays):
        s += f" · {plays:.0f} plays"
    return s


def _weather_str(row: pd.Series) -> Optional[str]:
    dome = row.get("wx_dome")
    if dome == 1 or dome is True:          # NaN/None are NOT dome
        return "Dome"
    temp, wind, precip = row.get("wx_temp"), row.get("wx_wind"), row.get("wx_precip")
    if temp is None or pd.isna(temp):
        return None
    parts = [f"{temp:.0f}°F"]
    if wind is not None and not pd.isna(wind):
        parts.append(f"wind {wind:.0f}mph")
    if precip is not None and not pd.isna(precip) and precip > 0:
        parts.append(f"{precip:.2f}in rain")
    return " · ".join(parts)


def _spot_str(row: pd.Series) -> Optional[str]:
    parts = []
    hr, ar = row.get("home_rest_days"), row.get("away_rest_days")
    if hr is not None and not pd.isna(hr) and ar is not None and not pd.isna(ar):
        parts.append(f"rest {int(hr)}/{int(ar)}")
    trav = row.get("away_travel_dist")
    if trav is not None and not pd.isna(trav):
        parts.append(f"trav {int(trav)}mi")
    hour = row.get("kickoff_local_hour")
    if hour is not None and not pd.isna(hour):
        parts.append(f"~{int(round(hour)):02d}:00 kick")
    return " · ".join(parts) if parts else None


def _returning_str(row: pd.Series) -> Optional[str]:
    h, a = row.get("home_returning_ppa"), row.get("away_returning_ppa")
    if (h is None or pd.isna(h)) and (a is None or pd.isna(a)):
        return None
    def _p(v):
        return f"{v*100:.0f}%" if v is not None and not pd.isna(v) else "—"
    return f"{_p(h)}/{_p(a)}"


def _factors(row: pd.Series, line: float) -> Dict:
    proj = row.get("proj_1h_total")
    return {
        "pace": _pace_str(row),
        "weather": _weather_str(row),
        "spot": _spot_str(row),
        "returning": _returning_str(row),
        "off_ppa": _f(row.get("combined_off_ppa")),
        "def_ppa": _f(row.get("combined_def_ppa")),
        "fh_home_pf": _f(row.get("home_fh_pf")), "fh_home_pa": _f(row.get("home_fh_pa")),
        "fh_away_pf": _f(row.get("away_fh_pf")), "fh_away_pa": _f(row.get("away_fh_pa")),
        "proj_1h_total": _f(proj),
        "bv_line": _f(row.get("bv_line")),
        "bv_gap": _f(row.get("bv_gap")),
        "bv_lo": _f(row.get("bv_lo")),
        "bv_hi": _f(row.get("bv_hi")),
        "bv_sigma": _f(row.get("bv_sigma")),
        "bv_gap_z": _f(row.get("bv_gap_z")),
        "qb_out_home": bool(row.get("qb_out_home")) if row.get("qb_out_home") is not None else None,
        "qb_out_away": bool(row.get("qb_out_away")) if row.get("qb_out_away") is not None else None,
        "qb_out_detail": row.get("qb_out_detail") if isinstance(row.get("qb_out_detail"), str) else None,
        "line": _f(line),
        "edge": _f(line - proj) if (line is not None and proj is not None) else None,
    }


def _f(v):
    return None if v is None or pd.isna(v) else round(float(v), 2)


def score_slate(target_season: int, target_week: Optional[int] = None,
                game_ids: Optional[List[int]] = None,
                line_lookup: Optional[Dict[int, float]] = None,
                df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    if df is None:
        df = build_feature_frame(min_games=2)
    train = df[df["season"] < target_season]
    target = df[df["season"] == target_season].copy()
    if target_week is not None:
        target = target[target["week"] == target_week]
    if game_ids is not None:
        target = target[target["id"].isin(game_ids)]
    if train.empty or target.empty:
        return target.assign(under_prob=[], under_score=[], line=[], rank=[])

    model = _new_model()
    model.fit(train[FEATURE_COLS], train["under"])
    target["under_prob"] = model.predict_proba(target[FEATURE_COLS])[:, 1]
    target["under_score"] = target["under_prob"].apply(under_score)
    ll = line_lookup or {}
    target["line"] = target.apply(
        lambda r: ll.get(r["id"], proxy_total(r["full_game_total"], 0.52)), axis=1)

    # Independent calibrated "BV line": our own 1H total from a MARKET-BLIND
    # regressor (no Vegas inputs). Display + gap sort only; does NOT influence
    # under_score. bv_lo/bv_hi = 80% prediction band; bv_gap_z = gap in sigmas
    # (noise-aware — a gap inside the band is noise, not an edge).
    target["bv_line"] = bv_line_for_slate(train, target).round(2)
    target["bv_gap"] = (target["line"] - target["bv_line"]).round(2)
    band = residual_band(train)
    sigma = band.get("sigma")
    lo_off, hi_off = band.get("lo_off"), band.get("hi_off")
    target["bv_sigma"] = sigma
    target["bv_lo"] = (target["bv_line"] + lo_off).round(2) if lo_off is not None else None
    target["bv_hi"] = (target["bv_line"] + hi_off).round(2) if hi_off is not None else None
    target["bv_gap_z"] = ((target["bv_gap"] / sigma).round(2)
                          if sigma else None)

    target = target.sort_values("under_prob", ascending=False).reset_index(drop=True)
    target["rank"] = target.index + 1
    return target


def store_predictions(scored: pd.DataFrame, model_version: str = MODEL_VERSION) -> int:
    init_db()
    now = datetime.utcnow()
    n = 0
    with session_scope() as s:
        ids = [int(x) for x in scored["id"].tolist()]
        if ids:
            (s.query(Prediction)
             .filter(Prediction.model_version == model_version,
                     Prediction.game_id.in_(ids)).delete(synchronize_session=False))
        for _, r in scored.iterrows():
            line = r.get("line")
            s.add(Prediction(
                game_id=int(r["id"]), model_version=model_version,
                under_probability=float(r["under_prob"]),
                under_score=int(r["under_score"]),
                projected_first_half_total=_f(r.get("proj_1h_total")),
                bv_line=_f(r.get("bv_line")), bv_gap=_f(r.get("bv_gap")),
                bv_lo=_f(r.get("bv_lo")), bv_hi=_f(r.get("bv_hi")),
                bv_sigma=_f(r.get("bv_sigma")),
                line_used=_f(line), rank=int(r["rank"]),
                factors_json=json.dumps(_factors(r, line)),
                created_at=now,
            ))
            n += 1
    return n
