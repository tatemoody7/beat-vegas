"""scripts/archive/wepa_weekly_extract.py: the derived H-WEPA-F z-table carries only
within-file z-scores of the 48 adjusted columns, keyed by game id, and refuses
an id set that does not match the registered list."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.archive import wepa_weekly_extract as X  # noqa: E402


def _file(tmp_path, post, week, ids, values, name=None, season=2025):
    cols = [
        "id",
        "start_date",
        "season",
        "season_type",
        "week",
        "neutral_site",
        "home_team",
        "home_conference",
        "home_elo",
        "home_talent",
        "away_team",
        "away_conference",
        "away_talent",
        "away_elo",
        "spread",
    ] + list(X.ADJUSTED_COLS)
    rows = []
    for i, gid in enumerate(ids):
        base = {
            "id": gid,
            "start_date": f"{season}-10-0{i + 1} 16:00:00",
            "season": season,
            "season_type": "regular",
            "week": week,
            "neutral_site": False,
            "home_team": f"H{gid}",
            "home_conference": "X",
            "home_elo": 1500,
            "home_talent": 700,
            "away_team": f"A{gid}",
            "away_conference": "Y",
            "away_talent": 650,
            "away_elo": 1450,
            "spread": -3.5,
        }
        for c in X.ADJUSTED_COLS:
            base[c] = values[i]
        rows.append(base)
    name = name or f"{post}_Week {week} Model Training Data (Tier 3+)_01.csv"
    p = tmp_path / name
    pd.DataFrame(rows, columns=cols).to_csv(p, index=False)
    return p


def test_zscores_are_within_file_and_nothing_raw_or_market_survives(tmp_path):
    _file(tmp_path, 1001, 5, [11, 12, 13], [1.0, 2.0, 6.0])
    _file(tmp_path, 1002, 6, [21, 22, 23], [10.0, 10.0, 40.0])
    files = X.base_weekly_files(tmp_path)
    assert sorted(files) == [5, 6]
    out = X.extract(files, expected_ids={11, 12, 13, 21, 22, 23})
    assert len(out) == 6 and out["id"].is_unique
    assert list(out.columns[:4]) == ["id", "season", "week", "posted_at"]
    zcols = [c for c in out.columns if c.startswith("z_")]
    assert len(zcols) == 48 and set(out.columns) == set(X.KEEP_COLS + ["posted_at"] + zcols)
    assert not any("spread" in c or "elo" in c or "talent" in c for c in out.columns)
    for wk in (5, 6):
        sub = out[out["week"] == wk][zcols]
        assert np.allclose(sub.mean(), 0.0, atol=1e-9)
        assert np.allclose(sub.std(ddof=0), 1.0, atol=1e-9)
    # week 5 values 1,2,6 -> z of the 6 is (6-3)/sd, sd = sqrt(14/3)
    z6 = out.loc[out["id"] == 13, "z_home_adjusted_epa"].iloc[0]
    assert z6 == pytest.approx(3 / np.sqrt(14 / 3))


def test_update_postseason_and_other_season_files_are_skipped(tmp_path):
    _file(tmp_path, 1001, 5, [11, 12, 13], [1.0, 2.0, 6.0])
    _file(tmp_path, 1003, 5, [31, 32, 33], [1.0, 2.0, 6.0], season=2026)
    _file(
        tmp_path,
        1004,
        12,
        [41, 42, 43],
        [1.0, 2.0, 6.0],
        name="1004_(Update) Week 12 Model Training Data_01.csv",
    )
    _file(
        tmp_path,
        1005,
        1,
        [51, 52, 53],
        [1.0, 2.0, 6.0],
        name="1005_Postseason (+ Army_Navy) Model Training Data_01.csv",
    )
    files = X.base_weekly_files(tmp_path)
    assert sorted(files) == [5]


def test_filename_with_a_space_before_the_suffix_still_matches(tmp_path):
    _file(
        tmp_path,
        1001,
        7,
        [11, 12, 13],
        [1.0, 2.0, 6.0],
        name="1001_Week 7 Model Training Data (Tier 3+) _01.csv",
    )
    assert sorted(X.base_weekly_files(tmp_path)) == [7]


def test_id_set_mismatch_and_duplicates_are_refused(tmp_path):
    _file(tmp_path, 1001, 5, [11, 12, 13], [1.0, 2.0, 6.0])
    files = X.base_weekly_files(tmp_path)
    with pytest.raises(X.ExtractRefusal, match="id set differs"):
        X.extract(files, expected_ids={11, 12, 13, 99})
    _file(tmp_path, 1002, 6, [13, 22, 23], [1.0, 2.0, 6.0])  # 13 again in week 6
    with pytest.raises(X.ExtractRefusal, match="more than one weekly file"):
        X.extract(X.base_weekly_files(tmp_path))


def test_constant_column_becomes_zero_not_nan(tmp_path):
    _file(tmp_path, 1001, 5, [11, 12, 13], [4.0, 4.0, 4.0])
    out = X.extract(X.base_weekly_files(tmp_path))
    assert (out[[c for c in out.columns if c.startswith("z_")]] == 0.0).all().all()


def test_main_writes_the_table_and_the_provenance_sidecar(tmp_path):
    _file(tmp_path, 1001, 5, [11, 12, 13], [1.0, 2.0, 6.0])
    (tmp_path / "_2025_ids.txt").write_text("11,12,13\n")
    dest = tmp_path / "out" / "wepa_2025_weekly_z.csv"
    assert X.main(["--src", str(tmp_path), "--out", str(dest)]) == 0
    assert dest.exists() and len(pd.read_csv(dest)) == 3
    meta = json.loads(dest.with_suffix(".meta.json").read_text())
    assert meta["row"] == "H-WEPA-F" and meta["rows"] == 3 and meta["weeks"] == [5]
    assert meta["sources"][0]["post_id"] == 1001 and len(meta["sources"][0]["sha256"]) == 64
    assert meta["columns_zscored"] == list(X.ADJUSTED_COLS)


def test_committed_table_matches_the_registered_cut():
    """The committed derived table: 561 games, weeks 5-15, 48 z columns, no raw
    or market column, within-week mean 0."""
    p = ROOT / "data" / "wepa_2025_weekly_z.csv"
    d = pd.read_csv(p)
    z = [c for c in d.columns if c.startswith("z_")]
    assert len(d) == 561 and d["id"].is_unique and len(z) == 48
    assert sorted(d["week"].unique()) == list(range(5, 16))
    assert (d["season"] == 2025).all()
    assert not any(("spread" in c) or ("elo" in c) or ("talent" in c) for c in d.columns)
    assert np.allclose(d.groupby("week")[z].mean().to_numpy(), 0.0, atol=1e-6)
    meta = json.loads(p.with_suffix(".meta.json").read_text())
    assert meta["rows"] == 561 and len(meta["sources"]) == 11
