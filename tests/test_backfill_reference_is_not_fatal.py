"""Reference data must never block grading (2026-09-13).

scripts/backfill.py is the FIRST step of grade.yml. Until this fix its first
action was backfill_venues(), unguarded -- so when CFBD rate-limited /venues on
2026-09-12/13, four consecutive grading runs died before fetching a single final
score. Week 2 finished with 14 of 303 games scored and 0 of 31 picks graded.

Venues change about once a year. Scores are the entire point of the run. So the
seasons load first, and the venue refresh is last and best-effort.
"""

import pytest
from conftest import _load_script

mod = _load_script("backfill")


class _Boom(RuntimeError):
    pass


def _run(monkeypatch, *, venues_raise: bool):
    """Drive main() with both halves stubbed, recording the call order."""
    order = []

    def fake_venues(client):
        order.append("venues")
        if venues_raise:
            raise _Boom("CFBD 429 for /venues")
        return 3

    def fake_season(client, season, season_type, use_pbp):
        order.append(f"season:{season}:{season_type}")
        return {"games": 5, "with_1h": 4, "cfbd_with_total": 5}

    monkeypatch.setattr(mod, "backfill_venues", fake_venues)
    monkeypatch.setattr(mod, "backfill_season", fake_season)
    monkeypatch.setattr(mod, "init_db", lambda: None)
    monkeypatch.setattr(mod, "CFBDClient", lambda *a, **k: object())
    monkeypatch.setattr(mod, "load_config", lambda: {})
    monkeypatch.setattr("sys.argv", ["backfill.py", "--season", "2026", "--season-type", "regular"])
    mod.main()
    return order


def test_scores_load_before_reference_data(monkeypatch):
    order = _run(monkeypatch, venues_raise=False)
    assert order == ["season:2026:regular", "venues"]


def test_a_venue_failure_does_not_stop_the_run(monkeypatch, capsys):
    order = _run(monkeypatch, venues_raise=True)
    # The season still loaded, and main() returned instead of propagating.
    assert order == ["season:2026:regular", "venues"]
    out = capsys.readouterr().out
    assert "2026 regular: 5 games" in out
    assert "venues: SKIPPED" in out
    assert "_Boom" in out


def test_a_season_failure_is_still_fatal(monkeypatch):
    # The guard is deliberately narrow: grading depends on the scores, so a
    # failure fetching them must still fail the job loudly.
    def fake_season(client, season, season_type, use_pbp):
        raise _Boom("CFBD 429 for /games")

    monkeypatch.setattr(mod, "backfill_venues", lambda c: 3)
    monkeypatch.setattr(mod, "backfill_season", fake_season)
    monkeypatch.setattr(mod, "init_db", lambda: None)
    monkeypatch.setattr(mod, "CFBDClient", lambda *a, **k: object())
    monkeypatch.setattr(mod, "load_config", lambda: {})
    monkeypatch.setattr("sys.argv", ["backfill.py", "--season", "2026", "--season-type", "regular"])
    with pytest.raises(_Boom):
        mod.main()
