"""scripts/archive/probe_alt_totals_h1.py: pure parsing only (the network call is never made here)."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "probe_alt",
    Path(__file__).resolve().parents[1] / "scripts" / "archive" / "probe_alt_totals_h1.py",
)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def _event(main, alt):
    def mk(key, pairs):
        outs = []
        for pt, over, under in pairs:
            outs += [
                {"name": "Over", "point": pt, "price": over},
                {"name": "Under", "point": pt, "price": under},
            ]
        return {"key": key, "outcomes": outs}

    return {
        "away_team": "A",
        "home_team": "B",
        "commence_time": "2026-10-17T19:30:00Z",
        "bookmakers": [
            {
                "key": "hardrockbet",
                "markets": [mk("totals_h1", main), mk("alternate_totals_h1", alt)],
            }
        ],
    }


def test_a_rung_fed_row_with_the_main_line_still_in_the_ladder():
    r = probe.summarize(
        _event([(30.5, -160, 125)], [(27.5, -110, -110), (30.5, -160, 125), (24.5, 135, -170)])
    )
    assert r["fed"] == (30.5, -160, 125) and r["fed_is_rung"] is True
    assert r["main_in_ladder"] == [27.5] and r["ladder_points"] == 3
    assert "on 1; the alternate ladder still carried a main-priced line on 1" in probe.verdict([r])


def test_a_main_fed_row_and_no_ladder():
    r = probe.summarize(_event([(27.5, -110, -110)], []))
    assert r["fed_is_rung"] is False and r["main_in_ladder"] == []


def test_the_cap_holds_the_credit_budget():
    assert probe.CREDITS_PER_EVENT * probe.MAX_EVENTS == 24


# --- 2026-10-15: other books in the same call, exact-line comparisons ----------------


def _bm(key, markets):
    out = []
    for mkey, pairs in markets.items():
        outs = []
        for pt, over, under in pairs:
            if over is not None:
                outs.append({"name": "Over", "point": pt, "price": over})
            if under is not None:
                outs.append({"name": "Under", "point": pt, "price": under})
        out.append({"key": mkey, "outcomes": outs, "last_update": "2026-10-17T18:59:00Z"})
    return {"key": key, "markets": out}


EVENT = {
    "id": "ev1",
    "away_team": "A",
    "home_team": "B",
    "commence_time": "2026-10-17T19:30:00Z",
    "bookmakers": [
        _bm(
            "hardrockbet",
            {
                "totals_h1": [(27.5, -110, -110)],
                "alternate_totals_h1": [(31.5, 150, -200), (34.5, 260, -380)],
            },
        ),
        _bm("draftkings", {"alternate_totals_h1": [(31.5, 165, -215), (30.5, 140, -175)]}),
        _bm("fanduel", {"alternate_totals_h1": [(31.5, 160, -210)]}),
        _bm("betmgm", {"totals_h1": [(31.5, None, -220)]}),  # one-sided: kept, never filled in
    ],
}


def test_the_budget_is_unchanged_with_ten_books():
    assert probe.MAX_BOOKS == 10
    assert probe.CREDITS_PER_EVENT == 2 and probe.CREDITS_PER_EVENT * probe.MAX_EVENTS == 24


def test_rows_are_kept_as_fed_with_missing_sides_left_empty():
    rows = probe.book_rows(EVENT, "2026-10-17T19:00:00+00:00")
    mgm = [r for r in rows if r["book"] == "betmgm"]
    assert len(mgm) == 1 and mgm[0]["over"] is None and mgm[0]["under"] == -220
    assert {r["book"] for r in rows} == {"hardrockbet", "draftkings", "fanduel", "betmgm"}


def test_hard_rock_is_compared_only_at_the_identical_line():
    cmp_rows = probe.compare_hr(probe.book_rows(EVENT, "2026-10-17T19:00:00+00:00"))
    u315 = next(r for r in cmp_rows if r["line"] == 31.5 and r["side"] == "under")
    assert u315["hr_price"] == -200 and u315["range"] == "-151 to -200"
    assert u315["others"] == 3  # DraftKings, FanDuel and BetMGM's one-sided under
    assert u315["best_other"] == -210
    assert u315["hr_minus_market_pts"] < -0.01  # Hard Rock charges less than the market
    assert u315["fair_books"] == 2  # only two-sided quotes make a fair share
    assert u315["fair"] is not None and u315["ev"] is not None
    # 34.5 exists only at Hard Rock: reported, never matched to DraftKings' 30.5 or 31.5.
    u345 = next(r for r in cmp_rows if r["line"] == 34.5 and r["side"] == "under")
    assert u345["others"] == 0 and u345["fair"] is None and u345["ev"] is None
    # A line Hard Rock does not quote is not a Hard Rock row.
    assert not any(r["line"] == 30.5 for r in cmp_rows)


def test_ev_against_the_market_fair_share_by_hand():
    # fair under 0.70 at -200 (pays 0.5): 0.70 * 0.5 - 0.30 = +0.05
    rows = [
        {
            "event_id": "e",
            "game": "g",
            "line": 31.5,
            "book": "hardrockbet",
            "over": 150,
            "under": -200,
        },
        {"event_id": "e", "game": "g", "line": 31.5, "book": "x", "over": 230, "under": -230},
        {"event_id": "e", "game": "g", "line": 31.5, "book": "y", "over": 230, "under": -230},
    ]
    u = next(r for r in probe.compare_hr(rows) if r["side"] == "under")
    assert abs(u["fair"] - 0.69697) < 1e-4  # 230/330 de-vigged on a symmetric quote
    assert abs(u["ev"] - (u["fair"] * 0.5 - (1 - u["fair"]))) < 1e-12


def test_hold_and_price_ranges():
    assert abs(probe.quote_stats(-110, -110)["hold"] - 0.04762) < 1e-4
    assert probe.quote_stats(None, -110) == {"hold": None, "fair_under": None}
    assert probe.price_range(-110) == "-100 to -120"
    assert (
        probe.price_range(-250) == "-201 to -250" and probe.price_range(-251) == "-251 and shorter"
    )
    assert probe.price_range(120) == "plus money" and probe.price_range(None) is None


def test_quality_names_missing_ladders_one_sided_quotes_and_conflicts():
    rows = probe.book_rows(EVENT, "2026-10-17T19:00:00+00:00")
    rows.append(
        dict(rows[0], market="alternate_totals_h1", over=-105, under=-115)
    )  # HR 27.5 priced twice
    q = "\n".join(probe.quality(rows, ["hardrockbet", "betmgm", "espnbet"], 1))
    assert "- betmgm: quoted 1 of 1 events; alternate ladder on 0; one-sided quotes 1" in q
    assert "- espnbet: quoted 0 of 1 events" in q
    assert (
        "hardrockbet: quoted 1 of 1 events; alternate ladder on 1; one-sided quotes 0; same line priced two ways 1"
        in q
    )
