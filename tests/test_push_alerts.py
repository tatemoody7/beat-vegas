"""Hard Rock 'lines dropped' detection + cloud push sender (fail-silent)."""

from beatvegas.alerts.detect import (
    detect_first_half_posted,
    detect_full_game_posted,
    format_posted_summary,
)
from beatvegas.alerts.push import send_push


def test_detect_full_game_posted_first_appearance_only():
    prev = {10}  # game 10 already had a HR line
    new = {10: 55.5, 11: 48.0, 12: 61.5}
    matchups = {11: "Baylor @ Auburn", 12: "Iowa @ Iowa St"}
    alerts = detect_full_game_posted(prev, new, matchups)
    gids = {a.game_id for a in alerts}
    assert gids == {11, 12}  # 10 suppressed (already seen)
    assert all(a.market == "full_game" and a.book == "hardrockbet" for a in alerts)
    assert {a.line for a in alerts} == {48.0, 61.5}


def test_detect_skips_none_lines():
    alerts = detect_full_game_posted(set(), {1: None, 2: 50.0}, {2: "X @ Y"})
    assert [a.game_id for a in alerts] == [2]


def test_detect_first_half_market_label():
    alerts = detect_first_half_posted(set(), {3: 27.5}, {3: "A @ B"})
    assert alerts[0].market == "1H"


def test_format_posted_summary_truncates():
    alerts = detect_full_game_posted(
        set(),
        {1: 50.0, 2: 51.0, 3: 52.0, 4: 53.0},
        {1: "A @ B", 2: "C @ D", 3: "E @ F", 4: "G @ H"},
    )
    msg = format_posted_summary(alerts)
    assert "Hard Rock full-game lines are LIVE" in msg
    assert "4 games" in msg
    assert "+1 more" in msg  # only first 3 sampled


def test_format_posted_summary_empty_is_none():
    assert format_posted_summary([]) is None


def test_send_push_unconfigured_is_fail_silent(monkeypatch):
    # No creds in env and (likely) none in example config -> returns (False, reason),
    # never raises. Force a clean provider with no token so it can't actually send.
    monkeypatch.delenv("PUSHOVER_TOKEN", raising=False)
    monkeypatch.delenv("PUSHOVER_USER", raising=False)
    import beatvegas.alerts.push as push

    monkeypatch.setattr(push, "_push_cfg", lambda: {"provider": "pushover", "pushover": {}})
    ok, detail = send_push("t", "b")
    assert ok is False
    assert "configured" in detail


def test_send_push_unknown_provider(monkeypatch):
    import beatvegas.alerts.push as push

    monkeypatch.setattr(push, "_push_cfg", lambda: {"provider": "smoke-signal"})
    ok, detail = push.send_push("t", "b")
    assert ok is False and "unknown push provider" in detail
