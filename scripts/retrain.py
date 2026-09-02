#!/usr/bin/env python
"""Evaluate the model walk-forward and log a model_runs row (track sharpening).

The model already re-fits on all prior seasons each time it scores, so this
doesn't persist a model — it records *how well it would have done* now, so you
can watch the metrics move as seasons accumulate.

    python scripts/retrain.py
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime

from beatvegas.backtest.engine import run_backtest
from beatvegas.db.models import ModelRun
from beatvegas.db.store import init_db, session_scope
from beatvegas.etl.features import build_feature_frame, training_frame
from beatvegas.model.bv_line import residual_report
from beatvegas.model.score import MODEL_VERSION


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--first-test-season", type=int, default=2023)
    ap.add_argument("--top-frac", type=float, default=0.20)
    ap.add_argument("--notes", default="")
    args = ap.parse_args()
    init_db()

    df = training_frame(build_feature_frame(min_games=2))  # played games only
    res = run_backtest(df, first_test_season=args.first_test_season, top_frac=args.top_frac)
    seasons = sorted(df["season"].unique().tolist())
    metrics = res.summary
    # Auditable BV-line calibration: OOF mean residual overall + per segment.
    metrics["bv_residual"] = residual_report(df)

    with session_scope() as s:
        s.add(
            ModelRun(
                version=MODEL_VERSION,
                train_window=f"{seasons[0]}-{seasons[-1]}",
                test_window=metrics.get("test_seasons"),
                metrics_json=json.dumps(metrics),
                notes=args.notes,
                created_at=datetime.utcnow(),
            )
        )
    print("logged model_run:", metrics)


if __name__ == "__main__":
    main()
