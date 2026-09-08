"""Pure post-mortem math (beatvegas/postmortem.py): parsing, regrading under two
proxy lines, hypothetical-bet rules, bucket tallies with intervals, wins-vs-
losses contrasts, and the change flags. No DB."""

import math

import pandas as pd
import pytest

from beatvegas import postmortem as pm

STEP = {"kind": "step", "base": 0.4975, "blowout": 0.5375, "cut": 21.0}
FBS = {2025: {"Alabama", "Georgia", "Ohio State"}, 2024: {"Alabama", "Georgia"}}


# ---------------------------------------------------------------- parsing


def test_parse_pace_reads_seconds_and_plays():
    assert pm.parse_pace("27.3s/play · 149 plays") == (27.3, 149.0)


def test_parse_pace_none_and_garbage():
    assert pm.parse_pace(None) == (None, None)
    assert pm.parse_pace("n/a") == (None, None)


def test_parse_weather_temp_wind_rain():
    w = pm.parse_weather("58°F · wind 12mph · 0.10in rain")
    assert w == {"wx_temp": 58.0, "wx_wind": 12.0, "wx_precip": 0.1, "dome": 0.0}


def test_parse_weather_dome_and_missing():
    assert pm.parse_weather("Dome")["dome"] == 1.0
    assert pm.parse_weather("Dome")["wx_temp"] is None
    assert pm.parse_weather(None) == {
        "wx_temp": None,
        "wx_wind": None,
        "wx_precip": None,
        "dome": None,
    }
    # no rain token -> precipitation is known-zero, not unknown
    assert pm.parse_weather("72°F · wind 5mph")["wx_precip"] == 0.0


def test_division_of():
    assert pm.division_of(2025, "Alabama", "Georgia", FBS) == "fbs"
    assert pm.division_of(2025, "Alabama", "Furman", FBS) == "fbs_v_fcs"
    assert pm.division_of(2025, "Furman", "Wofford", FBS) == "non_fbs"
    assert pm.division_of(2019, "Alabama", "Georgia", FBS) is None


# ---------------------------------------------------------------- lines + grading


def test_proxy_lines_flat_and_step_blowout():
    # 56-point total, 24-point favorite: flat 0.52 -> 29.0, blowout share -> 30.0
    assert pm.proxy_lines(56, -24, STEP) == (29.0, 30.0)


def test_proxy_lines_flat_and_step_close_game():
    assert pm.proxy_lines(56, -3, STEP) == (29.0, 28.0)


def test_proxy_lines_missing_total():
    assert pm.proxy_lines(None, -3, STEP) == (None, None)


def test_regrade_under_over_push_missing():
    out, units = pm.regrade(20, 24.5)
    assert out == "under" and abs(units - 100 / 110) < 1e-9
    assert pm.regrade(30, 24.5) == ("over", -1.0)
    assert pm.regrade(24, 24.0) == ("push", 0.0)
    assert pm.regrade(None, 24.0) == (None, None)


# ---------------------------------------------------------------- frames


def _pred(game_id, season, week, gap, score, fh, **kw):
    row = {
        "game_id": game_id,
        "season": season,
        "week": week,
        "home_team": kw.get("home", "Alabama"),
        "away_team": kw.get("away", "Georgia"),
        "bv_line": 27.0 - gap,
        "under_score": score,
        "line_used": 27.0,
        "factors_json": kw.get("factors", '{"pace": "26.0s/play · 150 plays", "weather": null}'),
        "first_half_total": fh,
        "first_half_source": kw.get("source", "linescores"),
        "home_points": kw.get("hp", 30),
        "away_points": kw.get("ap", 20),
        "spread": kw.get("spread", -7.0),
        "full_game_total": kw.get("total", 52.0),
        "neutral_site": False,
        "start_date": kw.get("start", "2025-10-04T20:00:00"),
    }
    return row


def test_build_hist_frame_grades_both_proxies_and_tags_division():
    preds = [
        _pred(1, 2025, 5, gap=2.0, score=55, fh=20),
        _pred(2, 2025, 5, gap=0.5, score=48, fh=31, spread=-24.0),
        _pred(3, 2025, 5, gap=1.0, score=50, fh=0, hp=35, ap=10),  # false zero -> dropped
        _pred(4, 2025, 5, gap=4.0, score=61, fh=17, home="Furman", away="Wofford"),
    ]
    df = pm.build_hist_frame(preds, STEP, FBS)
    assert list(df["game_id"]) == [1, 2, 4]
    assert df.attrs["dropped"] == {"untrusted_fh": 1}
    r1 = df.set_index("game_id").loc[1]
    assert r1["line_flat"] == 27.0
    # 52 * 0.4975 = 25.87 -> 26.0 ; gap_step = 26.0 - 25.0 = 1.0
    assert r1["line_step"] == 26.0 and r1["gap_step"] == 1.0
    assert r1["gap_flat"] == 2.0
    assert r1["outcome_flat"] == "under" and r1["outcome_step"] == "under"
    assert r1["division"] == "fbs" and r1["pace_spp"] == 26.0
    r2 = df.set_index("game_id").loc[2]
    # blowout: 52 * 0.5375 = 27.95 -> 28.0 ; fh 31 is over both lines
    assert r2["line_step"] == 28.0 and r2["outcome_step"] == "over"
    assert df.set_index("game_id").loc[4]["division"] == "non_fbs"


def test_weekly_cap_keeps_top_five_by_gap_per_week():
    rows = [
        _pred(i, 2025, 5, gap=g, score=50, fh=20)
        for i, g in enumerate([4, 3.5, 3, 2.5, 2, 1.8, 1.76, 1.5, 0.5])
    ]
    rows += [_pred(100 + i, 2025, 6, gap=g, score=50, fh=20) for i, g in enumerate([2.0, 1.0])]
    df = pm.build_hist_frame(rows, STEP, FBS)
    mask = pm.weekly_cap(df, "gap_flat", cap=5, min_gap=1.75)
    picked = set(df.loc[mask, "game_id"])
    assert picked == {0, 1, 2, 3, 4, 100}  # five in week 5, one eligible in week 6


def test_weekly_cap_tiebreak_is_deterministic():
    """Equal gaps: the five lowest game_ids are kept — under_score is NOT a
    tie-break (mirrors card.apply_weekly_cap, which never reads it)."""
    rows = [
        _pred(i, 2025, 5, gap=2.0, score=s, fh=20) for i, s in enumerate([50, 60, 55, 52, 58, 57])
    ]
    df = pm.build_hist_frame(rows, STEP, FBS)
    mask = pm.weekly_cap(df, "gap_flat", cap=5, min_gap=1.75)
    assert set(df.loc[mask, "game_id"]) == {0, 1, 2, 3, 4}  # highest id (5) drops


def test_hook_side_reads_on_key_and_the_half_point_hooks():
    assert pm._hook_side(28.0) == "on_key" and pm._hook_side(24.0) == "on_key"
    assert pm._hook_side(24.5) == "key+0.5" and pm._hook_side(27.5) == "key−0.5"
    assert pm._hook_side(26.0) == "other" and pm._hook_side(None) is None
    assert "on_key" in pm._ORDER["hook_side"]


def test_rule_masks_cover_policy_rules():
    rows = [
        _pred(i, 2025, 5, gap=g, score=s, fh=20)
        for i, (g, s) in enumerate([(4, 61), (2, 40), (1, 60), (-1, 30)])
    ]
    df = pm.build_hist_frame(rows, STEP, FBS)
    m = pm.rule_masks(df, "flat")
    assert set(m) == {"all", "gap175", "gap300", "score53", "both", "cap5", "top20"}
    assert list(m["gap175"]) == [True, True, False, False]
    assert list(m["gap300"]) == [True, False, False, False]
    assert list(m["score53"]) == [True, False, True, False]
    assert list(m["both"]) == [True, False, False, False]
    assert list(m["all"]) == [True] * 4


# ---------------------------------------------------------------- bands + tallies


def test_band_label_edges():
    assert pm.band_label(-0.5, pm.GAP_BANDS) == "<0"
    assert pm.band_label(1.75, pm.GAP_BANDS) == "1.75–3"
    assert pm.band_label(2.99, pm.GAP_BANDS) == "1.75–3"
    assert pm.band_label(3.0, pm.GAP_BANDS) == "3+"
    assert pm.band_label(None, pm.GAP_BANDS) is None
    assert pm.band_label(53, pm.SCORE_BANDS) == "53–59"
    assert pm.band_label(60, pm.SCORE_BANDS) == "60+"


def test_wilson_ci_brackets_the_rate():
    lo, hi = pm.wilson_ci(50, 100)
    assert 0.40 < lo < 0.41 and 0.59 < hi < 0.60
    assert pm.wilson_ci(0, 0) == (None, None)


def test_tally_excludes_pushes_from_rate_but_stakes_them():
    t = pm.tally(
        pd.Series(["under", "under", "over", "push"]),
        pd.Series([100 / 110, 100 / 110, -1.0, 0.0]),
    )
    assert (t["n"], t["unders"], t["overs"], t["pushes"]) == (4, 2, 1, 1)
    assert abs(t["under_pct"] - 2 / 3) < 1e-9
    assert abs(t["units"] - (200 / 110 - 1)) < 1e-9
    assert abs(t["roi"] - t["units"] / 4) < 1e-9
    assert t["ci_lo"] < t["under_pct"] < t["ci_hi"]
    assert 0.0 <= t["p_beat"] <= 1.0 and 0.0 < t["post_mean"] < 1.0


def test_tally_empty():
    t = pm.tally(pd.Series([], dtype=object), pd.Series([], dtype=float))
    assert t["n"] == 0 and t["under_pct"] is None and t["roi"] is None


def test_bucket_rows_emit_headline_and_bands():
    rows = [
        _pred(i, 2025, 5, gap=g, score=50, fh=fh)
        for i, (g, fh) in enumerate([(4, 20), (2, 30), (0.5, 20), (-1, 30)])
    ]
    df = pm.build_hist_frame(rows, STEP, FBS)
    df = pm.assign_dimensions(df, "flat")
    out = pm.bucket_rows(
        df,
        run_id="r",
        computed_at="2026-09-07T00:00:00Z",
        scope="hist_2023_25",
        segment="fbs_only",
        proxy="flat",
        selection_masks={"all": pd.Series([True] * 4, index=df.index)},
        outcome_col="outcome_flat",
        units_col="units_flat",
        dimensions=["gap_band"],
    )
    head = [r for r in out if r["dimension"] == "all"][0]
    assert head["n"] == 4 and head["unders"] == 2 and head["selection"] == "all"
    gap_rows = {r["bucket"]: r for r in out if r["dimension"] == "gap_band"}
    assert gap_rows["3+"]["unders"] == 1 and gap_rows["1.75–3"]["overs"] == 1
    assert gap_rows["<0"]["bucket_order"] < gap_rows["3+"]["bucket_order"]


def test_stress_rows_more_line_more_unders():
    rows = [_pred(i, 2025, 5, gap=2, score=50, fh=fh) for i, fh in enumerate([26, 27, 28, 29])]
    df = pm.build_hist_frame(rows, STEP, FBS)
    out = pm.stress_rows(
        df, pd.Series([True] * 4, index=df.index), "line_flat", deltas=(-1.0, 0.0, 1.0)
    )
    unders = [r["unders"] for r in sorted(out, key=lambda r: r["delta"])]
    assert unders == sorted(unders)
    assert unders[0] < unders[-1]


# ---------------------------------------------------------------- contrasts + flags


def test_bh_qvalues_step_up():
    q = pm.bh_qvalues([0.01, 0.04, 0.03, 0.5])
    assert abs(q[0] - 0.04) < 1e-9  # 0.01 * 4 / 1
    assert q[3] == 0.5
    assert all(0 <= v <= 1 for v in q)


def test_contrast_rows_sign_and_counts():
    # wins carry a higher `x` than losses
    df = pd.DataFrame(
        {
            "outcome": ["under"] * 6 + ["over"] * 6,
            "x": [10, 11, 12, 10, 11, 12, 1, 2, 3, 1, 2, 3],
            "y": [1.0] * 12,
        }
    )
    out = pm.contrast_rows(
        df,
        pd.Series([True] * 12),
        "outcome",
        features=("x", "y"),
        run_id="r",
        computed_at="t",
        scope="s",
        segment="fbs_only",
        proxy="flat",
        selection="gap175",
    )
    by = {r["bucket"]: r for r in out}
    assert by["x"]["unders"] == 6 and by["x"]["overs"] == 6
    assert by["x"]["stat_win"] > by["x"]["stat_loss"] and by["x"]["effect"] > 0
    assert by["x"]["p_value"] < 0.01 and by["x"]["q_value"] <= 1.0
    assert by["y"]["effect"] == 0.0  # constant feature -> no effect, no crash


def test_derive_flags_score_gate_fires_when_score_does_not_separate():
    def b(dim, bucket, n, pct):
        return {
            "scope": "hist_2023_25",
            "segment": "fbs_only",
            "proxy_kind": "step",
            "selection": "all",
            "dimension": dim,
            "bucket": bucket,
            "n": n,
            "under_pct": pct,
            "ci_lo": pct - 0.04,
            "ci_hi": pct + 0.04,
            "unders": int(n * pct),
            "overs": n - int(n * pct),
            "pushes": 0,
        }

    buckets = [
        b("score_band", "<47", 2000, 0.517),
        b("score_band", "60+", 560, 0.519),
        b("gap_band", "<0", 2100, 0.503),
        b("gap_band", "1–1.75", 300, 0.488),
        b("gap_band", "1.75–3", 350, 0.565),
        b("gap_band", "3+", 300, 0.553),
    ]
    flags = pm.derive_flags(buckets, contrasts=[], n_tests=10)
    codes = {f["code"]: f for f in flags}
    assert codes["score_gate"]["severity"] == "change"
    assert "gap_gate" in codes
    assert all({"code", "severity", "text", "evidence"} <= set(f) for f in flags)


# ---------------------------------------------------------------- live scope


def _item(gid, tier="PASS", hr_line=27.5, hr_price=-110, market_line=27.5, ev=-0.02):
    """A post-cutover card item: it carries hr_vs_market (Hard Rock minus the
    OTHER books' median). These fixtures have one other book, so that equals
    hr_line - market_line."""
    return {
        "game_id": gid,
        "away": "A",
        "home": "B",
        "kick": "2026-09-05T19:30:00Z",
        "tier": tier,
        "blocker": None,
        "hr_line": hr_line,
        "hr_price": hr_price,
        "hr_open": hr_line,
        "market_line": market_line,
        "hr_vs_market": (None if hr_line is None or market_line is None else hr_line - market_line),
        "fair_under": 0.5,
        "ev": ev,
        "bv_line": None,
        "gap": None,
    }


def test_build_live_frame_grades_hr_market_close_and_labels_off_consensus():
    items = [
        _item(1, hr_line=30.5, hr_price=-160, market_line=27.5, ev=-0.04),
        _item(2, hr_line=21.5, hr_price=135, market_line=23.5, ev=0.02),
        _item(3, hr_line=27.5, market_line=27.0),
        _item(4, hr_line=None, hr_price=None, market_line=24.5, ev=None),
    ]
    games = {
        1: {
            "season": 2026,
            "week": 1,
            "first_half_total": 29,
            "first_half_source": "pbp",
            "home_points": 40,
            "away_points": 20,
            "spread": -6.5,
            "full_game_total": 55.5,
        },
        2: {
            "season": 2026,
            "week": 1,
            "first_half_total": 22,
            "first_half_source": "linescores",
            "home_points": 35,
            "away_points": 3,
            "spread": -21.0,
            "full_game_total": 47.5,
        },
        3: {
            "season": 2026,
            "week": 1,
            "first_half_total": None,
            "first_half_source": None,
            "home_points": None,
            "away_points": None,
            "spread": -3.0,
            "full_game_total": 50.0,
        },
        4: {
            "season": 2026,
            "week": 1,
            "first_half_total": 20,
            "first_half_source": "pbp",
            "home_points": 30,
            "away_points": 10,
            "spread": -10.0,
            "full_game_total": 48.0,
        },
    }
    closes = {1: 27.5, 2: 23.5}
    df = pm.build_live_frame(items, games, closes).set_index("game_id")
    assert df.loc[1, "hr_vs_market"] == "HR ≥ +0.5" and df.loc[1, "outcome_hr"] == "under"
    assert df.loc[1, "outcome_market"] == "over" and df.loc[1, "outcome_close"] == "over"
    assert abs(df.loc[1, "units_hr"] - 100 / 160) < 1e-9
    assert df.loc[2, "hr_vs_market"] == "HR ≤ -0.5" and df.loc[2, "outcome_hr"] == "over"
    assert df.loc[2, "outcome_market"] == "under"
    assert df.loc[3, "hr_vs_market"] == "HR ≥ +0.5" and pd.isna(df.loc[3, "outcome_hr"])
    assert pd.isna(df.loc[4, "hr_vs_market"]) and df.loc[4, "outcome_market"] == "under"
    masks = pm.live_rule_masks(df.reset_index())
    assert list(masks["price_read"]) == [False, True, False, False]
    assert list(masks["bet"]) == [False] * 4
    assert list(masks["all_hr"]) == [True, True, True, False]


def test_live_hr_vs_market_has_five_bands_at_the_half_point_threshold():
    """Hard Rock minus the other books, banded on HR_OFF_MARKET_PTS: the two
    half-point-or-more bands, the two inside bands, and EXACTLY on the market
    (the modal case: most weeks Hard Rock matches the consensus number)."""
    assert pm.hr_vs_market(26.5, 27.5) == "HR ≤ -0.5"
    assert pm.hr_vs_market(27.0, 27.5) == "HR ≤ -0.5"  # the threshold itself is in the band
    assert pm.hr_vs_market(27.25, 27.5) == "HR -0.5..0"
    assert pm.hr_vs_market(27.5, 27.5) == "HR = market"
    assert pm.hr_vs_market(27.75, 27.5) == "HR 0..+0.5"
    assert pm.hr_vs_market(28.0, 27.5) == "HR ≥ +0.5"
    assert pm.hr_vs_market(28.5, 27.5) == "HR ≥ +0.5"
    assert pm.hr_vs_market(None, 27.5) is None and pm.hr_vs_market(27.5, None) is None
    assert pm._ORDER["hr_vs_market"] == [
        "HR ≤ -0.5",
        "HR -0.5..0",
        "HR = market",
        "HR 0..+0.5",
        "HR ≥ +0.5",
    ]
    assert pm.hr_vs_market_band(0.1 + 0.2 - 0.3) == "HR = market"  # float noise reads as zero


def test_build_live_frame_bands_only_cards_that_carry_hr_vs_market():
    """The dimension covers only comparable weeks. A card that carries the field
    is banded on it (Hard Rock minus the OTHER books' median); a pre-cutover card
    that does not is left out entirely rather than banded on hr_line -
    market_line, a median that INCLUDES Hard Rock. Two different definitions must
    never land in the same five buckets."""
    new = _item(1, hr_line=27.5, market_line=27.5)
    new["hr_vs_market"] = 0.25  # the other books sit at 27.25; the HR-inclusive median is 27.5
    old = _item(2, hr_line=28.5, market_line=27.5)
    del old["hr_vs_market"]  # pre-cutover card: no field
    games = {
        gid: {"season": 2026, "week": 3, "first_half_total": None, "first_half_source": None}
        for gid in (1, 2)
    }
    df = pm.build_live_frame([new, old], games, {}).set_index("game_id")
    assert df.loc[1, "hr_vs_market"] == "HR 0..+0.5"
    assert pd.isna(df.loc[2, "hr_vs_market"])  # NOT "HR ≥ +0.5" off the old definition


# ---------------------------------------------------------------- report


def test_render_markdown_smoke():
    md = pm.render_markdown(
        runs=[
            {
                "scope": "hist_2023_25",
                "computed_at": "2026-09-07T00:00:00Z",
                "n_games": 3,
                "notes": {"flags": [], "caveats": ["x"]},
            }
        ],
        buckets=[],
        contrasts=[],
    )
    assert "Post-mortem" in md and "hist_2023_25" in md


def test_run_id_for_is_stable_format():
    from datetime import datetime

    assert pm.run_id_for(datetime(2026, 9, 7, 12, 0, 1)) == "pm-20260907T120001Z"


def test_wilson_ci_monotone_in_n():
    lo1, hi1 = pm.wilson_ci(52, 100)
    lo2, hi2 = pm.wilson_ci(520, 1000)
    assert hi2 - lo2 < hi1 - lo1
    assert math.isclose((lo1 + hi1) / 2, 0.52, abs_tol=0.02)


@pytest.mark.parametrize("v,band", [(0.0, "0–1"), (1.0, "1–1.75"), (0.999, "0–1")])
def test_band_lower_inclusive(v, band):
    assert pm.band_label(v, pm.GAP_BANDS) == band


# ---------------------------------------------------------------- orchestrators + models


def _hist_fixture():
    rows = []
    gid = 0
    for season in (2024, 2025):
        for week in range(3, 9):
            for gap, score, fh, home, away in [
                (4.0, 61, 20, "Alabama", "Georgia"),
                (2.0, 40, 30, "Alabama", "Georgia"),
                (1.0, 60, 24, "Alabama", "Georgia"),
                (-1.0, 30, 31, "Alabama", "Georgia"),
                (2.5, 55, 17, "Furman", "Wofford"),
                (0.5, 50, 28, "Furman", "Wofford"),
            ]:
                gid += 1
                rows.append(
                    _pred(
                        gid,
                        season,
                        week,
                        gap=gap,
                        score=score,
                        fh=fh,
                        home=home,
                        away=away,
                        spread=-7.0 if gap < 3 else -24.0,
                        total=52.0 + gap,
                    )
                )
    return pm.build_hist_frame(rows, STEP, FBS)


def test_compute_hist_emits_both_segments_both_proxies_and_notes():
    df = _hist_fixture()
    out = pm.compute_hist(df, run_id="r1", computed_at="2026-09-07T00:00:00Z", cap=5)
    buckets, contrasts, notes, games = out["buckets"], out["contrasts"], out["notes"], out["games"]
    combos = {(b["segment"], b["proxy_kind"]) for b in buckets}
    assert combos == {("fbs_only", "flat"), ("fbs_only", "step"), ("all", "flat"), ("all", "step")}
    heads = [
        b
        for b in buckets
        if b["dimension"] == "all" and b["segment"] == "all" and b["proxy_kind"] == "flat"
    ]
    assert {b["selection"] for b in heads} == set(pm.RULES)
    all_flat = next(b for b in heads if b["selection"] == "all")
    assert all_flat["n"] == len(df)
    assert any(b["dimension"] == "line_stress" for b in buckets)
    assert any(b["dimension"] == "resid_by_gap" for b in buckets)
    assert any(c["dimension"] == "wl_contrast" for c in contrasts)
    assert {f["code"] for f in notes["flags"]} >= {"score_gate", "multiple_comparisons"}
    assert notes["dropped"] == {} and notes["n_tests"] > 0
    assert len(games) == len(df) and {"followed_system", "rules_json", "scope"} <= set(games[0])
    assert out["scope"] == pm.HIST_SCOPE


def test_compute_live_grades_at_hr_and_close():
    items = [
        _item(1, hr_line=30.5, hr_price=-160, market_line=27.5, ev=-0.04),
        _item(2, hr_line=21.5, hr_price=135, market_line=23.5, ev=0.02),
    ]
    games = {
        1: {
            "season": 2026,
            "week": 1,
            "first_half_total": 29,
            "first_half_source": "pbp",
            "home_points": 40,
            "away_points": 20,
            "spread": -6.5,
            "full_game_total": 55.5,
            "derived_line": 27.5,
        },
        2: {
            "season": 2026,
            "week": 1,
            "first_half_total": 22,
            "first_half_source": "pbp",
            "home_points": 35,
            "away_points": 3,
            "spread": -21.0,
            "full_game_total": 47.5,
            "derived_line": 25.5,
        },
    }
    df = pm.build_live_frame(items, games, {1: 27.5, 2: 23.5})
    out = pm.compute_live(df, season=2026, run_id="r2", computed_at="t")
    assert out["scope"] == "live_2026"
    kinds = {b["proxy_kind"] for b in out["buckets"]}
    assert kinds == {"hr", "hr_close", "market", "market_close"}
    head_hr = next(
        b
        for b in out["buckets"]
        if b["proxy_kind"] == "hr" and b["dimension"] == "all" and b["selection"] == "all_hr"
    )
    assert head_hr["n"] == 2 and head_hr["unders"] == 1
    assert out["notes"]["derived_line"]["n"] == 2 and "mae" in out["notes"]["derived_line"]
    assert out["notes"]["n_bets"] == 0
    assert len(out["games"]) == 2


def test_postmortem_models_exist():
    from beatvegas.db.models import PostMortemBucket, PostMortemGame, PostMortemRun

    assert PostMortemRun.__tablename__ == "postmortem_runs"
    assert PostMortemBucket.__tablename__ == "postmortem_buckets"
    assert PostMortemGame.__tablename__ == "postmortem_games"
    cols = {c.name for c in PostMortemBucket.__table__.columns}
    assert {
        "scope",
        "segment",
        "proxy_kind",
        "selection",
        "dimension",
        "bucket",
        "n",
        "under_pct",
        "ci_lo",
        "p_beat",
        "q_value",
    } <= cols


# ---------------------------------------------------------------- real closing lines


def test_build_hist_frame_grades_at_real_close_when_present():
    preds = [
        _pred(1, 2025, 5, gap=2.0, score=55, fh=20),
        _pred(2, 2025, 5, gap=0.5, score=48, fh=31),
    ]
    preds[0]["close_line"] = 26.5  # a real consensus 1H close captured pre-kickoff
    df = pm.build_hist_frame(preds, STEP, FBS).set_index("game_id")
    r1 = df.loc[1]
    assert r1["line_real"] == 26.5 and r1["gap_real"] == 1.5  # 26.5 - 25.0
    assert r1["outcome_real"] == "under"
    assert pd.isna(df.loc[2, "line_real"]) and pd.isna(df.loc[2, "outcome_real"])


def test_compute_hist_adds_real_column_only_when_real_closes_exist():
    df_none = _hist_fixture()
    out = pm.compute_hist(df_none, run_id="r", computed_at="t", cap=5)
    assert "real" not in {b["proxy_kind"] for b in out["buckets"]}
    rows = [_pred(i, 2025, 5, gap=2.0 + i * 0.1, score=55, fh=20 + i) for i in range(40)]
    for r in rows[:30]:
        r["close_line"] = 26.0
    df = pm.build_hist_frame(rows, STEP, FBS)
    out = pm.compute_hist(df, run_id="r", computed_at="t", cap=5)
    kinds = {b["proxy_kind"] for b in out["buckets"]}
    assert kinds == {"flat", "step", "real"}
    head = next(
        b
        for b in out["buckets"]
        if b["proxy_kind"] == "real"
        and b["dimension"] == "all"
        and b["selection"] == "all"
        and b["segment"] == "fbs_only"
    )
    assert head["n"] == 30  # only games with a real close are graded in the real column
    assert out["notes"]["real_lines"]["n"] == 30


# --- paper ledger + Hard Rock close in the live scope (2026-09-07) ----------------


def _paper_item(
    gid,
    tier,
    *,
    qualifies,
    paper_blocker=None,
    over_cap=False,
    cap_rank=None,
    blocker=None,
    gap=2.1,
    bv_line=22.4,
    hr_open=None,
    **kw,
):
    it = _item(gid, tier=tier, **kw)
    it.update(
        {
            "blocker": blocker,
            "gap": gap,
            "bv_line": bv_line,
            "qualifies": qualifies,
            "paper_blocker": paper_blocker,
            "over_cap": over_cap,
            "cap_rank": cap_rank,
            "hr_open": hr_open if hr_open is not None else it["hr_open"],
        }
    )
    return it


def test_live_blocker_reads_the_paper_gate_then_the_card_blocker():
    assert pm.live_blocker(_paper_item(1, "BET", qualifies=True, cap_rank=1)) == "none"
    assert (
        pm.live_blocker(
            _paper_item(2, "EDGE", qualifies=True, paper_blocker="price", blocker="price")
        )
        == "price"
    )
    assert (
        pm.live_blocker(
            _paper_item(3, "BET", qualifies=True, over_cap=True, blocker="cap", cap_rank=6)
        )
        == "cap"
    )
    assert (
        pm.live_blocker(_paper_item(4, "EDGE", qualifies=False, blocker="no_hr_line", gap=2.6))
        == "no_hr_line"
    )
    assert pm.live_blocker(_paper_item(5, "PASS", qualifies=False, gap=0.5)) == "gap"
    assert pm.live_blocker(_item(6)) == "no_model"  # derived card, no model read


def test_build_live_frame_grades_hard_rocks_own_close_and_carries_the_ledger():
    items = [
        _paper_item(
            1, "BET", qualifies=True, cap_rank=1, hr_line=24.5, hr_open=25.5, market_line=24.5
        ),
        _paper_item(
            2,
            "EDGE",
            qualifies=True,
            paper_blocker="price",
            blocker="price",
            hr_line=24.5,
            hr_price=-125,
            market_line=24.5,
        ),
        _paper_item(
            3, "BET", qualifies=True, over_cap=True, cap_rank=6, blocker="cap", hr_line=27.5
        ),
    ]
    games = {
        gid: {
            "season": 2026,
            "week": 3,
            "first_half_total": fh,
            "first_half_source": "pbp",
            "home_points": 30,
            "away_points": 10,
            "spread": -7.0,
            "full_game_total": 55.5,
        }
        for gid, fh in ((1, 23), (2, 24), (3, 28))
    }
    df = pm.build_live_frame(items, games, {1: 24.5}, hr_closes={1: 23.5, 3: 27.5}).set_index(
        "game_id"
    )
    # game 1: Hard Rock opened 25.5, built at 24.5, closed 23.5: under at build, PUSH... no: 23 < 23.5 -> under
    assert (
        df.loc[1, "hr_open"] == 25.5
        and df.loc[1, "hr_close"] == 23.5
        and df.loc[1, "hr_move"] == -2.0
    )
    assert df.loc[1, "outcome_hr"] == "under" and df.loc[1, "outcome_hr_close"] == "under"
    assert (
        df.loc[1, "blocker_dim"] == "none"
        and bool(df.loc[1, "qualifies"])
        and df.loc[1, "cap_rank"] == 1
    )
    assert df.loc[2, "blocker_dim"] == "price" and pd.isna(df.loc[2, "hr_close"])
    assert pd.isna(df.loc[2, "outcome_hr_close"])  # no HR close captured -> not graded there
    assert df.loc[3, "blocker_dim"] == "cap" and bool(df.loc[3, "over_cap"])
    assert df.loc[3, "outcome_hr_close"] == "over"  # 28 > 27.5
    masks = pm.live_rule_masks(df.reset_index())
    assert list(masks["qualifying"]) == [True, True, True]
    assert list(masks["bet"]) == [True, False, True]


def test_compute_live_adds_hr_close_grading_and_the_blocker_dimension():
    items = [
        _paper_item(1, "BET", qualifies=True, cap_rank=1, hr_line=24.5, market_line=24.5),
        _paper_item(
            2,
            "EDGE",
            qualifies=True,
            paper_blocker="price",
            blocker="price",
            hr_line=24.5,
            hr_price=-125,
            market_line=24.5,
        ),
        _paper_item(3, "PASS", qualifies=False, gap=0.5, hr_line=24.5),
    ]
    games = {
        gid: {
            "season": 2026,
            "week": 3,
            "first_half_total": fh,
            "first_half_source": "pbp",
            "home_points": 30,
            "away_points": 10,
            "spread": -7.0,
            "full_game_total": 55.5,
            "derived_line": 27.5,
        }
        for gid, fh in ((1, 23), (2, 27), (3, 20))
    }
    df = pm.build_live_frame(
        items, games, {1: 24.5, 2: 24.5, 3: 24.5}, hr_closes={1: 24.0, 2: 24.5}
    )
    out = pm.compute_live(df, season=2026, run_id="r3", computed_at="t")
    kinds = {b["proxy_kind"] for b in out["buckets"]}
    assert kinds == {"hr", "hr_close", "market", "market_close"}
    by_blocker = {
        b["bucket"]: b
        for b in out["buckets"]
        if b["proxy_kind"] == "hr"
        and b["dimension"] == "blocker"
        and b["selection"] == "qualifying"
    }
    assert set(by_blocker) == {"none", "price"}
    assert by_blocker["none"]["n"] == 1 and by_blocker["none"]["unders"] == 1
    assert by_blocker["price"]["n"] == 1 and by_blocker["price"]["overs"] == 1
    hr_close_all = next(
        b
        for b in out["buckets"]
        if b["proxy_kind"] == "hr_close"
        and b["dimension"] == "all"
        and b["selection"] == "qualifying"
    )
    assert hr_close_all["n"] == 2  # game 3 has no Hard Rock close captured
    assert out["notes"]["n_qualifying"] == 2 and out["notes"]["n_bets"] == 1
    assert not any("zero model bets" in c for c in out["notes"]["caveats"])
    g1 = next(g for g in out["games"] if g["game_id"] == 1)
    assert (
        g1["blocker_dim"] == "none" and g1["hr_close"] == 24.0 and g1["outcome_hr_close"] == "under"
    )
    assert any("hook_side" == b["dimension"] for b in out["buckets"])


# --- full-game under on the same picks at the real full-game close (2026-09-07) --


def test_build_hist_frame_grades_the_full_game_at_the_captured_fg_close():
    preds = [
        _pred(1, 2025, 5, gap=2.0, score=55, fh=20, hp=24, ap=20),  # 44 pts
        _pred(2, 2025, 5, gap=3.0, score=58, fh=22, hp=35, ap=31),  # 66 pts
        _pred(3, 2025, 5, gap=2.5, score=57, fh=19, hp=20, ap=17),  # no fg close
    ]
    preds[0]["close_line"], preds[0]["fg_close"] = 24.5, 51.5
    preds[1]["close_line"], preds[1]["fg_close"] = 26.5, 55.5
    preds[2]["close_line"] = 25.5  # 1H close but no full-game close captured
    df = pm.build_hist_frame(preds, STEP, FBS).set_index("game_id")
    assert df.loc[1, "pts"] == 44 and df.loc[1, "line_fg"] == 51.5
    assert df.loc[1, "outcome_fg"] == "under" and df.loc[1, "outcome_real"] == "under"
    assert df.loc[1, "gap_fg"] == df.loc[1, "gap_real"]  # selection stays the 1H gap
    assert df.loc[2, "outcome_fg"] == "over" and df.loc[2, "outcome_real"] == "under"
    assert pd.isna(df.loc[3, "line_fg"]) and pd.isna(df.loc[3, "outcome_fg"])


def test_compute_hist_adds_the_fg_column_graded_on_full_points():
    preds = []
    for i in range(1, 7):
        p = _pred(i, 2025, 5, gap=2.0 + 0.1 * i, score=55, fh=20 + i, hp=20 + i, ap=20)
        p["close_line"], p["fg_close"] = 27.0, 45.5  # gap_real = gap; pts 41..46 -> 5 under, 1 over
        preds.append(p)
    df = pm.build_hist_frame(preds, STEP, FBS)
    out = pm.compute_hist(df, run_id="r", computed_at="t", proxies=("step",))
    kinds = {b["proxy_kind"] for b in out["buckets"]}
    assert {"step", "real", "fg"} <= kinds
    fg_all = next(
        b
        for b in out["buckets"]
        if b["proxy_kind"] == "fg"
        and b["dimension"] == "all"
        and b["selection"] == "gap175"
        and b["segment"] == "all"
    )
    assert fg_all["n"] == 6 and fg_all["unders"] == 5 and fg_all["overs"] == 1
    stress = [
        b
        for b in out["buckets"]
        if b["proxy_kind"] == "fg"
        and b["dimension"] == "line_stress"
        and b["selection"] == "gap175"
        and b["segment"] == "all"
    ]
    # shifting the FULL-GAME line by -1 (44.5) flips the 45-point game to over
    minus1 = next(b for b in stress if b["bucket"] == "-1.0")
    assert minus1["unders"] == 4 and minus1["overs"] == 2
    assert not any(
        b["proxy_kind"] == "fg" and b["dimension"] == "resid_by_gap" for b in out["buckets"]
    )
    assert out["notes"]["fg_lines"]["n"] == 6
    assert any("'fg' grades the SAME picks" in c for c in out["notes"]["caveats"])
