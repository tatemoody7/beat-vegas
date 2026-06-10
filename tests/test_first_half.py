from beatvegas.etl.first_half import (
    attach_first_half,
    first_half_from_line_scores,
    first_half_from_plays,
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
