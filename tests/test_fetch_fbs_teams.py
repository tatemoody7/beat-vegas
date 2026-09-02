"""scripts/fetch_fbs_teams.py: CFBD /teams/fbs rows -> data/fbs_teams.json."""

import json


class _FakeClient:
    def __init__(self):
        self.years = []

    def fbs_teams(self, year):
        self.years.append(year)
        base = [{"school": "Alabama", "conference": "SEC"}, {"school": "Georgia"}]
        if year >= 2024:
            base.append({"school": "Kennesaw State", "conference": "Conference USA"})
        return base


def test_build_fbs_map_is_sorted_and_per_season(load_script):
    mod = load_script("fetch_fbs_teams")
    client = _FakeClient()
    out = mod.build_fbs_map(client, [2023, 2024], min_teams=1)
    assert out == {2023: ["Alabama", "Georgia"], 2024: ["Alabama", "Georgia", "Kennesaw State"]}
    assert client.years == [2023, 2024]


def test_build_fbs_map_refuses_an_implausibly_small_season(load_script):
    mod = load_script("fetch_fbs_teams")

    class Thin:
        def fbs_teams(self, year):
            return [{"school": "Alabama"}]

    try:
        mod.build_fbs_map(Thin(), [2023])
    except ValueError as e:
        assert "2023" in str(e)
    else:
        raise AssertionError("expected ValueError for a 1-team FBS season")


def test_write_snapshot_round_trips_through_load_fbs_teams(load_script, tmp_path):
    from beatvegas.etl.fbs import load_fbs_teams

    mod = load_script("fetch_fbs_teams")
    p = tmp_path / "fbs_teams.json"
    mod.write_snapshot({2023: ["Georgia", "Alabama"]}, p)
    assert json.loads(p.read_text()) == {"2023": ["Georgia", "Alabama"]}
    assert load_fbs_teams(p) == {2023: {"Alabama", "Georgia"}}
