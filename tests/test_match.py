from datetime import datetime

from beatvegas.etl.match import _norm, match_event, name_score, resolve_game
from beatvegas.sources.odds import normalize_first_half

GAMES = [
    {
        "id": 1,
        "home_team": "Ohio State",
        "away_team": "Michigan",
        "start_date": datetime(2024, 11, 30, 17, 0),
    },
    {
        "id": 2,
        "home_team": "Louisiana",
        "away_team": "Louisiana Tech",
        "start_date": datetime(2024, 11, 30, 20, 0),
    },
    {
        "id": 3,
        "home_team": "Texas A&M",
        "away_team": "LSU",
        "start_date": datetime(2024, 11, 30, 23, 30),
    },
]


def test_norm():
    assert _norm("Texas A&M") == "texas aandm"
    assert _norm("Miami (OH)") == "miami oh"


def test_basic_match_with_mascots():
    gid, score = match_event(
        "Ohio State Buckeyes", "Michigan Wolverines", "2024-11-30T17:00:00Z", GAMES
    )
    assert gid == 1 and score > 1.6


def test_disambiguates_louisiana_vs_louisiana_tech():
    # "Louisiana" must not greedily grab "Louisiana Tech".
    gid, _ = match_event(
        "Louisiana Ragin' Cajuns", "Louisiana Tech Bulldogs", "2024-11-30T20:00:00Z", GAMES
    )
    assert gid == 2


def test_neutral_site_orientation_swap():
    # Odds API lists the CFBD away team as home — should still match game 3.
    gid, _ = match_event("LSU Tigers", "Texas A&M Aggies", "2024-11-30T23:30:00Z", GAMES)
    assert gid == 3


def test_date_window_excludes_far_games():
    gid, _ = match_event(
        "Ohio State Buckeyes", "Michigan Wolverines", "2024-10-01T17:00:00Z", GAMES
    )
    assert gid is None


def test_no_match_returns_none():
    gid, score = match_event(
        "Alabama Crimson Tide", "Georgia Bulldogs", "2024-11-30T17:00:00Z", GAMES
    )
    assert gid is None and score == 0.0


def test_name_score_appended_mascot():
    assert name_score("Ohio State", "Ohio State Buckeyes") > 0.9


# --- resolve_game (manual-pick name resolution) ------------------------
RGAMES = [
    {"id": 1, "week": 9, "home_team": "Ohio State", "away_team": "Penn State"},
    {"id": 2, "week": 13, "home_team": "Michigan", "away_team": "Ohio State"},
    {"id": 3, "week": 7, "home_team": "Alabama", "away_team": "LSU"},
]


def test_resolve_simple_nickname():
    # "Bama" ≈ 0.727 vs "Alabama" — must clear the 0.72 floor.
    gid, _, n, _ = resolve_game("Bama", "LSU", RGAMES)
    assert gid == 3 and n == 1


def test_resolve_orientation_agnostic():
    # typed home/away reversed from CFBD storage still resolves
    gid, _, _, _ = resolve_game("LSU", "Alabama", RGAMES)
    assert gid == 3


def test_resolve_ambiguous_then_week():
    # Ohio State appears in two games -> ambiguous without a week
    gid, _, n, _ = resolve_game("Ohio State", "Penn State", RGAMES)
    assert gid == 1  # only game 1 has both teams
    # Both Ohio State games would match a vague query; week pins it.
    gid2, _, n2, _ = resolve_game("Ohio State", "Michigan", RGAMES, week=13)
    assert gid2 == 2 and n2 == 1


def test_resolve_no_match():
    gid, score, n, cands = resolve_game("Oregon", "Washington", RGAMES)
    assert gid is None and n == 0 and cands == []


def test_resolve_rejects_loose_partial_match():
    # "Pitt" vs a fabricated "Pittsford" style loose overlap: anything scoring
    # in the old 0.6-0.72 band must no longer attach. "Alaba" vs "Alabama"
    # scores ~0.83 (fine); "Ala" vs "Alabama" ~0.6 (rejected).
    gid, _, n, _ = resolve_game("Ala", "LSU", RGAMES)
    assert gid is None and n == 0


def test_resolve_rematch_returns_candidates():
    games = RGAMES + [{"id": 4, "week": 15, "home_team": "Ohio State", "away_team": "Michigan"}]
    gid, _, n, cands = resolve_game("Ohio State", "Michigan", games)
    assert n == 2
    assert {c["id"] for c in cands} == {2, 4}


def test_parse_dt_converts_non_utc_offsets():
    from beatvegas.etl.match import _parse_dt

    # A +05:00 timestamp must convert to UTC, not just drop the offset.
    assert _parse_dt("2024-11-30T22:00:00+05:00") == datetime(2024, 11, 30, 17, 0)
    assert _parse_dt("2024-11-30T17:00:00Z") == datetime(2024, 11, 30, 17, 0)
    assert _parse_dt("2024-11-30T17:00:00") == datetime(2024, 11, 30, 17, 0)


# --- odds normalizer ---------------------------------------------------
SAMPLE_EVENT = {
    "id": "abc123",
    "commence_time": "2024-11-30T17:00:00Z",
    "home_team": "Ohio State Buckeyes",
    "away_team": "Michigan Wolverines",
    "bookmakers": [
        {
            "key": "draftkings",
            "last_update": "2024-11-29T12:00:00Z",
            "markets": [
                {
                    "key": "totals_h1",
                    "last_update": "2024-11-29T12:00:00Z",
                    "outcomes": [
                        {"name": "Over", "price": -110, "point": 27.5},
                        {"name": "Under", "price": -110, "point": 27.5},
                    ],
                }
            ],
        }
    ],
}


def test_normalize_first_half():
    rows = normalize_first_half([SAMPLE_EVENT])
    assert len(rows) == 1
    r = rows[0]
    assert r["book"] == "draftkings" and r["line"] == 27.5
    assert r["over_price"] == -110 and r["under_price"] == -110
    assert r["home_team"] == "Ohio State Buckeyes"


def test_normalize_book_filter_and_missing_market():
    ev = dict(SAMPLE_EVENT)
    rows = normalize_first_half([ev], books=["fanduel"])
    assert rows == []  # draftkings filtered out
