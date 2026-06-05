"""CFBD /lines fallback: provider-priority pick + rows shaped like the DK path."""

from beatvegas.sources.cfbd_lines import (
    full_game_rows,
    open_close_lookup,
    pick_open_close,
    pick_total_spread,
)


def test_pick_total_spread_provider_priority():
    lines = [
        {"provider": "Bovada", "overUnder": 49.0, "spread": -6.0},
        {"provider": "DraftKings", "overUnder": 50.5, "spread": -10.5},
        {"provider": "consensus", "overUnder": 50.0, "spread": -9.5},
    ]
    ou, sp, prov = pick_total_spread(lines)
    assert (ou, sp, prov) == (50.0, -9.5, "consensus")  # consensus wins priority


def test_pick_total_spread_empty():
    assert pick_total_spread([]) == (None, None, None)
    assert pick_total_spread([{"provider": "X"}]) == (None, None, None)  # no total


class _FakeClient:
    def lines(self, year, season_type="regular"):
        return [
            {
                "id": 5,
                "homeTeam": "LSU",
                "awayTeam": "Clemson",
                "startDate": "2026-08-30T16:00:00Z",
                "lines": [{"provider": "DraftKings", "overUnder": 50.5, "spread": -10.5}],
            },
            {"id": 6, "homeTeam": "X", "awayTeam": "Y", "lines": []},  # no total -> dropped
        ]


def test_full_game_rows_shape_and_id():
    rows = full_game_rows(_FakeClient(), 2026)
    assert len(rows) == 1  # game 6 dropped (no total)
    r = rows[0]
    assert r["game_id"] == 5  # CFBD id == Game.id
    assert r["home_team"] == "LSU" and r["away_team"] == "Clemson"
    assert r["line"] == 50.5 and r["spread"] == -10.5
    assert r["over_price"] is None and r["under_price"] is None
    # same keys the DK full-game normalizer emits, so poll_full_game consumes both
    for k in ("event_id", "commence_time", "book", "line", "spread"):
        assert k in r


def test_pick_open_close_priority_and_open_fallback():
    lines = [
        {"provider": "Bovada", "overUnderOpen": 48.0, "overUnder": 49.0},
        {"provider": "consensus", "overUnder": 50.0},  # no opener -> backfills from close
    ]
    o, c, prov = pick_open_close(lines)
    assert (o, c, prov) == (50.0, 50.0, "consensus")  # consensus wins; open falls back to close


def test_pick_open_close_empty():
    assert pick_open_close([]) == (None, None, None)
    assert pick_open_close([{"provider": "X"}]) == (None, None, None)  # no totals at all


class _FakeOpenClose:
    def lines(self, year, season_type="regular"):
        return [
            {"id": 7, "lines": [{"provider": "DraftKings", "overUnderOpen": 55.5, "overUnder": 54.0}]},
            {"id": 8, "lines": []},  # no total -> omitted
        ]


def test_open_close_lookup_keys_by_game_id():
    lk = open_close_lookup(_FakeOpenClose(), 2026)
    assert set(lk) == {7}  # game 8 omitted (no total)
    assert lk[7] == (55.5, 54.0, "DraftKings")  # opener, close, provider
