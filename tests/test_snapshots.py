"""beatvegas/snapshots.py -- one row per (build, game) off the cards payloads, with
the realized first half and both closes attached, builds kept apart."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from beatvegas import snapshots as S
from beatvegas.db.models import Card, Game, OddsSnapshot
from tests.conftest import _sqlite_scope

KICK = datetime(2026, 9, 12, 19, 30)


def _item(gid, tier="BET", hr_line=44.5, **kw):
    it = {
        "game_id": gid,
        "away": "A",
        "home": "H",
        "kick": KICK.isoformat(),
        "tier": tier,
        "blocker": None,
        "hr_line": hr_line,
        "hr_price": -112,
        "hr_open": 45.0,
        "market_line": 44.5,
        "gap": 2.1,
        "bv_line": 42.4,
        "qualifies": tier == "BET",
        "over_cap": False,
    }
    it.update(kw)
    return it


def _seed(session):
    session.add(
        Game(
            id=1,
            season=2026,
            week=2,
            start_date=KICK,
            home_team="H",
            away_team="A",
            home_points=30,
            away_points=20,
            first_half_total=24,
            first_half_source="pbp",
        )
    )
    session.add(Game(id=2, season=2026, week=2, start_date=KICK, home_team="H2", away_team="A2"))
    # Hard Rock's own close (strict centring) and two other books for the consensus.
    for book, line, at in (
        ("hardrockbet", 44.0, KICK - timedelta(hours=1)),
        ("draftkings", 43.5, KICK - timedelta(hours=1)),
        ("fanduel", 43.5, KICK - timedelta(minutes=50)),
    ):
        session.add(
            OddsSnapshot(
                game_id=1,
                market="1H_total",
                book=book,
                line=line,
                over_price=-110,
                under_price=-110,
                captured_at=at,
            )
        )
    fri = {
        "season": 2026,
        "week": 2,
        "slot": "fri_pm",
        "status": "final",
        "items": [_item(1), _item(2, tier="PASS", hr_line=None)],
    }
    sat = {
        "season": 2026,
        "week": 2,
        "slot": "sat_am",
        "status": "final",
        "items": [_item(1, hr_line=44.5, qb_out=False)],
    }
    session.add(
        Card(season=2026, week=2, built_at=KICK - timedelta(days=1), payload=json.dumps(fri))
    )
    session.add(
        Card(season=2026, week=2, built_at=KICK - timedelta(hours=7), payload=json.dumps(sat))
    )
    session.commit()


def test_build_rows_keeps_every_build_and_attaches_closes_and_the_result():
    eng, scope = _sqlite_scope()
    with Session(eng) as s:
        _seed(s)
    with scope() as s:
        df = S.build_rows(s, 2026)
    assert len(df) == 3  # two Friday items + one Saturday item; builds not collapsed
    g1 = df[df.game_id == 1].sort_values("built_at")
    assert list(g1.slot) == ["fri_pm", "sat_am"]
    assert list(g1.schedule) == ["four", "four"]
    assert g1.hours_to_kick.round(1).tolist() == [24.0, 7.0]
    assert g1.fh.tolist() == [24.0, 24.0]
    assert g1.hr_close.tolist() == [44.0, 44.0]
    assert g1.close_line.tolist() == [43.5, 43.5]  # median of the last centred quotes
    # a field the older build never carried is None, never inferred
    assert g1.qb_out.tolist()[0] is None and g1.qb_out.tolist()[1] is False
    g2 = df[df.game_id == 2].iloc[0]
    assert g2.tier == "PASS" and g2.fh != g2.fh and g2.hr_close != g2.hr_close  # NaN


def test_schedule_labels_are_honest_about_legacy_names():
    assert S.schedule_of("fri_pm") == "four"
    assert S.schedule_of("morning") == "legacy" and S.schedule_of("afternoon") == "legacy"
    assert S.schedule_of(None) == "daily"
    assert S.schedule_of("manual") == "manual"


def test_build_rows_is_empty_with_columns_when_the_season_has_no_cards():
    eng, scope = _sqlite_scope()
    with scope() as s:
        df = S.build_rows(s, 2031)
    assert df.empty and "hr_close" in df.columns and "slot" in df.columns
