"""Tests for PBP normalization (cfbpbp) and 1H aggregation (fh_factors)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from beatvegas.etl.fh_factors import FH_METRICS, aggregate_fh
from beatvegas.sources.cfbpbp import NORM_COLS, normalize_cfbd


def test_normalize_cfbd_basic():
    plays = [
        {"gameId": 1, "period": 1, "offense": "A", "home": "A", "ppa": 0.5,
         "yardsGained": 12, "down": 1, "distance": 10, "playType": "Rush",
         "scoring": False, "driveId": "d1", "playNumber": 1},
        {"gameId": 1, "period": 1, "offense": "B", "home": "A", "ppa": -0.3,
         "yardsGained": 20, "down": 2, "distance": 7, "playType": "Pass Reception",
         "scoring": True, "driveId": "d2", "playNumber": 2},
        {"gameId": 1, "period": 3, "offense": "A", "home": "A", "ppa": 0.1,
         "yardsGained": 3, "down": 1, "distance": 10, "playType": "Kickoff",
         "scoring": False, "driveId": "d3", "playNumber": 3},
    ]
    n = normalize_cfbd(plays)
    assert set(NORM_COLS).issubset(n.columns)
    assert list(n["is_home_off"]) == [1.0, 0.0, 1.0]      # offense == home
    assert list(n["is_pass"]) == [0.0, 1.0, 0.0]          # Rush, Pass, Kickoff
    assert list(n["_is_scrim"]) == [1.0, 1.0, 0.0]        # kickoff not scrimmage


def _synthetic_plays() -> pd.DataFrame:
    """One game, home offense: 3 scrimmage plays in one opening drive, no score."""
    rows = [
        # game,per,home_off,epa,yds,down,dist,pass,score,to,havoc,yte,td,spec,drive,order
        (1000, 1, 1, 1.0, 10, 1, 10, 0, 0, 0, 0, 80, 0, 0, "A", 1),
        (1000, 1, 1, -1.0, 0, 2, 10, 1, 0, 0, 1, 70, 0, 0, "A", 2),
        (1000, 1, 1, 2.0, 16, 3, 5, 1, 0, 0, 0, 70, 0, 0, "A", 3),
        # away offense, scored a TD on opening drive (reached red zone)
        (1000, 1, 0, 0.5, 8, 1, 10, 1, 1, 0, 0, 15, 1, 0, "B", 4),
        # a 2nd-half play that must be ignored (period 3)
        (1000, 3, 1, 5.0, 50, 1, 10, 0, 1, 0, 0, 50, 0, 0, "C", 9),
    ]
    cols = ["game_id", "period", "is_home_off", "epa", "yards", "down", "distance",
            "is_pass", "scoring", "is_to", "is_havoc", "yte", "is_td", "is_special",
            "drive_key", "play_order"]
    df = pd.DataFrame(rows, columns=cols)
    df["_is_scrim"] = 1.0
    return df


def test_aggregate_fh_metrics():
    agg = aggregate_fh(_synthetic_plays())
    assert len(agg) == 2                                  # home + away offense
    home = agg[agg["is_home_off"] == 1].iloc[0]
    assert home["n_plays"] == 3                           # period-3 play excluded
    assert round(home["success"], 3) == round(2 / 3, 3)   # epa>0 on 2 of 3
    assert round(home["explosive"], 3) == round(1 / 3, 3)  # one 16-yd play
    assert round(home["pass_rate"], 3) == round(2 / 3, 3)
    assert round(home["third_conv"], 3) == 1.0            # 16 >= 5 on 3rd
    assert home["opening_score"] == 0 and home["opening_3out"] == 1
    away = agg[agg["is_home_off"] == 0].iloc[0]
    assert away["opening_score"] == 1                     # away scored opening drive


def test_aggregate_fh_excludes_second_half():
    agg = aggregate_fh(_synthetic_plays())
    # the period-3 turnover/score must not inflate any 1H metric
    home = agg[agg["is_home_off"] == 1].iloc[0]
    assert home["turnovers"] == 0.0
    assert all(m in agg.columns for m in FH_METRICS)
