"""The tracking writers of the week-6 stack (PR2, 2026-10-04): the system can
tell which signals work over time only if every decision freezes what it saw
and nothing is overwritten.

  - picks.freeze_factors: the {chips, factors, features} snapshot on paper and
    challenger picks; refit_id on every pick; model_refit_id reads the same row
    model_read does.
  - build_card.frozen_features: the newest game_records vector, BV columns only.
  - card.build_item carries `features`; a 60-item card stays far under 1 MB.
  - factor_ledger keeps every run under a run_id; readers take the newest.
  - post_mortem.write_run keeps the last 12 runs per scope and prunes older.
  - ops.record_gauge appends to app_settings_log beside the overwrite.
  - poll_lines.log_poll writes one poll_log row per sweep.
  - game_records / games carry CFBD's per-season conferences.

Offline: in-memory SQLite throughout (the Postgres-strict path is the e2e
schema dump, tests/test_e2e_schema_parity.py)."""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta

import pandas as pd
import pytest
from conftest import _load_script, _sqlite_scope
from sqlalchemy.orm import Session

from beatvegas import neggap, ops
from beatvegas.card import build_item
from beatvegas.db.models import (
    AppSetting,
    AppSettingLog,
    ChallengerPick,
    FactorLedger,
    Game,
    GameRecord,
    ManualPick,
    PollLog,
    PostMortemBucket,
    PostMortemGame,
    PostMortemRun,
    Prediction,
    Result,
)
from beatvegas.etl.game_records import snapshot_slate
from beatvegas.factors.ledger import latest_ledger_run_id, load_ledger
from beatvegas.model.bv_line import BV_FEATURE_COLS
from beatvegas.picks import add_pick, freeze_factors, model_read, model_refit_id

NOW = datetime(2026, 10, 2, 21, 5)
KICK = datetime(2026, 10, 3, 19, 30)


# ---------------------------------------------------------------- freeze_factors


def test_freeze_factors_has_three_keys_and_parses_the_prediction_payload():
    chips = {"total_band": "45–52", "tier": "BET"}
    pred = {"factors_json": json.dumps({"factor_board": [{"key": "pace"}], "pace": "slow"})}
    feats = {c: 1.5 for c in BV_FEATURE_COLS}
    out = json.loads(freeze_factors(chips, pred, feats))
    assert set(out) == {"chips", "factors", "features"}
    assert out["chips"] == chips
    assert out["factors"]["pace"] == "slow" and out["factors"]["factor_board"][0]["key"] == "pace"
    assert out["features"] == feats


def test_freeze_factors_nulls_what_it_does_not_have():
    out = json.loads(freeze_factors({"tier": "EDGE"}, None, None))
    assert out == {"chips": {"tier": "EDGE"}, "factors": None, "features": None}
    # an already-parsed payload is taken as is; garbage JSON reads as none
    assert json.loads(freeze_factors({}, {"factors": {"a": 1}}, None))["factors"] == {"a": 1}
    assert json.loads(freeze_factors({}, {"factors_json": "{nope"}, None))["factors"] is None


def test_freeze_factors_refuses_nan():
    with pytest.raises(ValueError):
        freeze_factors({}, None, {"week": float("nan")})


# ---------------------------------------------------------------- refit_id on picks


def _seed_predictions(eng):
    with Session(eng) as s:
        s.add(Game(id=1, season=2026, week=6, home_team="H", away_team="A", start_date=KICK))
        s.add_all(
            [
                Prediction(
                    game_id=1,
                    model_version="gbm_v1",
                    bv_line=22.4,
                    under_score=78,
                    line_used=24.5,
                    refit_id=7,
                    fingerprint="abc123",
                    created_at=NOW - timedelta(minutes=1),
                ),
                # the display-only reference row is newer but never the model read
                Prediction(
                    game_id=1,
                    model_version="derived_lines",
                    line_used=24.5,
                    under_score=12,
                    created_at=NOW,
                ),
            ]
        )
        s.commit()


def test_model_refit_id_reads_the_row_model_read_freezes():
    eng, _ = _sqlite_scope()
    _seed_predictions(eng)
    with Session(eng) as s:
        assert model_read(s, 1) == 22.4
        assert model_refit_id(s, 1) == 7
        assert model_refit_id(s, 1, "full") is None  # the model is 1H-only
        assert model_refit_id(s, None) is None and model_refit_id(s, 999) is None


def test_add_pick_stores_the_refit_id():
    eng, scope = _sqlite_scope()
    _seed_predictions(eng)
    with scope() as s:
        p = add_pick(
            s,
            game_id=1,
            season=2026,
            week=6,
            home_team="H",
            away_team="A",
            line=24.5,
            price=-110,
            is_paper=True,
            refit_id=model_refit_id(s, 1),
        )
        pid = p.id
    with Session(eng) as s:
        assert s.get(ManualPick, pid).refit_id == 7


# ---------------------------------------------------------------- the NEGGAP arms


def _item(gid, gap, **over):
    it = {
        "game_id": gid,
        "away": f"A{gid}",
        "home": f"H{gid}",
        "kick": KICK.isoformat() + "Z",
        "hr_line": 23.5,
        "hr_price": -115,
        "hr_over_price": -105,
        "bv_line": round(23.5 - gap, 2),
        "gap": gap,
        "gap_basis": "hardrock",
        "hr_centred": True,
        "hr_live": True,
        "tier": "PASS",
        "total_band": "45–52",
        "features": {c: 0.25 for c in BV_FEATURE_COLS},
    }
    it.update(over)
    return it


def test_neggap_rows_freeze_the_snapshot_and_the_refit():
    eng, scope = _sqlite_scope()
    card = {"season": 2026, "week": 6, "slot": "fri_pm", "items": [_item(1, -2.0)]}
    preds = [
        {
            "game_id": 1,
            "model_version": "gbm_v1",
            "bv_line": 25.5,
            "refit_id": 7,
            "factors_json": json.dumps({"pace": "fast"}),
        },
        # the reference row never contributes
        {"game_id": 1, "model_version": "derived_lines", "line_used": 23.5, "refit_id": 99},
    ]
    with scope() as s:
        added = neggap.log_neggap_picks(s, card, NOW, predictions=preds)
    assert added == {"neggap_lt0": 1, "neggap_le175": 1}
    with Session(eng) as s:
        rows = s.query(ChallengerPick).order_by(ChallengerPick.arm).all()
    assert [r.refit_id for r in rows] == [7, 7]
    for r in rows:
        frozen = json.loads(r.factors_json_at_pick)
        assert set(frozen) == {"chips", "factors", "features"}
        assert frozen["chips"]["total_band"] == "45–52" and frozen["chips"]["tier"] == "PASS"
        assert frozen["factors"] == {"pace": "fast"}
        assert frozen["features"]["week"] == 0.25 and set(frozen["features"]) == set(
            BV_FEATURE_COLS
        )


def test_neggap_rows_without_a_prediction_or_vector_freeze_nulls():
    eng, scope = _sqlite_scope()
    card = {"season": 2026, "week": 6, "items": [_item(2, -3.0, features=None)]}
    with scope() as s:
        neggap.log_neggap_picks(s, card, NOW)  # no predictions passed at all
    with Session(eng) as s:
        r = s.query(ChallengerPick).first()
    assert r.refit_id is None
    frozen = json.loads(r.factors_json_at_pick)
    assert frozen["factors"] is None and frozen["features"] is None
    assert frozen["chips"]["tier"] == "PASS"


# ---------------------------------------------------------------- frozen_features + the card item


def test_frozen_features_takes_the_newest_record_filtered_to_the_bv_columns():
    mod = _load_script("build_card")
    eng, _ = _sqlite_scope()
    old = {c: 1.0 for c in BV_FEATURE_COLS}
    old["spread"] = 7.5  # a market column: never part of the frozen vector
    new = {c: 2.0 for c in BV_FEATURE_COLS}
    del new[BV_FEATURE_COLS[0]]  # a record predating one input reads None there
    with Session(eng) as s:
        s.add_all(
            [
                GameRecord(
                    game_id=1,
                    season=2026,
                    week=6,
                    model_version="gbm_v1",
                    captured_at=NOW - timedelta(days=7),
                    features_json=json.dumps(old),
                ),
                GameRecord(
                    game_id=1,
                    season=2026,
                    week=6,
                    model_version="gbm_v1",
                    captured_at=NOW,
                    features_json=json.dumps(new),
                ),
                GameRecord(
                    game_id=2, season=2026, week=6, model_version="gbm_v1", features_json="{bad"
                ),
            ]
        )
        s.commit()
        got = mod.frozen_features(s, [1, 2, 3])
    assert set(got) == {1}
    assert set(got[1]) == set(BV_FEATURE_COLS)
    assert got[1][BV_FEATURE_COLS[0]] is None and got[1][BV_FEATURE_COLS[1]] == 2.0
    assert "spread" not in got[1]
    assert mod.frozen_features(None, []) == {}


def test_build_item_carries_the_vector_and_sixty_items_stay_small():
    feats = {c: 12.3456 for c in BV_FEATURE_COLS}
    feats[BV_FEATURE_COLS[0]] = None
    pred = {"game_id": 1, "model_version": "gbm_v1", "bv_line": 22.0, "features": feats}
    game = {"game_id": 1, "away": "Kansas", "home": "Missouri", "kick": KICK}
    it = build_item(game, [], pred, None, None, NOW)
    assert it["features"] == feats
    # no model, or a model row with no record: null, never a missing key
    assert build_item(game, [], None, None, None, NOW)["features"] is None
    assert build_item(game, [], {**pred, "features": None}, None, None, NOW)["features"] is None
    # NaN cleaned, bools numeric, junk dropped — the item stays strict JSON
    dirty = {**pred, "features": {"a": float("nan"), "b": True, "c": "x", "d": 1}}
    assert build_item(game, [], dirty, None, None, NOW)["features"] == {
        "a": None,
        "b": 1.0,
        "d": 1.0,
    }
    items = [build_item({**game, "game_id": i}, [], pred, None, None, NOW) for i in range(60)]
    size = len(json.dumps({"items": items}, ensure_ascii=False, allow_nan=False))
    assert size < 1_000_000, size
    assert size < 250_000, size  # ~60 floats an item; a 1 MB card would be a regression


# ---------------------------------------------------------------- factor_ledger history


def _ledger_rows(mean: float):
    return [
        {
            "factor": "pace_estimate",
            "n": 40,
            "hits": 24,
            "post_mean": mean,
            "post_lo": mean - 0.1,
            "post_hi": mean + 0.1,
            "tier": 2,
            "recent_n": 10,
            "recent_mean": mean,
            "drift_flag": False,
        }
    ]


def test_factor_ledger_keeps_every_run_and_readers_take_the_newest(monkeypatch):
    gfl = _load_script("grade_factor_ledger")
    eng, scope = _sqlite_scope()
    with Session(eng) as s:
        s.add(
            Result(game_id=1, model_version="market", market="1H", line_kind="real", under_hit=True)
        )
        s.commit()
    monkeypatch.setattr(gfl, "try_init_db", lambda: True)
    monkeypatch.setattr(gfl, "session_scope", scope)
    monkeypatch.setattr(
        gfl, "build_feature_frame", lambda: pd.DataFrame({"id": [1], "season": [2026], "week": [5]})
    )
    means = iter([0.55, 0.61])
    monkeypatch.setattr(gfl, "grade_ledger", lambda df, outcomes: _ledger_rows(next(means)))

    monkeypatch.setenv("GITHUB_RUN_ID", "111")
    gfl.main()
    monkeypatch.setenv("GITHUB_RUN_ID", "222")
    gfl.main()

    with Session(eng) as s:
        rows = s.query(FactorLedger).order_by(FactorLedger.id).all()
        assert [r.run_id for r in rows] == ["gha-111", "gha-222"]  # nothing deleted
        assert latest_ledger_run_id(s) == "gha-222"
        led = load_ledger(s)
    assert set(led) == {"pace_estimate"} and led["pace_estimate"]["mean"] == 0.61


def test_load_ledger_reads_legacy_rows_as_one_run():
    eng, _ = _sqlite_scope()
    with Session(eng) as s:
        s.add(FactorLedger(created_at=NOW, **_ledger_rows(0.5)[0]))  # run_id NULL
        s.commit()
        assert latest_ledger_run_id(s) is None
        assert load_ledger(s)["pace_estimate"]["n"] == 40


def test_ledger_run_id_falls_back_to_a_utc_stamp(monkeypatch):
    gfl = _load_script("grade_factor_ledger")
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    assert gfl.ledger_run_id(NOW) == "local-20261002T210500"


# ---------------------------------------------------------------- post-mortem history


def _pm_out(scope: str, run_id: str, gid: int):
    return {
        "scope": scope,
        "run_id": run_id,
        "buckets": [
            {
                "scope": scope,
                "segment": "fbs_only",
                "proxy_kind": "real",
                "selection": "cap5",
                "dimension": "all",
                "bucket": "all",
                "bucket_order": 0,
                "n": 10,
                "unders": 6,
                "overs": 4,
                "pushes": 0,
                "under_pct": 0.6,
                "units": 1.5,
            }
        ],
        "contrasts": [],
        "games": [{"scope": scope, "game_id": gid, "season": 2026, "week": 6}],
        "notes": {"dropped": {}},
    }


def test_write_run_keeps_prior_runs_and_prunes_past_twelve():
    pm = _load_script("post_mortem")
    eng, _ = _sqlite_scope()
    with Session(eng) as s:
        for i in range(1, 14):
            pm.write_run(s, _pm_out("live_2026", f"r{i:02d}", i), NOW + timedelta(hours=i), {})
        # another scope is untouched by live's pruning
        pm.write_run(s, _pm_out("hist_2023_25", "h01", 1), NOW, {})
        runs = (
            s.query(PostMortemRun.run_id)
            .filter(PostMortemRun.scope == "live_2026")
            .order_by(PostMortemRun.computed_at)
            .all()
        )
        assert [r[0] for r in runs] == [f"r{i:02d}" for i in range(2, 14)]  # r01 pruned
        assert s.query(PostMortemBucket).filter(PostMortemBucket.run_id == "r01").count() == 0
        assert s.query(PostMortemGame).filter(PostMortemGame.run_id == "r01").count() == 0
        assert s.query(PostMortemBucket).filter(PostMortemBucket.run_id == "r13").count() == 1
        assert s.query(PostMortemRun).filter(PostMortemRun.scope == "hist_2023_25").count() == 1
        # the newest run per scope is what every reader takes
        newest = (
            s.query(PostMortemRun.run_id)
            .filter(PostMortemRun.scope == "live_2026")
            .order_by(PostMortemRun.computed_at.desc())
            .first()
        )
        assert newest[0] == "r13"


def test_prune_sweeps_orphan_rows_whose_run_has_no_runs_row():
    pm = _load_script("post_mortem")
    eng, _ = _sqlite_scope()
    with Session(eng) as s:
        pm.write_run(s, _pm_out("live_2026", "r01", 1), NOW, {})
        # a crash between the chunked inserts and the runs row leaves these
        s.add(
            PostMortemBucket(
                run_id="crash",
                scope="live_2026",
                segment="fbs_only",
                proxy_kind="real",
                selection="cap5",
                dimension="all",
                bucket="all",
            )
        )
        s.commit()
        assert pm.prune_runs(s, "live_2026") == 1
        assert s.query(PostMortemBucket).filter(PostMortemBucket.run_id == "crash").count() == 0
        assert s.query(PostMortemBucket).filter(PostMortemBucket.run_id == "r01").count() == 1


# ---------------------------------------------------------------- app_settings_log


def test_record_gauge_appends_a_history_row_on_every_write():
    eng, scope = _sqlite_scope()
    with scope() as s:
        assert ops.record_gauge(ops.ODDS_CREDITS_REMAINING, 53946, note="a", session=s)
        assert ops.record_gauge(ops.ODDS_CREDITS_REMAINING, 53900, session=s)
    with Session(eng) as s:
        assert s.get(AppSetting, ops.ODDS_CREDITS_REMAINING).value == "53900"  # overwritten
        log = s.query(AppSettingLog).order_by(AppSettingLog.id).all()
    assert [(r.key, r.value, r.note) for r in log] == [
        (ops.ODDS_CREDITS_REMAINING, "53946", "a"),
        (ops.ODDS_CREDITS_REMAINING, "53900", None),
    ]
    assert all(r.written_at is not None for r in log)


# ---------------------------------------------------------------- poll_log


def test_log_poll_writes_one_row_per_sweep(monkeypatch):
    pl = _load_script("poll_lines")
    eng, scope = _sqlite_scope()
    monkeypatch.setattr(pl, "session_scope", scope)
    monkeypatch.setenv("GITHUB_RUN_ID", "4242")
    assert pl.log_poll(
        mode="close<=120m",
        events_in_window=14,
        events_polled=12,
        new_snapshots=31,
        unchanged=40,
        credits_spent=12,
    )
    assert pl.log_poll(
        mode="sweep<=6d",
        events_in_window=80,
        events_polled=80,
        new_snapshots=0,
        unchanged=0,
        credits_spent=None,
    )
    with Session(eng) as s:
        rows = s.query(PollLog).order_by(PollLog.id).all()
    assert len(rows) == 2
    a, b = rows
    assert (a.market, a.mode, a.events_in_window, a.events_polled) == (
        "1H_total",
        "close<=120m",
        14,
        12,
    )
    assert (a.new_snapshots, a.unchanged, a.credits_spent, a.run_id) == (31, 40, 12, "4242")
    assert b.credits_spent is None and b.captured_at is not None


def test_log_poll_never_raises(monkeypatch, capsys):
    pl = _load_script("poll_lines")

    def boom():
        raise RuntimeError("neon blip")

    monkeypatch.setattr(pl, "session_scope", boom)
    assert (
        pl.log_poll(
            mode="x",
            events_in_window=0,
            events_polled=0,
            new_snapshots=0,
            unchanged=0,
            credits_spent=0,
        )
        is False
    )
    assert "[poll_log] not recorded: neon blip" in capsys.readouterr().out


# ---------------------------------------------------------------- conferences


def test_snapshot_slate_copies_the_conferences_off_games():
    eng, _ = _sqlite_scope()
    scored = pd.DataFrame(
        [
            {"id": 1, "season": 2026, "week": 6, "line": 24.5, "bv_line": 22.0, "under_score": 55},
            {"id": 2, "season": 2026, "week": 6, "line": 21.0, "bv_line": 20.0, "under_score": 50},
        ]
    )
    with Session(eng) as s:
        s.add(Game(id=1, season=2026, week=6, home_conference="SEC", away_conference="Big 12"))
        s.add(Game(id=2, season=2026, week=6))  # backfilled before the column: NULL
        s.commit()
        assert snapshot_slate(s, scored, "gbm_v1", NOW) == 2
        recs = {r.game_id: r for r in s.query(GameRecord).all()}
    assert (recs[1].home_conference, recs[1].away_conference) == ("SEC", "Big 12")
    assert (recs[2].home_conference, recs[2].away_conference) == (None, None)


class _CFBD:
    def __init__(self, games):
        self._games = games

    def games(self, year, season_type):
        return self._games

    def lines(self, year, season_type):
        return []

    def plays(self, **kw):  # pragma: no cover
        raise AssertionError("not needed")


def test_backfill_writes_the_conferences_cfbd_already_sends(monkeypatch):
    bf = _load_script("backfill")
    eng, scope = _sqlite_scope()
    monkeypatch.setattr(bf, "session_scope", scope)
    g = {
        "id": 77,
        "season": 2026,
        "week": 6,
        "seasonType": "regular",
        "startDate": "2026-10-03T19:30:00.000Z",
        "homeTeam": "Missouri",
        "awayTeam": "Kansas",
        "homeId": 142,
        "awayId": 2305,
        "homeConference": "SEC",
        "awayConference": "Big 12",
        "completed": False,
    }
    bf.backfill_season(_CFBD([g]), 2026, "regular", use_pbp=False)
    with Session(eng) as s:
        row = s.get(Game, 77)
        assert (row.home_conference, row.away_conference) == ("SEC", "Big 12")
    # a second pass with the conference missing never blanks it (upsert rule)
    g2 = {k: v for k, v in g.items() if k not in ("homeConference", "awayConference")}
    bf.backfill_season(_CFBD([g2]), 2026, "regular", use_pbp=False)
    with Session(eng) as s:
        row = s.get(Game, 77)
        assert (row.home_conference, row.away_conference) == ("SEC", "Big 12")


def test_item_vector_is_the_regressors_columns_only():
    # The frozen vector is what the NUMBER depended on: never a market column.
    assert "spread" not in BV_FEATURE_COLS and "line" not in BV_FEATURE_COLS
    assert all(isinstance(c, str) for c in BV_FEATURE_COLS)
    assert not any(math.isnan(0.0) for _ in BV_FEATURE_COLS)  # sanity: list is iterable
