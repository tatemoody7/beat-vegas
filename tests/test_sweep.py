"""Friday 1H sweep ordering: the per-event budget must go to the games the card
can actually bet, not to whichever kick off first."""

from beatvegas.sweep import build_context, rank_events


def ev(eid, t, home="H", away="A"):
    return {"id": eid, "commence_time": t, "home_team": home, "away_team": away}


def test_rank_puts_bettable_spread_games_ahead_of_earlier_kickoffs():
    events = [
        ev("early-blowout", "2026-09-05T16:00:00Z"),
        ev("night-close", "2026-09-05T23:30:00Z"),
    ]
    ctx = {
        "early-blowout": {"spread": 31.5, "dome": False, "pace": 28.9},
        "night-close": {"spread": 10.5, "dome": False, "pace": 27.7},
    }
    assert [e["id"] for e in rank_events(events, ctx)] == ["night-close", "early-blowout"]


def test_rank_puts_unmatched_events_last():
    events = [ev("unknown", "2026-09-05T16:00:00Z"), ev("known", "2026-09-05T20:00:00Z")]
    ctx = {"known": {"spread": 7.0, "dome": False, "pace": None}}
    assert [e["id"] for e in rank_events(events, ctx)] == ["known", "unknown"]


def test_rank_prefers_outdoor_over_dome_at_equal_spread_band():
    events = [ev("dome", "2026-09-05T16:00:00Z"), ev("outdoor", "2026-09-05T20:00:00Z")]
    ctx = {
        "dome": {"spread": 7.0, "dome": True, "pace": 26.0},
        "outdoor": {"spread": 7.5, "dome": False, "pace": 26.0},
    }
    assert [e["id"] for e in rank_events(events, ctx)] == ["outdoor", "dome"]


def test_rank_prefers_slower_pace_then_kickoff_order():
    events = [
        ev("fast", "2026-09-05T16:00:00Z"),
        ev("slow", "2026-09-05T20:00:00Z"),
        ev("nopace-early", "2026-09-05T16:00:00Z"),
        ev("nopace-late", "2026-09-05T23:00:00Z"),
    ]
    ctx = {
        "fast": {"spread": 3.0, "dome": False, "pace": 24.2},
        "slow": {"spread": 3.0, "dome": False, "pace": 29.2},
        "nopace-early": {"spread": 3.0, "dome": False, "pace": None},
        "nopace-late": {"spread": 3.0, "dome": False, "pace": None},
    }
    assert [e["id"] for e in rank_events(events, ctx)] == [
        "slow",
        "fast",
        "nopace-early",
        "nopace-late",
    ]


def test_rank_spread_band_order_is_close_then_wide_then_unknown():
    events = [
        ev("no-spread", "2026-09-05T16:00:00Z"),
        ev("wide", "2026-09-05T17:00:00Z"),
        ev("close", "2026-09-05T18:00:00Z"),
    ]
    ctx = {
        "no-spread": {"spread": None, "dome": False, "pace": 27.0},
        "wide": {"spread": -20.5, "dome": False, "pace": 27.0},
        "close": {"spread": -14.0, "dome": False, "pace": 27.0},
    }
    assert [e["id"] for e in rank_events(events, ctx)] == ["close", "wide", "no-spread"]


def test_build_context_joins_spread_dome_and_mean_pace_via_event_match():
    events = [
        ev("e1", "2026-09-05T23:30:00Z", home="LSU Tigers", away="Clemson Tigers"),
        ev("e2", "2026-09-05T16:00:00Z", home="Nowhere State", away="Nobody Tech"),
    ]
    games = [
        {
            "id": 1,
            "home_team": "LSU",
            "away_team": "Clemson",
            "start_date": "2026-09-05T23:30:00",
            "spread": 10.5,
        }
    ]
    dome_by_game = {1: False}
    pace_by_team = {"LSU": 28.0, "Clemson": 27.4}
    ctx = build_context(events, games, dome_by_game, pace_by_team)
    assert ctx["e1"] == {"game_id": 1, "spread": 10.5, "dome": False, "pace": 27.7}
    assert "e2" not in ctx


def test_build_context_pace_is_none_when_either_team_lacks_tempo():
    events = [ev("e1", "2026-09-05T23:30:00Z", home="LSU Tigers", away="Clemson Tigers")]
    games = [
        {
            "id": 1,
            "home_team": "LSU",
            "away_team": "Clemson",
            "start_date": "2026-09-05T23:30:00",
            "spread": None,
        }
    ]
    ctx = build_context(events, games, {}, {"LSU": 28.0})
    assert ctx["e1"] == {"game_id": 1, "spread": None, "dome": None, "pace": None}


def test_latest_pace_by_team_skips_null_current_week_and_uses_last_real_value():
    from beatvegas.sweep import latest_pace_by_team

    rows = [
        (2026, 1, "LSU", None),  # week 1: season not started, TeamRankings blank
        (2025, 16, "LSU", 27.7),
        (2025, 15, "LSU", 27.9),
        (2024, 16, "LSU", 26.0),
        (2025, 16, "Clemson", 27.6),
        (2026, 1, "Clemson", None),
    ]
    assert latest_pace_by_team(rows) == {"LSU": 27.7, "Clemson": 27.6}
