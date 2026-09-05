"""scripts/build_card.py against a throwaway SQLite DB: the cards row lands,
BET items become PAPER picks exactly once, and the exit code is honest."""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest
from conftest import _load_script
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from beatvegas.db.models import Base, Card, Game, GamePreview, ManualPick, OddsSnapshot, Prediction

NOW = datetime(2026, 9, 18, 22, 5)
SEASON, WEEK = 2026, 3


def _snap(gid, book, market, line, over=-110, under=-110, hours_ago=2.0):
    return OddsSnapshot(
        game_id=gid,
        book=book,
        market=market,
        line=line,
        over_price=over,
        under_price=under,
        captured_at=NOW - timedelta(hours=hours_ago),
    )


def _game(gid, away, home, kick):
    return Game(id=gid, season=SEASON, week=WEEK, away_team=away, home_team=home, start_date=kick)


@pytest.fixture
def env():
    """(module, engine): the script bound to a fresh in-memory SQLite DB."""
    mod = _load_script("build_card")
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)

    @contextmanager
    def scope():
        with Session(eng) as s:
            yield s
            s.commit()

    mod.session_scope = scope
    return mod, eng


def seed_week(eng, *, kick_offset=timedelta(days=1)):
    """Three Hard Rock-universe games: a BET, a PASS and a no-HR-line game; a
    fourth game Hard Rock has not priced (outside the universe)."""
    kick = NOW + kick_offset
    with Session(eng) as s:
        s.add_all(
            [
                _game(1, "Kansas", "Missouri", kick),
                _game(2, "Kansas State", "Florida", kick + timedelta(hours=3)),
                _game(3, "Toledo", "Akron", kick + timedelta(hours=1)),
                _game(4, "Nobody", "Noone", kick),
            ]
        )
        for gid in (1, 2, 3):
            s.add(_snap(gid, "hardrockbet", "full_game_total", 50.5, hours_ago=100))
        # 1: BET (HR 24.5 -110 vs a market shaded to the under, bv 22.4 -> gap 2.1)
        s.add(_snap(1, "hardrockbet", "1H_total", 24.0, hours_ago=6))
        s.add(_snap(1, "hardrockbet", "1H_total", 24.5, -110, -110))
        s.add(_snap(1, "draftkings", "1H_total", 24.5, 100, -120))
        s.add(_snap(1, "fanduel", "1H_total", 24.5, 100, -120))
        # 2: PASS (gap 0.5)
        s.add(_snap(2, "hardrockbet", "1H_total", 24.5))
        s.add(_snap(2, "draftkings", "1H_total", 24.5, 100, -120))
        # 3: EDGE no_hr_line (market 25.0, bv 22.4)
        s.add(_snap(3, "draftkings", "1H_total", 25.0))
        s.add(_snap(3, "fanduel", "1H_total", 25.0))
        # 4 would be a BET but Hard Rock has no full-game total on it
        s.add(_snap(4, "draftkings", "1H_total", 25.0))
        for gid, bv in ((1, 22.4), (2, 24.0), (3, 22.4), (4, 20.0)):
            s.add(
                Prediction(
                    game_id=gid,
                    model_version="gbm_v1",
                    bv_line=bv,
                    under_score=55,
                    line_used=24.0,
                    created_at=NOW,
                )
            )
        s.add(GamePreview(game_id=2, season=SEASON, week=WEEK, qb_out=False, updated_at=NOW))
        s.commit()


def test_card_row_written_and_bet_becomes_one_paper_pick(env):
    mod, eng = env
    seed_week(eng)
    assert mod.run(SEASON, WEEK, dry_run=False, now=NOW) == 0

    with Session(eng) as s:
        (row,) = s.query(Card).all()
        picks = s.query(ManualPick).all()
    assert (row.season, row.week, row.built_at) == (SEASON, WEEK, NOW)
    payload = json.loads(row.payload)
    assert payload["season"] == SEASON and payload["week"] == WEEK
    assert payload["counts"] == {"bet": 1, "edge": 1, "pass": 1}
    ids = [it["game_id"] for it in payload["items"]]
    assert ids == [1, 3, 2] and 4 not in ids  # BET, EDGE, PASS; outside-universe dropped
    bet = payload["items"][0]
    assert bet["tier"] == "BET" and bet["paper_logged"] is True
    assert all(it["paper_logged"] is False for it in payload["items"][1:])

    (p,) = picks
    assert p.game_id == 1 and p.is_paper is True and p.stake == 1.0
    assert p.market == "1H" and p.side == "under" and p.book == "hardrockbet"
    assert p.line == 24.5 and p.price == -110
    assert p.reason == "model_gap" and p.verdict_at_pick == "BET"
    assert p.gap_at_pick == 2.1 and p.hr_line_at_pick == 24.5 and p.ev_at_pick is not None
    assert p.season == SEASON and p.week == WEEK and p.placed_at == NOW
    assert p.home_team == "Missouri" and p.away_team == "Kansas"
    assert p.note.startswith("card 2026-09-18: Bet now")


def test_rerun_adds_a_card_row_but_never_a_second_pick(env):
    mod, eng = env
    seed_week(eng)
    assert mod.run(SEASON, WEEK, dry_run=False, now=NOW) == 0
    later = NOW + timedelta(hours=17)  # the Saturday 11am refresh
    assert mod.run(SEASON, WEEK, dry_run=False, now=later) == 0
    with Session(eng) as s:
        cards = s.query(Card).order_by(Card.built_at).all()
        n_picks = s.query(ManualPick).count()
    assert [c.built_at for c in cards] == [NOW, later]
    assert n_picks == 1
    assert json.loads(cards[1].payload)["items"][0]["paper_logged"] is True


def test_an_existing_real_pick_blocks_the_paper_pick(env):
    mod, eng = env
    seed_week(eng)
    with Session(eng) as s:
        s.add(
            ManualPick(
                game_id=1,
                season=SEASON,
                week=WEEK,
                side="under",
                market="1H",
                line=24.5,
                price=-105,
                stake=1.0,
                is_paper=False,
                placed_at=NOW - timedelta(hours=1),
            )
        )
        s.commit()
    assert mod.run(SEASON, WEEK, dry_run=False, now=NOW) == 0
    with Session(eng) as s:
        picks = s.query(ManualPick).all()
        (row,) = s.query(Card).all()
    assert len(picks) == 1 and picks[0].is_paper is False
    assert json.loads(row.payload)["items"][0]["paper_logged"] is True


def test_dry_run_writes_nothing(env, capsys):
    mod, eng = env
    seed_week(eng)
    assert mod.run(SEASON, WEEK, dry_run=True, now=NOW) == 0
    with Session(eng) as s:
        assert s.query(Card).count() == 0 and s.query(ManualPick).count() == 0
    out = capsys.readouterr().out
    assert "1 BET / 1 EDGE / 1 PASS" in out and '"tier": "BET"' in out


def test_exit_1_when_universe_has_games_but_all_kicked_off(env):
    mod, eng = env
    seed_week(eng, kick_offset=-timedelta(hours=5))
    assert mod.run(SEASON, WEEK, dry_run=False, now=NOW) == 1
    with Session(eng) as s:
        assert s.query(Card).count() == 0 and s.query(ManualPick).count() == 0


def test_exit_0_when_hard_rock_universe_is_empty(env):
    mod, eng = env
    with Session(eng) as s:
        s.add(_game(9, "A", "B", NOW + timedelta(days=1)))
        s.add(_snap(9, "draftkings", "1H_total", 25.0))
        s.commit()
    assert mod.run(SEASON, WEEK, dry_run=False, now=NOW) == 0
    with Session(eng) as s:
        assert s.query(Card).count() == 0


def test_step_summary_lists_the_bets(env, tmp_path, monkeypatch):
    mod, eng = env
    seed_week(eng)
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert mod.run(SEASON, WEEK, dry_run=False, now=NOW) == 0
    text = summary.read_text()
    assert "## Bet card 2026 wk3" in text
    assert "**1 BET · 1 EDGE · 1 PASS**" in text
    assert "- Bet now: 1H under 24.5 at -110 on Hard Rock. (Kansas @ Missouri)" in text


def test_cards_table_is_created_by_create_all():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    from sqlalchemy import inspect

    cols = {c["name"] for c in inspect(eng).get_columns("cards")}
    assert cols == {"id", "season", "week", "built_at", "payload"}
    idx = {i["name"]: i["column_names"] for i in inspect(eng).get_indexes("cards")}
    assert idx["ix_cards_season_week_built"] == ["season", "week", "built_at"]
