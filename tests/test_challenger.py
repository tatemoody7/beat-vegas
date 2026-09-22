"""The H-INSEASON challenger family, live: arithmetic, isolation, and the spec.

Registry row H-INSEASON-P. The tests that matter most are not the statistics --
they are the ones that keep this measurement from touching the money path. A
challenger row reaching `manual_picks`, or an arm reaching real-money selection,
would contaminate H-STOP, and no number in any report would reveal it.
"""

import math
from pathlib import Path

import pytest

from beatvegas.backtest.inseason import K_GRID, in_season_shift
from beatvegas.backtest.stopping import CHALLENGER, REGISTERED, sprt_bounds
from beatvegas.challenger import (
    PAPER_ARMS,
    SeasonRead,
    arm_context,
    arm_label,
    arm_predictions,
    blend,
    season_read,
    weight,
)
from beatvegas.db.models import ChallengerPick
from beatvegas.picks import graded_pick_fields

ROOT = Path(__file__).resolve().parent.parent


# --- the family is one family ------------------------------------------------


def test_the_live_arms_are_the_studied_arms():
    """The family cannot drift from the one H-INSEASON tested."""
    assert tuple(PAPER_ARMS) == tuple(K_GRID) == (25.0, 50.0, 100.0, 200.0)
    assert CHALLENGER["arms"] == [arm_label(k) for k in PAPER_ARMS]


def test_the_live_blend_is_the_studied_blend():
    """One arithmetic, two call sites: the backtest's per-game shift and the
    live one must agree, or the prospective phase measures a different thing
    from the developmental one."""
    c_prior, k = -1.81, 50.0
    raw = [20.0, 22.0, 24.0]
    actual = [27.0, 25.0, 31.0]
    read = SeasonRead.from_completed(raw, actual)
    live = blend(c_prior, read.c_season, read.n, k)

    # The backtest computes the same thing for a week-2 game that has seen the
    # same three week-1 games.
    import numpy as np

    week = np.array([1.0, 1.0, 1.0, 2.0])
    out = in_season_shift(
        np.array(week),
        np.array(raw + [0.0]),
        np.array(actual + [0.0]),
        c_prior=c_prior,
        k=k,
    )
    assert out["shift"][3] == pytest.approx(live)


# --- the estimator -----------------------------------------------------------


def test_no_completed_games_means_the_champion_exactly():
    assert blend(-1.81, None, 0, 50.0) == -1.81
    assert blend(-1.81, 2.0, 0, 50.0) == -1.81
    assert weight(0, 50.0) == 0.0


def test_the_weight_rises_with_n_and_falls_with_k():
    assert weight(50, 50.0) == pytest.approx(0.5)
    assert weight(150, 50.0) > weight(150, 200.0)
    assert weight(10, 25.0) < weight(100, 25.0)


def test_c_season_uses_the_raw_prediction_not_the_calibrated_one():
    """The one arithmetic mistake this design can make.

    A row's raw prediction is `bv_line - bv_intercept`. Taking `bv_line` itself
    would fold the champion's intercept into c_season and then apply it again,
    scaled by w -- and every report would look completely normal.
    """
    rows = [{"bv_line": 25.0, "bv_intercept": -2.0, "first_half_total": 30.0}]
    read = season_read(rows)
    assert read.n == 1
    assert read.c_season == pytest.approx(30.0 - 27.0)  # actual - RAW (25 - -2)
    assert read.c_season != pytest.approx(30.0 - 25.0)  # not actual - calibrated


def test_a_row_missing_its_intercept_is_skipped_not_guessed():
    rows = [
        {"bv_line": 25.0, "bv_intercept": None, "first_half_total": 30.0},
        {"bv_line": 20.0, "bv_intercept": -1.0, "first_half_total": 26.0},
    ]
    read = season_read(rows)
    assert read.n == 1 and read.c_season == pytest.approx(5.0)


def test_a_nonpositive_k_is_refused():
    with pytest.raises(ValueError, match="positive"):
        blend(-1.0, 1.0, 10, 0.0)


# --- arm predictions ---------------------------------------------------------


_PREDS = [
    {"game_id": 1, "model_version": "gbm_v2", "bv_line": 24.0, "bv_intercept": -1.8},
    {"game_id": 2, "model_version": "derived_lines", "line_used": 31.0},
    {"game_id": 3, "model_version": "gbm_v2", "bv_line": 26.0, "bv_intercept": None},
]


def test_only_model_rows_with_an_intercept_are_shifted():
    read = SeasonRead(n=100, c_season=1.2)
    out = arm_predictions(_PREDS, read, 50.0, model_version="gbm_v2")
    assert out[0]["bv_line"] != _PREDS[0]["bv_line"]
    assert out[0]["champion_bv_line"] == 24.0
    # A reference row is not model output; an intercept has no meaning for it.
    assert out[1] == _PREDS[1]
    # A model row with no stored intercept cannot be reconstructed, so it stands.
    assert out[2]["bv_line"] == 26.0


def test_arm_predictions_do_not_mutate_the_champions_rows():
    before = [dict(p) for p in _PREDS]
    arm_predictions(_PREDS, SeasonRead(n=100, c_season=1.2), 50.0, model_version="gbm_v2")
    assert _PREDS == before


def test_the_arm_line_is_the_raw_line_plus_the_blended_intercept():
    read = SeasonRead(n=50, c_season=1.0)
    out = arm_predictions(_PREDS, read, 50.0, model_version="gbm_v2")
    raw = 24.0 - (-1.8)
    assert out[0]["bv_line"] == pytest.approx(round(raw + blend(-1.8, 1.0, 50, 50.0), 2))


def test_arm_context_freezes_what_the_pick_needs():
    ctx = arm_context(-1.8, SeasonRead(n=60, c_season=0.9), 100.0)
    assert ctx["arm"] == "k100"
    assert ctx["in_season_n"] == 60
    assert ctx["in_season_weight"] == pytest.approx(60 / 160)
    assert set(ctx) == {"arm", "c_prior", "c_season", "in_season_n", "in_season_weight"}


# --- isolation from the money path ------------------------------------------


def test_a_challenger_row_has_no_real_money_flag():
    """There is no kind of challenger pick but paper, so there is no flag that
    could make one real."""
    cols = set(ChallengerPick.__table__.columns.keys())
    assert "is_paper" not in cols and "is_bonus" not in cols
    assert "challenger_picks" == ChallengerPick.__tablename__


def test_the_challenger_ledger_carries_every_graded_field_the_champion_does():
    """So `picks.grade_pick` settles an arm with the champion's own code."""
    fields = graded_pick_fields(30, 28.5, -110, 1.0, 29.0, 28.0, fair_open=0.5, fair_close=0.5)
    cols = set(ChallengerPick.__table__.columns.keys())
    missing = sorted(set(fields) - cols)
    assert not missing, missing


def test_nothing_in_the_challenger_modules_writes_the_money_ledger():
    """A grep, deliberately: the guarantee is structural and must stay checkable."""
    for name in ("beatvegas/challenger.py", "beatvegas/challenger_picks.py"):
        src = (ROOT / name).read_text()
        assert "ManualPick" not in src, f"{name} references the real-money ledger"
        assert "is_paper" not in src, f"{name} references the champion's paper flag"


def test_the_card_logs_challengers_only_where_it_logs_paper():
    """The challenger must never run on a path the champion's paper logger does
    not, and a challenger failure must never cost the real card."""
    src = (ROOT / "scripts/build_card.py").read_text()
    assert "log_challenger_picks" in src
    # Guarded: an exception in the measurement cannot break the bet card.
    i = src.index("challenger_added = log_challenger_picks")
    assert "try:" in src[max(0, i - 400) : i]
    assert "never cost the real card" in src[max(0, i - 400) : i]


def test_the_position_reader_cannot_pause_real_money():
    """H-STOP pauses the bankroll; this reader may not even import the switch."""
    src = (ROOT / "scripts/challenger_position.py").read_text()
    assert "rule_pause" not in src and "ManualPick" not in src


# --- the registered design ---------------------------------------------------


def test_the_challenger_budget_is_split_across_arms_and_clocks():
    assert CHALLENGER["alpha_total"] == 0.05
    assert CHALLENGER["alpha_arm"] == pytest.approx(0.05 / 4)
    assert CHALLENGER["alpha_clock"] == pytest.approx(0.05 / 4 / 2)
    # Stricter than the champion's, because this tests four correlated ledgers.
    assert CHALLENGER["alpha_clock"] < REGISTERED["alpha_clock"]


def test_the_alternatives_are_the_champions_reused_deliberately():
    assert CHALLENGER["mu1"] == REGISTERED["mu1"]
    assert CHALLENGER["sigma"] == REGISTERED["sigma"]


def test_h_stop_is_untouched_by_the_challenger_design():
    assert REGISTERED["alpha_clock"] == 0.025
    assert REGISTERED["observation"].startswith("the locked paper pick (manual_picks")


def test_the_spec_quotes_the_bounds_the_code_computes():
    b = sprt_bounds(CHALLENGER["alpha_clock"], 1 - CHALLENGER["power"])
    doc = (ROOT / "docs/INSEASON_PAPER.md").read_text()
    assert f"{b['A']:.4f}" in doc, b["A"]
    assert f"{abs(b['B']):.4f}" in doc, b["B"]
    assert f"{CHALLENGER['mu1']['profit']:.4f}" in doc
    assert f"{CHALLENGER['sigma']['profit']}" in doc


def test_the_spec_does_not_claim_the_developmental_pass_proved_betting_value():
    doc = (ROOT / "docs/INSEASON_PAPER.md").read_text().lower()
    assert "no prospective betting value" in doc
    assert "partly mechanical" in doc
    assert "no k has been chosen" in doc


def test_the_spec_states_the_multiple_passer_rule():
    doc = (ROOT / "docs/INSEASON_PAPER.md").read_text().lower()
    assert "if more than one arm passes" in doc
    assert "own registered row" in doc


def test_a_family_verdict_needs_both_clocks():
    from beatvegas.backtest.stopping import challenger_position

    # Not enough observations to cross anything: everything accrues.
    pos = challenger_position({"k25": {"units": [0.9, -1.0], "clv": [0.1, 0.2]}})
    assert pos["arms"]["k25"]["family_verdict"] == "accruing"
    assert pos["passers"] == [] and pos["may_name_k"] is False


def test_the_bounds_formula_reproduces_h_stops_published_numbers():
    """The same formula, checked against a number already in the repo's docs."""
    b = sprt_bounds(REGISTERED["alpha_clock"], 1 - REGISTERED["power"])
    assert b["A"] == pytest.approx(3.466, abs=5e-4)
    assert b["B"] == pytest.approx(-1.584, abs=5e-4)
    assert not math.isnan(b["A"])


def test_challenger_collection_is_paused_by_default(monkeypatch):
    """PAUSED 2026-09-22 before the first pick: the licensing gate read Holm p
    0.004 on the Mac and 0.056 on the runner, and until the two are reconciled
    no challenger row may be written. The switch is an explicit env flag the
    workflows do not set; the source guard below keeps the call behind it."""
    import importlib.util
    from pathlib import Path as _P

    path = _P(__file__).resolve().parent.parent / "scripts" / "build_card.py"
    spec = importlib.util.spec_from_file_location("build_card_pause", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.delenv("CHALLENGER_COLLECT", raising=False)
    assert mod.challenger_collection_enabled() is False
    monkeypatch.setenv("CHALLENGER_COLLECT", "true")
    assert mod.challenger_collection_enabled() is False, "only the literal 1 turns it on"
    monkeypatch.setenv("CHALLENGER_COLLECT", "1")
    assert mod.challenger_collection_enabled() is True
    src = path.read_text()
    guard = src.index("if not challenger_collection_enabled():")
    call = src.index("challenger_added = log_challenger_picks(")
    assert guard < call, "the logging call must sit behind the pause switch"
    assert "CHALLENGER_COLLECT" not in _P(path).resolve().parent.parent.joinpath(
        ".github", "workflows", "card.yml"
    ).read_text(), "card.yml must not turn collection on"
