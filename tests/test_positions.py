"""beatvegas/positions.py (2026-10-14, programme step 10): one arm_positions row per
hypothesis per read date, rewritten on a retry, read newest-first by the site."""

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from beatvegas import positions as X
from beatvegas import protocol as P
from beatvegas.db.models import ArmPosition, Base


def _engine():
    eng = create_engine("sqlite://")
    Base.metadata.create_all(eng)
    return eng


LINE = {
    "logged": 12,
    "pending": 0,
    "completed_weeks": ["2026-w7"],
    "readings": 9,
    "excluded": 3,
    "excluded_by_reason": {"far_lines": 3},
    "weeks": 1,
    "llr": 0.412,
    "state": P.RUNNING if hasattr(P, "RUNNING") else "running",
    "label": "IN FORWARD TEST",
    "decided_at_week": None,
    "mean_ev": -0.0123,
    "ev_lo": -0.05,
    "ev_hi": 0.025,
}


def test_the_row_set_is_every_arm_plus_the_pricing_study_plus_the_exploratory_collector():
    assert X.HYPOTHESES == tuple(P.ARMS) + ("H-PRICE-HR", "H-ARM-EVP")
    assert X.PRICING_ID == "H-PRICE-HR"


def test_next_monday_and_read_date():
    assert X.next_monday(datetime(2026, 10, 19, 12, 5)) == "2026-10-26"  # a Monday -> the next one
    assert X.next_monday(datetime(2026, 10, 14, 23, 0)) == "2026-10-19"
    assert X.read_date(datetime(2026, 10, 19, 12, 5)) == "2026-10-19"


def test_mean_ci_needs_two_values():
    assert X.mean_ci([]) == (None, None, None)
    assert X.mean_ci([0.02]) == (0.02, None, None)
    m, lo, hi = X.mean_ci([0.0, 0.02, 0.04])
    assert round(m, 4) == 0.02 and lo < m < hi


def test_arm_row_carries_the_standard_the_needed_count_and_the_next_read():
    now = datetime(2026, 10, 19, 12, 5)
    r = X.arm_position("H-ARM-1HU", LINE, now, "38590000001")
    assert r["standard"] == "sprt" and r["needed"] == P.MIN_OBS == 30
    assert r["read_date"] == "2026-10-19" and r["next_read"] == "2026-10-26"
    assert (r["readings"], r["excluded"], r["llr"], r["mean_ev"]) == (9, 3, 0.412, -0.0123)
    assert r["run_id"] == "38590000001"


def test_pricing_row_reads_the_verdict_in_its_own_standard():
    now = datetime(2026, 10, 19, 12, 6)
    v = {
        "verdict": "insufficient",
        "why": "0 forward opportunities of the 40 needed",
        "opportunities": 3,
        "min_required": 40,
        "ev_close": {"n": 3, "mean": 0.021, "ci": (-0.01, 0.052)},
    }
    fwd = {
        "1H_total": {"states_compared": 120, "drops": {"rung": 4, "no_reference": 2}},
        "full_game_total": {"states_compared": 80, "drops": {}},
    }
    r = X.pricing_position(v, fwd, now, "-")
    assert r["standard"] == "pricing" and r["needed"] == 40 and r["readings"] == 3
    assert r["logged"] == 200 and r["excluded"] == 6
    assert (r["mean_ev"], r["ev_lo"], r["ev_hi"]) == (0.021, -0.01, 0.052)
    assert r["state"] == "insufficient" and r["label"] == "INSUFFICIENT"


def test_a_retry_on_the_same_day_rewrites_the_row_and_the_site_reads_the_newest():
    eng = _engine()
    monday = datetime(2026, 10, 19, 12, 5)
    with Session(eng) as s:
        X.upsert_position(s, X.arm_position("H-ARM-1HU", LINE, monday, "run-1"))
        X.upsert_position(
            s,
            X.arm_position(
                "H-ARM-1HU", {**LINE, "readings": 10}, monday + timedelta(hours=3), "run-2"
            ),
        )
        X.upsert_position(s, X.arm_position("H-ARM-1HU", LINE, monday - timedelta(days=7), "run-0"))
        s.commit()
    with Session(eng) as s:
        rows = s.query(ArmPosition).filter(ArmPosition.hypothesis == "H-ARM-1HU").all()
        assert len(rows) == 2  # two read dates, never two rows for one date
        newest = X.newest_positions(s)["H-ARM-1HU"]
        assert newest.run_id == "run-2" and newest.readings == 10


def test_freshness_words():
    now = datetime(2026, 10, 28, 0, 0)
    assert X.freshness(None, now) == "missing"
    assert X.freshness(datetime(2026, 10, 19, 12, 0), now) == "outdated"
    assert X.freshness(datetime(2026, 10, 26, 12, 0), now) == "current"


def test_the_pricing_row_carries_the_forward_opportunities_for_the_site():
    import json as _json

    v = {
        "verdict": "insufficient",
        "opportunities": 1,
        "min_required": 40,
        "ev_close": {"n": 1, "mean": 0.04, "ci": None},
    }
    opp = {
        "market": "1H_total",
        "week": 7,
        "game": "Ole Miss @ Vanderbilt",
        "captured_at": datetime(2026, 10, 17, 11, 58),
        "hrs_to_kick": 7.5,
        "hr_line": 28.5,
        "ref_line": 27.5,
        "side": "under",
        "price": -110,
        "ev_ref": 0.0478,
        "ev_ref_lower": 0.0292,
        "ev_close": 0.0478,
        "market_moved": "unchanged",
        "tier": 0,
        "fl_check": "none",
        "result": "loss",
        "hr_over": -120,  # not carried: the site lists only the report's columns
    }
    r = X.pricing_position(v, {}, datetime(2026, 10, 19, 12, 6), "-", [opp])
    payload = _json.loads(r["payload_json"])
    assert payload["verdict"]["verdict"] == "insufficient"
    assert payload["opportunities"] == [
        {k: (opp[k].isoformat() if k == "captured_at" else opp[k]) for k in X.OPPORTUNITY_FIELDS}
    ]
