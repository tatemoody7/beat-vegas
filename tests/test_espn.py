"""ESPN mapper + failure-visibility tests. Everything here is offline: the team
list is passed in or monkeypatched, never fetched."""

import pytest

from beatvegas.sources import espn

# Order matters: the wrong-but-prefix-matching team comes FIRST, as the old
# first-scanned-wins tie-break would have kept it.
TEAMS = [
    {"id": "193", "location": "Miami (OH)", "displayName": "Miami (OH) RedHawks"},
    {"id": "2390", "location": "Miami", "displayName": "Miami Hurricanes"},
    {"id": "2306", "location": "Kansas State", "displayName": "Kansas State Wildcats"},
    {"id": "2305", "location": "Kansas", "displayName": "Kansas Jayhawks"},
    {"id": "99", "location": "LSU", "displayName": "LSU Tigers"},
]


def test_best_team_id_prefers_exact_location_over_prefix_match():
    assert espn.best_team_id("Miami", TEAMS) == "2390"
    assert espn.best_team_id("Miami (OH)", TEAMS) == "193"
    assert espn.best_team_id("Kansas", TEAMS) == "2305"
    assert espn.best_team_id("Kansas State", TEAMS) == "2306"


def test_best_team_id_returns_none_for_unknown_school():
    assert espn.best_team_id("Nonexistent Tech", TEAMS) is None


def test_espn_team_id_uses_the_live_team_list(monkeypatch):
    monkeypatch.setattr(espn, "_teams", lambda: TEAMS)
    assert espn.espn_team_id("LSU") == "99"


def test_teams_fetch_failure_is_memoized_per_process(monkeypatch, tmp_path):
    """A 403 on /teams must cost one request per process, not one per game per
    side (the week-1 preview made 1,820 doomed calls)."""
    calls = []

    def fake_get(url, params=None, timeout=12):
        calls.append(url)
        return None

    monkeypatch.setattr(espn, "_CACHE", tmp_path)
    monkeypatch.setattr(espn, "_get", fake_get)
    espn._reset_team_memo()
    assert espn._teams() == []
    assert espn._teams() == []
    assert len(calls) == 1


def test_teams_available_false_when_list_empty(monkeypatch):
    monkeypatch.setattr(espn, "_teams", lambda: [])
    assert espn.teams_available() is False
    monkeypatch.setattr(espn, "_teams", lambda: TEAMS)
    assert espn.teams_available() is True


def test_research_preview_exits_loudly_when_both_sources_are_empty(monkeypatch, capsys):
    import sys

    from conftest import _load_script

    rp = _load_script("research_preview")
    monkeypatch.setattr(rp, "teams_available", lambda: False)
    monkeypatch.setattr(rp.rotowire, "fetch_injury_report", lambda timeout=15: [])
    monkeypatch.setattr(sys, "argv", ["research_preview.py", "--season", "2026", "--week", "1"])
    with pytest.raises(SystemExit) as e:
        rp.main()
    assert e.value.code == 3
    assert "[espn] FATAL" in capsys.readouterr().out


def test_research_preview_warns_but_continues_when_only_espn_is_empty(monkeypatch, capsys):
    """Rotowire carries the injuries now; a dead ESPN must not block writing them."""
    import sys

    from conftest import _load_script

    rp = _load_script("research_preview")
    monkeypatch.setattr(rp, "teams_available", lambda: False)
    monkeypatch.setattr(
        rp.rotowire, "fetch_injury_report", lambda timeout=15: [{"player": "x", "team": "LSU"}]
    )
    monkeypatch.setattr(rp, "try_init_db", lambda: False)  # stop before any DB work
    monkeypatch.setattr(sys, "argv", ["research_preview.py", "--season", "2026", "--week", "1"])
    rp.main()
    out = capsys.readouterr().out
    assert "[espn] WARNING" in out and "FATAL" not in out
