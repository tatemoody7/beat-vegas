"""Devig math — shared known vectors, mirrored by web/lib/devig.test.ts."""

import pytest

from beatvegas.devig import american_to_prob, devig_two_way, ev_under


def test_american_to_prob():
    assert american_to_prob(-110) == pytest.approx(0.52381, abs=1e-4)
    assert american_to_prob(120) == pytest.approx(0.45455, abs=1e-4)
    assert american_to_prob(100) == pytest.approx(0.5, abs=1e-9)


def test_symmetric_minus110_fair_half_and_hold():
    fo, fu, hold = devig_two_way(-110, -110, method="multiplicative")
    assert fo == pytest.approx(0.5, abs=1e-6)
    assert fu == pytest.approx(0.5, abs=1e-6)
    # -110/-110 standard hold ~4.55%.
    assert hold == pytest.approx(0.0476, abs=1e-3)


@pytest.mark.parametrize("method", ["multiplicative", "power", "shin"])
def test_fair_probs_sum_to_one(method):
    fo, fu, _ = devig_two_way(-130, 110, method=method)
    assert fo + fu == pytest.approx(1.0, abs=1e-6)


def test_under_favored_pushes_fair_under_above_half():
    # Under is the favorite (-130); its fair prob should exceed 0.5.
    _, fu, _ = devig_two_way(110, -130, method="multiplicative")
    assert fu > 0.5


def test_methods_diverge_on_lopsided_line():
    # On a skewed line the methods should not all agree (the reason power/shin
    # exist). Symmetric lines, by contrast, collapse to the same answer.
    mult = devig_two_way(-300, 240, method="multiplicative")[1]
    shin = devig_two_way(-300, 240, method="shin")[1]
    power = devig_two_way(-300, 240, method="power")[1]
    assert abs(mult - shin) > 1e-3 or abs(mult - power) > 1e-3


def test_symmetric_methods_agree():
    mult = devig_two_way(-110, -110, method="multiplicative")[1]
    shin = devig_two_way(-110, -110, method="shin")[1]
    power = devig_two_way(-110, -110, method="power")[1]
    assert mult == pytest.approx(shin, abs=1e-4)
    assert mult == pytest.approx(power, abs=1e-4)


def test_ev_under_sign():
    # Fair under is 0.55 but the book pays -110: clearly +EV.
    assert ev_under(0.55, -110) > 0
    # Fair under 0.50 at -110 is -EV (you pay the vig).
    assert ev_under(0.50, -110) < 0
    # Fair under 0.50 at +100 is break-even.
    assert ev_under(0.50, 100) == pytest.approx(0.0, abs=1e-9)


def test_unknown_method_raises():
    with pytest.raises(ValueError):
        devig_two_way(-110, -110, method="bogus")
