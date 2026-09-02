"""weekly_update._enrich_qb_out: QB-out flags come from ONE Rotowire report call
(ESPN publishes no college injuries), matched to the slate's school names the
same way scripts/research_preview.py does. Offline: the report is mocked."""

import pandas as pd
from conftest import _load_script

REPORT = [
    {
        "player": "Sam Starter",
        "team": "Michigan St.",
        "IR": "Out",
        "position": "QB",
        "injury_type": "Undisclosed",
        "RotoSchoolName": "Michigan St.",
    },
    {
        "player": "Famah Toure",
        "team": "Rutgers",
        "IR": "Questionable",
        "position": "WR",
        "injury_type": "Knee",
        "RotoSchoolName": "Rutgers",
    },
    {
        "player": "Healthy Guy",
        "team": "Ohio State",
        "IR": "Probable",
        "position": "QB",
        "injury_type": "Ankle",
        "RotoSchoolName": "Ohio State",
    },
]


def _slate() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"game_id": 1, "home_team": "Michigan State", "away_team": "Rutgers"},
            {"game_id": 2, "home_team": "Ohio State", "away_team": "Michigan"},
        ]
    )


def test_enrich_qb_out_flags_from_rotowire(monkeypatch, capsys):
    wu = _load_script("weekly_update")
    calls = []

    def fake_report(timeout=15):
        calls.append(1)
        return REPORT

    monkeypatch.setattr(wu.rotowire, "fetch_injury_report", fake_report)
    scored = _slate()
    wu._enrich_qb_out(scored)

    assert len(calls) == 1  # one report call for the whole slate
    by_gid = scored.set_index("game_id")
    assert bool(by_gid.loc[1, "qb_out_home"]) is True  # Michigan St. -> Michigan State
    assert bool(by_gid.loc[1, "qb_out_away"]) is False  # WR, not QB
    assert by_gid.loc[1, "qb_out_detail"] == "Michigan State: QB Sam Starter — Out"
    assert bool(by_gid.loc[2, "qb_out_home"]) is False  # Probable QB is not out
    assert bool(by_gid.loc[2, "qb_out_away"]) is False
    assert by_gid.loc[2, "qb_out_detail"] is None
    assert "qb-out flags: 1/2" in capsys.readouterr().out


def test_enrich_qb_out_empty_report_is_loud_and_leaves_flags_false(monkeypatch, capsys):
    wu = _load_script("weekly_update")
    monkeypatch.setattr(wu.rotowire, "fetch_injury_report", lambda timeout=15: [])
    scored = _slate()
    wu._enrich_qb_out(scored)
    assert not scored["qb_out_home"].any() and not scored["qb_out_away"].any()
    assert scored["qb_out_detail"].isna().all()
    assert "WARNING" in capsys.readouterr().out


def test_espn_injury_paths_are_gone():
    """ESPN's college injuries feed is always empty; the dead helpers and the
    spoofed User-Agent header must not linger for a future caller to reach for."""
    from beatvegas.sources import espn

    for name in ("team_injuries", "qb_out_flags", "game_context", "_UA"):
        assert not hasattr(espn, name), name
