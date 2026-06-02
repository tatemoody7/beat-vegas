from beatvegas.sources.teamrankings import _expand, map_to_cfbd

CFBD = ["South Florida", "Ohio State", "Michigan State", "Massachusetts",
        "Central Michigan", "Appalachian State", "Miami", "Alabama"]


def test_expand_abbreviations():
    assert _expand("S Florida") == "South Florida"
    assert _expand("Ohio St") == "Ohio State"
    assert _expand("C Michigan") == "Central Michigan"


def test_expand_aliases():
    assert _expand("UMass") == "Massachusetts"
    assert _expand("App State") == "Appalachian State"


def test_map_to_cfbd_resolves_abbrevs_and_aliases():
    # inputs mirror real TeamRankings naming (abbreviations + aliases)
    m = map_to_cfbd(["S Florida", "Ohio St", "UMass", "Alabama"], CFBD)
    assert m["S Florida"] == "South Florida"
    assert m["Ohio St"] == "Ohio State"
    assert m["UMass"] == "Massachusetts"
    assert m["Alabama"] == "Alabama"


def test_map_returns_none_for_unknown():
    m = map_to_cfbd(["Nonexistent Tech"], CFBD)
    assert m["Nonexistent Tech"] is None
