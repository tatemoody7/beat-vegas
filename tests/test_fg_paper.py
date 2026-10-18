"""H-FG-P (2026-10-06): the bv_fg_v1 shadow scorer, the paper full-game-under
collector and its position. Mirrors tests/test_neggap.py: universe, switch,
the champion's rule (bar then cap 5, held first), the paper window, one row per
game, never a manual pick, grading at the full-game close, the frozen clocks."""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta

import numpy as np
import pytest
from conftest import _load_script
from sqlalchemy.orm import Session
from test_residual_gate import _frame as residual_frame

from beatvegas import fg_paper as F
from beatvegas.backtest import stopping as S
from beatvegas.challenger_picks import grade_challenger_picks
from beatvegas.db.models import ChallengerPick, Game, ManualPick, ModelRun, OddsSnapshot, Prediction
from beatvegas.model.score import CHAMPION_READ_VERSIONS, MODEL_VERSION
from tests.conftest import _sqlite_scope

NOW = datetime(2026, 10, 9, 21, 5)  # Fri 5:05pm ET build
SAT = datetime(2026, 10, 10, 19, 30)  # Saturday 3:30pm ET
CARD = {"season": 2026, "week": 6, "slot": "fri_pm"}


def _seed(s, n, *, gap_of=lambda i: float(i), kick=SAT, start_id=1, hr=True, **quote):
    """n games with a centred Hard Rock full-game quote at 50.5 and a bv_fg_v1
    read 50.5 - gap_of(i): game i's gap is gap_of(i)."""
    for i in range(n):
        gid = start_id + i
        s.add(
            Game(
                id=gid,
                season=2026,
                week=6,
                home_team=f"H{gid}",
                away_team=f"A{gid}",
                start_date=kick,
            )
        )
        if hr:
            s.add(
                OddsSnapshot(
                    game_id=gid,
                    book="hardrockbet",
                    market="full_game_total",
                    line=50.5,
                    over_price=quote.get("over", -110),
                    under_price=quote.get("under", -110),
                    captured_at=NOW - timedelta(hours=1),
                )
            )
        s.add(
            Prediction(
                game_id=gid,
                model_version=F.FG_MODEL_VERSION,
                bv_line=50.5 - gap_of(i),
                refit_id=41,
                factors_json=json.dumps({"engine": "bv_fg_v1", "features": {"x": 1.0}}),
                created_at=NOW - timedelta(days=5),
            )
        )
        s.add(
            Prediction(
                game_id=gid,
                model_version=MODEL_VERSION,
                bv_line=24.0,
                created_at=NOW - timedelta(days=5),
            )
        )
    s.commit()


def test_the_shadow_version_is_outside_the_champion_allow_list():
    assert F.FG_MODEL_VERSION not in CHAMPION_READ_VERSIONS
    assert _load_script("fg_shadow").FG_MODEL_VERSION == F.FG_MODEL_VERSION


def test_collection_is_off_unless_fg_collect_is_1(monkeypatch):
    monkeypatch.delenv("FG_COLLECT", raising=False)
    assert F.collection_enabled() is False
    monkeypatch.setenv("FG_COLLECT", "0")
    assert F.collection_enabled() is False
    monkeypatch.setenv("FG_COLLECT", "1")
    assert F.collection_enabled() is True
    assert "off" in F.summary_line(None, False)


def test_universe_needs_a_centred_priced_hard_rock_quote_a_shadow_read_and_no_kickoff():
    eng, _ = _sqlite_scope()
    with Session(eng) as s:
        _seed(s, 2)  # 1, 2: in
        _seed(s, 1, start_id=3, under=-185)  # an alternate rung: not centred
        _seed(s, 1, start_id=4, hr=False)  # no Hard Rock quote
        _seed(s, 1, start_id=5, kick=NOW - timedelta(minutes=5))  # already kicked off
        _seed(s, 1, start_id=6)
        s.query(Prediction).filter(
            Prediction.game_id == 6, Prediction.model_version == F.FG_MODEL_VERSION
        ).delete()  # no shadow read (a champion row alone does not count)
        s.add(
            OddsSnapshot(  # another book's quote is not Hard Rock's
                game_id=4,
                book="draftkings",
                market="full_game_total",
                line=50.5,
                over_price=-110,
                under_price=-110,
                captured_at=NOW - timedelta(hours=1),
            )
        )
        s.commit()
        items = F.universe(s, 2026, 6, NOW)
    assert sorted(it["game_id"] for it in items) == [1, 2]
    it = next(i for i in items if i["game_id"] == 2)
    assert it["gap"] == 1.0 and it["hr_under_price"] == -110 and it["champion_bv_line"] == 24.0


def test_the_newest_hard_rock_quote_wins_and_a_quote_after_the_build_is_unseen():
    eng, _ = _sqlite_scope()
    with Session(eng) as s:
        _seed(s, 1)
        for line, at in ((52.5, NOW - timedelta(minutes=10)), (40.5, NOW + timedelta(minutes=1))):
            s.add(
                OddsSnapshot(
                    game_id=1,
                    book="HardRockBet",
                    market="full_game_total",
                    line=line,
                    over_price=-110,
                    under_price=-110,
                    captured_at=at,
                )
            )
        s.commit()
        (it,) = F.universe(s, 2026, 6, NOW)
    assert it["hr_line"] == 52.5 and it["gap"] == 2.0


def test_select_is_the_bar_then_the_cap_with_held_rows_first():
    items = [
        {"game_id": i, "gap": float(i), "kick": SAT, "away": f"A{i}"} for i in range(1, 31)
    ]  # 30 games -> k = 6, bar = 25.0: games 25..30 qualify
    sel = F.select(items, logged=[])
    assert sel["bar"] == 25.0 and sel["qualifying"] == 6
    assert [it["game_id"] for it in sel["selected"]] == [30, 29, 28, 27, 26]
    assert next(it for it in items if it["game_id"] == 25)["cap_rank"] == 6
    # Three rows already logged this week hold their slots: two new ones fit.
    sel = F.select(items, logged=[30, 3, 2])
    assert sel["held"] == 3
    assert [it["game_id"] for it in sel["selected"]] == [29, 28]


def test_ties_at_the_bar_qualify():
    items = [
        {"game_id": i, "gap": g, "kick": SAT, "away": ""} for i, g in enumerate([3, 3, 1, 0, -1])
    ]
    sel = F.select(items, logged=[])
    assert sel["bar"] == 3.0 and sel["qualifying"] == 2


def test_log_writes_one_challenger_under_per_selected_game_and_never_a_manual_pick():
    eng, _ = _sqlite_scope()
    with Session(eng) as s:
        _seed(s, 30, gap_of=lambda i: float(i + 1))  # gaps 1..30
        stats = F.log_fg_picks(s, CARD, NOW)
        s.commit()
        assert stats["added"] == 5 and stats["universe"] == 30 and stats["qualifying"] == 6
        rows = s.query(ChallengerPick).order_by(ChallengerPick.gap_at_pick.desc()).all()
        assert [r.game_id for r in rows] == [30, 29, 28, 27, 26]
        r = rows[0]
        assert (r.arm, r.side, r.market, r.book) == ("fg_under", "under", "full", "hardrockbet")
        assert (r.line, r.price, r.slot, r.refit_id) == (50.5, -110, "fri_pm", 41)
        assert r.arm_line_at_pick == 50.5 - 30 and r.champion_line_at_pick == 24.0
        frozen = json.loads(r.factors_json_at_pick)
        assert frozen["chips"]["bar"] == 25.0 and frozen["chips"]["cap_rank"] == 1
        assert frozen["features"] == {"x": 1.0} and "features" not in frozen["factors"]
        assert s.query(ManualPick).count() == 0
        # A second build the same week adds nothing: the five slots are held.
        again = F.log_fg_picks(s, CARD, NOW + timedelta(hours=15))
        assert again["added"] == 0 and again["held"] == 5
        assert s.query(ChallengerPick).count() == 5


def test_the_paper_window_defers_a_selected_game_without_giving_its_slot_away():
    eng, _ = _sqlite_scope()
    with Session(eng) as s:
        _seed(s, 10, gap_of=lambda i: float(i + 1))  # k = 2: games 10, 9 qualify
        s.query(Game).filter(Game.id == 10).update({"start_date": NOW + timedelta(hours=60)})
        s.commit()
        stats = F.log_fg_picks(s, CARD, NOW, window_hours=48.0)
        assert stats["added"] == 1
        assert [r.game_id for r in s.query(ChallengerPick).all()] == [9]


def test_summary_line_reads_the_stats():
    line = F.summary_line(
        {"added": 2, "universe": 40, "bar": 6.25, "qualifying": 8, "held": 3}, True
    )
    assert "universe 40" in line and "bar 6.25" in line and "+2 logged" in line


def test_build_card_logs_the_arm_inside_a_savepoint(monkeypatch):
    """A failure inside the arm must never cost the card: build_card wraps it
    in begin_nested + try/except, and the switch is FG_COLLECT."""
    src = _load_script("build_card").__file__
    text = open(src).read()
    assert "with s.begin_nested():" in text and "log_fg_picks(" in text
    assert "fg_summary_line(fg_stats, fg_on)" in text


def test_grade_challenger_picks_settles_a_full_game_under_at_the_full_game_close():
    eng, scope = _sqlite_scope()
    with Session(eng) as s:
        s.add(
            Game(
                id=1,
                season=2026,
                week=6,
                home_team="H",
                away_team="A",
                start_date=SAT,
                home_points=24,
                away_points=20,
                first_half_total=21,
                first_half_source="pbp",
            )
        )
        for book, line, at in (
            ("draftkings", 49.5, SAT - timedelta(hours=2)),
            ("fanduel", 49.5, SAT - timedelta(hours=2)),
            ("hardrockbet", 49.5, SAT - timedelta(hours=1)),
        ):
            s.add(
                OddsSnapshot(
                    game_id=1,
                    book=book,
                    market="full_game_total",
                    line=line,
                    over_price=-110,
                    under_price=-110,
                    captured_at=at,
                )
            )
        s.add(
            ChallengerPick(
                arm="fg_under",
                game_id=1,
                season=2026,
                week=6,
                home_team="H",
                away_team="A",
                side="under",
                market="full",
                line=50.5,
                price=-110,
                stake=1.0,
                book="hardrockbet",
                placed_at=NOW,
                graded=False,
            )
        )
        s.commit()
    with scope() as s:
        assert grade_challenger_picks(s, 2026) == 1
    with Session(eng) as s:
        p = s.query(ChallengerPick).one()
        assert p.graded and p.result == "under" and p.actual_first_half_total == 44
        assert round(p.units, 4) == 0.9091
        assert p.closing_line == 49.5 and p.clv == -1.0  # closing - bet: favourable for an under
        # draftkings/fanduel's stamp: Hard Rock's own row never counts toward the
    # close (lines.CLOSE_EXCLUDED_BOOKS, 2026-10-11).
    assert p.closing_captured_at == SAT - timedelta(hours=2)


def test_fg_constants_are_frozen_as_registered():
    c = S.FG
    assert c["arms"] == ["fg_under"] and c["side"] == "under" and c["market"] == "full"
    assert c["alpha_clock"] == 0.025 and c["power"] == 0.80 and c["edge"] == 0.04
    assert c["sigma"] == {"profit": 0.913, "clv": None}
    assert c["mu1"]["clv"] == 1.00 and c["clv_sign"] == -1 and c["close_window_h"] == 3.0


def test_fg_position_runs_profit_and_waits_on_the_unfrozen_line_value_sigma():
    pos = S.fg_position(
        {
            "fg_under": {
                "units": [0.9091, -1.0, 0.9091],
                "prices": [-110, -110, -110],
                "clv": [1.0, -0.5, 2.0],
                "clv_in_window": [True, True, False],
            }
        }
    )
    arm = pos["arms"]["fg_under"]
    assert arm["clocks"]["profit"]["n"] == 3 and arm["clocks"]["profit"]["status"] == "running"
    clv = arm["clocks"]["clv"]
    assert clv["llr"] is None and clv["status"].startswith("not started")
    assert clv["n"] == 2 and clv["excluded_no_close_in_window"] == 1
    assert arm["family_verdict"] == "accruing" and pos["passers"] == []


def test_fg_position_reads_the_full_game_window_and_only_fg_under_rows():
    fp = _load_script("fg_position")
    eng, _ = _sqlite_scope()
    with Session(eng) as s:
        s.add(Game(id=1, season=2026, week=6, home_team="H", away_team="A", start_date=SAT))
        common = dict(game_id=1, season=2026, week=6, price=-110, graded=True, units=0.9091)
        s.add_all(
            [
                # closes 2.5 h out: inside the full-game 3 h window, outside 1H's 2 h
                ChallengerPick(
                    arm="fg_under",
                    side="under",
                    market="full",
                    result="under",
                    clv=-1.5,
                    closing_captured_at=SAT - timedelta(hours=2.5),
                    placed_at=NOW,
                    **common,
                ),
                ChallengerPick(
                    arm="neggap_lt0",
                    side="over",
                    market="1H",
                    result="over",
                    clv=1.0,
                    placed_at=NOW,
                    **common,
                ),
            ]
        )
        s.commit()
        tallies, obs = fp.load_observations(s)
    assert list(tallies) == ["fg_under"] and tallies["fg_under"]["won"] == 1
    o = obs["fg_under"]
    assert o["clv"] == [1.5] and o["clv_in_window"] == [True] and o["move"] == [-1.5]


def test_fg_shadow_scores_the_full_game_and_stores_a_shadow_row_with_its_own_refit():
    fs = _load_script("fg_shadow")
    df, _ = residual_frame()
    df["h_games_played"] = 5
    df["a_games_played"] = 5
    scored = fs.score_fg_week(df, 2025, 3)
    assert len(scored) == 10 and np.all(np.isfinite(scored["bv_fg_line"]))
    assert float(scored["bv_fg_line"].mean()) == pytest.approx(50.0, abs=1.0)  # every final is 50
    assert scored.attrs["n_train"] > 0
    eng, _ = _sqlite_scope()
    with Session(eng) as s:
        s.add(
            Prediction(game_id=int(scored["id"].iloc[0]), model_version=MODEL_VERSION, bv_line=24.0)
        )
        refit = fs.record_fg_refit(s, scored, df, season=2025, week=3, frame_fingerprint="abc")
        n = fs.store_fg_predictions(s, scored, refit_id=refit, frame_fingerprint="abc")
        # a re-score replaces the shadow's rows and never the champion's
        n2 = fs.store_fg_predictions(s, scored, refit_id=refit, frame_fingerprint="abc")
        s.commit()
        assert n == n2 == 10
        assert s.query(Prediction).filter_by(model_version="bv_fg_v1").count() == 10
        assert s.query(Prediction).filter_by(model_version=MODEL_VERSION).count() == 1
        run = s.query(ModelRun).one()
        assert run.notes == "fg shadow refit" and run.version == "bv_fg_v1"
        p = s.query(Prediction).filter_by(model_version="bv_fg_v1").first()
        assert p.refit_id == refit and p.rank is None and p.fingerprint == "abc"
        feats = json.loads(p.factors_json)["features"]
        assert all(v is None or math.isfinite(v) for v in feats.values())


# --- p1.4 (Tate, 2026-10-18, final-2026 plan D9): Hard Rock's alternate rungs ------------


def _other_books(s, gid, line, at, books=("draftkings", "fanduel", "betmgm")):
    for b in books:
        s.add(
            OddsSnapshot(
                game_id=gid,
                book=b,
                market="full_game_total",
                line=line,
                over_price=-110,
                under_price=-110,
                captured_at=at,
            )
        )


def test_p14_a_rung_as_the_newest_hard_rock_quote_yields_the_last_main_line():
    """The newest Hard Rock row is priced -160/+130 (a rung by price); the arm
    reads the main 50.5 posted an hour earlier and counts the rung ignored."""
    eng, _ = _sqlite_scope()
    with Session(eng) as s:
        _seed(s, 1)  # main 50.5 at NOW-1h
        s.add(
            OddsSnapshot(
                game_id=1,
                book="hardrockbet",
                market="full_game_total",
                line=53.5,
                over_price=-160,
                under_price=130,
                captured_at=NOW - timedelta(minutes=10),
            )
        )
        s.commit()
        items, stats = F.universe_with_stats(s, 2026, 6, NOW)
    assert [it["hr_line"] for it in items] == [50.5]
    assert stats == {"hr_alt_ignored": 1}


def test_p14_a_main_priced_line_two_points_off_three_books_is_a_rung():
    """The distance rule: Hard Rock at 54.5 / -110 with three books at 50.5 is a
    rung even at a main price; with the earlier 50.5 main line it is used instead."""
    eng, _ = _sqlite_scope()
    with Session(eng) as s:
        _seed(s, 1)
        _other_books(s, 1, 50.5, NOW - timedelta(hours=2))
        s.add(
            OddsSnapshot(
                game_id=1,
                book="hardrockbet",
                market="full_game_total",
                line=54.5,
                over_price=-110,
                under_price=-110,
                captured_at=NOW - timedelta(minutes=10),
            )
        )
        s.commit()
        items, stats = F.universe_with_stats(s, 2026, 6, NOW)
    assert [it["hr_line"] for it in items] == [50.5] and stats["hr_alt_ignored"] == 1


def test_p14_a_game_whose_hard_rock_quotes_are_all_rungs_leaves_the_universe():
    eng, _ = _sqlite_scope()
    with Session(eng) as s:
        _seed(s, 1, under=-150)  # -150 passes the -160 centred test, fails is_hr_rung
        s.commit()
        items, stats = F.universe_with_stats(s, 2026, 6, NOW)
    assert items == [] and stats == {"hr_alt_ignored": 1}


def test_p14_the_logged_pick_and_the_summary_carry_the_main_line_and_the_count():
    eng, scope = _sqlite_scope()
    with Session(eng) as s:
        _seed(s, 1, gap_of=lambda i: 3.0)
        s.add(
            OddsSnapshot(
                game_id=1,
                book="hardrockbet",
                market="full_game_total",
                line=48.5,
                over_price=120,
                under_price=-150,
                captured_at=NOW - timedelta(minutes=5),
            )
        )
        s.commit()
    with scope() as s:
        out = F.log_fg_picks(s, CARD, NOW, arm="H-ARM-FGU", cap=None, require_positive=True)
    assert out["added"] == 1 and out["hr_alt_ignored"] == 1
    assert "1 Hard Rock alternate rung ignored (p1.4)" in F.arm_summary_line(out)
    with Session(eng) as s:
        (r,) = s.query(ChallengerPick).all()
        assert (r.line, r.price) == (50.5, -110)
