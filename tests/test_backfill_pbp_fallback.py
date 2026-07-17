"""S21: the default backfill must PBP-resolve finished games whose line scores
are missing or untrusted (e.g. a genuine 0-0 first half) instead of leaving NULL."""

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _load(script_name: str):
    path = _ROOT / "scripts" / f"{script_name}.py"
    spec = importlib.util.spec_from_file_location(script_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_needs_pbp = _load("backfill")._needs_pbp


def test_unplayed_game_never_needs_pbp():
    assert _needs_pbp({"id": 1, "week": 1}) is False


def test_trusted_line_scores_skip_pbp():
    g = {
        "id": 2,
        "homePoints": 24,
        "awayPoints": 10,
        "homeLineScores": [14, 3, 7, 0],
        "awayLineScores": [0, 7, 3, 0],
    }
    assert _needs_pbp(g) is False


def test_zero_first_half_with_scoring_final_needs_pbp():
    # The linescore 0-0 half can't be trusted (could be a placeholder), but PBP
    # can confirm it — this game must be queued for the plays fetch.
    g = {
        "id": 3,
        "homePoints": 20,
        "awayPoints": 7,
        "homeLineScores": [0, 0, 13, 7],
        "awayLineScores": [0, 0, 0, 7],
    }
    assert _needs_pbp(g) is True


def test_missing_line_scores_on_finished_game_needs_pbp():
    assert _needs_pbp({"id": 4, "homePoints": 31, "awayPoints": 17}) is True
