"""H-ARM-EVP, the exploratory value-at-price collector (docs/program/EVP_SPEC_2026-10.md;
Tate's option A, 2026-10-14): the shift arithmetic against hand-worked values, the
eligibility rules (missing information never qualifies), the +2% threshold, one pick
per game, and that it sits outside the registered arms."""

import json
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from beatvegas import evp_paper as E
from beatvegas import protocol as P
from beatvegas.consensus import HalfPointTable
from beatvegas.db.models import ChallengerPick, ManualPick
from beatvegas.model.score import MODEL_VERSION
from tests.conftest import _sqlite_scope

ROOT = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 10, 13, 20, 10)  # a Tuesday build
KICK = datetime(2026, 10, 17, 19, 30)  # Saturday, 95 h out

# Uniform mass 0.1 on every whole total 24..33 at centre 28.5 (a hand-workable table).
TABLE = HalfPointTable(
    {
        "version": "test",
        "markets": {
            "1H_total": {"centers": {"28.5": {"mass": {str(k): 0.1 for k in range(24, 34)}}}}
        },
    }
)


def _item(gid=1, **kw):
    it = {
        "game_id": gid,
        "home": f"H{gid}",
        "away": f"A{gid}",
        "kick": KICK.isoformat(),
        "hr_centred": True,
        "hr_line": 28.5,
        "hr_price": -110,
        "fair_under": 0.5,
        "fair_source": "books",
        "market_line": 28.5,
        "bv_line": 26.5,  # 2 pts below the market: shift 0.4 toward the under
        "gap": 2.0,
    }
    it.update(kw)
    return it


def test_the_shift_is_a_fifth_of_the_model_market_difference():
    assert E.shift_points(28.5, 26.5) == pytest.approx(0.4)  # model below: more unders
    assert E.shift_points(28.5, 30.5) == pytest.approx(-0.4)  # model above: fewer
    assert E.shift_points(28.5, 28.5) == 0.0


def test_hand_worked_half_point_line():
    mass = TABLE.mass("1H_total", 28.5)
    # Market: P(under 28.5) = 0.5. Shift 0.4 down moves 0.4 of 29's mass under the line.
    assert E.shifted_under(mass, 28.5, 0.5, 0.4) == pytest.approx(0.54)
    # Shift 0.4 up moves 0.4 of 28's mass over it.
    assert E.shifted_under(mass, 28.5, 0.5, -0.4) == pytest.approx(0.46)
    assert E.shifted_under(mass, 28.5, 0.5, 0.0) == pytest.approx(0.5)


def test_hand_worked_whole_number_line():
    mass = TABLE.mass("1H_total", 28.5)
    # Decided 0.5 on 28 with P(push) 0.1 -> unconditional 0.45; the shift adds 0.4 x 0.1.
    assert E.shifted_under(mass, 28.0, 0.5, 0.4) == pytest.approx(0.49)


def test_the_value_at_hard_rocks_price():
    r, why = E.evaluate(_item(), TABLE)
    assert why is None
    assert r["p_under"] == pytest.approx(0.54) and r["p_push"] == 0.0
    # 0.54 x (100/110) - 0.46
    assert r["ev"] == pytest.approx(0.54 * 100 / 110 - 0.46, abs=1e-6)
    assert r["w"] == 0.8 and r["shift"] == pytest.approx(0.4) and r["table"] == "hp1"
    assert E.qualifies(r)  # +3.09%


def test_the_threshold_is_two_percent():
    assert E.EVP_MIN_EV == 0.02
    assert E.qualifies({"ev": 0.02})
    assert not E.qualifies({"ev": 0.0199})
    assert not E.qualifies({"ev": None})
    assert not E.qualifies(None)
    # Model level with the market: the market's own price, no value.
    r, _ = E.evaluate(_item(bv_line=28.5), TABLE)
    assert r["ev"] < 0 and not E.qualifies(r)


@pytest.mark.parametrize(
    "override, reason",
    [
        ({"hr_centred": False}, E.SKIP_NOT_MAIN),
        ({"hr_line": None}, E.SKIP_NOT_MAIN),
        ({"hr_price": None}, E.SKIP_NO_PRICE),
        ({"fair_under": None}, E.SKIP_NO_FAIR),
        ({"market_line": None}, E.SKIP_NO_MARKET),
        ({"bv_line": None}, E.SKIP_NO_MODEL),
        # A 10-pt shift crosses totals the table does not hold: unread, never logged.
        ({"bv_line": -21.5}, E.SKIP_TABLE),
    ],
)
def test_missing_or_uncertain_information_never_qualifies(override, reason):
    r, why = E.evaluate(_item(**override), TABLE)
    assert r is None and why == reason


def test_logs_each_qualifying_game_once_at_hard_rocks_main_line():
    eng, scope = _sqlite_scope()
    card = {
        "season": 2026,
        "week": 8,
        "slot": "tue_pm",
        # 1 qualifies; 2 reads below the threshold; 3 is an alternate line; 4 has no model.
        "items": [
            _item(1),
            _item(2, bv_line=28.0),
            _item(3, hr_centred=False),
            _item(4, bv_line=None),
        ],
    }
    preds = [{"game_id": 1, "model_version": MODEL_VERSION, "refit_id": 7}]
    with scope() as s:
        first = E.log_first_half(s, card, NOW, predictions=preds, table=TABLE)
        again = E.log_first_half(s, card, NOW, table=TABLE)
    assert first == {
        "items": 4,
        "read": 2,
        "qualifying": 1,
        "added": 1,
        "skipped": {E.SKIP_NOT_MAIN: 1, E.SKIP_NO_MODEL: 1},
    }
    assert again["added"] == 0 and again["qualifying"] == 1
    with Session(eng) as s:
        (r,) = s.query(ChallengerPick).all()
        assert (r.arm, r.side, r.market, r.game_id) == ("H-ARM-EVP", "under", "1H", 1)
        assert r.line == 28.5 and r.price == -110 and r.book == "hardrockbet"
        assert r.slot == "tue_pm" and r.placed_at == NOW and r.gap_at_pick == 2.0
        assert r.refit_id == 7
        frozen = json.loads(r.factors_json_at_pick)
        assert frozen["market_line"] == 28.5 and frozen["bv_line"] == 26.5
        assert frozen["w"] == 0.8 and frozen["min_ev"] == 0.02
        assert frozen["ev"] == pytest.approx(0.030909, abs=1e-6)
        assert s.query(ManualPick).count() == 0


def test_respects_the_paper_window():
    eng, scope = _sqlite_scope()
    card = {"season": 2026, "week": 8, "slot": "tue_pm", "items": [_item(1)]}
    with scope() as s:
        assert E.log_first_half(s, card, NOW, window_hours=48, table=TABLE)["added"] == 0
        assert E.log_first_half(s, card, NOW, window_hours=None, table=TABLE)["added"] == 1


def test_the_blend_weight_is_the_frozen_h3a_fit():
    blend = json.loads((ROOT / "data" / "blend.json").read_text())
    assert E.EVP_BLEND_W == blend["w"] == 0.8


def test_it_is_exploratory_outside_the_registered_arms():
    assert E.ARM_EVP == "H-ARM-EVP"
    assert E.ARM_EVP not in P.ARMS
    assert E.ARM_EVP not in P.ARM_STARTS


def test_the_summary_line():
    assert E.summary_lines(None)[0].endswith(": not run")
    line = E.summary_lines(
        {"items": 57, "read": 55, "qualifying": 2, "added": 1, "skipped": {"not_main_line": 2}}
    )[0]
    assert "EXPLORATORY H-ARM-EVP" in line and "no alpha" in line
    assert "2 of 55 games read qualify, +1 logged; not read: not_main_line 2" in line
