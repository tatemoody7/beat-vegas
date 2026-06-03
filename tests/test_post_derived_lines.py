"""build_prediction_rows: derived-1H rows, model fields absent, ranked low->high."""
import importlib.util
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _load(script_name: str):
    path = _ROOT / "scripts" / f"{script_name}.py"
    spec = importlib.util.spec_from_file_location(script_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_build_prediction_rows():
    build = _load("post_derived_lines").build_prediction_rows
    # CFBD-shaped rows carry game_id directly (no name matching needed).
    fetched = [
        {"game_id": 1, "line": 50.5, "spread": -10.5},   # week 1
        {"game_id": 2, "line": 59.5, "spread": -6.5},    # week 1
        {"game_id": 3, "line": 44.0, "spread": -3.0},    # week 2 (filtered out)
    ]
    gmeta = {
        1: {"week": 1, "home": "LSU", "away": "Clemson"},
        2: {"week": 1, "home": "Auburn", "away": "Baylor"},
        3: {"week": 2, "home": "X", "away": "Y"},
    }
    rows = build(fetched, gmeta, week=1)

    assert len(rows) == 2                                  # week 2 dropped
    # ranked by lowest derived 1H first
    assert rows[0]["game_id"] == 1 and rows[0]["rank"] == 1
    assert rows[1]["game_id"] == 2 and rows[1]["rank"] == 2
    assert rows[0]["line_used"] < rows[1]["line_used"]

    # NO model fields present (they default to NULL in the DB)
    for d in rows:
        for k in ("under_score", "under_probability", "bv_line", "bv_gap"):
            assert k not in d

    f = json.loads(rows[0]["factors_json"])
    assert f["line_kind"] == "derived_fg"
    assert f["line"] == rows[0]["line_used"]
    assert f["full_game_total"] == 50.5 and f["spread"] == -10.5
    assert 0.48 <= f["fh_share"] <= 0.56


def test_build_prediction_rows_no_week_filter_keeps_all_matched():
    build = _load("post_derived_lines").build_prediction_rows
    fetched = [{"game_id": 1, "line": 50.0, "spread": 0.0},
               {"game_id": 99, "line": 48.0, "spread": 0.0}]  # 99 not in gmeta
    gmeta = {1: {"week": 1, "home": "A", "away": "B"}}
    rows = build(fetched, gmeta, week=None)
    assert len(rows) == 1 and rows[0]["game_id"] == 1     # unmatched dropped
