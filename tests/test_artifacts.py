"""Model persistence + fingerprint (PR-4).

The scoring job refits from scratch every run. `model_artifacts` keeps the
fitted residual regressor (joblib blob) and the training fingerprint it was
fitted on, so a refit is reproducible and a mid-season data change to the
training history shows up as a moved fingerprint in the job log. The incumbent
engine attaches no artifact, so its path writes nothing new.
"""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
import pytest
from conftest import _load_script
from sklearn.ensemble import HistGradientBoostingRegressor
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from beatvegas.db.models import Base, ModelArtifact, ModelRun
from beatvegas.model import residual
from beatvegas.model.artifacts import (
    dump_model,
    fingerprint_changed,
    latest_artifact,
    load_model,
    persist_artifact,
)

NOW = datetime(2026, 9, 12, 12, 30, 0)


def _fitted(seed: int = 0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(200, 3))
    y = X[:, 0] * 2.0 + rng.normal(scale=0.1, size=200)
    model = HistGradientBoostingRegressor(max_iter=20, random_state=seed)
    model.fit(X, y)
    return model, X


def _train_frame(n: int = 60, start=datetime(2024, 9, 1)) -> pd.DataFrame:
    """A residual training frame: season, kickoff date, the residual target."""
    rng = np.random.default_rng(1)
    return pd.DataFrame(
        {
            "season": [2024] * (n // 2) + [2025] * (n - n // 2),
            "start_date": [start + timedelta(days=7 * (i % 15)) for i in range(n)],
            residual.TARGET: rng.normal(size=n),
        }
    )


def _fp(train: Optional[pd.DataFrame] = None) -> dict:
    return residual.fingerprint(
        _train_frame() if train is None else train, residual.RESIDUAL_FEATURE_COLS
    )


@pytest.fixture
def mem():
    """(engine, scope): a fresh in-memory SQLite DB with the schema created."""
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)

    @contextmanager
    def scope():
        with Session(eng) as s:
            yield s
            s.commit()

    return eng, scope


# --- joblib round trip -----------------------------------------------------------


def test_dump_load_round_trip_predicts_identically():
    model, X = _fitted()
    blob = dump_model(model)
    assert isinstance(blob, bytes) and len(blob) > 0
    back = load_model(blob)
    np.testing.assert_array_equal(back.predict(X), model.predict(X))


# --- persist / latest --------------------------------------------------------------


def test_persist_then_latest_round_trips_the_fingerprint(mem):
    eng, scope = mem
    model, X = _fitted()
    fp = _fp()
    with scope() as s:
        rid = persist_artifact(
            s,
            engine="residual",
            model=model,
            fingerprint=fp,
            season=2026,
            week=3,
            metrics={"sigma": 5.1, "n_rows_residual": 40},
            now=NOW,
        )
        assert isinstance(rid, int) and rid > 0
    with Session(eng) as s:
        row = latest_artifact(s, "residual")
        assert row is not None and row.id == rid
        assert row.engine == "residual"
        assert row.model_version == residual.MODEL_VERSION_TAG
        assert (row.season, row.week) == (2026, 3)
        assert row.fitted_at == NOW
        assert row.n_rows == fp["n_rows"] == 60
        assert row.min_game_date == fp["min_game_date"] == "2024-09-01"
        assert row.max_game_date == fp["max_game_date"]
        assert row.feature_hash == fp["feature_hash"]
        assert len(row.feature_hash) == 16
        assert row.n_features == fp["n_features"] == len(residual.RESIDUAL_FEATURE_COLS)
        assert row.sklearn_version == fp["sklearn_version"]
        assert json.loads(row.fingerprint_json) == fp  # JSON-safe as stored
        assert json.loads(row.metrics_json) == {"sigma": 5.1, "n_rows_residual": 40}
        np.testing.assert_array_equal(load_model(row.blob).predict(X), model.predict(X))
        assert latest_artifact(s, "bv_line") is None


def test_latest_is_the_newest_fit_for_that_engine(mem):
    eng, scope = mem
    model, _ = _fitted()
    with scope() as s:
        first = persist_artifact(
            s, engine="residual", model=model, fingerprint=_fp(), season=2026, week=2,
            metrics={}, now=NOW - timedelta(days=7),
        )  # fmt: skip
        second = persist_artifact(
            s, engine="residual", model=model, fingerprint=_fp(), season=2026, week=3,
            metrics={}, now=NOW,
        )  # fmt: skip
        persist_artifact(
            s, engine="other", model=model, fingerprint=_fp(), season=2026, week=3,
            metrics={}, now=NOW + timedelta(days=1),
        )  # fmt: skip
    with Session(eng) as s:
        assert latest_artifact(s, "residual").id == second != first
        assert s.query(ModelArtifact).count() == 3


def test_fingerprint_json_coerces_numpy_scalars(mem):
    eng, scope = mem
    model, _ = _fitted()
    fp = _fp()
    fp["n_rows"] = np.int64(fp["n_rows"])
    fp["target_mean"] = np.float64(0.25)
    with scope() as s:
        persist_artifact(
            s, engine="residual", model=model, fingerprint=fp, season=2026, week=3,
            metrics={"sigma": np.float32(4.5)}, now=NOW,
        )  # fmt: skip
    with Session(eng) as s:
        row = latest_artifact(s, "residual")
        assert json.loads(row.fingerprint_json)["n_rows"] == 60
        assert json.loads(row.fingerprint_json)["target_mean"] == 0.25
        assert json.loads(row.metrics_json)["sigma"] == 4.5
        assert row.n_rows == 60 and isinstance(row.n_rows, int)


# --- fingerprint_changed --------------------------------------------------------------


def _prev(**over) -> ModelArtifact:
    base = dict(n_rows=60, max_game_date="2025-12-06", feature_hash="a" * 16)
    base.update(over)
    return ModelArtifact(engine="residual", **base)


def test_fingerprint_changed_names_exactly_the_moved_fields():
    fp = {"n_rows": 60, "max_game_date": "2025-12-06", "feature_hash": "a" * 16}
    assert fingerprint_changed(_prev(), fp) == []
    assert fingerprint_changed(_prev(n_rows=61), fp) == ["n_rows"]
    assert fingerprint_changed(_prev(max_game_date="2025-11-29"), fp) == ["max_game_date"]
    assert fingerprint_changed(_prev(feature_hash="b" * 16), fp) == ["feature_hash"]
    assert fingerprint_changed(_prev(n_rows=1, feature_hash="b" * 16), fp) == [
        "n_rows",
        "feature_hash",
    ]


def test_fingerprint_changed_with_no_incumbent_row_is_empty():
    assert (
        fingerprint_changed(None, {"n_rows": 1, "max_game_date": None, "feature_hash": "x"}) == []
    )


def test_fingerprint_changed_treats_a_missing_date_as_a_move():
    fp = {"n_rows": 60, "max_game_date": None, "feature_hash": "a" * 16}
    assert fingerprint_changed(_prev(), fp) == ["max_game_date"]


# --- weekly_update wiring --------------------------------------------------------------


def _scored(with_artifact: bool, fp: Optional[dict] = None) -> pd.DataFrame:
    scored = pd.DataFrame(
        {
            "id": [1, 2],
            "rank": [1, 2],
            "under_score": [70, 40],
            "away_team": ["Kansas", "Missouri"],
            "home_team": ["Kansas State", "Florida"],
            "line": [24.5, 27.0],
        }
    )
    if with_artifact:
        model, _ = _fitted()
        scored.attrs["engine_artifact"] = {
            "model": model,
            "fingerprint": fp or _fp(),
            "sigma": {"sigma": 5.2, "lo_off": -6.1, "hi_off": 6.4},
            "n_rows_residual": 2,
            "n_rows_fallback": 0,
        }
    return scored


def _wire(monkeypatch, mem, scored: pd.DataFrame, engine: str = "residual"):
    """weekly_update bound to the in-memory DB, with the score/store/network
    steps stubbed so only the artifact persistence runs for real."""
    eng, scope = mem
    frame = pd.DataFrame(
        {
            "id": [1, 2],
            "season": [2026, 2026],
            "week": [5, 5],
            "full_game_total": [50.0, 52.0],
            "h_games_played": [2, 2],
            "a_games_played": [2, 2],
        }
    )
    wu = _load_script("weekly_update")
    monkeypatch.setattr(wu, "engine_name", lambda: engine)
    monkeypatch.setattr(wu, "try_init_db", lambda: True)
    monkeypatch.setattr(wu, "detect_week", lambda season: 5)
    monkeypatch.setattr(wu, "build_feature_frame", lambda min_games=0: frame)
    monkeypatch.setattr(wu, "ranking_line_lookup", lambda season, week, basis="opener": ({}, {}))
    monkeypatch.setattr(wu, "training_real_closes", lambda frame, season: {})
    monkeypatch.setattr(wu, "score_slate", lambda *a, **k: scored)
    monkeypatch.setattr(wu, "_enrich_qb_out", lambda scored: None)
    monkeypatch.setattr(wu, "store_predictions", lambda scored: len(scored))
    monkeypatch.setattr(wu, "session_scope", scope)
    monkeypatch.setattr(sys, "argv", ["weekly_update.py", "--season", "2026"])
    return wu


def test_weekly_update_persists_one_artifact_and_prints_the_fingerprint(monkeypatch, mem, capsys):
    eng, _ = mem
    fp = _fp()
    wu = _wire(monkeypatch, mem, _scored(True, fp))
    wu.main()
    out = capsys.readouterr().out
    line = [ln for ln in out.splitlines() if ln.startswith("fingerprint ")]
    assert len(line) == 1, out
    assert line[0] == (
        f"fingerprint {fp['feature_hash']} n_rows=60 max_game_date={fp['max_game_date']} changed=[]"
    )
    with Session(eng) as s:
        rows = s.query(ModelArtifact).all()
        assert len(rows) == 1
        art = rows[0]
        assert (art.engine, art.season, art.week) == ("residual", 2026, 5)
        assert art.n_rows == 60 and art.feature_hash == fp["feature_hash"]
        assert json.loads(art.metrics_json)["sigma"] == {
            "sigma": 5.2,
            "lo_off": -6.1,
            "hi_off": 6.4,
        }
        runs = s.query(ModelRun).all()
        assert len(runs) == 1
        assert runs[0].version == residual.MODEL_VERSION_TAG
        assert runs[0].train_window == "2024-2025"
        metrics = json.loads(runs[0].metrics_json)
        assert metrics["fingerprint"] == fp
        assert metrics["sigma"] == {"sigma": 5.2, "lo_off": -6.1, "hi_off": 6.4}
        assert metrics["n_train"] == 60
        assert metrics["fallback"] is None


def test_weekly_update_names_what_moved_since_the_last_fit(monkeypatch, mem, capsys):
    eng, scope = mem
    model, _ = _fitted()
    old = _fp(_train_frame(n=58, start=datetime(2024, 8, 25)))  # fewer rows, earlier last game
    with scope() as s:
        persist_artifact(
            s, engine="residual", model=model, fingerprint=old, season=2026, week=4,
            metrics={}, now=NOW - timedelta(days=7),
        )  # fmt: skip
    fp = _fp()
    wu = _wire(monkeypatch, mem, _scored(True, fp))
    wu.main()
    out = capsys.readouterr().out
    line = [ln for ln in out.splitlines() if ln.startswith("fingerprint ")][0]
    assert line.endswith("changed=['n_rows', 'max_game_date']"), line
    with Session(eng) as s:
        assert s.query(ModelArtifact).count() == 2
        assert latest_artifact(s, "residual").n_rows == 60


def test_weekly_update_persists_nothing_under_the_incumbent(monkeypatch, mem, capsys):
    eng, _ = mem
    wu = _wire(monkeypatch, mem, _scored(False), engine="bv_line")
    wu.main()
    out = capsys.readouterr().out
    assert "scored 2 games" in out
    assert "fingerprint " not in out
    with Session(eng) as s:
        assert s.query(ModelArtifact).count() == 0
        assert s.query(ModelRun).count() == 0


def test_weekly_update_persists_nothing_when_the_residual_fell_back(monkeypatch, mem, capsys):
    """A demoted residual run attaches no artifact (nothing was fitted)."""
    eng, _ = mem
    scored = _scored(False)
    scored.attrs["engine_fallback"] = "insufficient_real_closes"
    wu = _wire(monkeypatch, mem, scored)
    wu.main()
    out = capsys.readouterr().out
    assert "FALLBACK=insufficient_real_closes" in out
    assert "fingerprint " not in out
    with Session(eng) as s:
        assert s.query(ModelArtifact).count() == 0
        assert s.query(ModelRun).count() == 0


# --- --if-engine -----------------------------------------------------------------


def test_if_engine_mismatch_exits_zero_before_any_db_work(monkeypatch, capsys):
    wu = _load_script("weekly_update")
    monkeypatch.setattr(wu, "engine_name", lambda: "bv_line")

    def boom(*a, **k):
        raise AssertionError("database touched")

    monkeypatch.setattr(wu, "try_init_db", boom)
    monkeypatch.setattr(wu, "build_feature_frame", boom)
    monkeypatch.setattr(wu, "score_slate", boom)
    monkeypatch.setattr(
        sys,
        "argv",
        ["weekly_update.py", "--season", "2026", "--week", "3", "--if-engine", "residual"],
    )
    wu.main()  # returns, no SystemExit
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1
    assert "residual" in out[0] and "bv_line" in out[0]


def test_if_engine_match_proceeds(monkeypatch, mem, capsys):
    wu = _wire(monkeypatch, mem, _scored(True))
    monkeypatch.setattr(
        sys, "argv", ["weekly_update.py", "--season", "2026", "--if-engine", "residual"]
    )
    wu.main()
    assert "scored 2 games" in capsys.readouterr().out


# --- scripts/model_artifacts.py list ------------------------------------------------------


def test_model_artifacts_list_prints_the_newest_first(monkeypatch, mem, capsys):
    eng, scope = mem
    model, _ = _fitted()
    with scope() as s:
        for i in range(3):
            persist_artifact(
                s, engine="residual", model=model, fingerprint=_fp(_train_frame(n=50 + i)),
                season=2026, week=2 + i, metrics={}, now=NOW + timedelta(days=7 * i),
            )  # fmt: skip
    ma = _load_script("model_artifacts")
    monkeypatch.setattr(ma, "try_init_db", lambda: True)
    monkeypatch.setattr(ma, "session_scope", scope)
    monkeypatch.setattr(
        sys, "argv", ["model_artifacts.py", "list", "--engine", "residual", "--limit", "2"]
    )
    ma.main()
    out = capsys.readouterr().out.strip().splitlines()
    body = [ln for ln in out if "2026" in ln]
    assert len(body) == 2
    assert "wk4" in body[0] and "n_rows=52" in body[0]
    assert "wk3" in body[1] and "n_rows=51" in body[1]
    assert (
        residual.fingerprint(_train_frame(), residual.RESIDUAL_FEATURE_COLS)["sklearn_version"]
        in body[0]
    )


def test_model_artifacts_list_empty(monkeypatch, mem, capsys):
    _, scope = mem
    ma = _load_script("model_artifacts")
    monkeypatch.setattr(ma, "try_init_db", lambda: True)
    monkeypatch.setattr(ma, "session_scope", scope)
    monkeypatch.setattr(sys, "argv", ["model_artifacts.py", "list"])
    ma.main()
    assert "no artifacts" in capsys.readouterr().out
