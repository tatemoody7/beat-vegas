"""Rotowire injury-report normalization — offline, fixture is a real 2026-09-02
response shape from /cfootball/tables/injury-report.php?league=college."""

from beatvegas.sources import rotowire

ROWS = [
    {
        "ID": "44223",
        "player": "Famah Toure",
        "team": "Rutgers",
        "IR": "Questionable",
        "position": "WR",
        "injury_type": "Knee",
        "RotoSchoolName": "Rutgers",
        "game_datetime": "2026-09-03 18:00:00",
    },
    {
        "ID": "1",
        "player": "Sam Starter",
        "team": "Michigan St.",
        "IR": "Out",
        "position": "QB",
        "injury_type": "Undisclosed",
        "RotoSchoolName": "Michigan St.",
        "game_datetime": "2026-09-05 00:00:00",
    },
    {
        "ID": "2",
        "player": "Backup Guy",
        "team": "Michigan St.",
        "IR": "Probable",
        "position": "QB",
        "injury_type": "Ankle",
        "RotoSchoolName": "Michigan St.",
    },
    {"ID": "3", "player": "Nobody Known", "team": "Podunk Tech", "IR": "Out", "position": "QB"},
]

SCHOOLS = ["Rutgers", "Michigan State", "Michigan", "Ohio State"]


def test_format_entry_matches_the_preview_shape():
    assert rotowire.format_entry(ROWS[0]) == "WR Famah Toure — Questionable (Knee)"
    # 'Undisclosed' adds nothing, so it is dropped
    assert rotowire.format_entry(ROWS[1]) == "QB Sam Starter — Out"


def test_by_school_maps_rotowire_labels_to_our_school_names_and_drops_unknowns():
    grouped = rotowire.by_school(ROWS, SCHOOLS)
    assert set(grouped) == {
        "Rutgers",
        "Michigan State",
    }  # "Michigan St." -> Michigan State, not Michigan
    assert [r["player"] for r in grouped["Michigan State"]] == ["Sam Starter", "Backup Guy"]
    assert "Podunk Tech" not in grouped


def test_qb_out_detail_only_fires_on_out_or_doubtful_qbs():
    grouped = rotowire.by_school(ROWS, SCHOOLS)
    assert rotowire.qb_out_detail(grouped["Michigan State"]) == "QB Sam Starter — Out"
    assert rotowire.qb_out_detail(grouped["Rutgers"]) is None  # WR, not QB
    assert rotowire.qb_out_detail([ROWS[2]]) is None  # Probable QB is not out


def test_fetch_fails_silent(monkeypatch):
    def boom(*a, **k):
        raise rotowire.requests.RequestException("down")

    monkeypatch.setattr(rotowire.requests, "get", boom)
    assert rotowire.fetch_injury_report() == []
