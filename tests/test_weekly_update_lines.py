"""weekly_update.ranking_line_lookup: the per-game line the board ranks on.

basis="opener" is the incumbent behaviour (consensus 1H OPENER, else a 1H
number derived from the full-game opener). basis="current" is what the
residual engine conditions on: Hard Rock's latest 1H line (kind hr_1h), else
the median of every book's latest 1H line (observed_1h), else derived_fg.
Offline: in-memory SQLite, script loaded via conftest._load_script."""

from __future__ import annotations

import sys
from contextlib import contextmanager
from datetime import datetime, timedelta

import pandas as pd
import pytest
from conftest import _load_script
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from beatvegas.db.models import Base, Game, OddsSnapshot
from beatvegas.etl.proxy_line import proxy_total

SEASON, WEEK = 2026, 5
KICK = datetime(2026, 10, 3, 19, 30)


def _snap(gid, book, market, line, hours_before, spread=None):
    return OddsSnapshot(
        game_id=gid,
        book=book,
        market=market,
        line=line,
        spread=spread,
        captured_at=KICK - timedelta(hours=hours_before),
    )


@pytest.fixture
def wu(monkeypatch):
    mod = _load_script("weekly_update")
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)

    @contextmanager
    def scope():
        with Session(eng) as s:
            yield s
            s.commit()

    mod.session_scope = scope
    with Session(eng) as s:
        for gid in (1, 2, 3, 4, 5, 7, 8):
            s.add(
                Game(
                    id=gid,
                    season=SEASON,
                    week=WEEK,
                    home_team=f"H{gid}",
                    away_team=f"A{gid}",
                    start_date=KICK,
                )
            )
        s.add(
            Game(
                id=9, season=SEASON, week=WEEK + 1, home_team="H9", away_team="A9", start_date=KICK
            )
        )
        # game 6: NULL start_date — the pre-kick filter must not apply (no kickoff
        # to filter against), so current behaviour (latest-by-captured_at) holds.
        s.add(Game(id=6, season=SEASON, week=WEEK, home_team="H6", away_team="A6", start_date=None))
        s.add_all(
            [
                # game 1: Hard Rock + DraftKings 1H, plus a full-game opener
                _snap(1, "hardrockbet", "1H_total", 24.5, 30),
                _snap(1, "hardrockbet", "1H_total", 25.0, 3),
                _snap(1, "draftkings", "1H_total", 24.0, 30),
                _snap(1, "draftkings", "1H_total", 26.0, 2),
                _snap(1, "draftkings", "full_game_total", 50.5, 48, spread=-3.0),
                # game 2: no Hard Rock; two books moved
                _snap(2, "draftkings", "1H_total", 23.0, 30),
                _snap(2, "draftkings", "1H_total", 23.5, 2),
                _snap(2, "fanduel", "1H_total", 22.5, 30),
                _snap(2, "fanduel", "1H_total", 24.5, 2),
                # game 3: full-game opener only
                _snap(3, "draftkings", "full_game_total", 50.0, 48, spread=-7.0),
                _snap(3, "draftkings", "full_game_total", 52.0, 2, spread=-7.0),
                # game 4: nothing. game 9: another week (must be ignored)
                _snap(9, "hardrockbet", "1H_total", 30.5, 3),
                # game 5: Hard Rock's pre-kick line, then an IN-PLAY snapshot from
                # a midweek re-run (poll_lines --hours-back 24 catches games that
                # already kicked) — the post-kick one must never win "current".
                _snap(5, "hardrockbet", "1H_total", 24.5, 1),  # 1h before kickoff
                _snap(5, "hardrockbet", "1H_total", 17.5, -1),  # 1h AFTER kickoff
                # game 6: same shape, but the game has no known start_date.
                _snap(6, "hardrockbet", "1H_total", 20.0, 1),
                _snap(6, "hardrockbet", "1H_total", 15.0, -1),
                # game 7: ONLY in-play 1H captures (the game kicked before we ever
                # polled its 1H market) + a full-game opener. There is no pre-kick
                # 1H line to bet, so "current" must fall through to derived_fg.
                _snap(7, "hardrockbet", "1H_total", 13.5, -1),
                _snap(7, "draftkings", "1H_total", 12.5, -2),
                _snap(7, "draftkings", "full_game_total", 54.0, 48, spread=-10.0),
                # game 8: only in-play 1H captures and no full-game opener either
                # — no line at all, left to score_slate's internal proxy.
                _snap(8, "hardrockbet", "1H_total", 11.0, -1),
            ]
        )
        s.commit()
    return mod


def test_opener_basis_is_the_incumbent_lookup(wu):
    lines, kinds = wu.ranking_line_lookup(SEASON, WEEK, basis="opener")
    assert lines[1] == 24.25 and kinds[1] == "observed_1h"  # median(24.5, 24.0) first per book
    assert lines[2] == 22.75 and kinds[2] == "observed_1h"
    assert lines[3] == proxy_total(50.0, spread=-7.0) and kinds[3] == "derived_fg"
    assert 4 not in lines and 9 not in lines
    assert wu.opening_line_lookup(SEASON, WEEK) == (lines, kinds)  # thin wrapper


def test_current_basis_prefers_hard_rock_then_consensus_latest_then_derived(wu):
    lines, kinds = wu.ranking_line_lookup(SEASON, WEEK, basis="current")
    assert lines[1] == 25.0 and kinds[1] == "hr_1h"  # HR's LATEST, not DK's 26.0
    assert lines[2] == 24.0 and kinds[2] == "observed_1h"  # median(23.5, 24.5) latest per book
    assert lines[3] == proxy_total(50.0, spread=-7.0) and kinds[3] == "derived_fg"  # opener
    assert 4 not in lines and 9 not in lines


def test_current_basis_ignores_in_play_snapshots_after_kickoff(wu):
    """A midweek re-run must not condition the residual model on an in-play
    line: game 5's Hard Rock snapshot posted 1h AFTER kickoff (17.5) is later
    than its pre-kick snapshot (24.5) by captured_at, but must be filtered out."""
    lines, kinds = wu.ranking_line_lookup(SEASON, WEEK, basis="current")
    assert lines[5] == 24.5 and kinds[5] == "hr_1h"


def test_opener_basis_unaffected_by_pre_kickoff_filter(wu):
    lines, kinds = wu.ranking_line_lookup(SEASON, WEEK, basis="opener")
    assert lines[5] == 24.5 and kinds[5] == "observed_1h"  # unchanged: first-seen already pre-kick


def test_current_basis_null_start_date_keeps_no_filter(wu):
    """Game 6 has no known start_date — pre_kickoff can't filter without a
    kickoff, so current behaviour (plain latest-by-captured_at) still applies."""
    lines, kinds = wu.ranking_line_lookup(SEASON, WEEK, basis="current")
    assert lines[6] == 15.0 and kinds[6] == "hr_1h"


def test_current_basis_skips_a_game_whose_only_1h_snaps_are_in_play(wu):
    """lines.pre_kickoff returns EVERY snapshot when none is pre-kick (so callers
    with no kickoff still get a consensus). For a game we only ever caught
    in-play that would hand the residual model a LIVE 1H line. With a known
    kickoff and an empty pre-kick subset the 1H market is skipped entirely:
    game 7 falls through to its full-game opener, game 8 has no line at all."""
    lines, kinds = wu.ranking_line_lookup(SEASON, WEEK, basis="current")
    assert lines[7] == proxy_total(54.0, spread=-10.0) and kinds[7] == "derived_fg"
    assert 8 not in lines and 8 not in kinds


def test_opener_basis_unaffected_by_the_in_play_skip(wu):
    """The opener basis never filtered on kickoff and must not start: it reads
    each book's FIRST snapshot, and an opener is pre-kick by construction."""
    lines, kinds = wu.ranking_line_lookup(SEASON, WEEK, basis="opener")
    assert lines[7] == 13.0 and kinds[7] == "observed_1h"  # median(13.5, 12.5)


def test_unknown_basis_raises(wu):
    with pytest.raises(ValueError):
        wu.ranking_line_lookup(SEASON, WEEK, basis="closing")


@pytest.mark.parametrize(
    "basis,engine,expected",
    [
        ("auto", "residual", "current"),
        ("auto", "bv_line", "opener"),
        ("opener", "residual", "opener"),
        ("current", "bv_line", "current"),
    ],
)
def test_resolve_basis(wu, basis, engine, expected):
    assert wu.resolve_basis(basis, engine) == expected


# --- main(): engine-aware wiring --------------------------------------------------


def _frame() -> pd.DataFrame:
    """Two played training seasons (ids 100..103) + one 2026 wk5 target row."""
    return pd.DataFrame(
        {
            "id": [100, 101, 102, 103, 1],
            "season": [2024, 2024, 2025, 2025, SEASON],
            "week": [3, 4, 3, 4, WEEK],
            "start_date": [
                KICK - timedelta(days=700),
                KICK - timedelta(days=693),
                KICK - timedelta(days=365),
                pd.NaT,
                KICK,
            ],
            "full_game_total": [50.0, 48.0, 52.0, 46.0, 50.5],
            "first_half_total": [24.0, 20.0, 27.0, 19.0, None],
            "h_games_played": [5, 5, 5, 5, 5],
            "a_games_played": [5, 5, 5, 5, 5],
        }
    )


def _wire(monkeypatch, wu, engine: str, argv_extra=()):
    monkeypatch.setattr(wu, "try_init_db", lambda: True)
    monkeypatch.setattr(wu, "detect_week", lambda season: WEEK)
    monkeypatch.setattr(wu, "build_feature_frame", lambda min_games=0: _frame())
    monkeypatch.setattr(wu, "engine_name", lambda: engine)
    monkeypatch.setattr(wu, "_enrich_qb_out", lambda scored: None)
    monkeypatch.setattr(wu, "store_predictions", lambda scored: len(scored))
    got = {}

    def fake_lookup(season, week, basis="opener"):
        got["basis"] = basis
        return {1: 25.0}, {1: "hr_1h"}

    def fake_real_closes(session, game_ids, kickoffs, market="1H_total", within_hours=None):
        got["close_args"] = (sorted(game_ids), dict(kickoffs), market, within_hours)
        return {gid: 22.5 for gid in game_ids}

    def fake_score(
        season, target_week=None, line_lookup=None, line_kind_lookup=None, df=None, **kw
    ):
        got["score"] = dict(kw, line_lookup=line_lookup, line_kind_lookup=line_kind_lookup)
        return pd.DataFrame(
            {
                "id": [1],
                "rank": [1],
                "under_score": [55],
                "away_team": ["A1"],
                "home_team": ["H1"],
                "line": [25.0],
            }
        )

    monkeypatch.setattr(wu, "ranking_line_lookup", fake_lookup)
    monkeypatch.setattr(wu, "real_closes", fake_real_closes)
    monkeypatch.setattr(wu, "score_slate", fake_score)
    monkeypatch.setattr(sys, "argv", ["weekly_update.py", "--season", str(SEASON), *argv_extra])
    return got


def test_main_residual_fetches_training_closes_and_uses_current_basis(monkeypatch, wu, capsys):
    got = _wire(monkeypatch, wu, "residual")
    wu.main()
    assert got["basis"] == "current"
    ids, kickoffs, market, within = got["close_args"]
    assert ids == [100, 101, 102]  # training rows (season < 2026) with a known kickoff
    assert 103 not in kickoffs and 1 not in ids  # NaT kickoff dropped; target never queried
    assert market == "1H_total" and within == wu.REAL_1H_CLOSE_WINDOW_H
    assert got["score"]["engine"] == "residual"
    assert got["score"]["real_closes"] == {100: 22.5, 101: 22.5, 102: 22.5}
    assert got["score"]["line_kind_lookup"] == {1: "hr_1h"}
    out = capsys.readouterr().out
    assert "engine=residual basis=current train_rows_with_close=3" in out
    assert "1 Hard Rock 1H" in out


def test_main_bv_line_does_not_touch_closes(monkeypatch, wu, capsys):
    got = _wire(monkeypatch, wu, "bv_line")
    wu.main()
    assert got["basis"] == "opener"
    assert "close_args" not in got  # no real_closes query for the incumbent
    assert got["score"]["engine"] == "bv_line"
    assert got["score"]["real_closes"] is None
    assert "engine=bv_line basis=opener train_rows_with_close=0" in capsys.readouterr().out


def test_main_prints_actual_train_rows_not_all_fetched_closes(monkeypatch, wu, capsys):
    """training_real_closes fetches closes off the PRE-apply_min_games frame,
    but score_slate's residual branch trains on the post-filter frame — so the
    rows it actually fit on can be fewer than len(closes). The summary line
    must report what score_slate says it trained on (its fingerprint's
    n_rows), not the wider close count, when that's available."""
    _wire(monkeypatch, wu, "residual")

    def fake_score_fewer_rows(
        season, target_week=None, line_lookup=None, line_kind_lookup=None, df=None, **kw
    ):
        out = pd.DataFrame(
            {
                "id": [1],
                "rank": [1],
                "under_score": [55],
                "away_team": ["A1"],
                "home_team": ["H1"],
                "line": [25.0],
            }
        )
        # real_closes handed 3 rows (100, 101, 102); the residual branch's
        # min-games/training cut only kept 2 of them.
        out.attrs["engine_artifact"] = {"fingerprint": {"n_rows": 2}}
        return out

    monkeypatch.setattr(wu, "score_slate", fake_score_fewer_rows)
    wu.main()
    out = capsys.readouterr().out
    assert "train_rows_with_close=2" in out
    assert "train_rows_with_close=3" not in out


def test_main_line_basis_flag_overrides_auto(monkeypatch, wu):
    got = _wire(monkeypatch, wu, "bv_line", argv_extra=("--line-basis", "current"))
    wu.main()
    assert got["basis"] == "current"
