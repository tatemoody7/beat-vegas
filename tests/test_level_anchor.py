"""The prior-season level anchor: the seeded season-to-date window, the empty
cache it exposed, and the gate that decides whether any of it goes live."""

import json

import pandas as pd
import pytest

from beatvegas.backtest.level_anchor import (
    NON_INFERIORITY_MARGIN,
    PRIOR_WEIGHT_GRID,
    _paired_ci,
    _verdict,
)
from beatvegas.etl.features import PRIOR_SEASON_WEIGHT, _season_to_date


def _long(**over):
    """Two seasons for one team. 2023: 10, 20, 30 (mean 20). 2024: 40, 50."""
    d = {
        "id": [1, 2, 3, 4, 5],
        "season": [2023, 2023, 2023, 2024, 2024],
        "week": [1, 2, 3, 1, 2],
        "start_date": pd.to_datetime(
            ["2023-09-01", "2023-09-08", "2023-09-15", "2024-09-01", "2024-09-08"]
        ),
        "team": ["A"] * 5,
        "fh_pf": [10.0, 20.0, 30.0, 40.0, 50.0],
        "fh_pa": [0.0] * 5,
        "full_pf": [0.0] * 5,
        "full_pa": [0.0] * 5,
    }
    d.update(over)
    return pd.DataFrame(d)


def _pf(long, k):
    return _season_to_date(long, prior_weight=k).set_index("id")["fh_pf_std"]


# --- the seeded window -------------------------------------------------------


def test_production_default_is_zero_so_the_seed_ships_inert():
    """The gate found no adoption, so the live feature build must be unchanged.
    If this ever fails, a seed went live without a report."""
    assert PRIOR_SEASON_WEIGHT == 0.0


def test_k_zero_is_an_exact_no_op():
    """k=0 must reproduce the unseeded expanding mean EXACTLY -- that is what
    makes the incumbent an arm of the experiment rather than a rival code path,
    and what lets the gate pair its comparisons on the same games."""
    long = _long()
    base = _pf(long, 0.0)
    assert pd.isna(base[1]) and base[2] == 10.0 and base[3] == 15.0
    assert pd.isna(base[4]) and base[5] == 40.0


def test_the_seed_is_a_weighted_blend_that_decays():
    """Game 1 reads the prior-season mean; later games blend it away as k/(n+k).
    Hand-checked: prior mean is 20, first 2024 game scored 40."""
    long = _long()
    k1, k2 = _pf(long, 1.0), _pf(long, 2.0)
    assert k1[4] == pytest.approx(20.0)  # (1*20 + 0) / (1 + 0)
    assert k2[4] == pytest.approx(20.0)  # k does not change game 1's value
    assert k1[5] == pytest.approx(30.0)  # (1*20 + 40) / (1 + 1)
    assert k2[5] == pytest.approx(80.0 / 3)  # (2*20 + 40) / (2 + 1)


def test_a_first_season_keeps_its_nan_whatever_k_is():
    """A team with no prior season on file is NOT given a league-average prior:
    that would be a different feature. The NaN stands."""
    long = _long()
    for k in (0.0, 1.0, 3.0):
        s = _pf(long, k)
        assert pd.isna(s[1]), k
        assert s[2] == 10.0 and s[3] == 15.0, k  # 2023 identical at every k


def test_the_seed_survives_an_unplayed_prior_game():
    """expanding().sum() over an all-NaN window returns NaN, not 0, which would
    swallow the seed on exactly the row this exists to fix. An unscored game
    must contribute to neither the sum nor the count."""
    long = _long(fh_pf=[10.0, float("nan"), 30.0, 40.0, 50.0])
    s = _pf(long, 1.0)
    assert s[4] == pytest.approx(20.0)  # prior mean of 10 and 30, NaN skipped
    assert s[5] == pytest.approx(30.0)  # (1*20 + 40) / (1 + 1)


def test_games_played_counts_real_games_only():
    """apply_min_games reads this, and a synthetic seed is not a game played."""
    out = _season_to_date(_long(), prior_weight=3.0).set_index("id")
    assert list(out["games_played"]) == [0, 1, 2, 0, 1]


# --- the gate's arithmetic and its rule --------------------------------------


def test_paired_ci_mean_and_interval():
    ci = _paired_ci(pd.Series([1.0, 1.0, 1.0, 1.0]))
    assert ci["n"] == 4 and ci["mean"] == pytest.approx(1.0)
    assert ci["lo"] == pytest.approx(1.0) and ci["hi"] == pytest.approx(1.0)
    empty = _paired_ci(pd.Series([], dtype=float))
    assert empty["n"] == 0 and empty["mean"] is None and empty["lo"] is None
    single = _paired_ci(pd.Series([2.0]))
    assert single["mean"] == pytest.approx(2.0) and single["lo"] is None


def _arm(k, early, late):
    return {
        "prior_weight": k,
        "weeks_1_2": {"paired_gain": _paired_ci(pd.Series(early))},
        "weeks_3plus": {"paired_gain": _paired_ci(pd.Series(late))},
    }


def test_adoption_needs_early_improvement_and_late_non_inferiority():
    # Clear early gain, late unchanged -> adopt.
    good = _verdict(_arm(1.0, [1.0] * 10, [0.0] * 10))
    assert good["adopt"] is True

    # Early interval spans zero -> no. This is what the real run returned.
    flat = _verdict(_arm(1.0, [1.0, -1.0] * 10, [0.0] * 10))
    assert flat["adopt"] is False and "does not exclude 0" in flat["why"]

    # Early improves but weeks 3+ regress past the margin -> no.
    regress = _verdict(_arm(1.0, [1.0] * 10, [-NON_INFERIORITY_MARGIN * 3] * 10))
    assert regress["adopt"] is False and "margin" in regress["why"]


def test_the_incumbent_arm_never_adopts_itself():
    assert _verdict(_arm(0.0, [0.0] * 10, [0.0] * 10))["adopt"] is False


def test_an_empty_bucket_reads_as_not_evaluable_not_as_a_loss():
    """2026 has no weeks 3+ played yet. 'We could not test it' must never render
    as 'we tested it and it lost' -- the same distinction PR #123 drew between
    a price we could not check and a price that was too dear."""
    v = _verdict(_arm(1.0, [1.0] * 10, []))
    assert v["adopt"] is False and "not evaluable" in v["why"]


def test_the_grid_contains_the_incumbent():
    assert 0.0 in [float(k) for k in PRIOR_WEIGHT_GRID]


# --- the empty cache the guard exposed ---------------------------------------


def test_empty_cache_is_a_miss_and_is_never_written(tmp_path, monkeypatch):
    """data/cache/{sp,talent,...}_2026.json were all 2 bytes ('[]'), written
    before 2026 data existed, and a hit is forever: every column they feed went
    silently NaN on any local build. An empty payload must refetch, and an empty
    RESULT must not be cached, or the next caller inherits the hole."""
    from beatvegas.sources import season_stats as ss

    monkeypatch.setattr(ss, "CACHE", tmp_path)
    calls = []

    def fetch(payload):
        def _f():
            calls.append(1)
            return payload

        return _f

    (tmp_path / "sp_2026.json").write_text("[]")
    assert ss._cached("sp_2026.json", fetch([])) == []
    assert len(calls) == 1, "an empty cache file must not be served as a hit"
    assert (tmp_path / "sp_2026.json").read_text() == "[]", "empty result not re-written"

    assert ss._cached("sp_2026.json", fetch([{"team": "A"}])) == [{"team": "A"}]
    assert len(calls) == 2
    assert json.loads((tmp_path / "sp_2026.json").read_text()) == [{"team": "A"}]

    # Now it is a real hit and the fetch must not run again.
    assert ss._cached("sp_2026.json", fetch([{"team": "B"}])) == [{"team": "A"}]
    assert len(calls) == 2


def test_a_season_that_cannot_be_fetched_warns_instead_of_killing_the_build(
    tmp_path, monkeypatch, capsys
):
    """build_feature_frame asks for a prior per season in the games table,
    including the current one, whose full-year aggregate does not exist yet.
    With the empty-payload guard that hole would otherwise take down every
    feature build -- trading a silent wrong answer for a loud useless one."""
    from beatvegas.sources import season_stats as ss

    monkeypatch.setattr(ss, "CACHE", tmp_path)

    def boom():
        raise RuntimeError("401 Unauthorized")

    assert ss._cached_soft("sp_2026.json", boom, "SP+ 2026") == []
    out = capsys.readouterr().out
    assert "::warning::" in out and "SP+ 2026" in out
    assert not (tmp_path / "sp_2026.json").exists()
