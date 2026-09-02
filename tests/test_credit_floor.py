"""Odds API credit reserve: one helper on the client (it already tracks the
x-requests-remaining header) shared by poll_lines and poll_full_game, so the
Sunday opener budget can't be spent by a mid-week sweep or vice versa."""

from conftest import _load_script

from beatvegas.sources.odds import Credits, OddsAPIClient


def _client(remaining):
    c = OddsAPIClient(api_key="k")
    c.last_credits = None if remaining is None else Credits(remaining, 10, 1)
    return c


def test_credits_low_helper():
    assert _client(60).credits_low(60) is True
    assert _client(30).credits_low(60) is True
    assert _client(61).credits_low(60) is False
    assert _client(None).credits_low(60) is False  # no call made yet -> unknown, not low
    assert _client(0).credits_low(0) is False  # floor 0 disables the guard
    c = _client(None)
    c.last_credits = Credits(None, None, None)  # headers missing on the response
    assert c.credits_low(60) is False


def test_poll_full_game_oddsapi_skips_paid_call_at_the_floor(monkeypatch, capsys):
    mod = _load_script("poll_full_game")
    paid = []

    class _Client:
        def __init__(self):
            self.last_credits = None

        def list_events(self):  # free; carries the credit headers
            self.last_credits = Credits(remaining=40, used=460, last_cost=0)
            return []

        def credits_low(self, floor):
            return OddsAPIClient.credits_low(self, floor)

        def list_full_game_totals(self, regions=None):
            paid.append(regions)
            return [{"id": "e1", "bookmakers": []}]

    monkeypatch.setattr(mod, "OddsAPIClient", _Client)
    fg, h1, source, n = mod._fetch("oddsapi", 2026, credit_floor=60)
    assert (fg, h1, source, n) == ([], [], "oddsapi", 0)
    assert paid == []  # the paid bulk call never happened
    assert "[credits]" in capsys.readouterr().out

    # Above the floor (or floor disabled) the paid call goes through.
    fg, _, source, n = mod._fetch("oddsapi", 2026, credit_floor=30)
    assert source == "oddsapi" and n == 1 and paid == ["us,us2"]
    mod._fetch("oddsapi", 2026, credit_floor=0)
    assert len(paid) == 2


def test_poll_full_game_has_credit_floor_flag():
    import sys

    mod = _load_script("poll_full_game")
    captured = {}

    def fake_fetch(source, season, regions="us,us2", credit_floor=60):
        captured["credit_floor"] = credit_floor
        raise SystemExit(0)  # stop before any DB write

    monkeypatch_args = ["poll_full_game.py", "--source", "oddsapi", "--credit-floor", "75"]
    old = sys.argv
    sys.argv = monkeypatch_args
    try:
        mod._fetch = fake_fetch
        mod.try_init_db = lambda: True
        try:
            mod.main()
        except SystemExit:
            pass
    finally:
        sys.argv = old
    assert captured["credit_floor"] == 75
