"""score_slate must score an UPCOMING week — games that have a full-game total
(the Sunday opener) but no first-half result yet. Before this fix the feature
frame dropped every unplayed game, so the target slice was always empty and
weekly_update printed "no scorable games" for every live week."""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd
import pytest

from beatvegas.etl.features import FEATURE_COLS, apply_min_games, training_frame
from beatvegas.etl.proxy_line import proxy_total
from beatvegas.model import score as score_mod


def _frame(seasons=range(2016, 2026), per_season=80, seed=3) -> pd.DataFrame:
    """Played seasons with a clean 1H target + ONE upcoming 2026 wk5 game with
    first_half_total NaN (unplayed) and a full-game total (opener captured)."""
    rng = np.random.default_rng(seed)
    rows = []
    gid = 1
    for s in seasons:
        for i in range(per_season):
            row = {c: 0.0 for c in FEATURE_COLS}
            x1, x2 = rng.normal(0, 1), rng.normal(0, 1)
            row.update(
                {
                    "id": gid,
                    "season": s,
                    "week": 3 + (i % 10),
                    "home_team": f"H{i}",
                    "away_team": f"A{i}",
                    "combined_off_ppa": x1,
                    "combined_def_ppa": x2,
                    "combined_sec_play": rng.uniform(20, 32),
                    "wx_dome": float(rng.integers(0, 2)),
                    "era_post2023": 1.0 if s >= 2023 else 0.0,
                    "full_game_total": 50.0 + 2 * x1,
                    "spread": -3.0,
                    "h_games_played": 5,
                    "a_games_played": 5,
                }
            )
            fh = 24 + 3 * x1 - 2 * x2 + rng.normal(0, 1.5)
            row["first_half_total"] = fh
            row["proxy_line"] = 0.52 * row["full_game_total"]
            row["under"] = float(fh < row["proxy_line"])
            rows.append(row)
            gid += 1
    df = pd.DataFrame(rows)
    # A played game whose 1H result is missing (e.g. a cancelled game that still
    # carries a total): must be EXCLUDED from training, not treated as an over.
    bad = df.iloc[0].copy()
    bad["id"] = 900_000
    bad["season"] = 2024
    bad["first_half_total"] = np.nan
    bad["under"] = np.nan
    # The upcoming game: full-game total captured, no result yet.
    up = df.iloc[1].copy()
    up["id"] = 999_999
    up["season"] = 2026
    up["week"] = 5
    up["home_team"], up["away_team"] = "Kansas State", "Kansas"
    up["first_half_total"] = np.nan
    up["under"] = np.nan
    up["full_game_total"] = 48.5
    return pd.concat([df, bad.to_frame().T, up.to_frame().T], ignore_index=True).astype(
        {c: float for c in FEATURE_COLS}
    )


def test_score_slate_scores_the_unplayed_target_week(monkeypatch):
    df = _frame()
    seen = {}
    real = score_mod.bv_line_for_slate

    def spy(train_df, target_df):
        seen["train"] = train_df
        return real(train_df, target_df)

    monkeypatch.setattr(score_mod, "bv_line_for_slate", spy)

    out = score_mod.score_slate(2026, target_week=5, df=df)

    assert len(out) == 1
    r = out.iloc[0]
    assert int(r["id"]) == 999_999
    assert pd.isna(r["under"])  # target keeps an undefined outcome
    for col in ("bv_line", "bv_gap", "under_score", "under_prob", "line", "rank"):
        assert pd.notna(r[col]), col
    assert r["line_kind"] == "proxy"
    assert "is_opportunity" not in out.columns  # sigma gate removed (point gates in verdict)
    assert "is_opportunity" not in score_mod._factors(r, float(r["line"]))

    train = seen["train"]
    assert train["under"].notna().all()
    assert train["first_half_total"].notna().all()
    assert 900_000 not in set(train["id"])
    assert (train["season"] < 2026).all()


def test_training_frame_drops_nan_targets_and_casts_under_to_int():
    df = _frame(seasons=range(2020, 2022), per_season=5)
    tf = training_frame(df)
    assert len(tf) == 10
    assert tf["under"].dtype.kind in "iu"
    assert set(tf["under"].unique()) <= {0, 1}


def test_apply_min_games_filters_both_sides():
    df = pd.DataFrame({"h_games_played": [0, 2, 5], "a_games_played": [5, 1, 5]})
    assert apply_min_games(df, 2)["h_games_played"].tolist() == [5]
    assert len(apply_min_games(df, 0)) == 3


# --- weekly_update exit semantics -------------------------------------------


def _wire(monkeypatch, frame, scored_empty=True):
    from conftest import _load_script

    wu = _load_script("weekly_update")
    monkeypatch.setattr(wu, "try_init_db", lambda: True)
    monkeypatch.setattr(wu, "detect_week", lambda season: 5)
    monkeypatch.setattr(wu, "build_feature_frame", lambda min_games=0: frame)
    monkeypatch.setattr(wu, "ranking_line_lookup", lambda season, week, basis="opener": ({}, {}))
    if scored_empty:
        monkeypatch.setattr(wu, "score_slate", lambda *a, **k: pd.DataFrame())
    monkeypatch.setattr(sys, "argv", ["weekly_update.py", "--season", "2026"])
    return wu


def _target_frame(n_played: int) -> pd.DataFrame:
    """Two 2026 wk5 rows: both have a total; `n_played` of them clear min_games=2."""
    return pd.DataFrame(
        {
            "id": [1, 2],
            "season": [2026, 2026],
            "week": [5, 5],
            "full_game_total": [50.0, 52.0],
            "h_games_played": [2 if i < n_played else 1 for i in range(2)],
            "a_games_played": [2, 2],
        }
    )


def test_weekly_update_exits_zero_when_min_games_filters_everything(monkeypatch, capsys):
    wu = _wire(monkeypatch, _target_frame(n_played=0))
    wu.main()  # no SystemExit
    out = capsys.readouterr().out
    assert "need >= 2 games played" in out


def test_weekly_update_exits_zero_when_week_has_no_totals_yet(monkeypatch, capsys):
    frame = _target_frame(n_played=2)
    frame["week"] = 6  # nothing for wk5 at all
    wu = _wire(monkeypatch, frame)
    wu.main()
    assert "no games with a full-game total" in capsys.readouterr().out


def test_weekly_update_fails_loudly_when_eligible_games_score_to_nothing(monkeypatch, capsys):
    wu = _wire(monkeypatch, _target_frame(n_played=2))
    with pytest.raises(SystemExit) as e:
        wu.main()
    assert e.value.code == 1
    assert "ERROR" in capsys.readouterr().out


def test_weekly_update_passes_min_games_frame_to_score_slate(monkeypatch):
    frame = _target_frame(n_played=1)
    wu = _wire(monkeypatch, frame, scored_empty=False)
    got = {}

    def fake_score(
        season, target_week=None, line_lookup=None, line_kind_lookup=None, df=None, **kw
    ):
        got["df"] = df
        return pd.DataFrame()

    monkeypatch.setattr(wu, "score_slate", fake_score)
    with pytest.raises(SystemExit):  # eligible row scored to nothing -> loud failure
        wu.main()
    assert got["df"]["id"].tolist() == [1]  # the under-min_games row was filtered


# --- engine switch: bv_line (incumbent) vs residual ------------------------------


def _closes_for(df: pd.DataFrame, seasons_below: int, n: int = None) -> dict:
    """Synthetic REAL 1H closes for played rows: a half-point number near the
    proxy so the residual model has a line to condition on."""
    played = df[(df["season"] < seasons_below) & df["first_half_total"].notna()]
    if n is not None:
        played = played.head(n)
    return {int(r.id): round(float(r.proxy_line) * 2) / 2 for r in played.itertuples()}


# Pinned from the incumbent code path (default args) before the engine switch
# landed: the bv_line engine must keep producing these numbers. Compared with a
# tolerance, not ==: CI runs ubuntu/py3.11, where a different BLAS can sum the
# tree ensemble in another order and shift the .round(2) value.
_PIN_TOL = 0.011  # one cent of rounding: a BLAS-order flip lands exactly 0.01 away
_BV_LINE_PIN = {
    723: 24.33,
    733: 19.47,
    743: 23.06,
    753: 22.32,
    763: 28.51,
    773: 22.79,
    783: 21.77,
    793: 20.79,
}


def _assert_matches_pin(got: dict) -> None:
    assert set(got) == set(_BV_LINE_PIN)
    for gid, want in _BV_LINE_PIN.items():
        assert got[gid] == pytest.approx(want, abs=_PIN_TOL), gid


def _real_lines(df: pd.DataFrame, kind: str = "hr_1h", season: int = 2025, week: int = 5):
    """Present the slate's own proxy numbers as a REAL posted 1H market, so the
    residual engine runs on every row while the `line` values stay identical to
    the no-lookup default (which score_slate would label kind 'proxy')."""
    slate = df[(df["season"] == season) & (df["week"] == week)]
    lines = {
        int(r.id): proxy_total(float(r.full_game_total), spread=float(r.spread))
        for r in slate.itertuples()
    }
    return lines, {gid: kind for gid in lines}


def test_bv_line_engine_output_unchanged_by_engine_switch(monkeypatch):
    monkeypatch.delenv("BV_ENGINE", raising=False)
    # explicit engine: a local config.yaml must not be able to flip this test
    out = score_mod.score_slate(2025, target_week=5, df=_frame(), engine="bv_line")
    got = {int(r.id): float(r.bv_line) for r in out.itertuples()}
    _assert_matches_pin(got)
    assert (out["engine"] == "bv_line").all()
    assert out["resid_hat"].isna().all()
    assert "engine_fallback" not in out.attrs and "engine_artifact" not in out.attrs
    f = score_mod._factors(out.iloc[0], float(out.iloc[0]["line"]))
    assert f["engine"] == "bv_line" and f["resid_hat"] is None and f["model_fingerprint"] is None


def test_residual_engine_conditions_on_the_line():
    df = _frame()
    closes = _closes_for(df, 2025)  # 720 played training rows with a "real" close
    lines, kinds = _real_lines(df)
    out = score_mod.score_slate(
        2025,
        target_week=5,
        df=df,
        engine="residual",
        real_closes=closes,
        line_lookup=lines,
        line_kind_lookup=kinds,
    )
    assert len(out) == 8
    assert out["bv_line"].notna().all() and out["resid_hat"].notna().all()
    assert (out["engine"] == "residual").all()
    # bv_line = line + r_hat, so the gap is exactly -r_hat.
    np.testing.assert_allclose(out["bv_gap"].to_numpy(), -out["resid_hat"].to_numpy(), atol=0.011)
    np.testing.assert_allclose(
        out["bv_line"].to_numpy(), (out["line"] + out["resid_hat"]).to_numpy(), atol=0.011
    )
    assert out["bv_sigma"].notna().all() and (out["bv_sigma"] > 0).all()
    assert (out["bv_lo"] < out["bv_line"]).all() and (out["bv_hi"] > out["bv_line"]).all()
    assert out["bv_gap_z"].notna().all()
    assert out["rank"].tolist() == list(range(1, 9))
    assert out["bv_gap"].is_monotonic_decreasing
    assert out["under_score"].notna().all()  # classifier still runs
    assert "engine_fallback" not in out.attrs
    art = out.attrs["engine_artifact"]
    assert hasattr(art["model"], "predict")
    assert art["fingerprint"]["n_rows"] == len(closes)
    assert art["fingerprint"]["model_version"] == "resid_v1"
    assert art["sigma"]["sigma"] == out["bv_sigma"].iloc[0]
    assert art["n_rows_residual"] == 8 and art["n_rows_fallback"] == 0
    assert "factor_refs" in out.attrs


def test_residual_engine_factors_json_keys():
    df = _frame()
    closes = _closes_for(df, 2025)
    lines, kinds = _real_lines(df)
    out = score_mod.score_slate(
        2025,
        target_week=5,
        df=df,
        engine="residual",
        real_closes=closes,
        line_lookup=lines,
        line_kind_lookup=kinds,
    )
    r = out.iloc[0]
    f = score_mod._factors(
        r, float(r["line"]), fingerprint=out.attrs["engine_artifact"]["fingerprint"]
    )
    assert f["engine"] == "residual"
    assert f["resid_hat"] == pytest.approx(float(r["resid_hat"]))
    assert f["bv_gap"] == pytest.approx(-f["resid_hat"], abs=0.011)
    assert set(f["model_fingerprint"]) == {"feature_hash", "n_rows", "max_game_date"}
    assert f["model_fingerprint"]["n_rows"] == len(closes)
    json.dumps(f)  # store_predictions serialises this payload


def test_residual_engine_falls_back_when_closes_are_scarce(monkeypatch):
    monkeypatch.delenv("BV_ENGINE", raising=False)
    df = _frame()
    few = _closes_for(df, 2025, n=score_mod.RESIDUAL_MIN_TRAIN - 1)
    out = score_mod.score_slate(2025, target_week=5, df=df, engine="residual", real_closes=few)
    assert out.attrs["engine_fallback"] == "insufficient_real_closes"
    assert "engine_artifact" not in out.attrs
    assert (out["engine"] == "bv_line").all()
    assert out["resid_hat"].isna().all()
    got = {int(r.id): float(r.bv_line) for r in out.itertuples()}
    _assert_matches_pin(got)  # the incumbent's numbers, untouched


def test_residual_engine_falls_back_row_by_row_without_a_real_posted_line():
    """A derived_fg / proxy row has no real posted 1H number, so there is no
    market error for the residual to model: those rows keep the incumbent's
    market-blind bv_line and are stamped engine='bv_line'. Only rows with a real
    line (hr_1h / observed_1h) get the residual read."""
    df = _frame()
    closes = _closes_for(df, 2025)
    lines, kinds = _real_lines(df)
    derived_id, proxy_id = 733, 743
    kinds[derived_id] = "derived_fg"
    del lines[proxy_id], kinds[proxy_id]  # no lookup at all -> kind 'proxy'
    out = score_mod.score_slate(
        2025,
        target_week=5,
        df=df,
        engine="residual",
        real_closes=closes,
        line_lookup=lines,
        line_kind_lookup=kinds,
    )
    art = out.attrs["engine_artifact"]
    by_id = out.set_index("id")

    for gid in (derived_id, proxy_id):
        assert by_id.loc[gid, "engine"] == "bv_line"
        assert by_id.loc[gid, "bv_line"] == pytest.approx(_BV_LINE_PIN[gid], abs=_PIN_TOL)
        assert pd.isna(by_id.loc[gid, "resid_hat"])

    hr_ids = [gid for gid in _BV_LINE_PIN if gid not in (derived_id, proxy_id)]
    for gid in hr_ids:
        assert by_id.loc[gid, "engine"] == "residual"
        assert by_id.loc[gid, "bv_gap"] == pytest.approx(-by_id.loc[gid, "resid_hat"], abs=0.011)
    assert art["n_rows_residual"] == len(hr_ids) and art["n_rows_fallback"] == 2

    # ...and the two engines' rows carry their OWN noise band, not each other's.
    assert by_id.loc[derived_id, "bv_sigma"] != by_id.loc[hr_ids[0], "bv_sigma"]

    # the per-row factors payload reports the engine that made THAT row, and a
    # fallback row must NOT carry the residual fit's fingerprint even though the
    # same slate produced one — the number came from the incumbent.
    fp = art["fingerprint"]
    f = score_mod._factors(by_id.loc[derived_id], 23.0, fingerprint=fp)
    assert f["engine"] == "bv_line" and f["resid_hat"] is None
    assert f["model_fingerprint"] is None
    r = score_mod._factors(by_id.loc[hr_ids[0]], 23.0, fingerprint=fp)
    assert r["engine"] == "residual"
    assert r["model_fingerprint"]["feature_hash"] == fp["feature_hash"]


def test_residual_engine_on_an_all_proxy_slate_is_the_incumbent_board():
    """Sunday: no retail 1H market is posted yet, so every row is derived/proxy.
    The board must be exactly the incumbent's, not a residual off a fake line."""
    df = _frame()
    closes = _closes_for(df, 2025)
    out = score_mod.score_slate(2025, target_week=5, df=df, engine="residual", real_closes=closes)
    assert (out["engine"] == "bv_line").all()
    assert out["resid_hat"].isna().all()
    _assert_matches_pin({int(r.id): float(r.bv_line) for r in out.itertuples()})
    art = out.attrs["engine_artifact"]
    assert art["n_rows_residual"] == 0 and art["n_rows_fallback"] == 8


def test_engine_artifact_is_attached_after_the_final_reshape():
    """pandas deep-copies .attrs on sort_values/reset_index, so a fitted model
    parked there before the final sort is cloned for nothing. The artifact must
    be the object score_slate fitted, attached once at the end."""
    df = _frame()
    closes = _closes_for(df, 2025)
    lines, kinds = _real_lines(df)
    seen = {}
    real_fit = score_mod.residual_1h_for_slate

    def spy(train_r, target, line):
        pred, model, fp = real_fit(train_r, target, line)
        seen["model"] = model
        return pred, model, fp

    try:
        score_mod.residual_1h_for_slate = spy
        out = score_mod.score_slate(
            2025,
            target_week=5,
            df=df,
            engine="residual",
            real_closes=closes,
            line_lookup=lines,
            line_kind_lookup=kinds,
        )
    finally:
        score_mod.residual_1h_for_slate = real_fit
    assert out.attrs["engine_artifact"]["model"] is seen["model"]


def test_residual_engine_without_closes_falls_back():
    out = score_mod.score_slate(2025, target_week=5, df=_frame(), engine="residual")
    assert out.attrs["engine_fallback"] == "insufficient_real_closes"


def test_engine_defaults_to_config(monkeypatch):
    monkeypatch.setattr(score_mod, "engine_name", lambda: "residual")
    out = score_mod.score_slate(2025, target_week=5, df=_frame())
    assert out.attrs["engine_fallback"] == "insufficient_real_closes"  # residual was chosen


def test_unknown_engine_raises():
    with pytest.raises(ValueError):
        score_mod.score_slate(2025, target_week=5, df=_frame(), engine="gbm")


def test_derived_factors_carry_no_engine():
    f = score_mod.derived_factors(24.5, 50.0, -3.0, 0.49)
    assert f["engine"] is None and f["resid_hat"] is None and f["model_fingerprint"] is None
    assert f["line_kind"] == "derived_fg"
