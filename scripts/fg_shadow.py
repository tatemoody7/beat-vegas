#!/usr/bin/env python
"""Score the full-game shadow engine `bv_fg_v1` for one week (H-FG-P).

Registry row H-FG-P (docs/HYPOTHESES.md); design in docs/FG_MARKET.md. The
champion's regressor fitted to the FULL-GAME total (`model/fg_line.py`): same 58
market-blind inputs, same HGB, same global intercept, trained on every played
prior season exactly as the champion trains (`score.score_slate`). One
`predictions` row per target-week game with `model_version='bv_fg_v1'`, and
one `model_runs` row noted `fg shadow refit` (never `weekly refit`: health's
`sunday.model_run_recorded` keys on that note and must keep reading the
champion's).

A SHADOW: nothing that reads "the model's line" can see these rows
(`score.CHAMPION_READ_VERSIONS`, PR #293); no GameRecord is frozen; the only
reader is `beatvegas/fg_paper.py`, which logs paper full-game unders into
`challenger_picks`. Real money is first-half unders only.

Run by sunday.yml after the champion scores (continue-on-error: a failure here
never costs the champion's Sunday) and by fg_shadow.yml by hand.

    PYTHONPATH=. python scripts/fg_shadow.py --season 2026 --week 6
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import datetime
from typing import Dict, Optional

import pandas as pd

from beatvegas.db.models import ModelRun, Prediction
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.etl.features import (
    CFBD_TOTALS_FROM,
    FRAME_MIN_SEASON,
    apply_min_games,
    build_feature_frame,
    serve_skew_report,
    serve_skew_violations,
    training_frame,
)
from beatvegas.etl.frame_fingerprint import fingerprint, fingerprint_hash
from beatvegas.markets import FG_ACTUAL_COL, FULL_GAME, with_target
from beatvegas.model.bv_line import BV_FEATURE_COLS, bias_corrections
from beatvegas.model.fg_line import bv_fg_line_for_slate
from beatvegas.model.score import CHAMPION_TRAIN_MIN_SEASON
from beatvegas.season import current_season, detect_week

FG_MODEL_VERSION = "bv_fg_v1"
FG_REFIT_NOTE = "fg shadow refit"


def fg_train_target(df: pd.DataFrame, season: int, week: int):
    """(train, target) as the champion slices them (`score.score_slate`): train
    = PLAYED games of every prior season with a full-game final, target = the
    season's `week` rows (unplayed included -- that is the point)."""
    train = with_target(training_frame(df[df["season"] < season]), FULL_GAME)
    train = train[train[FG_ACTUAL_COL].notna()]
    target = df[(df["season"] == season) & (df["week"] == week)].copy()
    return train, target


def score_fg_week(df: pd.DataFrame, season: int, week: int) -> pd.DataFrame:
    """[id, bv_fg_line, bv_intercept] for the week; empty when either side is."""
    train, target = fg_train_target(df, season, week)
    if train.empty or target.empty:
        return pd.DataFrame(columns=["id", "bv_fg_line", "bv_intercept"])
    lines = bv_fg_line_for_slate(train, target, drop_all_nan=True)
    intercept = float(bias_corrections(train, FG_ACTUAL_COL, drop_all_nan=True).get("global", 0.0))
    out = target[["id", *BV_FEATURE_COLS]].copy()
    out["bv_fg_line"] = pd.Series(lines, index=target.index).round(2)
    out["bv_intercept"] = round(intercept, 6)
    out.attrs["n_train"] = int(len(train))
    return out


def _clean(v):
    """A frozen input value: float, or None for NaN/None (json refuses NaN)."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def store_fg_predictions(
    session,
    scored: pd.DataFrame,
    *,
    refit_id: Optional[int],
    frame_fingerprint: Optional[str],
    now: Optional[datetime] = None,
) -> int:
    """Delete-then-insert the week's `bv_fg_v1` rows per game (a re-score
    replaces cleanly; no other version is touched). The input vector rides in
    `factors_json["features"]` because the shadow freezes no GameRecord."""
    now = now or datetime.utcnow()
    ids = [int(x) for x in scored["id"].tolist()]
    if ids:
        (
            session.query(Prediction)
            .filter(Prediction.model_version == FG_MODEL_VERSION, Prediction.game_id.in_(ids))
            .delete(synchronize_session=False)
        )
    n = 0
    for _, r in scored.iterrows():
        session.add(
            Prediction(
                game_id=int(r["id"]),
                model_version=FG_MODEL_VERSION,
                bv_line=_clean(r["bv_fg_line"]),
                bv_intercept=_clean(r["bv_intercept"]),
                line_used=None,
                rank=None,
                refit_id=None if refit_id is None else int(refit_id),
                fingerprint=frame_fingerprint,
                factors_json=json.dumps(
                    {
                        "engine": FG_MODEL_VERSION,
                        "market": FULL_GAME.ledger_market,
                        "features": {c: _clean(r.get(c)) for c in BV_FEATURE_COLS},
                    },
                    allow_nan=False,
                ),
                created_at=now,
            )
        )
        n += 1
    return n


def record_fg_refit(
    session,
    scored: pd.DataFrame,
    df: pd.DataFrame,
    *,
    season: int,
    week: int,
    frame_fingerprint: str,
) -> int:
    """The shadow's own `model_runs` row; returns its id (stamped on every row
    as `refit_id`). Noted FG_REFIT_NOTE, never the champion's `weekly refit`."""
    seasons = sorted(int(x) for x in df.loc[df["season"] < season, "season"].dropna().unique())
    intercept = (
        None
        if scored.empty or pd.isna(scored["bv_intercept"].iloc[0])
        else float(scored["bv_intercept"].iloc[0])
    )
    metrics: Dict = {
        "kind": "fg_shadow_refit",
        "season": int(season),
        "week": int(week),
        "engine": FG_MODEL_VERSION,
        "target": FG_ACTUAL_COL,
        "n_inputs": int(len(BV_FEATURE_COLS)),
        "intercept": intercept,
        "train_rows": int(scored.attrs.get("n_train", 0) or 0),
        "scored_rows": int(len(scored)),
        "frame_fingerprint": frame_fingerprint,
        "run_id": os.environ.get("GITHUB_RUN_ID"),
    }
    row = ModelRun(
        version=FG_MODEL_VERSION,
        train_window=f"{seasons[0]}-{seasons[-1]}" if seasons else None,
        test_window=f"{season} wk{week}",
        metrics_json=json.dumps(metrics),
        notes=FG_REFIT_NOTE,
        created_at=datetime.utcnow(),
    )
    session.add(row)
    session.flush()
    return int(row.id)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--season", type=int, default=current_season())
    ap.add_argument("--week", type=int)
    args = ap.parse_args(argv)
    if not try_init_db():
        print("[fg_shadow] DB unreachable — skipped.")
        return 0
    week = args.week or detect_week(args.season)
    if week is None:
        print(f"[fg_shadow] no active week for {args.season}; pass --week.")
        return 0

    # The live frame, cut as the champion's Sunday cuts it (weekly_update.py).
    # Trains like the champion (2003+, Tate 2026-10-07); the guard judges the
    # live era only (older seasons have no pace/weather).
    df = apply_min_games(
        build_feature_frame(
            min_games=0, min_season=CHAMPION_TRAIN_MIN_SEASON, total_required_from=CFBD_TOTALS_FROM
        ),
        0,
    )
    skew = serve_skew_report(
        df[df["season"] >= FRAME_MIN_SEASON], args.season, week, BV_FEATURE_COLS
    )
    bad = serve_skew_violations(skew)
    if bad:
        print(f"ERROR: [fg_shadow] serve skew on {len(bad)} input(s): {', '.join(bad)}")
        return 1
    scored = score_fg_week(df, args.season, week)
    if scored.empty:
        print(f"[fg_shadow] {args.season} wk{week}: nothing to score.")
        return 0
    fp = fingerprint_hash(fingerprint(df))
    with session_scope() as s:
        refit_id = record_fg_refit(
            s, scored, df, season=args.season, week=week, frame_fingerprint=fp
        )
        n = store_fg_predictions(s, scored, refit_id=refit_id, frame_fingerprint=fp)
    lines = scored["bv_fg_line"]
    print(
        f"[fg_shadow] {args.season} wk{week}: {n} {FG_MODEL_VERSION} rows, refit_id={refit_id}, "
        f"train_rows={scored.attrs.get('n_train')}, intercept={scored['bv_intercept'].iloc[0]:+.3f}, "
        f"line mean {lines.mean():.2f} (min {lines.min():.1f}, max {lines.max():.1f}), frame={fp}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
