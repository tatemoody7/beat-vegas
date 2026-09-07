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


# --- paid-tier window + universe filters (2026-09: capture EVERY Hard Rock 1H line) ---

from datetime import datetime  # noqa: E402

from beatvegas.sweep import filter_hr_universe, filter_missing_hr, select_window  # noqa: E402

NOW = datetime(2026, 9, 19, 15, 0)  # Sat 11am ET


def test_select_window_days_ahead_and_hours_back():
    events = [
        ev("yesterday", "2026-09-18T15:00:00Z"),
        ev("two-hours-ago", "2026-09-19T13:00:00Z"),
        ev("tonight", "2026-09-19T23:30:00Z"),
        ev("next-week", "2026-09-26T16:00:00Z"),
        ev("no-time", None),
    ]
    got = [e["id"] for e in select_window(events, NOW, days_ahead=3, hours_back=0)]
    assert got == ["tonight", "no-time"]  # unparseable kickoff is kept (matched later)
    got = [e["id"] for e in select_window(events, NOW, days_ahead=3, hours_back=24)]
    assert got == ["yesterday", "two-hours-ago", "tonight", "no-time"]


def test_select_window_kickoff_within_minutes_is_the_close_mode():
    events = [
        ev("kicked-5m-ago", "2026-09-19T14:55:00Z"),
        ev("in-40m", "2026-09-19T15:40:00Z"),
        ev("in-75m", "2026-09-19T16:15:00Z"),
        ev("in-3h", "2026-09-19T18:00:00Z"),
    ]
    got = select_window(events, NOW, days_ahead=6, hours_back=0, kickoff_within_min=75)
    assert [e["id"] for e in got] == ["in-40m", "in-75m"]


def test_filter_missing_hr_drops_games_hard_rock_already_priced():
    events = [ev("a", "t"), ev("b", "t"), ev("c-unmatched", "t")]
    ctx = {"a": {"game_id": 1}, "b": {"game_id": 2}}
    got = filter_missing_hr(events, ctx, games_with_hr_1h={1})
    assert [e["id"] for e in got] == ["b", "c-unmatched"]


def test_filter_hr_universe_keeps_only_hard_rock_priced_games():
    events = [ev("a", "t"), ev("b", "t"), ev("c-unmatched", "t")]
    ctx = {"a": {"game_id": 1}, "b": {"game_id": 2}}
    got, fallback = filter_hr_universe(events, ctx, hr_universe={2})
    assert [e["id"] for e in got] == ["b"] and fallback is False


def test_filter_hr_universe_falls_back_to_everything_when_universe_is_empty():
    """sunday.yml dropped -> no HR full-game rows: sweep everything and warn."""
    events = [ev("a", "t"), ev("c-unmatched", "t")]
    got, fallback = filter_hr_universe(events, {"a": {"game_id": 1}}, hr_universe=set())
    assert [e["id"] for e in got] == ["a", "c-unmatched"] and fallback is True
