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
    rows = [
        _pred(i, 2025, 5, gap=2.0, score=s, fh=20) for i, s in enumerate([50, 60, 55, 52, 58, 57])
    ]
    df = pm.build_hist_frame(rows, STEP, FBS)
    mask = pm.weekly_cap(df, "gap_flat", cap=5, min_gap=1.75)
    assert set(df.loc[mask, "game_id"]) == {1, 2, 3, 4, 5}  # lowest score (id 0) drops


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
    assert df.loc[1, "hr_vs_market"] == "HR higher" and df.loc[1, "outcome_hr"] == "under"
    assert df.loc[1, "outcome_market"] == "over" and df.loc[1, "outcome_close"] == "over"
    assert abs(df.loc[1, "units_hr"] - 100 / 160) < 1e-9
    assert df.loc[2, "hr_vs_market"] == "HR lower" and df.loc[2, "outcome_hr"] == "over"
    assert df.loc[2, "outcome_market"] == "under"
    assert df.loc[3, "hr_vs_market"] == "within 0.5" and df.loc[3, "outcome_hr"] is None
    assert df.loc[4, "hr_vs_market"] is None and df.loc[4, "outcome_market"] == "under"
    masks = pm.live_rule_masks(df.reset_index())
    assert list(masks["price_read"]) == [False, True, False, False]
    assert list(masks["bet"]) == [False] * 4
    assert list(masks["all_hr"]) == [True, True, True, False]


def test_live_hr_vs_market_threshold_is_strict_half_point():
    assert pm.hr_vs_market(28.0, 27.5) == "within 0.5"
    assert pm.hr_vs_market(28.5, 27.5) == "HR higher"
    assert pm.hr_vs_market(26.5, 27.5) == "HR lower"
    assert pm.hr_vs_market(None, 27.5) is None


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
    assert kinds == {"hr", "market", "market_close"}
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
