"""DraftKings normalizers: fixture JSON -> rows; garbage/empty -> [] (fail-silent).

Fixture mirrors DK's sportscontent leagues/{id} schema (events / markets /
selections), including the unicode-minus american odds DK actually returns.
"""
from beatvegas.sources.draftkings import normalize_first_half, normalize_full_game

_PAYLOAD = {
    "events": [
        {"id": "100", "name": "Iowa @ Ohio State",
         "startEventDate": "2026-09-05T16:00:00.0000000Z",
         "participants": [
             {"name": "Iowa", "venueRole": "Away"},
             {"name": "Ohio State", "venueRole": "Home"}]},
    ],
    "markets": [
        {"id": "T100", "eventId": "100", "name": "Total", "main": True},
        {"id": "S100", "eventId": "100", "name": "Spread", "main": True},
        {"id": "H100", "eventId": "100", "name": "1st Half Total", "main": True},
        {"id": "Talt", "eventId": "100", "name": "Total", "main": False},  # alt line
    ],
    "selections": [
        {"marketId": "T100", "outcomeType": "Over", "points": 55.5,
         "displayOdds": {"american": "−110"}},
        {"marketId": "T100", "outcomeType": "Under", "points": 55.5,
         "displayOdds": {"american": "−110"}},
        {"marketId": "S100", "outcomeType": "Away", "points": 17.0,
         "displayOdds": {"american": "−110"}},
        {"marketId": "S100", "outcomeType": "Home", "points": -17.0,
         "displayOdds": {"american": "−110"}},
        {"marketId": "H100", "outcomeType": "Over", "points": 28.5,
         "displayOdds": {"american": "−105"}},
        {"marketId": "H100", "outcomeType": "Under", "points": 28.5,
         "displayOdds": {"american": "−115"}},
        {"marketId": "Talt", "outcomeType": "Over", "points": 60.5,
         "displayOdds": {"american": "+100"}},
    ],
}


def test_normalize_full_game_total_and_spread():
    rows = normalize_full_game(_PAYLOAD)
    assert len(rows) == 1                       # main total only, not the alt line
    r = rows[0]
    assert r["book"] == "draftkings"
    assert r["line"] == 55.5
    assert r["spread"] == -17.0                 # home (Ohio State) favored by 17
    assert r["home_team"] == "Ohio State"
    assert r["away_team"] == "Iowa"
    assert r["over_price"] == -110 and r["under_price"] == -110


def test_normalize_first_half_only_1h_total():
    rows = normalize_first_half(_PAYLOAD)
    assert len(rows) == 1
    r = rows[0]
    assert r["line"] == 28.5
    assert r["over_price"] == -105 and r["under_price"] == -115
    assert "spread" not in r                    # 1H rows match odds.py shape


def test_first_half_total_excluded_from_full_game():
    # The 28.5 1H total must NOT leak into the full-game set (only the 55.5 main).
    assert {r["line"] for r in normalize_full_game(_PAYLOAD)} == {55.5}


def test_empty_and_garbage_fail_silent():
    assert normalize_full_game({}) == []
    assert normalize_first_half({}) == []
    assert normalize_full_game({"junk": 1}) == []
    assert normalize_full_game({"events": [], "markets": [], "selections": []}) == []
