"""The probe's pure pieces: reading totals_h1 quotes out of an event response,
splitting discovered keys into ours and others, and the coverage arithmetic."""

from __future__ import annotations


def _event(eid, books):
    return {
        "id": eid,
        "commence_time": "2026-09-19T19:30:00Z",
        "home_team": "H",
        "away_team": "A",
        "bookmakers": [
            {
                "key": k,
                "title": k.title(),
                "last_update": upd,
                "markets": [
                    {
                        "key": "totals_h1",
                        "outcomes": [
                            {"name": "Over", "price": -105, "point": line},
                            {"name": "Under", "price": -115, "point": line},
                        ],
                    },
                    {"key": "spreads", "outcomes": []},
                ],
            }
            for k, line, upd in books
        ],
    }


def test_h1_quotes_reads_only_the_first_half_market(load_script):
    P = load_script("sharp_book_probe")
    ev = _event(
        "e1",
        [("hardrockbet", 45.5, "2026-09-15T20:00:00Z"), ("pinnacle", 45.0, "2026-09-15T21:00:00Z")],
    )
    q = {r["book"]: r for r in P.h1_quotes(ev)}
    assert set(q) == {"hardrockbet", "pinnacle"}
    assert (
        q["pinnacle"]["line"] == 45.0
        and q["pinnacle"]["under"] == -115
        and q["pinnacle"]["over"] == -105
    )


def test_discovered_keys_splits_ours_from_others_and_labels_sharps(load_script):
    P = load_script("sharp_book_probe")
    evs = [
        _event("e1", [("hardrockbet", 45.5, ""), ("draftkings", 45.5, ""), ("pinnacle", 45.0, "")]),
        _event("e2", [("hardrockbet", 40.5, ""), ("pinnacle", 40.0, ""), ("unibet_eu", 40.5, "")]),
    ]
    d = P.discovered_keys(evs, ["hardrockbet", "draftkings"])
    assert d["ours_seen"] == {"hardrockbet": 2, "draftkings": 1}
    assert d["others"] == {"pinnacle": 2, "unibet_eu": 1}
    assert d["sharp_labelled"] == {"pinnacle": "Pinnacle"}


def test_coverage_counts_posting_diff_and_timing(load_script):
    P = load_script("sharp_book_probe")
    evs = [
        _event(
            "e1",
            [
                ("hardrockbet", 45.5, "2026-09-15T20:00:00Z"),
                ("pinnacle", 45.0, "2026-09-15T21:00:00Z"),
            ],
        ),
        _event("e2", [("hardrockbet", 40.5, "2026-09-15T20:00:00Z")]),
        _event("e3", [("pinnacle", 30.0, "2026-09-15T19:00:00Z")]),
        {"id": "e4", "bookmakers": []},
    ]
    c = P.coverage(evs, ["pinnacle"])["summary"]
    assert c["events"] == 4 and c["hr_posted"] == 2
    b = c["books"]["pinnacle"]
    assert (
        b["posted"] == 2
        and b["posted_where_hr_posted"] == 1
        and b["hr_posted_where_sharp_absent"] == 1
    )
    assert b["mean_signed_diff_vs_hr"] == -0.5 and b["mean_abs_diff_vs_hr"] == 0.5
    assert b["updated_after_hr"] == 1


def test_dry_run_is_the_default(load_script):
    P = load_script("sharp_book_probe")
    a = P.parse_args([])
    assert not a.live and a.max_credits == 120
