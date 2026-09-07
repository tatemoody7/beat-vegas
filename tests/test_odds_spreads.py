"""Odds API bulk /odds now carries `spreads` alongside `totals`: the home-relative
spread rides on each (event, book) full-game row instead of being None."""

from beatvegas.sources.odds import _home_spreads, normalize_full_game


def _spreads_mkt(home, away, home_pt=None, away_pt=None, last_update=None):
    outcomes = []
    if home_pt is not None:
        outcomes.append({"name": home, "price": -110, "point": home_pt})
    if away_pt is not None:
        outcomes.append({"name": away, "price": -110, "point": away_pt})
    mkt = {"key": "spreads", "outcomes": outcomes}
    if last_update:
        mkt["last_update"] = last_update
    return mkt


def _totals_mkt(point, last_update=None):
    mkt = {
        "key": "totals",
        "outcomes": [
            {"name": "Over", "price": -110, "point": point},
            {"name": "Under", "price": -110, "point": point},
        ],
    }
    if last_update:
        mkt["last_update"] = last_update
    return mkt


def _event(bookmakers, eid="evt1", home="LSU", away="Clemson"):
    return {
        "id": eid,
        "commence_time": "2026-08-30T16:00:00Z",
        "home_team": home,
        "away_team": away,
        "bookmakers": bookmakers,
    }


def test_home_spreads_picks_the_home_outcome():
    ev = _event([{"key": "draftkings", "markets": [_spreads_mkt("LSU", "Clemson", -3.5, 3.5)]}])
    assert _home_spreads([ev]) == {("evt1", "draftkings"): -3.5}


def test_home_spreads_negates_an_away_only_outcome():
    ev = _event([{"key": "draftkings", "markets": [_spreads_mkt("LSU", "Clemson", None, 7.0)]}])
    assert _home_spreads([ev]) == {("evt1", "draftkings"): -7.0}


def test_home_spreads_keeps_the_freshest_duplicate():
    ev = _event(
        [
            {
                "key": "fanduel",
                "markets": [_spreads_mkt("LSU", "Clemson", -3.0, 3.0, "2026-09-02T01:30:00Z")],
            },
            {
                "key": "fanduel",
                "markets": [_spreads_mkt("LSU", "Clemson", -3.5, 3.5, "2026-09-02T01:35:00Z")],
            },
        ]
    )
    assert _home_spreads([ev]) == {("evt1", "fanduel"): -3.5}


def test_home_spreads_folds_hardrockbet_fl_onto_hardrockbet():
    ev = _event([{"key": "hardrockbet_fl", "markets": [_spreads_mkt("LSU", "Clemson", -4.0)]}])
    assert _home_spreads([ev]) == {("evt1", "hardrockbet"): -4.0}


def test_home_spreads_ignores_books_without_a_spreads_market():
    ev = _event([{"key": "draftkings", "markets": [_totals_mkt(56.5)]}])
    assert _home_spreads([ev]) == {}


def test_home_spreads_skips_a_malformed_point_but_keeps_the_rest():
    ev = _event(
        [
            {"key": "draftkings", "markets": [_spreads_mkt("LSU", "Clemson", "bad", "bad")]},
            {"key": "fanduel", "markets": [_spreads_mkt("LSU", "Clemson", -3.5, 3.5)]},
        ]
    )
    assert _home_spreads([ev]) == {("evt1", "fanduel"): -3.5}


def test_normalize_full_game_carries_spread_per_book():
    ev = _event(
        [
            {
                "key": "hardrockbet_fl",
                "markets": [_totals_mkt(56.5), _spreads_mkt("LSU", "Clemson", -4.0, 4.0)],
            },
            {
                "key": "draftkings",
                "markets": [_totals_mkt(57.0), _spreads_mkt("LSU", "Clemson", -3.5, 3.5)],
            },
            {"key": "fanduel", "markets": [_totals_mkt(57.5)]},  # totals only, no spread
        ]
    )
    rows = normalize_full_game([ev])
    by_book = {r["book"]: r for r in rows}
    assert set(by_book) == {"hardrockbet", "draftkings", "fanduel"}
    assert by_book["hardrockbet"]["spread"] == -4.0
    assert by_book["draftkings"]["spread"] == -3.5
    assert by_book["fanduel"]["spread"] is None  # book posted no spreads market
    assert by_book["fanduel"]["line"] == 57.5
