"""The full-game SIDE markets (roadmap step 4, 2026-10-07): each book's spread
and moneyline become their own rows with both teams' prices, picked by the
same honesty rules the totals parser uses."""

from beatvegas.sources.odds import SIDE_MARKETS, normalize_full_game_sides

HOME, AWAY = "LSU", "Clemson"


def _oc(name, price, point=None):
    oc = {"name": name, "price": price}
    if point is not None:
        oc["point"] = point
    return oc


def _mkt(key, outcomes, last_update=None):
    m = {"key": key, "outcomes": outcomes}
    if last_update:
        m["last_update"] = last_update
    return m


def _event(bookmakers, eid="evt1"):
    return {
        "id": eid,
        "commence_time": "2026-10-10T16:00:00Z",
        "home_team": HOME,
        "away_team": AWAY,
        "bookmakers": bookmakers,
    }


def _rows(bookmakers):
    return {(r["book"], r["market"]): r for r in normalize_full_game_sides([_event(bookmakers)])}


def test_side_markets_map_to_their_snapshot_markets():
    assert SIDE_MARKETS == {"spreads": "full_game_spread", "h2h": "full_game_ml"}


def test_spread_and_moneyline_rows_carry_both_prices():
    bm = {
        "key": "draftkings",
        "markets": [
            _mkt("spreads", [_oc(HOME, -115, -7.5), _oc(AWAY, -105, 7.5)]),
            _mkt("h2h", [_oc(HOME, -300), _oc(AWAY, 240)]),
            _mkt("totals", [_oc("Over", -110, 55.5), _oc("Under", -110, 55.5)]),
        ],
    }
    rows = _rows([bm])
    assert set(rows) == {("draftkings", "full_game_spread"), ("draftkings", "full_game_ml")}
    sp = rows[("draftkings", "full_game_spread")]
    assert (sp["line"], sp["home_price"], sp["away_price"]) == (-7.5, -115, -105)
    ml = rows[("draftkings", "full_game_ml")]
    assert (ml["line"], ml["home_price"], ml["away_price"]) == (None, -300, 240)
    assert sp["event_id"] == "evt1" and sp["home_team"] == HOME and sp["away_team"] == AWAY


def test_a_spread_ladder_keeps_the_most_balanced_pair(capsys):
    bm = {
        "key": "fanduel",
        "markets": [
            _mkt(
                "spreads",
                [
                    _oc(HOME, -180, -3.5),
                    _oc(AWAY, 150, 3.5),
                    _oc(HOME, -110, -7.0),
                    _oc(AWAY, -110, 7.0),
                    _oc(HOME, 140, -10.5),
                    _oc(AWAY, -170, 10.5),
                ],
            )
        ],
    }
    sp = _rows([bm])[("fanduel", "full_game_spread")]
    assert (sp["line"], sp["home_price"], sp["away_price"]) == (-7.0, -110, -110)
    assert "3 spreads point pairs" in capsys.readouterr().out


def test_away_only_spread_is_negated_to_the_home_line():
    bm = {"key": "betmgm", "markets": [_mkt("spreads", [_oc(AWAY, -110, 6.5)])]}
    sp = _rows([bm])[("betmgm", "full_game_spread")]
    assert (sp["line"], sp["home_price"], sp["away_price"]) == (-6.5, None, -110)


def test_unmirrored_spread_points_are_rungs_and_skipped():
    """A home -7.5 and an away +6.5 are two different lines; pairing their
    prices would invent a quote, so the book yields no spread row."""
    bm = {
        "key": "betrivers",
        "markets": [_mkt("spreads", [_oc(HOME, -110, -7.5), _oc(AWAY, -110, 6.5)])],
    }
    assert _rows([bm]) == {}


def test_moneyline_with_one_side_keeps_it_and_an_empty_market_is_skipped():
    one = {"key": "espnbet", "markets": [_mkt("h2h", [_oc(AWAY, 240)])]}
    none = {"key": "fliff", "markets": [_mkt("h2h", [_oc("Draw", 900)])]}
    rows = _rows([one, none])
    ml = rows[("espnbet", "full_game_ml")]
    assert (ml["home_price"], ml["away_price"]) == (None, 240)
    assert ("fliff", "full_game_ml") not in rows


def test_a_book_listed_twice_keeps_the_freshest_quote_and_the_hard_rock_key_folds():
    """Two regions can list one book twice; the newer last_update wins, and
    hardrockbet_fl folds into the canonical hardrockbet key."""
    old = {
        "key": "hardrockbet",
        "markets": [_mkt("h2h", [_oc(HOME, -300), _oc(AWAY, 240)], "2026-10-10T10:00:00Z")],
    }
    new = {
        "key": "hardrockbet_fl",
        "markets": [_mkt("h2h", [_oc(HOME, -280), _oc(AWAY, 225)], "2026-10-10T11:00:00Z")],
    }
    rows = normalize_full_game_sides([_event([old, new])])
    assert len(rows) == 1
    r = rows[0]
    assert r["book"] == "hardrockbet" and (r["home_price"], r["away_price"]) == (-280, 225)
    assert r["last_update"] == "2026-10-10T11:00:00Z"


def test_book_filter_and_malformed_points():
    bms = [
        {"key": "draftkings", "markets": [_mkt("spreads", [_oc(HOME, -110, "bad")])]},
        {"key": "caesars", "markets": [_mkt("spreads", [_oc(HOME, -110, -3), _oc(AWAY, -110, 3)])]},
    ]
    assert normalize_full_game_sides([_event(bms)], books=["draftkings"]) == []
    rows = normalize_full_game_sides([_event(bms)])
    assert [(r["book"], r["line"]) for r in rows] == [("caesars", -3.0)]
