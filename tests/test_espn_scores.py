"""ESPN scoreboard -> CFBD-shaped game dicts (2026-09-13).

Grading depended on one vendor until CFBD exhausted its monthly quota and 429'd
everything for two days. ESPN is the second source for SCORES ONLY; it reuses
etl/first_half.py by emitting CFBD's key names, so the false-zero guard applies
to it unchanged.
"""

from beatvegas.etl.first_half import attach_first_half
from beatvegas.sources.espn_scores import _as_cfbd_game


def _ev(status="STATUS_FINAL", home_ls=(0, 14, 7, 14), away_ls=(0, 7, 14, 3), hp=35, ap=24):
    def side(which, score, ls):
        c = {"homeAway": which, "score": str(score)}
        if ls is not None:
            c["linescores"] = [{"value": float(v)} for v in ls]
        return c

    return {
        "id": "401856783",
        "competitions": [
            {
                "status": {"type": {"name": status}},
                "competitors": [side("home", hp, home_ls), side("away", ap, away_ls)],
            }
        ],
    }


def test_a_final_becomes_a_cfbd_shaped_game():
    g = _as_cfbd_game(_ev())
    assert g == {
        "id": 401856783,
        "completed": True,
        "homePoints": 35,
        "awayPoints": 24,
        "homeLineScores": [0, 14, 7, 14],
        "awayLineScores": [0, 7, 14, 3],
    }


def test_the_first_half_matches_the_real_week_2_result():
    # Texas Tech at Oregon State: 1H was 21, under Tate's 28.5 at -115.
    fh = attach_first_half(_as_cfbd_game(_ev()))
    assert fh["first_half_total"] == 21
    assert fh["first_half_source"] == "linescores"


def test_a_game_in_progress_is_dropped_entirely():
    # Never a partial score: write-once pick grading would freeze a half-played
    # game (see tests/test_backfill_finality.py).
    assert _as_cfbd_game(_ev(status="STATUS_IN_PROGRESS")) is None


def test_missing_linescores_leave_the_first_half_null_not_zero():
    g = _as_cfbd_game(_ev(home_ls=None, away_ls=None))
    assert g["homeLineScores"] is None
    assert attach_first_half(g)["first_half_total"] is None


def test_linescores_that_do_not_reconcile_are_rejected():
    # Quarters summing to something other than the final is the corruption the
    # trust guard exists for; ESPN gets no exemption from it.
    fh = attach_first_half(_as_cfbd_game(_ev(home_ls=(0, 0, 0, 0), hp=35)))
    assert fh["first_half_total"] is None


def test_overtime_periods_do_not_break_the_first_half():
    g = _as_cfbd_game(_ev(home_ls=(7, 7, 7, 7, 6), hp=34, away_ls=(3, 10, 7, 8, 0), ap=28))
    assert attach_first_half(g)["first_half_total"] == 27
