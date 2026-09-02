"""FBS-vs-FBS game filter: the feature frame, backtest and weekly scoring must
never see FCS / D2 / D3 games (CFBD started carrying lines for them in 2022,
which quietly put ~40% lower-division rows into the training set)."""

import json

import pandas as pd
import pytest

from beatvegas.etl import features
from beatvegas.etl.fbs import filter_fbs_games, load_fbs_teams
from beatvegas.sources.cfbd import CFBDClient

FBS = {2023: {"Alabama", "Georgia"}, 2024: {"Alabama", "Georgia", "Kennesaw State"}}


def _games():
    return pd.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "season": [2023, 2023, 2023, 2024],
            "home_team": ["Alabama", "Alabama", "Furman", "Kennesaw State"],
            "away_team": ["Georgia", "Furman", "Wofford", "Georgia"],
        }
    )


def test_filter_keeps_only_games_where_both_teams_are_fbs_that_season():
    out = filter_fbs_games(_games(), FBS)
    assert out["id"].tolist() == [1, 4]  # FBS-vs-FCS (2) and FCS-vs-FCS (3) dropped


def test_filter_uses_the_per_season_list_not_a_global_one():
    # Kennesaw State is FBS in 2024 only; a 2023 game of theirs must be dropped.
    df = pd.DataFrame(
        {"id": [9], "season": [2023], "home_team": ["Kennesaw State"], "away_team": ["Alabama"]}
    )
    assert filter_fbs_games(df, FBS).empty


def test_filter_raises_on_a_season_missing_from_the_map():
    df = pd.DataFrame(
        {"id": [1], "season": [2015], "home_team": ["Alabama"], "away_team": ["Georgia"]}
    )
    with pytest.raises(ValueError, match="2015"):
        filter_fbs_games(df, FBS)


def test_filter_on_empty_frame_returns_empty_frame():
    df = _games().iloc[0:0]
    assert filter_fbs_games(df, FBS).empty


def test_load_fbs_teams_parses_season_keyed_json(tmp_path):
    p = tmp_path / "fbs_teams.json"
    p.write_text(json.dumps({"2023": ["Alabama", "Georgia"], "2024": ["Alabama"]}))
    fbs = load_fbs_teams(p)
    assert fbs == {2023: {"Alabama", "Georgia"}, 2024: {"Alabama"}}


def test_load_fbs_teams_missing_file_names_the_fetch_script(tmp_path):
    with pytest.raises(FileNotFoundError, match="fetch_fbs_teams"):
        load_fbs_teams(tmp_path / "nope.json")


class _FakeResp:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self):
        self.calls = []
        self.headers = {}

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        return _FakeResp([{"school": "Alabama"}, {"school": "Georgia"}])


def test_cfbd_client_fbs_teams_hits_teams_fbs_for_the_year():
    c = CFBDClient(api_key="x", base_url="https://api.test")
    c._session = _FakeSession()
    rows = c.fbs_teams(2024)
    assert [r["school"] for r in rows] == ["Alabama", "Georgia"]
    assert c._session.calls == [("https://api.test/teams/fbs", {"year": 2024})]


def test_load_all_games_applies_the_fbs_filter_by_default(monkeypatch):
    raw = _games()
    raw["week"] = 1
    monkeypatch.setattr(features, "_query_games", lambda: raw)
    monkeypatch.setattr(features, "load_fbs_teams", lambda: FBS)
    out = features._load_all_games()
    assert out["id"].tolist() == [1, 4]


def test_load_all_games_can_skip_the_filter(monkeypatch):
    raw = _games()
    raw["week"] = 1
    monkeypatch.setattr(features, "_query_games", lambda: raw)
    monkeypatch.setattr(
        features, "load_fbs_teams", lambda: (_ for _ in ()).throw(AssertionError("not called"))
    )
    out = features._load_all_games(fbs_only=False)
    assert out["id"].tolist() == [1, 2, 3, 4]
