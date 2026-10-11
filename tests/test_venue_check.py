"""H-VENUE-1: the two-venue read's pure summary, pinned on synthetic records."""

from __future__ import annotations

from conftest import _load_script


def _rec(gid, hr_off, k_off, hr_ev, k_ev, hr_u, k_u):
    def side(ev, u):
        return {
            "price": -110,
            "ev": ev,
            "excluded": None if ev is not None else "far_lines",
            "units": u,
        }

    return {
        "game_id": gid,
        "week": 6,
        "total": 50.0,
        "median": 48.5,
        "books": 5,
        "hardrockbet": {
            "line": 48.5 + hr_off,
            "off": hr_off,
            "under": side(hr_ev, hr_u),
            "over": side(
                -hr_ev if hr_ev is not None else None, -hr_u if hr_u is not None else None
            ),
        },
        "kalshi": {
            "line": 48.5 + k_off,
            "off": k_off,
            "under": side(k_ev, k_u),
            "over": side(-k_ev if k_ev is not None else None, -k_u if k_u is not None else None),
        },
    }


def test_summarize_counts_offsets_evs_and_the_better_venue():
    vc = _load_script("venue_check")
    recs = [
        _rec(1, 0.0, 1.5, -0.045, 0.02, -1.0, -1.0),
        _rec(2, 1.0, 0.0, 0.01, -0.03, 0.91, 0.91),
        _rec(3, 0.0, -3.0, -0.04, None, -1.0, None),  # Kalshi rung too far: no reading
    ]
    s = vc.summarize(recs)
    assert s["games"] == 3 and s["weeks"] == [6]
    hr, k = s["venues"]["hardrockbet"], s["venues"]["kalshi"]
    assert hr["off_1pt_n"] == 1 and k["off_1pt_n"] == 2
    assert hr["sides"]["under"]["n"] == 3 and k["sides"]["under"]["n"] == 2
    assert k["sides"]["under"]["excluded_by_reason"] == {"far_lines": 1}
    assert abs(hr["sides"]["under"]["ev_mean"] - (-0.045 + 0.01 - 0.04) / 3) < 1e-9
    assert abs(hr["sides"]["under"]["units_total"] - (-1.0 + 0.91 - 1.0)) < 1e-9
    best = s["best_of_two"]["under"]
    assert best["n"] == 2  # game 3 has no Kalshi reading
    assert abs(best["ev_mean"] - (0.02 + 0.01) / 2) < 1e-9
    assert best["kalshi_better_share"] == 0.5


def test_render_names_every_venue_and_side():
    vc = _load_script("venue_check")
    md = vc.render(vc.summarize([_rec(1, 0.0, 0.5, -0.04, -0.03, -1.0, -1.0)]), 2026, "stamp")
    for needle in ("hardrockbet", "kalshi", "| under |", "| over |", "best-of-two"):
        assert needle in md
