#!/usr/bin/env python
"""H-MARGIN backtest (docs/HYPOTHESES.md; docs/MARGIN.md): how close the
market-blind margin regressor gets to the Vegas closing spread.

Read-only: writes no table, spends no Odds API credit. Walk-forward exactly as
the champion trains: one fit per test season on every played season before it
(2003+, `CHAMPION_TRAIN_MIN_SEASON`); test seasons 2025 and 2026 to date, games
with both final scores and a closing spread. Reports MAE, MSE, straight-up and
ATS with intervals beside Vegas, and the paired MAE difference. Entering the
Pick'em does not depend on any of it (Tate, 2026-10-07).

    PYTHONPATH=. python scripts/archive/margin_backtest.py            # on the runner: study.yml
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd

from beatvegas.db.store import try_init_db
from beatvegas.etl.features import CFBD_TOTALS_FROM, apply_min_games, build_feature_frame
from beatvegas.etl.frame_fingerprint import fingerprint, fingerprint_hash
from beatvegas.model.margin_line import (
    MARGIN_ACTUAL_COL,
    MARGIN_MODEL_VERSION,
    bv_margin_for_slate,
    margin_metrics,
    played_margin,
    vegas_margin,
)
from beatvegas.model.score import CHAMPION_TRAIN_MIN_SEASON

ROW_ID = "H-MARGIN"
REGISTRY = Path(__file__).resolve().parents[2] / "docs" / "HYPOTHESES.md"
TEST_SEASONS = (2025, 2026)


def row_registered() -> bool:
    return f"| {ROW_ID} |" in REGISTRY.read_text()


def backtest(df: pd.DataFrame, seasons=TEST_SEASONS) -> Dict:
    """{season: metrics, ..., "pooled": metrics} plus the per-game rows."""
    out: Dict = {}
    rows: List[pd.DataFrame] = []
    for s in seasons:
        train = df[df["season"] < s]
        test = played_margin(df[df["season"] == s])
        test = test[pd.to_numeric(test["spread"], errors="coerce").notna()]
        if train.empty or test.empty:
            out[str(s)] = {"n": 0}
            continue
        pred = bv_margin_for_slate(train, test, drop_all_nan=True)
        t = test[["id", "season", "week", MARGIN_ACTUAL_COL]].copy()
        t["pred"] = pred
        t["vegas"] = vegas_margin(test["spread"]).to_numpy()
        out[str(s)] = margin_metrics(t["pred"], t[MARGIN_ACTUAL_COL], t["vegas"])
        out[str(s)]["train_seasons"] = f"{int(train['season'].min())}-{int(train['season'].max())}"
        rows.append(t)
    allrows = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    out["pooled"] = (
        margin_metrics(allrows["pred"], allrows[MARGIN_ACTUAL_COL], allrows["vegas"])
        if len(allrows)
        else {"n": 0}
    )
    out["_rows"] = allrows
    return out


def _pct(w) -> str:
    return "—" if not w else f"{100 * w['pct']:.1f}% ({100 * w['lo']:.1f}–{100 * w['hi']:.1f})"


def render(res: Dict, fp: str) -> str:
    lines = [
        f"# {ROW_ID} backtest — `{MARGIN_MODEL_VERSION}` vs the Vegas closing spread",
        "",
        f"Computed {datetime.utcnow().isoformat(timespec='seconds')}Z on the runner, frame `{fp}`.",
        "Margins are home minus away; the Vegas margin is minus CFBD's closing spread.",
        "",
        "| test | n | train | model MAE | Vegas MAE | MAE diff (model − Vegas, 95%) | model MSE | Vegas MSE | model SU | Vegas SU | model ATS |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for key in [*[str(s) for s in TEST_SEASONS], "pooled"]:
        m = res.get(key) or {}
        if not m.get("n"):
            lines.append(f"| {key} | 0 | | | | | | | | | |")
            continue
        d = m["mae_diff"]
        lines.append(
            f"| {key} | {m['n']} | {m.get('train_seasons', '')} | {m['model']['mae']:.2f} | "
            f"{m['vegas']['mae']:.2f} | {d['mean']:+.2f} ({d['lo']:+.2f} to {d['hi']:+.2f}) | "
            f"{m['model']['mse']:.1f} | {m['vegas']['mse']:.1f} | {_pct(m['model']['su'])} | "
            f"{_pct(m['vegas']['su'])} | {_pct(m['model']['ats'])} |"
        )
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", default="reports")
    args = ap.parse_args(argv)
    if not row_registered():
        print(f"REFUSED: {ROW_ID} is not in docs/HYPOTHESES.md; the row comes first.")
        return 2
    if not try_init_db():
        print("[margin_backtest] DB unreachable — nothing computed.")
        return 0
    df = apply_min_games(
        build_feature_frame(
            min_games=0, min_season=CHAMPION_TRAIN_MIN_SEASON, total_required_from=CFBD_TOTALS_FROM
        ),
        0,
    )
    fp = fingerprint_hash(fingerprint(df))
    res = backtest(df)
    rows = res.pop("_rows")
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"margin_backtest_{stamp}.md").write_text(render(res, fp))
    (out / f"margin_backtest_{stamp}.json").write_text(json.dumps({"frame": fp, **res}, indent=1))
    if len(rows):
        rows.to_csv(out / f"margin_backtest_{stamp}_games.csv", index=False)
    print(render(res, fp))
    return 0


if __name__ == "__main__":
    sys.exit(main())
