"""The blend's arithmetic and its pre-registered rules, pinned: MAE-only fit with
ties to the close, the mechanical gate-crossing identity, the two verdict words, the
bucket family's Holm test, and the frozen record."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from beatvegas.backtest import blend as B
from beatvegas.model.score import BET_GAP_PTS


def _pg(n=600, seasons=(2023, 2024, 2025), close_sd=1.0, bv_sd=3.0, seed=3):
    """Actual = truth + noise; close is a tight read of truth, bv a loose one, so
    the best w is high but below 1 (bv carries a little independent information)."""
    rng = np.random.default_rng(seed)
    rows = []
    for s in seasons:
        truth = rng.normal(46, 6, n)
        actual = truth + rng.normal(0, 9, n)
        close = truth + rng.normal(0, close_sd, n)
        bv = truth + rng.normal(0, bv_sd, n)
        spread = np.abs(rng.normal(12, 9, n))
        rows.append(
            pd.DataFrame(
                {
                    "game_id": np.arange(n) + s * 10_000,
                    "season": s,
                    "week": rng.integers(1, 14, n),
                    "spread_abs": spread,
                    "bucket": [B.bucket_of(v) for v in spread],
                    "close": close,
                    "actual": actual,
                    "pred_bv": bv,
                }
            )
        )
    return pd.concat(rows, ignore_index=True)


def test_buckets_follow_the_post_mortem_edges():
    assert B.bucket_of(0) == "<14" and B.bucket_of(13.99) == "<14"
    assert B.bucket_of(14) == "14-21" and B.bucket_of(21) == "21-28" and B.bucket_of(28) == "28+"
    assert B.bucket_of(None) is None and B.bucket_of(float("nan")) is None


def test_fit_w_minimises_mae_and_breaks_ties_toward_the_close():
    close = np.array([40.0, 50.0, 60.0])
    bv = np.array([40.0, 50.0, 60.0])  # identical arms: every w ties
    actual = np.array([41.0, 49.0, 60.0])
    fit = B.fit_w(close, bv, actual)
    assert fit["w"] == 1.0 and fit["mae"] == pytest.approx(2 / 3)
    assert len(fit["curve"]) == 101


def test_fit_w_recovers_a_planted_weight_on_clean_data():
    rng = np.random.default_rng(1)
    close, bv = rng.normal(45, 5, 4000), rng.normal(45, 5, 4000)
    actual = 0.7 * close + 0.3 * bv + rng.normal(0, 0.01, 4000)
    assert B.fit_w(close, bv, actual)["w"] == pytest.approx(0.70, abs=0.011)


def test_gate_crossings_are_the_mechanical_identity():
    pg = pd.DataFrame({"close": [50.0, 50.0, 50.0], "pred_bv": [48.0, 47.0, 40.0]})
    c = B.gate_crossings(pg, w=0.5)
    # raw gaps 2.0, 3.0, 10.0 -> blended gaps 1.0, 1.5, 5.0 against 1.75
    assert (c["clear_before"], c["clear_after"], c["changed_side"]) == (3, 1, 2)
    assert c["raw_gap_equivalent"] == pytest.approx(BET_GAP_PTS / 0.5)
    assert B.raw_gap_equivalent(1.0) is None and B.raw_gap_equivalent(0.9) == pytest.approx(17.5)


def test_evaluate_split_reports_the_three_arms_and_the_bucket_family():
    pg = _pg()
    s = B.evaluate_split(pg, (2023,), 2024, n_boot=200)
    assert s["evaluated"] and 0.5 < s["w"] < 1.0
    tm = s["test_mae"]
    assert tm["blend"] <= tm["bv"] and tm["blend"] <= tm["close"] + 0.05
    assert {b["bucket"] for b in s["buckets"]} == {"<14", "14-21", "21-28", "28+"}
    for b in s["buckets"]:
        if b.get("p") is not None:
            assert b["p_holm"] >= b["p"]


def test_verdict_words():
    good = {
        "evaluated": True,
        "train_seasons": [2023],
        "test_season": 2024,
        "w": 0.9,
        "test_mae": {"blend": 8.5, "close": 8.7, "bv": 9.2},
    }
    close = dict(good, test_mae={"blend": 8.8, "close": 8.7, "bv": 9.2})
    assert B.verdict([good, dict(good, test_season=2025)])["word"] == "BLEND WINS AT CLOSE"
    assert B.verdict([close, dict(close, test_season=2025)])["word"] == "CLOSE WINS"
    assert B.verdict([good, dict(close, test_season=2025)])["word"] == "NO STABLE WINNER"
    assert B.verdict([good, {"evaluated": False}])["word"] == "NOT EVALUATED"


def _bucket_rows(passes):
    return [
        {
            "bucket": name,
            "n_test": 200,
            "p_holm": 0.01 if passes.get(name) else 0.5,
            "passes": bool(passes.get(name)),
        }
        for name in ("<14", "14-21", "21-28", "28+")
    ]


def test_bucket_verdict_needs_both_seasons_and_never_adopts_28_plus_alone():
    s1 = {
        "evaluated": True,
        "test_season": 2024,
        "buckets": _bucket_rows({"<14": True, "28+": True}),
    }
    s2 = {
        "evaluated": True,
        "test_season": 2025,
        "buckets": _bucket_rows({"<14": True, "28+": True}),
    }
    v = B.bucket_verdict([s1, s2])
    assert v["adopted"] == ["<14", "28+"]  # 28+ rides along once another bucket is in
    only28 = _bucket_rows({"28+": True})
    v2 = B.bucket_verdict([dict(s1, buckets=only28), dict(s2, buckets=only28)])
    assert v2["adopted"] == [] and any("never adopted on its own" in r for r in v2["reasons"])
    v3 = B.bucket_verdict([s1, dict(s2, buckets=_bucket_rows({}))])
    assert v3["adopted"] == []


def test_freeze_record_and_writer(tmp_path):
    pg = _pg(n=200)
    rec = B.freeze(pg, (2023, 2024, 2025))
    assert rec["n"] == 600 and rec["fitted_on"] == "2023-2025" and "nothing" in rec["read_by"]
    p = B.write_freeze(rec, tmp_path / "blend.json")
    assert json.loads(p.read_text())["w"] == rec["w"]


def test_live_frame_takes_the_last_final_build_before_kickoff():
    kick = pd.Timestamp("2026-09-12 19:30")
    rows = pd.DataFrame(
        {
            "game_id": [1, 1, 1, 2],
            "week": [2, 2, 2, 2],
            "status": ["final", "final", "preview", "final"],
            "built_at": [
                kick - pd.Timedelta(days=2),
                kick - pd.Timedelta(hours=7),
                kick - pd.Timedelta(hours=1),
                kick,
            ],
            "kickoff": [kick] * 4,
            "market_line": [45.0, 44.5, 44.0, 40.0],
            "bv_line": [42.0, 42.2, 42.5, 39.0],
            "fh": [41.0, 41.0, 41.0, 38.0],
        }
    )
    lf = B.live_frame(rows)
    assert len(lf) == 1 and lf.iloc[0].market_line == 44.5  # game 2 built AT kickoff is out
    s = B.live_summary(lf, 0.8)
    assert s["n"] == 1 and s["mae"]["blend"] == pytest.approx(abs(0.8 * 44.5 + 0.2 * 42.2 - 41.0))
