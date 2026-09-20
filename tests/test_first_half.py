from beatvegas.etl.first_half import (
    attach_first_half,
    final_from_plays,
    first_half_from_line_scores,
    first_half_from_plays,
    line_scores_trustworthy,
)


def test_line_scores_camel_case():
    game = {"id": 1, "homeLineScores": [7, 10, 3, 14], "awayLineScores": [0, 3, 7, 7]}
    assert first_half_from_line_scores(game) == (17, 3)


def test_line_scores_snake_case():
    game = {"id": 2, "home_line_scores": [3, 0, 0, 0], "away_line_scores": [7, 14, 0, 0]}
    assert first_half_from_line_scores(game) == (3, 21)


def test_line_scores_with_overtime_ignored():
    # OT entries beyond Q4 must not affect the first-half sum.
    game = {"id": 3, "homeLineScores": [7, 7, 7, 7, 6], "awayLineScores": [0, 14, 7, 0, 7]}
    assert first_half_from_line_scores(game) == (14, 14)


def test_line_scores_missing_returns_none():
    assert first_half_from_line_scores({"id": 4}) is None
    assert first_half_from_line_scores({"id": 5, "homeLineScores": [7]}) is None
    assert (
        first_half_from_line_scores({"id": 6, "homeLineScores": [7, 7], "awayLineScores": None})
        is None
    )


def test_plays_running_score_end_of_half():
    plays = [
        {"gameId": 10, "period": 1, "homeScore": 0, "awayScore": 0},
        {"gameId": 10, "period": 1, "homeScore": 7, "awayScore": 0},
        {"gameId": 10, "period": 2, "homeScore": 7, "awayScore": 10},
        {"gameId": 10, "period": 2, "homeScore": 14, "awayScore": 10},
        # 3rd-quarter plays must be ignored.
        {"gameId": 10, "period": 3, "homeScore": 21, "awayScore": 10},
    ]
    assert first_half_from_plays(plays) == {10: (14, 10)}


def test_attach_prefers_line_scores():
    game = {"id": 20, "homeLineScores": [7, 7, 0, 0], "awayLineScores": [3, 0, 7, 7]}
    out = attach_first_half(game, pbp_lookup={20: (99, 99)})
    assert out["first_half_total"] == 17
    assert out["first_half_source"] == "linescores"


def test_attach_falls_back_to_pbp():
    game = {"id": 21}  # no line scores
    out = attach_first_half(game, pbp_lookup={21: (10, 6)})
    assert out["home_first_half_points"] == 10
    assert out["first_half_total"] == 16
    assert out["first_half_source"] == "pbp"


def test_attach_no_data():
    out = attach_first_half({"id": 22})
    assert out["first_half_total"] is None
    assert out["first_half_source"] is None


def test_attach_rejects_false_zero_first_half():
    # Placeholder all-zero line scores while the game actually scored 27 points:
    # must not persist a false 0 — fall back to NULL.
    game = {
        "id": 30,
        "homeLineScores": [0, 0, 0, 0],
        "awayLineScores": [0, 0, 0, 0],
        "homePoints": 17,
        "awayPoints": 10,
    }
    out = attach_first_half(game)
    assert out["first_half_total"] is None
    assert out["first_half_source"] is None


def test_attach_false_zero_falls_back_to_pbp():
    game = {
        "id": 31,
        "homeLineScores": [0, 0, 0, 0],
        "awayLineScores": [0, 0, 0, 0],
        "homePoints": 17,
        "awayPoints": 10,
    }
    out = attach_first_half(game, pbp_lookup={31: (7, 3)})
    assert out["first_half_total"] == 10
    assert out["first_half_source"] == "pbp"


def test_attach_rejects_when_quarters_dont_reconcile():
    # Quarter totals (24/14) disagree with the final score (17/10): untrustworthy.
    game = {
        "id": 32,
        "homeLineScores": [10, 14, 0, 0],
        "awayLineScores": [7, 7, 0, 0],
        "homePoints": 17,
        "awayPoints": 10,
    }
    out = attach_first_half(game)
    assert out["first_half_total"] is None


def test_attach_trusts_consistent_line_scores_with_points():
    # Quarters reconcile with the final score → trusted, 1H = Q1+Q2.
    game = {
        "id": 33,
        "homeLineScores": [7, 7, 0, 3],
        "awayLineScores": [3, 0, 7, 0],
        "homePoints": 17,
        "awayPoints": 10,
    }
    out = attach_first_half(game)
    assert out["first_half_total"] == 17  # home 14 + away 3
    assert out["first_half_source"] == "linescores"


def test_plays_running_score_offense_defense_shape():
    # Live CFBD /plays carries the score relative to the OFFENSE, not home/away.
    plays = [
        {
            "gameId": 9,
            "period": 1,
            "offense": "Home U",
            "home": "Home U",
            "away": "Away U",
            "offenseScore": 7,
            "defenseScore": 0,
        },
        {
            "gameId": 9,
            "period": 2,
            "offense": "Away U",
            "home": "Home U",
            "away": "Away U",
            "offenseScore": 3,
            "defenseScore": 7,
        },
        {
            "gameId": 9,
            "period": 3,
            "offense": "Home U",
            "home": "Home U",
            "away": "Away U",
            "offenseScore": 14,
            "defenseScore": 10,
        },
    ]
    assert first_half_from_plays(plays) == {9: (7, 3)}


def test_plays_scoreless_half_yields_real_zero():
    plays = [
        {
            "gameId": 9,
            "period": 2,
            "offense": "Away U",
            "home": "Home U",
            "away": "Away U",
            "offenseScore": 0,
            "defenseScore": 0,
        },
    ]
    assert first_half_from_plays(plays) == {9: (0, 0)}


# --- A scoreless first half is real football, not automatically a false zero -----
# Iowa @ Northwestern 2023 (10-7), Nebraska @ Purdue 2024 (28-10) and SDSU @ UCLA
# 2026 (28-10) all finished with points after a 0-0 half; 15 such games sat on file
# as PBP zeros on 2026-09-20 and every one checked out against ESPN's box score.
# The rule is evidence, not a blanket rejection.


def test_reconciled_full_box_with_scoreless_half_is_trusted():
    game = {
        "id": 401858443,
        "homePoints": 28,
        "awayPoints": 10,
        "homeLineScores": [0, 0, 7, 21],
        "awayLineScores": [0, 0, 0, 10],
    }
    assert line_scores_trustworthy(game, (0, 0)) is True
    out = attach_first_half(game)
    assert out["first_half_total"] == 0
    assert out["first_half_source"] == "linescores"


def test_all_zero_placeholder_box_is_still_rejected():
    # The original corruption: every quarter 0 against a 27-point final.
    game = {
        "id": 1,
        "homePoints": 17,
        "awayPoints": 10,
        "homeLineScores": [0, 0, 0, 0],
        "awayLineScores": [0, 0, 0, 0],
    }
    assert line_scores_trustworthy(game, (0, 0)) is False
    assert attach_first_half(game)["first_half_total"] is None


def test_partial_box_with_scoreless_half_is_not_trusted():
    # Two quarters posted so far, the final already known: cannot reconcile -> reject.
    game = {
        "id": 2,
        "homePoints": 17,
        "awayPoints": 10,
        "homeLineScores": [0, 0],
        "awayLineScores": [0, 0],
    }
    assert line_scores_trustworthy(game, (0, 0)) is False
    # A full box whose quarters do not sum to the final is a corrupt box, not a zero half.
    game = {
        "id": 3,
        "homePoints": 17,
        "awayPoints": 10,
        "homeLineScores": [0, 0, 7, 3],
        "awayLineScores": [0, 0, 3, 7],
    }
    assert line_scores_trustworthy(game, (0, 0)) is False


def test_final_from_plays_takes_the_largest_running_score_any_period():
    plays = [
        {"gameId": 5, "period": 1, "homeScore": 0, "awayScore": 0},
        {"gameId": 5, "period": 3, "homeScore": 7, "awayScore": 0},
        {"gameId": 5, "period": 4, "homeScore": 28, "awayScore": 10},
        {"gameId": 6, "period": 2, "homeScore": 0, "awayScore": 0},
    ]
    assert final_from_plays(plays) == {5: (28, 10), 6: (0, 0)}


def test_pbp_scoreless_half_is_kept_when_the_feed_reaches_the_final():
    game = {"id": 7, "homePoints": 28, "awayPoints": 10}  # no box score at all
    out = attach_first_half(game, pbp_lookup={7: (0, 0)}, pbp_final={7: (28, 10)})
    assert out["first_half_total"] == 0
    assert out["first_half_source"] == "pbp"


def test_pbp_scoreless_half_is_dropped_when_the_feed_stops_short():
    game = {"id": 8, "homePoints": 28, "awayPoints": 10}
    # Feed ends at 0-0: it never saw the 38 points, so its 0-0 half is worthless.
    out = attach_first_half(game, pbp_lookup={8: (0, 0)}, pbp_final={8: (0, 0)})
    assert out["first_half_total"] is None and out["first_half_source"] is None
    # No corroboration offered at all -> not trusted either.
    out = attach_first_half(game, pbp_lookup={8: (0, 0)})
    assert out["first_half_total"] is None


def test_pbp_nonzero_half_and_zero_final_need_no_corroboration():
    # 0-0 final: a 0-0 half contradicts nothing.
    out = attach_first_half({"id": 9, "homePoints": 0, "awayPoints": 0}, pbp_lookup={9: (0, 0)})
    assert out["first_half_total"] == 0
    # A half with points is not the false-zero shape; the existing behaviour stands.
    out = attach_first_half({"id": 10, "homePoints": 28, "awayPoints": 10}, pbp_lookup={10: (7, 3)})
    assert out["first_half_total"] == 10
