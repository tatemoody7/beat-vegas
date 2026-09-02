"""derive_multiplier.py: walk-forward comparison of flat 0.52 vs linear vs step
share models, adoption gated on a meaningful MAE win."""

import numpy as np
import pandas as pd


def _frame():
    rng = np.random.default_rng(0)
    rows = []
    for season in (2023, 2024, 2025):
        for _ in range(300):
            spread = float(rng.choice([1, 3, 7, 10, 14, 17, 24, 28, 35]))
            total = float(rng.choice([45.5, 50.5, 55.5, 60.5]))
            share = 0.54 if spread >= 21 else 0.51
            fh = round(total * share + rng.normal(0, 0.5))
            rows.append(
                dict(season=season, spread=spread, full_game_total=total, first_half_total=fh)
            )
    return pd.DataFrame(rows)


def test_walk_forward_scores_flat_linear_and_step(load_script):
    mod = load_script("derive_multiplier")
    res = mod.walk_forward(_frame())
    assert set(res) >= {"flat", "linear", "step", "n"}
    assert res["n"] == 600  # 2024 and 2025 scored; 2023 is training only
    # A true step process: the step model must beat flat 0.52 and the linear fit.
    assert res["step"] < res["flat"]
    assert res["step"] <= res["linear"]


def test_choose_model_respects_the_adoption_margin(load_script):
    mod = load_script("derive_multiplier")
    assert mod.choose_model({"flat": 9.00, "linear": 8.99, "step": 8.98}, margin=0.05) is None
    assert mod.choose_model({"flat": 9.00, "linear": 8.99, "step": 8.90}, margin=0.05) == "step"
    assert mod.choose_model({"flat": 9.00, "linear": 8.90, "step": 8.95}, margin=0.05) == "linear"
