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
from ..config import engine_name
from ..db.models import Prediction
from ..db.store import init_db, session_scope
from ..etl.context import SITUATIONAL_KEYS, context_for_games, json_safe
from ..etl.features import FEATURE_COLS, build_feature_frame, training_frame
from ..etl.form import form_for_games
from ..etl.game_records import snapshot_slate
from ..etl.proxy_line import proxy_total
from ..factors.board import build_factor_board, factor_references
from ..factors.ledger import load_ledger
from .bv_line import bv_line_for_slate, residual_band
from .residual import (
    RESIDUAL_MIN_TRAIN,
    residual_1h_for_slate,
    residual_sigma,
    residual_training_frame,
)

MODEL_VERSION = "gbm_v1"  # stored tag stays gbm_v1 for ledger continuity; the engine itself is the gbm_v2 gap ranker
MODEL_BET_THRESHOLD = 53  # under_score at/above this = the model "bets" it

# Verdict gates, in POINTS of bv_gap (line - our 1H number), from the validated
# top-20%-by-gap selection rule — never in sigmas: bv_sigma (~12 pts) is the
# per-GAME outcome noise, so a 1-sigma gap never occurs. Mirrored by
# web/lib/verdict.ts; tests/test_gate_parity.py keeps the two in lock-step.
BET_GAP_PTS = 1.75  # ~ the season's top-20% gap cutoff -> BET
STRONG_GAP_PTS = 3.0  # ~ top-10% -> "high" confidence (gap alone; under_score no longer gates it)
WATCH_GAP_PTS = 1.0  # below BET but worth watching for a line move
WEEKLY_BET_CAP = 5  # docs/BETTING_POLICY.md: at most this many bets a week
# Hard Rock's 1H total more than this far BELOW the market's = off-market
# number: giving up points on an under + void risk under HR house rules. WATCH.
HR_OFF_MARKET_PTS = 0.5
# weekly_update --min-games: both teams need this many games for a model read,
# so weeks 1-2 have no model by design.
MIN_GAMES_FOR_MODEL = 2
# Worst per-$1 EV of Hard Rock's under (vs the market's no-vig fair under) still
# treated as a fair price: the unavoidable ~2 cents of vig. Below it the price
# gate fails (web/lib/edge.ts FAIR_EV_FLOOR / lineCheck.ts "neg").
EV_FLOOR = -0.05  # standard -110 juice on a balanced market passes; -115+ fails


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
    if dome == 1 or dome is True:  # NaN/None are NOT dome
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
        return f"{v * 100:.0f}%" if v is not None and not pd.isna(v) else "—"

    return f"{_p(h)}/{_p(a)}"


# Raw numeric factor inputs copied into factors_json under their feature-frame
# names, so the card can render drivers (not just the pre-formatted chips). The
# same keys come from the feature frame (model rows) or etl/context.py (derived
# rows / gaps in the frame).
CONTEXT_NUMERIC_KEYS = (
    "combined_sec_play",
    "combined_plays",
    "wx_temp",
    "wx_wind",
    "wx_precip",
    "wx_dome",
    "home_off_ppa",
    "away_off_ppa",
    "home_def_ppa",
    "away_def_ppa",
    "combined_off_ppa",
    "combined_def_ppa",
    "combined_fh_offense",
    "combined_fh_defense",
) + SITUATIONAL_KEYS
FORM_KEYS = ("form_home", "form_away", "split_home", "split_away")


def _missing(v) -> bool:
    if v is None:
        return True
    if isinstance(v, (str, bool, list, dict)):
        return False
    try:
        return bool(pd.isna(v))
    except (TypeError, ValueError):
        return False


def _merge_context(row: pd.Series, context: Optional[Dict]) -> pd.Series:
    """Fill the row's missing/NaN factor inputs from a context dict (the row's
    own values win). Returns an object-dtype Series so strings and floats mix."""
    if not context:
        return row
    merged = {k: row[k] for k in row.index}
    for k, v in context.items():
        if k not in merged or _missing(merged[k]):
            merged[k] = v
    return pd.Series(merged, dtype=object)


def _fh_prior_source(row: pd.Series) -> Optional[str]:
    src = row.get("fh_prior_source")
    if isinstance(src, str):
        return src
    # Feature-frame rows: the fh_* columns are the season-to-date expanding means.
    return "season_to_date" if not _missing(row.get("home_fh_pf")) else None


def _factors(
    row: pd.Series,
    line: float,
    refs: Optional[Dict] = None,
    ledger: Optional[Dict] = None,
    context: Optional[Dict] = None,
    form: Optional[Dict] = None,
    fingerprint: Optional[Dict] = None,
) -> Dict:
    """The per-game factors_json payload. `context` (etl/context.py) fills any
    input the row lacks; `form` (etl/form.py) adds form_*/split_* blocks;
    `fingerprint` (residual engine, score_slate attrs["engine_artifact"]) tags
    which fit produced the row's number."""
    row = _merge_context(row, context)
    proj = row.get("proj_1h_total")
    out = {
        # Green/red factor board (pure explainer; never affects rank). Empty
        # until references are available; the ledger fills each factor's `live`.
        "factor_board": build_factor_board(row, refs, ledger=ledger) if refs else [],
        "pace": _pace_str(row),
        "weather": _weather_str(row),
        "spot": _spot_str(row),
        "returning": _returning_str(row),
        "off_ppa": _f(row.get("combined_off_ppa")),
        "def_ppa": _f(row.get("combined_def_ppa")),
        "fh_home_pf": _f(row.get("home_fh_pf")),
        "fh_home_pa": _f(row.get("home_fh_pa")),
        "fh_away_pf": _f(row.get("away_fh_pf")),
        "fh_away_pa": _f(row.get("away_fh_pa")),
        "proj_1h_total": _f(proj),
        "bv_line": _f(row.get("bv_line")),
        "bv_gap": _f(row.get("bv_gap")),
        "bv_lo": _f(row.get("bv_lo")),
        "bv_hi": _f(row.get("bv_hi")),
        "bv_sigma": _f(row.get("bv_sigma")),
        "bv_gap_z": _f(row.get("bv_gap_z")),
        "qb_out_home": bool(row.get("qb_out_home")) if row.get("qb_out_home") is not None else None,
        "qb_out_away": bool(row.get("qb_out_away")) if row.get("qb_out_away") is not None else None,
        "qb_out_detail": row.get("qb_out_detail")
        if isinstance(row.get("qb_out_detail"), str)
        else None,
        "line": _f(line),
        "line_kind": (row.get("line_kind") if isinstance(row.get("line_kind"), str) else None),
        "edge": _f(line - proj) if (line is not None and proj is not None) else None,
        # primary-engine fields (gbm_v2 gap ranking). The BET/WATCH/PASS verdict
        # is derived downstream from bv_gap against the point gates above.
        "rank_basis": "bv_gap",
        # which 1H engine produced bv_line (config model.engine). Residual engine
        # only: resid_hat = predicted (actual - line), so bv_gap == -resid_hat,
        # and a compact fingerprint of the fit (None for the incumbent).
        "engine": row.get("engine") if isinstance(row.get("engine"), str) else None,
        "resid_hat": _f(row.get("resid_hat")),
        "model_fingerprint": (
            {
                "feature_hash": fingerprint.get("feature_hash"),
                "n_rows": fingerprint.get("n_rows"),
                "max_game_date": fingerprint.get("max_game_date"),
            }
            if fingerprint
            else None
        ),
        # genuine 1H-scoring signal chips (corr_1h drivers)
        "fh_off_epa_home": _f(row.get("home_fh_off_epa")),
        "fh_off_epa_away": _f(row.get("away_fh_off_epa")),
        "fh_off_success_home": _f(row.get("home_fh_off_success")),
        "fh_off_success_away": _f(row.get("away_fh_off_success")),
    }
    # Raw driver numbers under their feature names (+ dome as a bool), the
    # provenance of the 1H scoring priors, and the form/split blocks.
    out.update({k: _f(row.get(k)) for k in CONTEXT_NUMERIC_KEYS})
    dome = row.get("wx_dome")
    out["dome"] = None if _missing(dome) else bool(dome)
    out["fh_prior_source"] = _fh_prior_source(row)
    out["fh_source_home"] = (
        row.get("fh_source_home")
        if isinstance(row.get("fh_source_home"), str)
        else out["fh_prior_source"]
    )
    out["fh_source_away"] = (
        row.get("fh_source_away")
        if isinstance(row.get("fh_source_away"), str)
        else out["fh_prior_source"]
    )
    for k in FORM_KEYS:
        out[k] = (form or {}).get(k)
    return json_safe(out)


def derived_factors(
    line: float,
    full_game_total: Optional[float],
    spread: Optional[float],
    fh_share_used: Optional[float],
    context: Optional[Dict] = None,
    form: Optional[Dict] = None,
    refs: Optional[Dict] = None,
    ledger: Optional[Dict] = None,
) -> Dict:
    """factors_json for a `derived_lines` board row (no model fields): the same
    driver keys + factor board as a model row, built from context alone, plus the
    derived-line provenance (`full_game_total`, `spread`, `fh_share`)."""
    row = pd.Series(dict(context or {}), dtype=object)
    out = _factors(row, line, refs=refs, ledger=ledger, form=form)
    out.update(
        {
            "line": _f(line),
            "line_kind": "derived_fg",
            "full_game_total": _f(full_game_total),
            "spread": _f(spread),
            "fh_share": _f(fh_share_used),
            "rank_basis": "derived_line",
        }
    )
    return json_safe(out)


def slate_context(session, scored: pd.DataFrame) -> tuple:
    """(context, form) maps keyed by game id for every (season, week) in the
    scored slate. Fail-soft per group: a DB hiccup logs and leaves that week's
    cards without the extra keys rather than failing the scoring run. The
    prior-season PPA keys are skipped here — model rows already carry them."""
    ctx: Dict[int, Dict] = {}
    form: Dict[int, Dict] = {}
    if scored.empty or "season" not in scored.columns or "week" not in scored.columns:
        return ctx, form
    for (season, week), grp in scored.groupby(["season", "week"]):
        ids = [int(x) for x in grp["id"].tolist()]
        try:
            ctx.update(context_for_games(session, int(season), int(week), ids))
        except Exception as e:  # noqa: BLE001 - display-only enrichment
            print(f"[context] {int(season)} wk{int(week)}: context unavailable ({e!r})")
        try:
            form.update(form_for_games(session, int(season), int(week), ids))
        except Exception as e:  # noqa: BLE001
            print(f"[context] {int(season)} wk{int(week)}: form unavailable ({e!r})")
    return ctx, form


def _f(v):
    return None if v is None or pd.isna(v) else round(float(v), 2)


def score_slate(
    target_season: int,
    target_week: Optional[int] = None,
    game_ids: Optional[List[int]] = None,
    line_lookup: Optional[Dict[int, float]] = None,
    line_kind_lookup: Optional[Dict[int, str]] = None,
    df: Optional[pd.DataFrame] = None,
    engine: Optional[str] = None,
    real_closes: Optional[Dict[int, float]] = None,
) -> pd.DataFrame:
    """Score the target slate; DB-free (pass `df`), refits per call.

    `engine` (default: config model.engine / env BV_ENGINE) picks how `bv_line`
    is produced:
      * "bv_line"  — the incumbent MARKET-BLIND regressor: our own 1H number.
      * "residual" — the market-residual engine (model/residual.py): `bv_line`
        = the ranking line the model was GIVEN + its predicted residual, so
        `bv_gap == -resid_hat`. It trains only on prior-season games with a
        REAL pre-kick 1H close (`real_closes`, game_id -> close, from
        lines.real_closes); with fewer than RESIDUAL_MIN_TRAIN such games it
        falls back to the incumbent and says so in attrs["engine_fallback"].
    Either way bv_gap = line - bv_line and the board sorts by it.
    """
    engine = engine or engine_name()
    if engine not in ("bv_line", "residual"):
        raise ValueError(f"unknown engine {engine!r}")
    if df is None:
        df = build_feature_frame(min_games=2)
    # Train on PLAYED prior-season games only: the frame keeps unplayed rows
    # (NaN `under`) so the upcoming slate can be scored, and a NaN target must
    # never reach a fit. Target rows keep their NaN `under` — they have no
    # outcome yet; that is the point.
    train = training_frame(df[df["season"] < target_season])
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
    # The ranking line per game, with provenance: an observed retail 1H opener
    # (kind from line_kind_lookup, default 'observed_1h'); else a 1H number
    # DERIVED from the captured full-game opener (passed in via line_lookup with
    # kind 'derived_fg'); else the internal proxy off Game.full_game_total. On
    # Sunday the retail 1H market isn't posted, so derived_fg is the live signal.
    ll = line_lookup or {}
    lk = line_kind_lookup or {}
    target["line"] = target.apply(
        lambda r: ll.get(r["id"], proxy_total(r["full_game_total"], spread=r.get("spread"))), axis=1
    )
    target["line_kind"] = target["id"].map(
        lambda gid: lk.get(gid, "observed_1h" if gid in ll else "proxy")
    )

    # Our 1H number + its noise band. bv_lo/bv_hi = 80% prediction band;
    # bv_gap_z = gap in sigmas (noise-aware — a gap inside the band is noise,
    # not an edge). Display + gap sort only; does NOT influence under_score.
    target["engine"] = "bv_line"
    target["resid_hat"] = float("nan")
    band: Dict = {}
    if engine == "residual":
        train_r = residual_training_frame(train, real_closes or {})
        if len(train_r) < RESIDUAL_MIN_TRAIN:
            # Never silently: the caller/board must see the engine that ran.
            target.attrs["engine_fallback"] = "insufficient_real_closes"
        else:
            pred, model, fp = residual_1h_for_slate(train_r, target, target["line"])
            target["engine"] = "residual"
            target["bv_line"] = pd.Series(pred, index=target.index).round(2)
            target["resid_hat"] = (target["bv_line"] - target["line"]).round(2)
            band = residual_sigma(train_r)
            target.attrs["engine_artifact"] = {"model": model, "fingerprint": fp, "sigma": band}
    if "bv_line" not in target.columns:
        # Incumbent: an independent calibrated "BV line" from a MARKET-BLIND
        # regressor (no Vegas inputs).
        target["bv_line"] = bv_line_for_slate(train, target).round(2)
        band = residual_band(train)
    target["bv_gap"] = (target["line"] - target["bv_line"]).round(2)
    sigma = band.get("sigma")
    lo_off, hi_off = band.get("lo_off"), band.get("hi_off")
    target["bv_sigma"] = sigma
    target["bv_lo"] = (target["bv_line"] + lo_off).round(2) if lo_off is not None else None
    target["bv_hi"] = (target["bv_line"] + hi_off).round(2) if hi_off is not None else None
    target["bv_gap_z"] = (target["bv_gap"] / sigma).round(2) if sigma else None

    # PRIMARY ENGINE (gbm_v2, validated Phase 3): rank the board by the raw gap
    # (line ABOVE our predicted 1H total = under lean). The BET/WATCH/PASS call is
    # made downstream against the POINT gates (BET_GAP_PTS etc.), not a sigma
    # threshold. under_prob/under_score remain a secondary classifier lean.
    target = target.sort_values("bv_gap", ascending=False).reset_index(drop=True)
    target["rank"] = target.index + 1
    # Stash historical board references (median/spread per factor) on the frame
    # so store_predictions can tint the factor board against HISTORY, not the
    # current slate. Computed from the full frame (display-only, not a model input).
    target.attrs["factor_refs"] = factor_references(df)
    return target


def store_predictions(scored: pd.DataFrame, model_version: str = MODEL_VERSION) -> int:
    init_db()
    now = datetime.utcnow()
    # Board references: prefer the historical ones score_slate attached; else
    # fall back to the scored slate (noisier, but keeps direct callers working).
    refs = scored.attrs.get("factor_refs") or factor_references(scored)
    fingerprint = (scored.attrs.get("engine_artifact") or {}).get("fingerprint")
    n = 0
    with session_scope() as s:
        ledger = load_ledger(s)  # real-line track record → each card's `live` badge
        ctx, form = slate_context(s, scored)  # drivers + form for the card
        ids = [int(x) for x in scored["id"].tolist()]
        if ids:
            (
                s.query(Prediction)
                .filter(Prediction.model_version == model_version, Prediction.game_id.in_(ids))
                .delete(synchronize_session=False)
            )
        for _, r in scored.iterrows():
            line = r.get("line")
            s.add(
                Prediction(
                    game_id=int(r["id"]),
                    model_version=model_version,
                    under_probability=float(r["under_prob"]),
                    under_score=int(r["under_score"]),
                    projected_first_half_total=_f(r.get("proj_1h_total")),
                    bv_line=_f(r.get("bv_line")),
                    bv_gap=_f(r.get("bv_gap")),
                    bv_lo=_f(r.get("bv_lo")),
                    bv_hi=_f(r.get("bv_hi")),
                    bv_sigma=_f(r.get("bv_sigma")),
                    line_used=_f(line),
                    rank=int(r["rank"]),
                    factors_json=json.dumps(
                        _factors(
                            r,
                            line,
                            refs=refs,
                            ledger=ledger,
                            context=ctx.get(int(r["id"])),
                            form=form.get(int(r["id"])),
                            fingerprint=fingerprint,
                        )
                    ),
                    created_at=now,
                )
            )
            n += 1
        # Freeze immutable per-game snapshots (our own model-shaped record).
        # Idempotent per (game, model): the first pre-kickoff capture stands.
        snapshot_slate(s, scored, model_version, now)
    return n
