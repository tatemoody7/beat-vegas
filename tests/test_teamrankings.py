from beatvegas.sources.teamrankings import _expand, map_to_cfbd

CFBD = [
    "South Florida",
    "Ohio State",
    "Michigan State",
    "Massachusetts",
    "Central Michigan",
    "Appalachian State",
    "Miami",
    "Alabama",
]


def test_expand_abbreviations():
    assert _expand("S Florida") == "South Florida"
    assert _expand("Ohio St") == "Ohio State"
    assert _expand("C Michigan") == "Central Michigan"


def test_expand_aliases():
    assert _expand("UMass") == "Massachusetts"
    assert _expand("App State") == "App State"


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


# Real CFBD names. "Kansas" is listed BEFORE "Kansas State" on purpose: the old
# mapper scored both 1.0 for "Kansas St" and kept the first one scanned.
FBS = [
    "App State",
    "Coastal Carolina",
    "Florida",
    "Florida International",
    "Georgia",
    "Georgia Southern",
    "Georgia State",
    "James Madison",
    "Kansas",
    "Kansas State",
    "Louisiana",
    "Louisiana Tech",
    "Miami",
    "Miami (OH)",
    "Middle Tennessee",
    "Mississippi State",
    "Northern Illinois",
    "Ole Miss",
    "San Diego State",
    "San José State",
    "Southern Miss",
    "Texas",
    "Texas State",
    "Texas Tech",
]


def test_map_prefers_exact_expanded_name_over_prefix_school():
    m = map_to_cfbd(
        ["Kansas St", "Kansas", "Texas Tech", "Texas St", "Texas", "Louisiana Tech"], FBS
    )
    assert m["Kansas St"] == "Kansas State"
    assert m["Kansas"] == "Kansas"
    assert m["Texas Tech"] == "Texas Tech"
    assert m["Texas St"] == "Texas State"
    assert m["Texas"] == "Texas"
    assert m["Louisiana Tech"] == "Louisiana Tech"


def test_map_ole_miss_and_mississippi_state_do_not_collide():
    m = map_to_cfbd(["Mississippi", "Mississippi St"], FBS)
    assert m["Mississippi"] == "Ole Miss"
    assert m["Mississippi St"] == "Mississippi State"


def test_map_irregular_teamrankings_abbreviations():
    names = [
        "Miami OH",
        "Miami (OH)",
        "Miami (FL)",
        "San Jose St",
        "Georgia So",
        "Georgia St",
        "Coastal Car",
        "Middle Tenn",
        "J Madison",
        "N Illinois",
        "Florida Intl",
        "San Diego St",
        "App State",
        "Southern Miss",
    ]
    m = map_to_cfbd(names, FBS)
    assert m["Miami OH"] == "Miami (OH)"
    assert m["Miami (OH)"] == "Miami (OH)"
    assert m["Miami (FL)"] == "Miami"
    assert m["San Jose St"] == "San José State"
    assert m["Georgia So"] == "Georgia Southern"
    assert m["Georgia St"] == "Georgia State"
    assert m["Coastal Car"] == "Coastal Carolina"
    assert m["Middle Tenn"] == "Middle Tennessee"
    assert m["J Madison"] == "James Madison"
    assert m["N Illinois"] == "Northern Illinois"
    assert m["Florida Intl"] == "Florida International"
    assert m["San Diego St"] == "San Diego State"
    assert m["App State"] == "App State"
    assert m["Southern Miss"] == "Southern Miss"


def test_map_never_collapses_two_teamrankings_names_onto_one_school():
    names = [
        "Kansas",
        "Kansas St",
        "Texas",
        "Texas Tech",
        "Texas St",
        "Georgia",
        "Georgia So",
        "Georgia St",
        "Florida",
        "Florida Intl",
        "Louisiana",
        "Louisiana Tech",
        "Mississippi",
        "Mississippi St",
        "Miami (FL)",
        "Miami (OH)",
    ]
    mapped = [v for v in map_to_cfbd(names, FBS).values() if v]
    assert len(mapped) == len(names)
    assert len(set(mapped)) == len(mapped)
