"""The challenger family against a real database: does a build actually log it,
and does it stay out of the money ledger?

The unit tests pin the arithmetic and grep for isolation. This one runs the real
`log_challenger_picks` through the real `build_card` against real tables, because
the failure that would matter most -- a challenger row landing somewhere the
bankroll or H-STOP can see -- is invisible to both of those.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import text

from beatvegas.challenger import PAPER_ARMS, arm_label
from beatvegas.db.models import ChallengerPick, Game, ManualPick, OddsSnapshot, Prediction
from beatvegas.model.score import MODEL_VERSION

SEASON, WEEK = 2026, 9
NOW = datetime(2026, 10, 24, 20, 0, 0)
C_PRIOR = -1.8


def _clean(store):
    with store.get_engine().begin() as conn:
        conn.execute(
            text(
                "TRUNCATE challenger_picks, manual_picks, odds_snapshots, "
                "predictions, games RESTART IDENTITY CASCADE"
            )
        )


def _completed_game(s, gid: int, kick: datetime, bv_line: float, actual: int):
    """A finished game the arms may learn from: it kicked off before the build
    and its first half is on file."""
    s.add(
        Game(
            id=gid,
            season=SEASON,
            week=WEEK - 1,
            start_date=kick,
            home_team=f"H{gid}",
            away_team=f"A{gid}",
            home_points=30,
            away_points=20,
            first_half_total=actual,
            first_half_source="pbp",
        )
    )
    s.add(
        Prediction(
            game_id=gid,
            model_version=MODEL_VERSION,
            bv_line=bv_line,
            bv_intercept=C_PRIOR,
            under_score=60,
            line_used=bv_line,
            rank=1,
        )
    )


@pytest.fixture
def slate(pg_sandbox):
    """A week with 40 completed games the model read LOW on, and one upcoming
    game Hard Rock has priced far enough above our number that every arm still
    qualifies after lifting its line."""
    store = pg_sandbox
    _clean(store)
    kick = NOW + timedelta(hours=20)
    with store.session_scope() as s:
        for i in range(40):
            # realized 28 against a calibrated 24 (raw 25.8), so the season says
            # the model reads ~2.2 points low and every arm lifts its number --
            # k25 most, k200 least.
            _completed_game(s, 1000 + i, NOW - timedelta(days=7), bv_line=24.0, actual=28)
        s.add(
            Game(
                id=9001,
                season=SEASON,
                week=WEEK,
                start_date=kick,
                home_team="Home",
                away_team="Away",
                full_game_total=52.0,
                spread=-3.0,
            )
        )
        s.add(
            Prediction(
                game_id=9001,
                model_version=MODEL_VERSION,
                bv_line=24.0,
                bv_intercept=C_PRIOR,
                under_score=75,
                line_used=30.0,
                rank=1,
            )
        )
        for book in ("hardrockbet", "draftkings", "betmgm"):
            s.add(
                OddsSnapshot(
                    game_id=9001,
                    book=book,
                    market="1H_total",
                    line=30.0,
                    over_price=-110,
                    under_price=-110,
                    captured_at=NOW - timedelta(hours=1),
                )
            )
    yield store, kick
    _clean(store)


def _build(store, kick):
    from scripts.build_card import load_inputs, log_challenger_picks

    games = [
        {
            "game_id": 9001,
            "away": "Away",
            "home": "Home",
            "kick": kick,
            "total": 52.0,
            "spread": -3.0,
        }
    ]
    with store.session_scope() as s:
        snaps, preds, previews = load_inputs(s, [9001])
        return log_challenger_picks(
            s,
            games=games,
            snaps=snaps,
            preds=preds,
            previews=previews,
            season=SEASON,
            week=WEEK,
            now=NOW,
            slot="fri_pm",
            held=set(),
            real=set(),
            degraded=[],
            window_hours=None,
        )


def test_a_build_logs_one_observation_per_arm_and_nothing_to_the_money_ledger(slate):
    store, kick = slate
    added = _build(store, kick)
    assert set(added) == {arm_label(k) for k in PAPER_ARMS}
    assert sum(added.values()) == len(PAPER_ARMS), added

    with store.session_scope() as s:
        rows = s.query(ChallengerPick).all()
        assert len(rows) == len(PAPER_ARMS)
        # THE point of the separate table.
        assert s.query(ManualPick).count() == 0

        by_arm = {r.arm: r for r in rows}
        for r in rows:
            assert r.line == 30.0 and r.price == -110 and r.book == "hardrockbet"
            assert r.stake == 1.0 and r.graded is False
            assert r.c_prior == pytest.approx(C_PRIOR)
            assert r.in_season_n == 40
            assert r.champion_line_at_pick == pytest.approx(24.0)

        # The season read is the same for every arm; only the weight differs, so
        # a smaller k must trust it more and land further from the champion.
        assert by_arm["k25"].in_season_weight > by_arm["k200"].in_season_weight
        assert by_arm["k25"].arm_line_at_pick > by_arm["k200"].arm_line_at_pick
        # The model read low, so every arm lifts its number above the champion's
        # and therefore sees a SMALLER gap than the champion did.
        for r in rows:
            assert r.arm_line_at_pick > 24.0
            assert r.gap_at_pick < 30.0 - 24.0


def test_the_same_build_twice_logs_each_arm_once(slate):
    """One canonical observation per decision per arm."""
    store, kick = slate
    _build(store, kick)
    again = _build(store, kick)
    assert sum(again.values()) == 0
    with store.session_scope() as s:
        assert s.query(ChallengerPick).count() == len(PAPER_ARMS)


def test_a_game_completing_later_cannot_change_an_already_logged_observation(slate):
    """The as-of window is the build's own past, and a logged pick is frozen."""
    store, kick = slate
    _build(store, kick)
    with store.session_scope() as s:
        before = {r.arm: r.arm_line_at_pick for r in s.query(ChallengerPick).all()}
        # 20 more results land after the build.
        for i in range(20):
            _completed_game(s, 2000 + i, NOW - timedelta(days=1), bv_line=24.0, actual=40)
    _build(store, kick)
    with store.session_scope() as s:
        after = {r.arm: r.arm_line_at_pick for r in s.query(ChallengerPick).all()}
    assert after == before


def test_the_arms_grade_with_the_champions_grader(slate):
    store, kick = slate
    _build(store, kick)
    with store.session_scope() as s:
        g = s.query(Game).filter(Game.id == 9001).one()
        g.home_points, g.away_points = 21, 10
        g.first_half_total = 17  # under 30 -> every arm wins
        g.first_half_source = "pbp"
        # A pre-kickoff close the CLV comes from. It has to move on EVERY book:
        # the closing line is the market consensus median, never one book's
        # number (Hard Rock posts an off-centre rung on most late quotes).
        for book in ("hardrockbet", "draftkings", "betmgm"):
            s.add(
                OddsSnapshot(
                    game_id=9001,
                    book=book,
                    market="1H_total",
                    line=29.0,
                    over_price=-110,
                    under_price=-110,
                    captured_at=kick - timedelta(minutes=30),
                )
            )

    from beatvegas.challenger_picks import grade_challenger_picks

    with store.session_scope() as s:
        n = grade_challenger_picks(s, SEASON)
    assert n == len(PAPER_ARMS)

    with store.session_scope() as s:
        for r in s.query(ChallengerPick).all():
            assert r.graded is True
            assert r.result == "under"
            assert r.units == pytest.approx(1.0 * (100 / 110), abs=1e-6)
            assert r.actual_first_half_total == 17
            # Stored clv is closing - bet; the line FELL, which for an under is
            # the favourable direction, so the stored value is negative.
            assert r.clv is not None and r.clv < 0
