"""The strategic review's two exploratory looks (H-WX-HIST, H-JUDGE): the shared
early-line / close / result frame and each script's pure readings."""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from beatvegas.backtest import early_close as E

KICK = datetime(2025, 10, 18, 19, 30)


def _snap(book, line, at_hours_before, over=-110, under=-110, seen=None):
    return SimpleNamespace(
        book=book,
        line=line,
        over_price=over,
        under_price=under,
        captured_at=KICK - timedelta(hours=at_hours_before),
        last_seen_at=seen,
    )


def test_early_line_reads_each_books_earliest_centred_quote_a_day_or_more_out():
    snaps = [
        _snap("draftkings", 27.5, 48),
        _snap("draftkings", 26.5, 30),  # later than the same book's first: ignored
        _snap("fanduel", 28.5, 47),
        _snap("betmgm", 30.5, 48, over=-170, under=135),  # off-centre rung: never counts
        _snap("hardrockbet", 20.5, 48),  # the judge never counts Hard Rock
        _snap("espnbet", 25.5, 2),  # inside a day: not early
    ]
    assert E.early_line(snaps, KICK) == 28.0  # median(27.5, 28.5) on the half-point grid
    assert E.early_line([_snap("draftkings", 27.5, 3)], KICK) is None


def test_the_consensus_close_line_needs_three_fresh_books():
    from beatvegas.consensus import BookClose

    fresh = KICK - timedelta(minutes=30)
    closes = {
        b: BookClose(b, line, -110, -110, fresh)
        for b, line in [("draftkings", 26.5), ("fanduel", 27.5), ("betmgm", 27.5)]
    }
    assert E.consensus_close_line(closes, KICK) == 27.5
    closes["betmgm"] = BookClose("betmgm", 27.5, -110, -110, KICK - timedelta(hours=5))
    assert E.consensus_close_line(closes, KICK) is None  # stale: two fresh books only


def test_settle_and_units_at_minus_110():
    assert E.settle(24, 27.5, "under") == "win" and E.settle(24, 27.5, "over") == "loss"
    assert E.settle(28, 28.0, "under") == "push" and E.settle(None, 27.5, "under") is None
    assert E.units("win") == pytest.approx(100 / 110) and E.units("loss") == -1.0
    assert E.units("push") == 0.0 and E.units(None) is None


def test_bowls_key_apart_from_week_one():
    reg = {"season": 2025, "season_type": "regular", "week": 1}
    bowl = {"season": 2025, "season_type": "postseason", "week": 1}
    assert E.week_key(reg) != E.week_key(bowl)


def test_bootstrap_mean_ci_brackets_the_mean_and_needs_two_weeks():
    lo, hi = E.bootstrap_mean_ci([[0.0, 0.1], [0.2, 0.3], [0.1, 0.1]])
    assert lo <= 0.1333 <= hi
    assert E.bootstrap_mean_ci([[0.1, 0.2]]) is None


def _rec(gid, week, early, close, total, ev_u, ev_o=None):
    return {
        "game_id": gid,
        "season": 2025,
        "season_type": "regular",
        "week": week,
        "early": early,
        "close": close,
        "total": total,
        "under": {"ev": ev_u, "excluded": None, "books": 5},
        "over": {"ev": ev_o, "excluded": None, "books": 5},
    }


def test_weather_look_splits_outdoor_games_by_the_frozen_threshold(load_script):
    wx = load_script("weather_history_look")
    recs = [
        _rec(1, 5, 27.5, 27.5, 20, -0.04),
        _rec(2, 5, 27.5, 27.5, 30, -0.05),
        _rec(3, 6, 27.5, 26.5, 26, 0.02),
    ]
    fc = {
        1: {"wind": 12.0, "dome": False},
        2: {"wind": 9.9, "dome": False},
        3: {"wind": 30.0, "dome": True},
    }
    groups = wx.split(recs, fc)
    assert [r["game_id"] for r in groups["windy"]] == [1]
    assert [r["game_id"] for r in groups["calm"]] == [2]  # the dome is out entirely
    assert wx.WIND_MIN_MPH == 10.0 and wx.LEAD_HOURS == 72
    out = wx.summarize(groups["windy"])
    assert out["close_record"] == "1-0-0" and out["line_value_mean"] == -0.04


def test_judge_check_pairs_both_sides_at_the_early_line_and_fits_a_line(load_script):
    jc = load_script("judge_check")
    recs = [_rec(1, 5, 27.5, 27.5, 20, -0.02, -0.07), _rec(2, 6, 27.5, 27.5, 30, -0.06, -0.03)]
    groups = jc.pairs(recs)
    flat = sorted(p for g in groups.values() for p in g)
    want = sorted([(-0.02, 100 / 110), (-0.07, -1.0), (-0.06, -1.0), (-0.03, 100 / 110)])
    assert len(flat) == 4
    assert all(a == pytest.approx(b) for a, b in zip(flat, want))
    slope, icpt = jc.ols([(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)])
    assert slope == pytest.approx(1.0) and icpt == pytest.approx(0.0)
    assert jc.ols([(1.0, 0.0), (1.0, 1.0), (1.0, 2.0)]) is None


def test_records_reads_a_real_judge_value_end_to_end():
    """The regression the first H-WX-HIST / H-JUDGE runs hit (2026-10-09): the
    judge's half-point table is keyed by the SNAPSHOT market; passing the wager
    market ('1H') excluded every bet. One synthetic game through the real table."""
    from sqlalchemy.orm import Session

    from beatvegas.db.models import Game, OddsSnapshot
    from tests.conftest import _sqlite_scope

    eng, scope = _sqlite_scope()
    with Session(eng) as s:
        s.add(
            Game(
                id=1,
                season=2025,
                week=7,
                season_type="regular",
                start_date=KICK,
                home_team="Ohio State",
                away_team="Michigan",
                home_points=24,
                away_points=17,
                first_half_total=17,
                first_half_source="linescores",
            )
        )
        for book in ("draftkings", "fanduel", "betmgm", "espnbet"):
            for hours, line in ((48, 27.5), (0.5, 26.5)):
                s.add(
                    OddsSnapshot(
                        game_id=1,
                        book=book,
                        market="1H_total",
                        line=line,
                        over_price=-110,
                        under_price=-110,
                        captured_at=KICK - timedelta(hours=hours),
                    )
                )
        s.commit()
    with scope() as s:
        (rec,) = E.records(s, [2025], "1H_total")
    assert rec["early"] == 27.5 and rec["close"] == 26.5 and rec["total"] == 17
    assert rec["under"]["ev"] is not None and rec["over"]["ev"] is not None
    assert rec["under"]["ev"] > rec["over"]["ev"]  # the market moved toward the under
    assert E.exclusion_counts([rec]) == {}
