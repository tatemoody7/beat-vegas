"""beatvegas/backtest/wepa_f.py: the H-WEPA-F ARM R candidates are the
champion's line plus a within-season walk-forward correction that can read
no actual from the week it predicts or later."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from beatvegas.backtest import wepa_f as W

ROOT = Path(__file__).resolve().parents[1]


def _ztable(ids, seed=3):
    rng = np.random.default_rng(seed)
    z = pd.DataFrame({"id": ids, "season": 2025, "week": 5, "posted_at": "x"})
    for m in W.COMPOSITE_METRICS:
        for side in ("home", "away"):
            for suf in ("", "_allowed"):
                z[f"z_{side}_adjusted_{m}{suf}"] = rng.normal(size=len(ids))
    return z


def _target(n_weeks=6, per_week=12, first_week=5, seed=1, signal=2.0):
    """A 2025 target frame whose actual = 27 + signal * epa composite + noise,
    so a correction fitted on the composite should help."""
    rng = np.random.default_rng(seed)
    rows = []
    gid = 500000
    for w in range(first_week, first_week + n_weeks):
        for _ in range(per_week):
            rows.append({"id": gid, "season": 2025, "week": w})
            gid += 1
    t = pd.DataFrame(rows)
    z = _ztable(t["id"].tolist(), seed=seed + 10)
    comp = W.composites(z)
    t = t.merge(comp[["id", "epa"]], on="id")
    t["actual"] = 27.0 + signal * t["epa"] + rng.normal(scale=1.0, size=len(t))
    return t.drop(columns=["epa"]), z


def const27(train, target):
    return np.full(len(target), 27.0)


def test_composites_orient_every_term_toward_more_scoring():
    z = _ztable([1, 2, 3])
    c = W.composites(z)
    m = "epa"
    expect = (
        z[f"z_home_adjusted_{m}"]
        + z[f"z_away_adjusted_{m}"]
        + z[f"z_home_adjusted_{m}_allowed"]
        + z[f"z_away_adjusted_{m}_allowed"]
    )
    assert np.allclose(c["epa"], expect)
    assert list(c.columns) == ["id", *W.COMPOSITE_METRICS]


def test_first_week_and_rows_without_wepa_return_the_champion_exactly(tmp_path):
    t, z = _target()
    z = z[z["id"] != t["id"].iloc[-1]]  # last game has no WEPA row
    p = tmp_path / "z.csv"
    z.to_csv(p, index=False)
    cand = W.make_candidate(W.EPA1_COLS, champion=const27, wepa_path=p)
    pred = cand(pd.DataFrame(), t)
    assert pred.shape == (len(t),) and np.all(np.isfinite(pred))
    first = t["week"] == t["week"].min()
    assert np.allclose(pred[first.to_numpy()], 27.0)
    assert pred[-1] == 27.0
    later = ~first.to_numpy()
    later[-1] = False
    assert not np.allclose(pred[later], 27.0)


def test_week_k_prediction_cannot_read_an_actual_from_week_k_or_later(tmp_path):
    t, z = _target()
    p = tmp_path / "z.csv"
    z.to_csv(p, index=False)
    cand = W.make_candidate(W.K4_COLS, champion=const27, wepa_path=p)
    base = cand(pd.DataFrame(), t)
    for k in sorted(t["week"].unique()):
        bent = t.copy()
        bent.loc[bent["week"] >= k, "actual"] += 40.0  # a huge, obvious leak if read
        pred = cand(pd.DataFrame(), bent)
        upto = (t["week"] <= k).to_numpy()
        assert np.allclose(pred[upto], base[upto]), f"week {k} read a same-or-later actual"


def test_correction_recovers_a_planted_signal_walk_forward(tmp_path):
    t, z = _target(n_weeks=8, per_week=20, signal=2.0)
    p = tmp_path / "z.csv"
    z.to_csv(p, index=False)
    cand = W.make_candidate(W.EPA1_COLS, champion=const27, wepa_path=p)
    pred = cand(pd.DataFrame(), t)
    later = (t["week"] >= t["week"].min() + 2).to_numpy()
    mae_champ = np.abs(t["actual"].to_numpy()[later] - 27.0).mean()
    mae_cand = np.abs(t["actual"].to_numpy()[later] - pred[later]).mean()
    assert mae_cand < mae_champ * 0.6


def test_min_train_rows_guard_leaves_the_champion_untouched(tmp_path):
    t, z = _target(n_weeks=3, per_week=5)  # 5 earlier rows < MIN_TRAIN_ROWS
    comp = W.composites(z)
    corr = W.walk_forward_correction(t, np.full(len(t), 27.0), comp, W.EPA1_COLS)
    assert np.all(corr == 0.0)


def test_champion_length_mismatch_is_a_defect():
    t, z = _target(n_weeks=2, per_week=3)
    with pytest.raises(ValueError, match="predictions for"):
        W.walk_forward_correction(t, np.zeros(2), W.composites(z), W.EPA1_COLS)


def test_committed_table_loads_and_every_composite_is_finite():
    z = W.load_wepa_z()
    c = W.composites(z)
    assert len(c) == 561 and np.isfinite(c[list(W.COMPOSITE_METRICS)].to_numpy()).all()


def _report(epa1, k4, holm=None):
    pairs = {"wepa_epa1": epa1, "wepa_k4": k4}
    holm = holm or {"wepa_epa1": 0.01, "wepa_k4": 0.01}
    return {"comparisons": {"pairs": pairs, "holm": {"abs_err": holm}}}


def _pair(mean, excl, units_hi):
    return {
        "abs_err": {"mean": mean, "excludes_zero": excl, "lo": mean - 0.1, "hi": mean + 0.1},
        "portfolio_units": {"mean": 0.0, "lo": units_hi - 0.2, "hi": units_hi},
    }


def test_criterion_reads_met_not_met_and_not_evaluable():
    good, bad = _pair(-0.3, True, 0.05), _pair(-0.1, False, 0.05)
    assert W.criterion(_report(good, bad)) is True
    assert W.criterion(_report(bad, bad)) is False
    # lower MAE but units interval entirely below zero -> not a pass
    assert W.criterion(_report(_pair(-0.3, True, -0.01), bad)) is False
    # Holm-adjusted p at or above 0.05 -> not a pass
    assert W.criterion(_report(good, bad, holm={"wepa_epa1": 0.06, "wepa_k4": 0.5})) is False
    # a missing sub-arm or a missing number -> None
    assert W.criterion({"comparisons": {"pairs": {"wepa_epa1": good}, "holm": {}}}) is None
    assert W.criterion(_report(good, {"abs_err": {}, "portfolio_units": {}})) is None


def test_criterion_reads_a_real_harness_report_end_to_end():
    """Plumbing: both sub-arms through `harness.run` with the registered
    criterion. The hand frame's ids are not in the z-table, so every
    correction is 0 and each sub-arm equals the incumbent -> 'not met' (a
    False from the criterion, never a None: the key paths it reads exist)."""
    from test_harness import PRE_ROW, first_game_id, hand_frame

    from beatvegas.backtest import harness as H

    frame, closes = hand_frame()
    g1 = first_game_id(frame, 2024, 5)
    grading = H.Grading(
        closes=closes,
        hr_closes={g1: 30.5},
        hr_prices={g1: -115},
        decision_lines={g1: 31.0},
        decision_rule="consensus_as_of(fri_pm)",
    )
    arms = (
        H.Arm("incumbent", const27, is_incumbent=True),
        H.Arm("wepa_epa1", W.make_candidate(W.EPA1_COLS, champion=const27)),
        H.Arm("wepa_k4", W.make_candidate(W.K4_COLS, champion=const27)),
    )
    spec = H.HarnessSpec(
        row_id=PRE_ROW.id, arms=arms, test_seasons=(2024, 2025), criterion=W.criterion
    )
    res = H.run(frame, grading, spec, PRE_ROW, {"rows": len(frame), "path": "x"})
    assert res.report["verdict"]["verdict"] == "not met"
    assert res.report["verdict"]["criterion_answer"] is False
    assert res.report["verdict"]["criterion_fn"].endswith("wepa_f.criterion")
    for arm in W.ARM_NAMES:
        assert res.report["comparisons"]["pairs"][arm]["abs_err"]["mean"] == 0.0
