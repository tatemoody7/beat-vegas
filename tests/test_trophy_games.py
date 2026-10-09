"""The trophy-game list behind `rivalry_game` (Tate's call, 2026-10-09), the
per-game conference flag, the pace backfill's as-of date and the model's inputs
after the leak fix (strategic review topic 3)."""

import json
from datetime import datetime

import pandas as pd

from beatvegas.etl import trophy_games as T
from beatvegas.etl.features import LEAKY_WEATHER_COLS
from beatvegas.etl.situational import _revenge_and_rivalry, same_conference
from beatvegas.model.bv_line import BV_FEATURE_COLS

WIKI = """intro
<!-- example: {{Trophy game|[[game]]|[[trophy]]|[[teama]]|[[teamb]]|1|2|3}} -->
==NCAA Division I Football Bowl Subdivision==
{{Start trophy game list}}
{{Trophy game|[[Paul Bunyan's Axe|Minnesota–Wisconsin]]|[[Paul Bunyan's Axe]]|[[Minnesota Golden Gophers football|Minnesota]]|[[Wisconsin Badgers football|Wisconsin]]|1890|2025|135}}
{{Trophy game|[[The Game (rivalry)|The Game]]||[[Michigan Wolverines football|Michigan]]|[[Ohio State Buckeyes football|Ohio State]]|1897|2025|121}}
{{Trophy game|Hawaii–SJSU|[[Dick Tomey Legacy Trophy]]|[[Hawaii Rainbow Warriors football|Hawaii]]|[[San Jose State Spartans football|San Jose State]]|1936|2025|45}}
{| class="wikitable sortable"
!Series
!Trophy
!Teams
!First meeting
|-
|
|[[Commander-in-Chief's Trophy]]
|[[Air Force Falcons football|Air Force]], [[Army Black Knights football|Army]], [[Navy Midshipmen football|Navy]]
|1972
|-
|
|[[Beehive Boot]]
|[[BYU Cougars football|BYU]], [[Utah Utes football|Utah]] (previously [[Weber State Wildcats football|Weber State]])
|1971
|-
|[[Tobacco Road (rivalry)|Tobacco Road]]
|
|[[Duke Blue Devils football|Duke]], [[North Carolina Tar Heels football|North Carolina]]
|1924
|}
==NCAA Division I Football Championship Subdivision==
{{Trophy game|x|[[Brice–Cowell Musket]]|[[Maine Black Bears football|Maine]]|[[New Hampshire Wildcats football|New Hampshire]]|1903|2025|115}}
==Rivalries involving FBS and FCS teams==
{{Trophy game|x|[[Some Cup]]|[[Navy Midshipmen football|Navy]]|[[Villanova Wildcats football|Villanova]]|1|2|3}}
==NCAA Division II==
{{Trophy game|x|[[Other Cup]]|[[Army Black Knights football|Army]]|[[Navy Midshipmen football|Navy]]|1|2|3}}
"""

SCHOOLS = {
    "Minnesota",
    "Wisconsin",
    "Michigan",
    "Ohio State",
    "Hawai'i",
    "San José State",
    "Air Force",
    "Army",
    "Navy",
    "BYU",
    "Utah",
    "Duke",
    "North Carolina",
}


def test_parse_keeps_only_filled_trophy_cells_in_the_fbs_sections():
    rows = T.parse_wikitext(WIKI)
    trophies = sorted(r["trophy"] for r in rows)
    assert trophies == [
        "Beehive Boot",
        "Commander-in-Chief's Trophy",
        "Dick Tomey Legacy Trophy",
        "Paul Bunyan's Axe",
        "Some Cup",
    ]  # no The Game (no trophy), no Tobacco Road, no FCS-only, no Division II, no comment


def test_pairs_map_names_expand_multi_team_trophies_and_drop_previous_teams():
    pairs, unmapped = T.pairs_from_rows(T.parse_wikitext(WIKI), SCHOOLS)
    got = {frozenset(p["teams"]) for p in pairs}
    assert frozenset(("Hawai'i", "San José State")) in got
    assert {frozenset(("Army", "Navy")), frozenset(("Air Force", "Army"))} <= got
    assert frozenset(("Air Force", "Navy")) in got and frozenset(("BYU", "Utah")) in got
    assert frozenset(("Michigan", "Ohio State")) not in got
    assert unmapped == ["Villanova"]  # Weber State was "previously": dropped, not unmapped


def test_the_frozen_list_is_pinned_and_holds_known_pairs():
    data = json.loads(T.DATA.read_text())
    assert data["revid"] == 1379225783 and data["frozen"] == "2026-10-09"
    pairs = T.load_pairs()
    assert len(pairs) == len(data["pairs"]) == 112
    for a, b in [("Minnesota", "Wisconsin"), ("Army", "Navy"), ("Iowa", "Iowa State")]:
        assert frozenset((a, b)) in pairs
    assert frozenset(("Michigan", "Ohio State")) not in pairs
    fbs = json.loads((T.DATA.parent / "fbs_teams.json").read_text())
    schools = {x if isinstance(x, str) else x.get("school") for ts in fbs.values() for x in ts}
    assert all(set(p) <= schools for p in pairs)


def _games(rows):
    return pd.DataFrame(
        rows,
        columns=[
            "id",
            "season",
            "start_date",
            "home_team",
            "away_team",
            "home_points",
            "away_points",
        ],
    )


def test_rivalry_flag_is_the_trophy_list_and_never_reads_later_meetings():
    pairs = {frozenset(("A", "B"))}
    early = [
        (1, 2003, datetime(2003, 9, 1), "A", "B", 20, 10),
        (2, 2003, datetime(2003, 9, 8), "C", "D", 7, 3),
    ]
    alone = _revenge_and_rivalry(_games(early), pairs).set_index("id")["rivalry_game"]
    # C and D meet in eight later seasons: under the old rule that made game 2 a rivalry
    later = early + [(10 + y, 2004 + y, datetime(2004 + y, 9, 1), "C", "D", 1, 0) for y in range(8)]
    full = _revenge_and_rivalry(_games(later), pairs).set_index("id")["rivalry_game"]
    assert alone.to_dict() == {1: 1, 2: 0}
    assert full.loc[[1, 2]].to_dict() == {1: 1, 2: 0}


def test_conference_game_is_that_seasons_conference_and_never_independents():
    assert same_conference("Big 12", "Big 12") == 1
    assert same_conference("SEC", "Big 12") == 0
    assert same_conference("FBS Independents", "FBS Independents") == 0
    assert same_conference(None, "SEC") == 0 and same_conference(float("nan"), "SEC") == 0


def test_pace_backfill_reads_the_sunday_before_the_weeks_first_kickoff(load_script):
    be = load_script("backfill_enrichment")
    assert be.as_of_sunday(datetime(2025, 9, 4, 22, 0)) == "2025-08-31"  # Thu 6pm ET
    assert be.as_of_sunday(datetime(2025, 9, 7, 3, 59)) == "2025-08-31"  # Sat 11:59pm ET
    assert be.as_of_sunday(datetime(2025, 9, 6, 16, 0)) == "2025-08-31"  # Sat noon ET
    assert be.as_of_sunday(datetime(2025, 9, 7, 17, 0)) == "2025-08-31"  # a Sunday kickoff
    assert be.as_of_sunday(datetime(2025, 9, 2, 0, 0)) == "2025-08-31"  # Mon 8pm ET


def test_the_model_drops_the_kickoff_weather_but_keeps_the_dome_flag():
    assert set(LEAKY_WEATHER_COLS) == {"wx_temp", "wx_wind", "wx_precip"}
    assert not set(LEAKY_WEATHER_COLS) & set(BV_FEATURE_COLS)
    assert "wx_dome" in BV_FEATURE_COLS
    assert {"rivalry_game", "conference_game", "combined_plays"} <= set(BV_FEATURE_COLS)
    assert len(BV_FEATURE_COLS) == 55
