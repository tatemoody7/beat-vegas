"""The lead/lag tables: as-of forward fill, who-moves-first, price-before-number."""

import pandas as pd
import pytest

from beatvegas.backtest import hr_lag as H

KICK = "2026-09-12 20:00:00"


def snap(gid, t, book, line, over=-110, under=-110):
    return {
        "game_id": gid,
        "week": 2,
        "start_date": KICK,
        "captured_at": t,
        "book": book,
        "line": line,
        "over_price": over,
        "under_price": under,
    }


def _market(gid, t, line, books=("draftkings", "fanduel", "betrivers")):
    return [snap(gid, t, b, line) for b in books]


def test_as_of_grid_forward_fills_books_not_rewritten_in_a_later_capture():
    d = H.prepare(
        pd.DataFrame(
            _market(1, "2026-09-09 12:00", 24.5)
            + [snap(1, "2026-09-09 12:00", "hardrockbet", 25.5)]
            + [snap(1, "2026-09-11 12:00", "draftkings", 25.0)]
        )
    )
    grid = H.as_of_grid(d)
    assert list(grid.columns) == sorted(["draftkings", "fanduel", "betrivers", "hardrockbet"])
    # fanduel/betrivers/hardrock did not change on the 11th: they carry forward
    assert grid.iloc[1]["fanduel"] == 24.5 and grid.iloc[1]["hardrockbet"] == 25.5
    assert grid.iloc[1]["draftkings"] == 25.0


def test_position_and_next_move_toward_consensus():
    rows = _market(1, "2026-09-09 12:00", 24.5) + [snap(1, "2026-09-09 12:00", "hardrockbet", 26.0)]
    rows += [snap(1, "2026-09-11 12:00", "hardrockbet", 25.0)]  # HR comes back toward 24.5
    d = H.prepare(pd.DataFrame(rows))
    pos = H.position_table(d)
    assert pos[0]["diff"] == 1.5 and pos[0]["next_hr_move"] == -1.0
    summ = {p["bucket"]: p for p in H.position_summary(pos)}
    assert summ["HR ≥ 1 above"]["share_toward_consensus_next"] == 1.0


def test_who_moves_first_counts_same_later_and_never():
    rows = []
    # game 1: consensus rises at t2, HR rises in the same capture
    rows += _market(1, "2026-09-09 12:00", 24.5) + [
        snap(1, "2026-09-09 12:00", "hardrockbet", 24.5)
    ]
    rows += _market(1, "2026-09-10 12:00", 25.5) + [
        snap(1, "2026-09-10 12:00", "hardrockbet", 25.5)
    ]
    # game 2: consensus rises at t2, HR follows at t3
    rows += _market(2, "2026-09-09 12:00", 24.5) + [
        snap(2, "2026-09-09 12:00", "hardrockbet", 24.5)
    ]
    rows += _market(2, "2026-09-10 12:00", 25.5)
    rows += [snap(2, "2026-09-11 12:00", "hardrockbet", 25.5)]
    # game 3: consensus rises, HR never moves
    rows += _market(3, "2026-09-09 12:00", 24.5) + [
        snap(3, "2026-09-09 12:00", "hardrockbet", 24.5)
    ]
    rows += _market(3, "2026-09-10 12:00", 25.5)
    # game 4: HR moves alone, consensus follows later
    rows += _market(4, "2026-09-09 12:00", 24.5) + [
        snap(4, "2026-09-09 12:00", "hardrockbet", 24.5)
    ]
    rows += [snap(4, "2026-09-10 12:00", "hardrockbet", 25.5)]
    rows += _market(4, "2026-09-11 12:00", 25.5)
    w = H.who_moves_first(H.prepare(pd.DataFrame(rows)))
    assert (w["hr_same_capture"], w["hr_later_capture"], w["hr_never_before_kick"]) == (1, 1, 1)
    # game 4: the consensus arrived where Hard Rock already was -- HR led, once, and was followed
    assert w["hr_already_there"] == 1
    assert w["hr_leads"] == 1 and w["hr_leads_then_consensus_followed"] == 1
    # game 2 at t3: HR closing the gap the market opened is catching up, not leading
    assert w["hr_catches_up"] == 1
    assert w["consensus_moves"] == 4


def test_price_before_number_events_and_direction():
    rows = [
        snap(1, "2026-09-09 12:00", "hardrockbet", 25.0, -110, -110),
        snap(1, "2026-09-10 12:00", "hardrockbet", 25.0, -105, -115),  # dearer under, number held
        snap(1, "2026-09-11 12:00", "hardrockbet", 24.5, -110, -110),  # number falls: agrees
        snap(2, "2026-09-09 12:00", "hardrockbet", 25.0, -110, -110),
        snap(
            2, "2026-09-10 12:00", "hardrockbet", 25.5, -110, -110
        ),  # number moved (not price-only)
        snap(2, "2026-09-11 12:00", "hardrockbet", 25.5, -110, -110),
    ]
    p = H.price_before_number(H.prepare(pd.DataFrame(rows)))
    assert p["price_only_events"] == 1
    assert p["share_number_moves_next_after_price_only"] == 1.0
    assert p["share_direction_agrees"] == 1.0
    assert p["hr_rows_with_prev_and_next"] == 2


def test_dispersion_and_closing_position():
    rows = [
        snap(1, "2026-09-09 12:00", "draftkings", 24.5),
        snap(1, "2026-09-09 12:00", "fanduel", 25.5),
        snap(1, "2026-09-09 12:00", "betrivers", 24.5),
        snap(1, "2026-09-09 12:00", "hardrockbet", 23.5),
        snap(1, "2026-09-09 12:00", "betmgm", 28.5, 195, -275),
    ]  # a rung: excluded from consensus
    d = H.prepare(pd.DataFrame(rows))
    disp = {b["band"]: b for b in H.dispersion(d)}
    assert disp["> 72h"]["captures"] == 1 and disp["> 72h"]["mean_range_pts"] == pytest.approx(1.0)
    c = H.closing_position(d)
    assert c["games"] == 1 and c["mean_diff"] == pytest.approx(23.5 - 24.5)
    assert c["share_below_by_1_or_more"] == 1.0


def test_post_kick_rows_are_dropped():
    d = H.prepare(pd.DataFrame([snap(1, "2026-09-12 21:00", "hardrockbet", 20.5)]))
    assert d.empty
