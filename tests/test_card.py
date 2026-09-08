"""beatvegas/card.py — the pure card rules, mirroring web/lib/edge.ts.

Every scenario builds plain rows (no DB) and checks the tier, the blocker, the
action wording, the kill numbers and the payload contract the Board renders."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from beatvegas.card import (
    EXCHANGE_BOOKS,
    EXCHANGE_MAX_AGE_H,
    EXCHANGE_MAX_HOLD,
    FAIR_PRICE_EXCLUDED,
    FAIR_PRICE_LINE_WINDOW,
    FAIR_PRICE_WIDE_WINDOW,
    PAPER_BLOCKERS,
    break_even_price,
    build_card,
    fair_price_window,
    hold_note,
    kill_line,
    market_read,
    round_half_up,
)
from beatvegas.devig import devig_two_way, ev_under
from beatvegas.model.score import BET_GAP_PTS, EV_FLOOR

NOW = datetime(2026, 9, 18, 22, 5)  # Friday 6:05pm ET, in UTC
KICK = NOW + timedelta(days=1)


def game(gid=1, away="Kansas", home="Missouri", kick=KICK):
    return {"game_id": gid, "away": away, "home": home, "kick": kick}


def snap(gid, book, line, over=-110, under=-110, hours_ago=1.0):
    return {
        "game_id": gid,
        "book": book,
        "line": line,
        "over_price": over,
        "under_price": under,
        "captured_at": NOW - timedelta(hours=hours_ago),
    }


def market(gid, line, books=("draftkings", "fanduel", "betmgm"), over=100, under=-120):
    """The other books, shaded toward the under (fair under 0.5217) so Hard
    Rock's plain -110 reads as a fair price (ev -0.4%). At a flat -110/-110
    market the fair under is 0.5: -110 (ev -4.5%) is inside the -5% floor,
    -115 (ev -6.5%) is not."""
    return [snap(gid, b, line, over, under) for b in books]


FAIR_UNDER = 12 / 23  # devig of +100/-120


def model(gid, bv_line, line_used=None):
    return {"game_id": gid, "model_version": "gbm_v1", "bv_line": bv_line, "line_used": line_used}


def card(games, snaps, preds=(), previews=(), **kw):
    kw.setdefault("season", 2026)
    kw.setdefault("week", 3)
    kw.setdefault("now", NOW)
    return build_card(games, snaps, list(preds), list(previews), **kw)


def only(c):
    assert len(c["items"]) == 1, c["items"]
    return c["items"][0]


# --- tiers ---------------------------------------------------------------------


def test_bet_path_logs_hard_rocks_number_and_price():
    snaps = [snap(1, "hardrockbet", 24.5, -110, -110)] + market(1, 24.5)
    c = card([game()], snaps, [model(1, 22.4)])
    it = only(c)
    assert it["tier"] == "BET" and it["blocker"] is None
    assert it["hr_line"] == 24.5 and it["hr_price"] == -110
    assert it["market_line"] == 24.5 and it["gap"] == 2.1 and it["bv_line"] == 22.4
    assert it["fair_under"] == pytest.approx(FAIR_UNDER, abs=1e-4)
    assert it["ev"] == pytest.approx(-0.004, abs=1e-3)  # fair: inside the -5% floor
    # -120 vs fair 0.5217 is -4.7% (inside); -125 is -6.1% (outside).
    assert it["kill_line"] == 24.5 and it["kill_price"] == -120
    assert it["action"] == "Bet now: 1H under 24.5 at -110 on Hard Rock."
    assert c["counts"] == {"bet": 1, "edge": 0, "pass": 0, "over_cap": 0, "degraded": 0}
    assert c["model_read"] is True and c["notes"] == []
    assert it["paper_logged"] is False


def test_edge_no_hr_line_uses_the_market_median_as_basis():
    c = card([game()], market(1, 25.0), [model(1, 22.4)])
    it = only(c)
    assert it["tier"] == "EDGE" and it["blocker"] == "no_hr_line"
    assert it["hr_line"] is None and it["market_line"] == 25.0 and it["gap"] == 2.6
    assert it["kill_line"] == 24.5
    assert it["action"] == "No Hard Rock line yet. A bet at under 24.5 or higher, -110 or better."
    assert "Hard Rock hasn’t posted a first-half line for this game yet." in it["why"]


def test_edge_off_market_when_hard_rock_sits_below_the_market():
    snaps = [snap(1, "hardrockbet", 24.0)] + market(1, 25.0)
    it = only(card([game()], snaps, [model(1, 21.5)]))
    assert it["tier"] == "EDGE" and it["blocker"] == "off_market"
    assert it["market_line"] == 25.0 and it["gap"] == 2.5  # gap is vs Hard Rock's own number
    assert it["fair_under"] is None and it["ev"] is None  # no other book at 24.0 -> no fair price
    assert it["action"] == (
        "Wait: Hard Rock’s 24.0 is 1.0 below the market’s 25.0 — giving up points and a void "
        "risk. Bet if it moves to 24.5 or higher."
    )


def test_edge_price_when_hard_rock_is_worse_than_fair():
    snaps = [snap(1, "hardrockbet", 24.5, -110, -125)] + market(1, 24.5)
    it = only(card([game()], snaps, [model(1, 22.4)]))
    assert it["tier"] == "EDGE" and it["blocker"] == "price"
    assert it["ev"] == pytest.approx(-0.0609, abs=1e-3) and it["ev"] < EV_FLOOR
    assert it["kill_price"] == -120  # worst price still inside the floor vs the market's fair
    assert it["action"] == "Wait: Hard Rock is -125; needs -120 or better."
    assert any("worse than the market’s fair price" in w for w in it["why"])


def test_edge_qb_out_blocks_the_bet_and_flags_it():
    snaps = [snap(1, "hardrockbet", 24.5)] + market(1, 24.5)
    prev = [{"game_id": 1, "qb_out": True, "qb_out_detail": "Missouri QB Smith (knee) out"}]
    it = only(card([game()], snaps, [model(1, 22.4)], prev))
    assert it["tier"] == "EDGE" and it["blocker"] == "qb_out"
    assert it["action"] == (
        "Wait: a starting QB is listed out — re-check the number after the news settles."
    )
    assert any(w.startswith("QB OUT") and "Smith" in w for w in it["why"])


def test_edge_gap_blocker_when_the_score_clears_60_short_of_the_bar():
    snaps = [snap(1, "hardrockbet", 24.5)] + market(1, 24.5)
    it = only(card([game()], snaps, [model(1, 23.2)]))  # gap 1.3 -> score 63
    assert it["tier"] == "EDGE" and it["blocker"] == "gap"
    assert it["gap"] == 1.3 and it["kill_line"] == 25.0
    assert it["action"] == "Pass: the line is only 1.3 above our number; needs 25.0 or higher."


def test_no_model_price_only_edge():
    snaps = [snap(1, "hardrockbet", 24.5, -115, 105)] + market(1, 24.5)
    c = card([game()], snaps)
    it = only(c)
    assert it["tier"] == "EDGE" and it["blocker"] == "no_model"
    assert it["bv_line"] is None and it["gap"] is None and it["kill_line"] is None
    assert it["ev"] == pytest.approx(0.0696, abs=1e-3)
    assert it["action"] == (
        "Price only: Hard Rock pays 7.0% better than the market on this under. No model behind it."
    )
    assert c["model_read"] is False
    assert c["notes"][0].startswith("No model read this week (weeks 1-2)")


def test_no_model_pass_and_reference_line_in_why():
    snaps = [snap(1, "hardrockbet", 24.5)] + market(1, 24.5)
    it = only(card([game()], snaps))
    assert it["tier"] == "PASS" and it["blocker"] is None
    assert it["action"] == "Pass: no model read this week and no price edge at Hard Rock."
    assert it["why"][0].startswith("No model read yet")


def test_model_pass_leans_over_wording():
    snaps = [snap(1, "hardrockbet", 22.0)] + market(1, 22.0)
    it = only(card([game()], snaps, [model(1, 24.0)]))
    assert it["tier"] == "PASS"
    assert it["gap"] == -2.0 and it["kill_line"] == 26.0
    assert it["action"] == (
        "Pass: the line is 2.0 below our number (leans over); needs 26.0 or higher."
    )


def test_hard_rock_gap_gates_the_bet_not_the_consensus_gap():
    # Market clears the bar, Hard Rock's own number is lower but within 0.5.
    snaps = [snap(1, "hardrockbet", 24.0)] + market(1, 24.5)
    it = only(card([game()], snaps, [model(1, 22.4)]))
    assert it["tier"] != "BET" and it["gap"] == 1.6  # gap is vs Hard Rock's line


def test_derived_reference_is_the_basis_when_no_book_has_posted():
    preds = [
        model(1, 22.0, line_used=23.0),
        {"game_id": 1, "model_version": "derived_lines", "bv_line": None, "line_used": 24.0},
    ]
    it = only(card([game()], [], preds))
    assert it["market_line"] is None and it["gap"] == 2.0  # derived_lines row wins
    assert it["tier"] == "EDGE" and it["blocker"] == "no_hr_line"
    assert it["action"] == "No Hard Rock line yet. A bet at under 24.0 or higher, -110 or better."


def test_no_line_at_all_wording():
    it = only(card([game()], [], [model(1, 22.0)]))
    assert it["gap"] is None and it["tier"] == "PASS" and it["blocker"] is None
    assert it["action"] == "No line captured yet. A bet at under 24.0 or higher, -110 or better."
    assert it["why"][0].startswith("Our number for the first half is 22.0, but no Vegas line")


# --- market read ------------------------------------------------------------------


def test_fair_price_excludes_hard_rock_fliff_consensus_and_off_line_exchanges():
    assert {"hardrockbet", "fliff", "consensus", "kalshi", "novig", "prophetx", "betopenly"} <= set(
        FAIR_PRICE_EXCLUDED
    )
    assert EXCHANGE_BOOKS == {"kalshi", "polymarket", "novig", "prophetx", "betopenly"}
    snaps = [
        snap(1, "hardrockbet", 24.5, -110, -105),
        snap(1, "draftkings", 24.5, -110, -110),
        snap(1, "fliff", 24.5, 100, 100),  # would drag fair to 0.5 exactly; excluded
        snap(1, "kalshi", 25.0, 100, 100),  # exchange at ANOTHER line: never in the book median
        snap(1, "consensus", 30.0, -110, -110),  # synthetic: not in the market line either
        snap(1, "betmgm", 25.5, -105, -115),  # a full point away: outside the 0.5 window
    ]
    m = market_read(snaps)
    assert m["fair_under"] == pytest.approx(0.5) and m["fair_source"] == "books"
    assert m["n_exchange"] == 0
    assert m["market_line"] == 24.5  # median of HR, DK, fliff, kalshi, MGM (24.5 x3, 25.0, 25.5)
    assert m["hr_line"] == 24.5 and m["hr_price"] == -105


def test_exchange_quote_at_hard_rocks_exact_line_is_the_fair_price():
    """Exchange-first: a ~0-hold exchange priced at Hard Rock's SAME number is a
    sharper fair price than the books' de-vigged median, so it wins outright."""
    snaps = [
        snap(1, "hardrockbet", 24.5, -110, -110),
        snap(1, "draftkings", 24.5, 100, -120),
        snap(1, "kalshi", 24.5, 100, -102),
    ]
    m = market_read(snaps)
    assert m["fair_source"] == "exchange" and m["n_exchange"] == 1
    assert m["fair_under"] == pytest.approx(devig_two_way(100, -102)[1])
    assert m["fair_under"] != pytest.approx(FAIR_UNDER)  # DK's shaded read no longer enters
    assert m["ev"] == pytest.approx(ev_under(m["fair_under"], -110))
    # two exchanges at the line -> the mean of their de-vigged unders
    snaps.append(snap(1, "novig", 24.5, -104, 102))
    m2 = market_read(snaps)
    k, n = devig_two_way(100, -102)[1], devig_two_way(-104, 102)[1]
    assert m2["n_exchange"] == 2 and m2["fair_under"] == pytest.approx((k + n) / 2)


def test_exchange_at_another_line_falls_back_to_the_book_median():
    snaps = [
        snap(1, "hardrockbet", 24.5, -110, -110),
        snap(1, "draftkings", 24.5, 100, -120),
        snap(1, "kalshi", 25.0, 100, -102),  # half a point off: not the same market
    ]
    m = market_read(snaps)
    assert m["fair_source"] == "books" and m["n_exchange"] == 0
    assert m["fair_under"] == pytest.approx(FAIR_UNDER)


def test_exchange_with_one_side_unpriced_does_not_count():
    snaps = [snap(1, "hardrockbet", 24.5), snap(1, "kalshi", 24.5, None, -102)]
    m = market_read(snaps)
    assert m["fair_under"] is None and m["fair_source"] is None and m["n_exchange"] == 0


def test_a_wide_exchange_quote_is_ignored_and_the_book_median_wins():
    """An exchange only earns the fair price by being ~0-hold. One wide illiquid
    two-way (+200/-500, hold 16.7%) de-vigs to a fair under near 0.71 — enough on
    its own to flip a BET and set the kill price — so it never enters."""
    assert EXCHANGE_MAX_HOLD == 0.02
    assert devig_two_way(200, -500)[2] > EXCHANGE_MAX_HOLD
    assert devig_two_way(200, -500)[1] > 0.7  # what it would have claimed as fair
    snaps = [
        snap(1, "hardrockbet", 24.5, -110, -110),
        snap(1, "kalshi", 24.5, 200, -500),  # wide: dropped
    ] + market(1, 24.5)
    m = market_read(snaps, now=NOW)
    assert m["n_exchange"] == 0 and m["fair_source"] == "books"
    assert m["fair_under"] == pytest.approx(FAIR_UNDER)
    # ...and a hold exactly ON the cap still counts (the bound is "exceeds").
    snaps = [snap(1, "hardrockbet", 24.5, -110, -110), snap(1, "kalshi", 24.5, 100, -102)]
    assert market_read(snaps, now=NOW)["n_exchange"] == 1


def test_a_stale_exchange_quote_is_ignored():
    """_latest_by_book keeps a book's newest row forever, so a delisted Friday
    exchange quote is still 'latest' on Saturday. Anything older than
    EXCHANGE_MAX_AGE_H before the build is not a live price."""
    assert EXCHANGE_MAX_AGE_H == 24.0
    snaps = [
        snap(1, "hardrockbet", 24.5, -110, -110),
        snap(1, "kalshi", 24.5, 100, -102, hours_ago=30),  # stale: dropped
    ] + market(1, 24.5)
    m = market_read(snaps, now=NOW)
    assert m["n_exchange"] == 0 and m["fair_source"] == "books"
    assert m["fair_under"] == pytest.approx(FAIR_UNDER)
    # the card build passes its own `now`, so the same row is stale on the card
    it = only(card([game()], snaps, [model(1, 22.4)]))
    assert it["fair_source"] == "books"
    # with no reference instant the newest snapshot in the set stands in for now
    assert market_read(snaps)["n_exchange"] == 0
    # an unknown capture time is not evidence of staleness: keep the quote
    undated = dict(snap(1, "kalshi", 24.5, 100, -102), captured_at=None)
    assert (
        market_read([snap(1, "hardrockbet", 24.5, -110, -110), undated], now=NOW)["n_exchange"] == 1
    )


def test_a_tight_fresh_exchange_quote_still_wins_over_the_books():
    snaps = [
        snap(1, "hardrockbet", 24.5, -110, -110),
        snap(1, "kalshi", 24.5, 100, -102, hours_ago=6),
    ] + market(1, 24.5)
    m = market_read(snaps, now=NOW)
    assert m["n_exchange"] == 1 and m["fair_source"] == "exchange"
    assert m["fair_under"] == pytest.approx(devig_two_way(100, -102)[1])


def test_three_or_more_exchange_quotes_use_the_median_not_the_mean():
    """One odd quote among several must not drag the fair price."""
    snaps = [
        snap(1, "hardrockbet", 24.5, -110, -110),
        snap(1, "kalshi", 24.5, 100, -102),
        snap(1, "novig", 24.5, -104, 102),
        snap(1, "prophetx", 24.5, -101, 101),
    ]
    fairs = sorted(devig_two_way(o, u)[1] for o, u in ((100, -102), (-104, 102), (-101, 101)))
    m = market_read(snaps, now=NOW)
    assert m["n_exchange"] == 3 and m["fair_under"] == pytest.approx(fairs[1])


def test_fair_price_window_widens_below_only_when_hard_rock_is_above_the_market():
    assert (FAIR_PRICE_LINE_WINDOW, FAIR_PRICE_WIDE_WINDOW) == (0.5, 1.5)
    assert fair_price_window(0.5) == (1.5, 0.5)
    assert fair_price_window(0.0) == (0.5, 0.5)
    assert fair_price_window(-0.5) == (0.5, 0.5)
    assert fair_price_window(None) == (0.5, 0.5)


def test_hard_rock_above_the_market_is_priced_by_the_books_a_point_below():
    """Hard Rock a full point ABOVE the market is the best case for an under —
    and by construction no book is within half a point, so the like-for-like
    window would leave the price unjudgeable and paper the bet. A book at a
    LOWER total is a conservative reference, so it is allowed in to 1.5."""
    snaps = [snap(1, "hardrockbet", 25.5, -110, -110)] + market(1, 24.5)
    it = only(card([game()], snaps, [model(1, 23.0)]))
    assert it["hr_vs_market"] == 1.0 and it["gap"] == 2.5
    assert it["fair_source"] == "books"
    assert it["fair_under"] == pytest.approx(FAIR_UNDER, abs=1e-4)
    assert it["tier"] == "BET" and it["blocker"] is None and it["paper_blocker"] is None


def test_a_book_two_points_below_hard_rock_is_still_no_fair_price():
    snaps = [snap(1, "hardrockbet", 25.5, -110, -110)] + market(1, 23.5)
    it = only(card([game()], snaps, [model(1, 23.0)]))
    assert it["hr_vs_market"] == 2.0
    assert it["fair_under"] is None and it["fair_source"] is None
    assert it["tier"] == "EDGE" and it["blocker"] == "no_fair_price"
    assert it["paper_blocker"] == "no_fair_price"


def test_hard_rock_below_the_market_keeps_the_half_point_window_and_off_market():
    """The widening is one-directional: below the market Hard Rock is still an
    off-market number, which is the blocker that fires."""
    snaps = [snap(1, "hardrockbet", 23.5, -110, -110)] + market(1, 24.5)
    it = only(card([game()], snaps, [model(1, 21.0)]))
    assert it["hr_vs_market"] == -1.0
    assert it["fair_under"] is None  # the 24.5 books stay outside the 0.5 window
    assert it["tier"] == "EDGE" and it["blocker"] == "off_market"
    assert it["paper_blocker"] == "off_market"


def test_hr_vs_market_is_hard_rock_minus_the_other_books_median():
    assert market_read([snap(1, "hardrockbet", 25.0)] + market(1, 24.5))["hr_vs_market"] == 0.5
    assert market_read([snap(1, "hardrockbet", 24.0)] + market(1, 24.5))["hr_vs_market"] == -0.5
    assert market_read([snap(1, "hardrockbet", 24.5)] + market(1, 24.5))["hr_vs_market"] == 0.0
    assert market_read([snap(1, "hardrockbet", 24.5)])["hr_vs_market"] is None  # HR alone
    assert market_read(market(1, 24.5))["hr_vs_market"] is None  # no Hard Rock
    # the synthetic aggregate never enters the median; Hard Rock itself neither
    snaps = [snap(1, "hardrockbet", 25.0), snap(1, "draftkings", 24.5), snap(1, "consensus", 30.0)]
    assert market_read(snaps)["hr_vs_market"] == 0.5


def test_latest_snapshot_per_book_and_hard_rock_open():
    snaps = [
        snap(1, "hardrockbet", 23.5, hours_ago=30),
        snap(1, "hardrockbet_fl", 24.5, hours_ago=1),  # alias folds onto hardrockbet
        snap(1, "draftkings", 23.0, hours_ago=20),
        snap(1, "draftkings", 24.5, hours_ago=2),
    ]
    m = market_read(snaps)
    assert m["hr_line"] == 24.5 and m["hr_open"] == 23.5 and m["market_line"] == 24.5
    it = only(card([game()], snaps, [model(1, 22.4)]))
    assert "Hard Rock opened at 23.5 and has moved up to 24.5." in it["why"]


# --- kill numbers -----------------------------------------------------------------


def test_round_half_up_and_kill_line():
    assert round_half_up(23.55) == 24.0
    assert round_half_up(23.1) == 23.5
    assert round_half_up(23.5) == 23.5
    assert kill_line(22.4) == round_half_up(22.4 + BET_GAP_PTS) == 24.5
    assert kill_line(23.2) == 25.0


def test_break_even_price_is_the_worst_price_inside_the_floor():
    assert EV_FLOOR == -0.05
    assert break_even_price(0.5) == -110  # -110 is -4.5%: inside; -115 is -6.5%
    assert break_even_price(0.55) == -135  # -135 is -4.3%; -140 is -5.7%
    assert break_even_price(0.52) == -120  # -120 is -4.7%; -125 is -6.4%
    assert break_even_price(FAIR_UNDER) == -120
    assert break_even_price(0.48) == 100  # +100 is -4.0%; -105 is -6.3%; never -100
    assert break_even_price(0.0) is None
    for fair in (0.48, 0.5, 0.52, FAIR_UNDER, 0.55):
        p = break_even_price(fair)
        assert ev_under(fair, p) >= EV_FLOOR
        assert ev_under(fair, p - 5 if p != 100 else -105) < EV_FLOOR


def test_standard_juice_passes_the_price_gate_and_a_nickel_more_does_not():
    """Headline of the -0.05 floor: at a balanced -110/-110 market (fair under
    0.5) Hard Rock's own -110 is a BET; -115 is EDGE / price."""
    balanced = market(1, 24.5, over=-110, under=-110)
    at_110 = only(
        card([game()], [snap(1, "hardrockbet", 24.5, -110, -110)] + balanced, [model(1, 22.4)])
    )
    assert at_110["fair_under"] == pytest.approx(0.5)
    assert at_110["ev"] == pytest.approx(-0.0455, abs=1e-3) and at_110["ev"] >= EV_FLOOR
    assert at_110["tier"] == "BET" and at_110["blocker"] is None
    assert at_110["kill_price"] == -110
    assert at_110["action"] == "Bet now: 1H under 24.5 at -110 on Hard Rock."

    at_115 = only(
        card([game()], [snap(1, "hardrockbet", 24.5, -110, -115)] + balanced, [model(1, 22.4)])
    )
    assert at_115["ev"] == pytest.approx(-0.0652, abs=1e-3) and at_115["ev"] < EV_FLOOR
    assert at_115["tier"] == "EDGE" and at_115["blocker"] == "price"
    assert at_115["kill_price"] == -110
    assert at_115["action"] == "Wait: Hard Rock is -115; needs -110 or better."


# --- ordering, filtering, notes -------------------------------------------------


def test_items_sort_bet_then_edge_by_gap_then_pass_by_gap_then_ev():
    k = [KICK + timedelta(hours=i) for i in range(5)]
    games = [game(i + 1, away=f"A{i}", home=f"H{i}", kick=k[i]) for i in range(5)]
    snaps = []
    # 1: PASS, fair price (ev 0)
    snaps += [snap(1, "hardrockbet", 24.5)] + market(1, 24.5)
    # 2: EDGE price, ev strongly negative
    snaps += [snap(2, "hardrockbet", 24.5, -110, -130)] + market(2, 24.5)
    # 3: BET (Hard Rock a nickel better than -110)
    snaps += [snap(3, "hardrockbet", 24.5, -115, -105)] + market(3, 24.5)
    # 4: EDGE no_hr_line (ev None -> after any priced EDGE)
    snaps += market(4, 25.0)
    # 5: PASS with a positive price (ev > 0) -> ahead of PASS #1
    snaps += [snap(5, "hardrockbet", 24.5, -120, 100)] + market(5, 24.5)
    preds = [model(1, 24.0), model(2, 22.4), model(3, 22.4), model(4, 22.4), model(5, 24.0)]
    c = card(games, snaps, preds)
    order = [(it["game_id"], it["tier"]) for it in c["items"]]
    # gap first (4: 2.6 beats 2: 2.1); equal gaps (5 and 1, both 0.5) fall back to ev
    assert order == [(3, "BET"), (4, "EDGE"), (2, "EDGE"), (5, "PASS"), (1, "PASS")]
    assert c["counts"] == {"bet": 1, "edge": 2, "pass": 2, "over_cap": 0, "degraded": 0}


def test_only_games_still_to_kick_off_are_on_the_card():
    games = [game(1, kick=NOW - timedelta(hours=1)), game(2, kick=NOW + timedelta(hours=1))]
    c = card(games, market(1, 24.5) + market(2, 24.5), [model(1, 22.0), model(2, 22.0)])
    assert [it["game_id"] for it in c["items"]] == [2]


def test_timezone_aware_inputs_are_normalized_to_utc():
    aware_now = NOW.replace(tzinfo=timezone.utc)
    aware_kick = KICK.replace(tzinfo=timezone.utc)
    c = card([game(kick=aware_kick)], market(1, 24.5), [model(1, 22.0)], now=aware_now)
    assert c["built_at"] == "2026-09-18T22:05:00Z"
    assert only(c)["kick"] == "2026-09-19T22:05:00Z"


def test_hold_note_when_hard_rock_charges_three_cents_more():
    snaps = [snap(1, "hardrockbet", 24.5, -120, -120)] + market(1, 24.5)  # 9.1% vs 4.5%
    c = card([game()], snaps, [model(1, 22.4)])
    assert any(
        n.startswith("Hard Rock’s average hold on this slate is 9.1% vs 4.5%") for n in c["notes"]
    )
    # a fair-priced Hard Rock produces no note
    c2 = card([game()], [snap(1, "hardrockbet", 24.5)] + market(1, 24.5), [model(1, 22.4)])
    assert not any(n.startswith("Hard Rock’s average hold") for n in c2["notes"])
    assert hold_note([]) is None


def test_no_hard_rock_line_anywhere_note():
    c = card([game()], market(1, 24.5), [model(1, 24.0)])
    assert "Hard Rock has not posted a first-half line on any game yet." in c["notes"]


# --- contract ---------------------------------------------------------------------

ITEM_KEYS = {
    "game_id",
    "away",
    "home",
    "kick",
    "tier",
    "blocker",
    "hr_line",
    "hr_price",
    "hr_open",
    "market_line",
    "fair_under",
    "fair_source",
    "hr_vs_market",
    "ev",
    "bv_line",
    "gap",
    "kill_line",
    "kill_price",
    "action",
    "why",
    "paper_logged",
    # paper ledger + weekly cap
    "qualifies",
    "paper_blocker",
    "cap_rank",
    "over_cap",
    "degraded_inputs",
    # display chips
    "full_game_total",
    "spread",
    "total_band",
    "hook_side",
    "key_dist",
}


def test_payload_contract_and_strict_json_round_trip():
    nan = float("nan")
    snaps = [snap(1, "hardrockbet", 24.5, nan, nan)] + market(1, 24.5)
    preds = [model(1, nan), {"game_id": 1, "model_version": "derived_lines", "line_used": 24.5}]
    c = card([game()], snaps, preds)
    assert set(c) == {
        "season",
        "week",
        "built_at",
        "model_read",
        "slot",
        "status",
        "degraded",
        "counts",
        "paper",
        "items",
        "notes",
    }
    assert set(c["counts"]) == {"bet", "edge", "pass", "over_cap", "degraded"}
    it = only(c)
    assert set(it) == ITEM_KEYS
    assert it["hr_price"] is None and it["bv_line"] is None  # NaN read as missing
    text = json.dumps(c, allow_nan=False)  # raises on any NaN/inf
    back = json.loads(text)
    assert back == c
    assert back["items"][0]["tier"] in {"BET", "EDGE", "PASS"}


# --- paper ledger: qualifying games, blockers, chips, the weekly cap (2026-09-07) --

from beatvegas.card import apply_weekly_cap, hook_side, key_dist, total_band  # noqa: E402
from beatvegas.model.score import WEEKLY_BET_CAP  # noqa: E402


def test_bet_item_qualifies_with_no_paper_blocker():
    snaps = [snap(1, "hardrockbet", 24.5, -110, -110)] + market(1, 24.5)
    it = only(card([game()], snaps, [model(1, 22.4)]))
    assert it["qualifies"] is True and it["paper_blocker"] is None
    assert it["cap_rank"] == 1 and it["over_cap"] is False


def test_price_blocked_edge_qualifies_with_blocker_price():
    snaps = [snap(1, "hardrockbet", 24.5, -110, -125)] + market(1, 24.5)
    it = only(card([game()], snaps, [model(1, 22.4)]))
    assert it["tier"] == "EDGE" and it["qualifies"] is True and it["paper_blocker"] == "price"


def test_off_market_pass_still_qualifies_with_blocker_off_market():
    """gap 2.0 at Hard Rock but 1.0 under the market: score 70-10 = 60 -> EDGE;
    with a QB out too the score drops to 55 -> PASS. Either way it qualifies and
    the paper ledger tags off_market first (gate order)."""
    snaps = [snap(1, "hardrockbet", 24.0)] + market(1, 25.0)
    prev = [{"game_id": 1, "qb_out": True, "qb_out_detail": "QB out"}]
    it = only(card([game()], snaps, [model(1, 22.0)], prev))
    assert it["tier"] == "PASS" and it["blocker"] is None
    assert it["qualifies"] is True and it["paper_blocker"] == "off_market"


def test_no_comparable_price_is_a_paper_only_edge_with_blocker_no_fair_price():
    """Hard Rock alone at 24.5 -110: the gap qualifies but no book or exchange
    is priced at that number, so the price cannot be judged. Never a BET."""
    snaps = [snap(1, "hardrockbet", 24.5, -110, -110)]
    c = card([game()], snaps, [model(1, 22.4)])
    it = only(c)
    assert it["qualifies"] is True and it["gap"] == 2.1
    assert it["ev"] is None and it["fair_under"] is None and it["fair_source"] is None
    assert it["tier"] == "EDGE" and it["blocker"] == "no_fair_price"
    assert it["paper_blocker"] == "no_fair_price"
    assert it["action"] == (
        "Wait: Hard Rock’s -110 can’t be judged — no other book or exchange is priced at 24.5. "
        "Paper only until a comparable price appears."
    )
    assert it["hr_vs_market"] is None
    assert c["counts"] == {"bet": 0, "edge": 1, "pass": 0, "over_cap": 0, "degraded": 0}
    assert c["paper"]["qualifying"] == 1


def test_unpriced_hard_rock_line_is_blocked_as_no_fair_price():
    snaps = [snap(1, "hardrockbet", 24.5, None, None)] + market(1, 24.5)
    it = only(card([game()], snaps, [model(1, 22.4)]))
    assert it["hr_price"] is None and it["ev"] is None
    assert it["fair_under"] == pytest.approx(FAIR_UNDER, abs=1e-4) and it["fair_source"] == "books"
    assert it["tier"] == "EDGE" and it["blocker"] == "no_fair_price"
    assert it["paper_blocker"] == "no_fair_price"
    assert it["action"].startswith("Wait: Hard Rock hasn’t priced its 24.5 under yet")
    # The why sentence must not contradict that action by blaming the other
    # books: three of them ARE priced at 24.5 — Hard Rock is the one that isn't.
    assert (
        "Hard Rock has under 24.5, but hasn’t posted a price for it yet — nothing to judge."
    ) in it["why"]


def test_price_sentence_blames_the_other_books_only_when_hard_rock_has_a_price():
    snaps = [snap(1, "hardrockbet", 24.5, -110, -110)]  # Hard Rock alone
    it = only(card([game()], snaps, [model(1, 22.4)]))
    assert it["ev"] is None
    assert (
        "Hard Rock has under 24.5 at -110; not enough other books at that number to judge "
        "the price."
    ) in it["why"]


def test_blocker_order_off_market_then_price_then_no_fair_price_then_qb_out():
    assert PAPER_BLOCKERS == ("off_market", "price", "no_fair_price", "qb_out")
    # Hard Rock alone (no fair price) AND a QB out: the price gate's "cannot
    # judge" branch is named first; the QB news is transient.
    prev = [{"game_id": 1, "qb_out": True, "qb_out_detail": "QB out"}]
    it = only(card([game()], [snap(1, "hardrockbet", 24.5)], [model(1, 22.4)], prev))
    assert it["blocker"] == "no_fair_price" and it["paper_blocker"] == "no_fair_price"
    # Hard Rock 24.0 alone vs a market at 25.0: off-market is the market read on
    # Hard Rock's number and comes before the price gates.
    it = only(card([game()], [snap(1, "hardrockbet", 24.0)] + market(1, 25.0), [model(1, 21.5)]))
    assert it["ev"] is None and it["blocker"] == "off_market"
    assert it["paper_blocker"] == "off_market"


def test_a_bet_needs_a_judgeable_price_but_an_exchange_quote_is_enough():
    snaps = [snap(1, "hardrockbet", 24.5, -110, -110), snap(1, "kalshi", 24.5, 100, -102)]
    it = only(card([game()], snaps, [model(1, 22.4)]))
    assert it["fair_source"] == "exchange" and it["tier"] == "BET" and it["blocker"] is None


def test_hr_vs_market_chip_and_why_sentence():
    snaps = [snap(1, "hardrockbet", 25.0, -110, -110)] + market(1, 24.5)
    it = only(card([game()], snaps, [model(1, 22.4)]))
    assert it["hr_vs_market"] == 0.5 and it["market_line"] == 24.5
    assert it["tier"] == "BET"  # 24.5 is inside the 0.5 window, so the books still price it
    assert (
        "Hard Rock’s 25.0 is 0.5 points above the other books’ median (24.5) — a better number "
        "for an under."
    ) in it["why"]
    snaps = [snap(1, "hardrockbet", 24.0, -110, -110)] + market(1, 24.5)
    it = only(card([game()], snaps, [model(1, 22.0)]))
    assert it["hr_vs_market"] == -0.5
    assert (
        "Hard Rock’s 24.0 is 0.5 points below the other books’ median (24.5) — a worse number "
        "for an under."
    ) in it["why"]
    # on the market: no sentence
    it = only(card([game()], [snap(1, "hardrockbet", 24.5)] + market(1, 24.5), [model(1, 22.4)]))
    assert it["hr_vs_market"] == 0.0
    assert not any("other books’ median" in w for w in it["why"])


def test_small_gap_does_not_qualify():
    snaps = [snap(1, "hardrockbet", 24.5)] + market(1, 24.5)
    it = only(card([game()], snaps, [model(1, 23.2)]))  # gap 1.3
    assert it["qualifies"] is False and it["paper_blocker"] is None


def test_no_hr_line_never_qualifies_even_with_a_consensus_gap():
    it = only(card([game()], market(1, 25.0), [model(1, 22.4)]))  # consensus gap 2.6
    assert it["blocker"] == "no_hr_line" and it["qualifies"] is False


def test_chips_total_band_hook_and_key_distance():
    assert total_band(44.9) == "<45" and total_band(45) == "45–52"
    assert total_band(59.5) == "52–60" and total_band(60) == "60+" and total_band(None) is None
    assert hook_side(24.5) == "key+0.5" and hook_side(27.5) == "key−0.5"
    assert hook_side(30.5) == "key−0.5" and hook_side(26.0) == "other" and hook_side(None) is None
    assert (
        hook_side(24.0) == "on_key" and hook_side(28.0) == "on_key" and hook_side(31.0) == "on_key"
    )
    assert key_dist(26.0) == 2.0 and key_dist(31.5) == 0.5
    g = {**game(), "total": 55.5, "spread": -7.5}
    snaps = [snap(1, "hardrockbet", 24.5)] + market(1, 24.5)
    it = only(card([g], snaps, [model(1, 22.4)]))
    assert it["total_band"] == "52–60" and it["full_game_total"] == 55.5 and it["spread"] == -7.5
    assert it["hook_side"] == "key+0.5" and it["key_dist"] == 0.5


def _bets(n, start_gap=3.0):
    """n BET games with gaps start_gap, start_gap-0.1, ... (all >= 1.75)."""
    games, snaps, preds = [], [], []
    for i in range(n):
        gid = i + 1
        games.append(game(gid, away=f"A{gid}", home=f"H{gid}", kick=KICK + timedelta(minutes=i)))
        snaps += [snap(gid, "hardrockbet", 24.5)] + market(gid, 24.5)
        preds.append(model(gid, round(24.5 - (start_gap - 0.1 * i), 2)))
    return games, snaps, preds


def test_weekly_cap_ranks_bets_by_gap_and_papers_the_sixth():
    games, snaps, preds = _bets(6)
    c = card(games, snaps, preds)
    bets = [it for it in c["items"] if it["tier"] == "BET"]
    assert [it["cap_rank"] for it in bets] == [1, 2, 3, 4, 5, 6]
    assert [it["gap"] for it in bets] == sorted((it["gap"] for it in bets), reverse=True)
    assert [it["over_cap"] for it in bets] == [False] * 5 + [True]
    sixth = bets[-1]
    assert sixth["tier"] == "BET" and sixth["blocker"] == "cap"
    assert sixth["action"].startswith("Over the weekly cap (#6 by gap): paper only")
    # counts.bet is what the site and the Saturday text read: bettable BETs only.
    assert c["counts"] == {"bet": 5, "edge": 0, "pass": 0, "over_cap": 1, "degraded": 0}
    assert c["paper"] == {"qualifying": 6, "over_cap": 1, "cap": WEEKLY_BET_CAP}


def test_weekly_cap_counts_prior_bets_on_games_not_on_the_card():
    games, snaps, preds = _bets(3)
    c = card(games, snaps, preds, prior_bet_game_ids={901, 902, 903, 904})
    bets = [it for it in c["items"] if it["tier"] == "BET"]
    assert [it["cap_rank"] for it in bets] == [5, 6, 7]
    assert [it["over_cap"] for it in bets] == [False, True, True]


def test_weekly_cap_does_not_double_count_a_prior_bet_that_is_on_the_card():
    games, snaps, preds = _bets(2)
    c = card(games, snaps, preds, prior_bet_game_ids={1}, held_game_ids={1})
    bets = [it for it in c["items"] if it["tier"] == "BET"]
    assert [it["cap_rank"] for it in bets] == [1, 2]


def test_held_bet_keeps_its_slot_ahead_of_a_bigger_new_gap():
    """A BET logged Thursday (game 6, smallest gap) is not bumped Saturday."""
    games, snaps, preds = _bets(6)
    c = card(games, snaps, preds, held_game_ids={6})
    bets = [it for it in c["items"] if it["tier"] == "BET"]
    by_id = {it["game_id"]: it for it in bets}
    assert by_id[6]["cap_rank"] == 1 and by_id[6]["over_cap"] is False
    assert by_id[5]["cap_rank"] == 6 and by_id[5]["over_cap"] is True


def test_apply_weekly_cap_uses_the_policy_cap_constant():
    items = [
        {
            "game_id": i,
            "tier": "BET",
            "gap": 2.0,
            "ev": 0.0,
            "kick": "",
            "away": str(i),
            "action": "",
            "blocker": None,
            "cap_rank": None,
            "over_cap": False,
        }
        for i in range(WEEKLY_BET_CAP + 2)
    ]
    apply_weekly_cap(items)
    assert sum(1 for it in items if it["over_cap"]) == 2


def test_edge_items_sort_by_gap_before_price():
    """EDGE order is gap-first now (was price-first): the cap-5 rule is by gap."""
    g1, g2 = game(1, "A", "B"), game(2, "C", "D", kick=KICK + timedelta(hours=1))
    snaps = [snap(1, "hardrockbet", 24.5, -110, -125), snap(2, "hardrockbet", 24.5, -110, -130)]
    snaps += market(1, 24.5) + market(2, 24.5)
    c = card([g1, g2], snaps, [model(1, 22.4), model(2, 21.9)])  # gaps 2.1, 2.6
    assert [it["game_id"] for it in c["items"]] == [2, 1]
