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
        s.get(Game, 1).full_game_total = 50.5  # -> total_band "45–52" chip
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
        # 5: qualifies (gap 2.0) but Hard Rock's -125 fails the price gate -> EDGE [price]
        s.add(_game(5, "Iowa", "Nebraska", kick + timedelta(hours=2)))
        s.add(_snap(5, "hardrockbet", "full_game_total", 44.5, hours_ago=100))
        s.add(_snap(5, "hardrockbet", "1H_total", 24.5, -110, -125))
        s.add(_snap(5, "draftkings", "1H_total", 24.5, 100, -120))
        s.add(_snap(5, "fanduel", "1H_total", 24.5, 100, -120))
        for gid, bv in ((1, 22.4), (2, 24.0), (3, 22.4), (4, 20.0), (5, 22.5)):
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


def test_card_row_written_and_every_qualifying_game_becomes_a_paper_pick(env):
    mod, eng = env
    seed_week(eng)
    assert mod.run(SEASON, WEEK, dry_run=False, now=NOW) == 0

    with Session(eng) as s:
        (row,) = s.query(Card).all()
        picks = s.query(ManualPick).order_by(ManualPick.game_id).all()
    assert (row.season, row.week, row.built_at) == (SEASON, WEEK, NOW)
    payload = json.loads(row.payload)
    assert payload["season"] == SEASON and payload["week"] == WEEK
    assert payload["counts"] == {"bet": 1, "edge": 2, "pass": 1, "over_cap": 0}
    assert payload["paper"] == {"qualifying": 2, "over_cap": 0, "cap": 5}
    ids = [it["game_id"] for it in payload["items"]]
    # BET; EDGE by gap (3: 2.6 no_hr_line, 5: 2.0 price); PASS. Outside-universe 4 dropped.
    assert ids == [1, 3, 5, 2] and 4 not in ids
    by_id = {it["game_id"]: it for it in payload["items"]}
    assert by_id[1]["tier"] == "BET" and by_id[1]["paper_logged"] is True
    assert by_id[1]["cap_rank"] == 1 and by_id[1]["total_band"] == "45–52"
    assert by_id[5]["tier"] == "EDGE" and by_id[5]["blocker"] == "price"
    assert by_id[5]["qualifies"] is True and by_id[5]["paper_logged"] is True
    assert by_id[3]["paper_logged"] is False  # no Hard Rock line: nothing to log
    assert by_id[2]["paper_logged"] is False  # gap 0.5: does not qualify

    p, q = picks
    assert p.game_id == 1 and p.is_paper is True and p.stake == 1.0
    assert p.market == "1H" and p.side == "under" and p.book == "hardrockbet"
    assert p.line == 24.5 and p.price == -110
    assert p.reason == "model_gap" and p.verdict_at_pick == "BET" and p.blocker == "none"
    assert p.gap_at_pick == 2.1 and p.hr_line_at_pick == 24.5 and p.ev_at_pick is not None
    assert p.season == SEASON and p.week == WEEK and p.placed_at == NOW
    assert p.home_team == "Missouri" and p.away_team == "Kansas"
    assert p.note.startswith("card 2026-09-18 [none]: Bet now")
    chips = json.loads(p.factors_json_at_pick)
    assert chips["total_band"] == "45–52" and chips["hook_side"] == "key+0.5"
    assert chips["tier"] == "BET" and chips["cap_rank"] == 1

    assert q.game_id == 5 and q.is_paper is True and q.blocker == "price"
    assert q.verdict_at_pick == "WATCH" and q.price == -125 and q.gap_at_pick == 2.0
    assert q.note.startswith("card 2026-09-18 [price]: Wait: Hard Rock is -125")


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
    assert n_picks == 2  # the BET and the price-blocked qualifier, once each
    assert json.loads(cards[1].payload)["items"][0]["paper_logged"] is True


def test_a_real_ticket_and_the_paper_pick_coexist_on_one_game(env):
    """Per-ledger guard: Tate's real bet must not stop the card's paper record,
    and (the important direction) the card's paper pick must not block his
    real ticket — the paper ledger now logs every qualifying game."""
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
                verdict_at_pick="BET",
                placed_at=NOW - timedelta(hours=1),
            )
        )
        s.commit()
    assert mod.run(SEASON, WEEK, dry_run=False, now=NOW) == 0
    with Session(eng) as s:
        picks = s.query(ManualPick).filter(ManualPick.game_id == 1).order_by(ManualPick.id).all()
        (row,) = s.query(Card).all()
    assert [p.is_paper for p in picks] == [False, True]
    assert json.loads(row.payload)["items"][0]["paper_logged"] is True


def test_paper_window_skips_games_kicking_off_later(env):
    """The Friday preview logs only Friday-night games (--paper-log-window-hours 6)."""
    mod, eng = env
    seed_week(eng)  # everything kicks off ~24h out
    assert mod.run(SEASON, WEEK, dry_run=False, now=NOW, paper_window_hours=6) == 0
    with Session(eng) as s:
        assert s.query(ManualPick).count() == 0
    assert mod.run(SEASON, WEEK, dry_run=False, now=NOW, paper_window_hours=30) == 0
    with Session(eng) as s:
        assert s.query(ManualPick).count() == 2


def test_no_paper_publishes_the_card_without_picks(env):
    mod, eng = env
    seed_week(eng)
    assert mod.run(SEASON, WEEK, dry_run=False, now=NOW, no_paper=True) == 0
    with Session(eng) as s:
        assert s.query(Card).count() == 1 and s.query(ManualPick).count() == 0


def test_sixth_bet_by_gap_is_paper_only_with_blocker_cap(env):
    mod, eng = env
    kick = NOW + timedelta(days=1)
    with Session(eng) as s:
        for gid in range(11, 17):  # six BET games, gaps 3.0 .. 2.5
            s.add(_game(gid, f"A{gid}", f"H{gid}", kick + timedelta(minutes=gid)))
            s.add(_snap(gid, "hardrockbet", "full_game_total", 50.5, hours_ago=100))
            s.add(_snap(gid, "hardrockbet", "1H_total", 24.5, -110, -110))
            s.add(_snap(gid, "draftkings", "1H_total", 24.5, 100, -120))
            s.add(_snap(gid, "fanduel", "1H_total", 24.5, 100, -120))
            s.add(
                Prediction(
                    game_id=gid,
                    model_version="gbm_v1",
                    bv_line=24.5 - (3.0 - 0.1 * (gid - 11)),
                    under_score=55,
                    line_used=24.0,
                    created_at=NOW,
                )
            )
        s.commit()
    assert mod.run(SEASON, WEEK, dry_run=False, now=NOW) == 0
    with Session(eng) as s:
        picks = {p.game_id: p for p in s.query(ManualPick).all()}
        (row,) = s.query(Card).all()
    payload = json.loads(row.payload)
    assert payload["counts"]["bet"] == 5 and payload["counts"]["over_cap"] == 1
    assert payload["paper"]["over_cap"] == 1
    assert picks[16].blocker == "cap" and picks[16].verdict_at_pick == "BET"
    assert all(picks[g].blocker == "none" for g in range(11, 16))
    over = [it for it in payload["items"] if it["over_cap"]]
    assert [it["game_id"] for it in over] == [16] and over[0]["cap_rank"] == 6


def test_a_bet_logged_earlier_in_the_week_holds_its_cap_slot(env):
    """A Thursday BET (smallest gap) already on the ledger is ranked #1 on
    Saturday's build; a new bigger gap does not bump it into paper-only."""
    mod, eng = env
    kick = NOW + timedelta(days=1)
    with Session(eng) as s:
        for gid in range(11, 17):
            s.add(_game(gid, f"A{gid}", f"H{gid}", kick + timedelta(minutes=gid)))
            s.add(_snap(gid, "hardrockbet", "full_game_total", 50.5, hours_ago=100))
            s.add(_snap(gid, "hardrockbet", "1H_total", 24.5, -110, -110))
            s.add(_snap(gid, "draftkings", "1H_total", 24.5, 100, -120))
            s.add(_snap(gid, "fanduel", "1H_total", 24.5, 100, -120))
            s.add(
                Prediction(
                    game_id=gid,
                    model_version="gbm_v1",
                    bv_line=24.5 - (3.0 - 0.1 * (gid - 11)),
                    under_score=55,
                    line_used=24.0,
                    created_at=NOW,
                )
            )
        s.add(
            ManualPick(
                game_id=16,
                season=SEASON,
                week=WEEK,
                side="under",
                market="1H",
                line=24.5,
                price=-110,
                stake=1.0,
                is_paper=True,
                verdict_at_pick="BET",
                blocker="none",
                placed_at=NOW - timedelta(days=2),
            )
        )
        s.commit()
    assert mod.run(SEASON, WEEK, dry_run=False, now=NOW) == 0
    with Session(eng) as s:
        (row,) = s.query(Card).all()
        p15 = s.query(ManualPick).filter(ManualPick.game_id == 15).one()
    by_id = {it["game_id"]: it for it in json.loads(row.payload)["items"]}
    assert by_id[16]["cap_rank"] == 1 and by_id[16]["over_cap"] is False
    assert by_id[15]["cap_rank"] == 6 and by_id[15]["over_cap"] is True and p15.blocker == "cap"


def test_dry_run_writes_nothing(env, capsys):
    mod, eng = env
    seed_week(eng)
    assert mod.run(SEASON, WEEK, dry_run=True, now=NOW) == 0
    with Session(eng) as s:
        assert s.query(Card).count() == 0 and s.query(ManualPick).count() == 0
    out = capsys.readouterr().out
    assert "1 BET / 2 EDGE / 1 PASS" in out and '"tier": "BET"' in out


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
    assert "**1 BET · 2 EDGE · 1 PASS**" in text
    assert (
        "- Bet now: 1H under 24.5 at -110 on Hard Rock. (Kansas @ Missouri)"
        " | kill: below u24.5 or worse than -120" in text
    )


def test_cards_table_is_created_by_create_all():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    from sqlalchemy import inspect

    cols = {c["name"] for c in inspect(eng).get_columns("cards")}
    assert cols == {"id", "season", "week", "built_at", "payload"}
    idx = {i["name"]: i["column_names"] for i in inspect(eng).get_indexes("cards")}
    assert idx["ix_cards_season_week_built"] == ["season", "week", "built_at"]
