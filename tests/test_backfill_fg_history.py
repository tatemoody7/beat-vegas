"""Full-game close backfill (scripts/backfill_fg_history.py): wave bucketing, the
idempotent scope and event matching, plus the bulk historical client call."""

from datetime import datetime, timedelta

from conftest import _load_script
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from beatvegas.db.models import Base, Game, OddsSnapshot, Prediction
from beatvegas.sources.odds import OddsAPIClient


def test_wave_ts_is_the_hour_bucket_of_kickoff_minus_30():
    bf = _load_script("backfill_fg_history")
    assert bf.wave_ts(datetime(2024, 10, 19, 19, 30)) == datetime(2024, 10, 19, 19, 0)
    assert bf.wave_ts(datetime(2024, 10, 19, 16, 0)) == datetime(2024, 10, 19, 15, 0)
    assert bf.wave_ts(datetime(2024, 10, 19, 16, 15)) == datetime(2024, 10, 19, 15, 0)


def _db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    k = datetime(2024, 10, 19, 19, 30)
    with Session(eng) as s:
        s.add_all(
            [
                Game(
                    id=1,
                    season=2024,
                    week=8,
                    home_team="Auburn",
                    away_team="Missouri",
                    start_date=k,
                ),
                Game(
                    id=2,
                    season=2024,
                    week=8,
                    home_team="Iowa",
                    away_team="Penn State",
                    start_date=k + timedelta(minutes=15),
                ),
                Game(
                    id=3,
                    season=2024,
                    week=8,
                    home_team="Texas",
                    away_team="Vanderbilt",
                    start_date=k + timedelta(hours=3),
                ),
                Game(
                    id=4,
                    season=2024,
                    week=9,
                    home_team="Ohio",
                    away_team="Akron",
                    start_date=k + timedelta(days=7),
                ),
            ]
        )
        for gid in (1, 2, 3):
            s.add(Prediction(game_id=gid, model_version="gbm_v1", bv_line=22.0))
        # game 2 already has a pre-kick full-game close (2h before) -> done
        s.add(
            OddsSnapshot(
                game_id=2,
                book="draftkings",
                market="full_game_total",
                line=50.5,
                captured_at=k + timedelta(minutes=15) - timedelta(hours=2),
            )
        )
        # game 3 only has a Sunday opener (5 days out) -> still needs a close
        s.add(
            OddsSnapshot(
                game_id=3,
                book="draftkings",
                market="full_game_total",
                line=48.5,
                captured_at=k - timedelta(days=5),
            )
        )
        s.commit()
    return eng, k


def test_scope_skips_games_with_a_pre_kick_close_and_groups_waves():
    bf = _load_script("backfill_fg_history")
    eng, k = _db()
    with Session(eng) as s:
        scope = bf.games_needing_fg_close(s, 2024, rated_only="gbm_v1")
    assert [g["id"] for g in scope] == [1, 3]  # 2 done, 4 unrated
    waves = bf.group_by_wave(scope)
    assert list(waves) == [datetime(2024, 10, 19, 19, 0), datetime(2024, 10, 19, 22, 0)]
    with Session(eng) as s:
        assert [g["id"] for g in bf.games_needing_fg_close(s, 2024, week=8)] == [
            1,
            3,
        ]


def test_match_events_to_games_by_teams_and_kickoff():
    bf = _load_script("backfill_fg_history")
    eng, k = _db()
    with Session(eng) as s:
        scope = bf.games_needing_fg_close(s, 2024, rated_only="gbm_v1")
    events = [
        {
            "id": "e1",
            "home_team": "Auburn Tigers",
            "away_team": "Missouri Tigers",
            "commence_time": k.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        {
            "id": "e9",
            "home_team": "Nobody",
            "away_team": "Noone",
            "commence_time": k.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    ]
    assert bf.match_events_to_games(events, scope) == {"e1": 1}


def test_historical_bulk_totals_hits_the_bulk_endpoint_and_unwraps(monkeypatch):
    seen = {}

    class _Resp:
        status_code = 200
        headers = {"x-requests-remaining": "100", "x-requests-used": "20", "x-requests-last": "10"}

        def raise_for_status(self):
            pass

        def json(self):
            return {"timestamp": "2024-10-19T19:00:00Z", "data": [{"id": "e1", "bookmakers": []}]}

    def fake_get(url, params, timeout):
        seen["url"], seen["params"] = url, params
        return _Resp()

    import beatvegas.sources.odds as odds

    monkeypatch.setattr(odds.requests, "get", fake_get)
    c = OddsAPIClient(api_key="k")
    out = c.historical_bulk_totals("2024-10-19T19:00:00Z", regions="us")
    assert out == [{"id": "e1", "bookmakers": []}]
    assert seen["url"].endswith("/historical/sports/americanfootball_ncaaf/odds")
    assert seen["params"]["markets"] == "totals" and seen["params"]["regions"] == "us"
    assert seen["params"]["date"] == "2024-10-19T19:00:00Z"
    assert c.last_credits.last_cost == 10


def test_fetch_with_retry_retries_transient_errors_then_gives_up_quietly():
    import requests

    bf = _load_script("backfill_fg_history")
    calls = {"n": 0}
    slept = []

    def _resp(code):
        r = requests.Response()
        r.status_code = code
        return r

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise requests.HTTPError("502", response=_resp(502))
        return [{"id": "e1"}]

    out = bf.fetch_with_retry(flaky, backoff=(1, 2, 3), sleep=slept.append)
    assert out == [{"id": "e1"}] and calls["n"] == 3 and slept == [1, 2]

    def always_502():
        raise requests.HTTPError("502", response=_resp(502))

    slept.clear()
    assert bf.fetch_with_retry(always_502, backoff=(1, 2, 3), sleep=slept.append) is None
    assert slept == [1, 2, 3]  # every retry spent, then the wave is skipped

    def unauthorized():
        raise requests.HTTPError("401", response=_resp(401))

    slept.clear()
    assert bf.fetch_with_retry(unauthorized, backoff=(1, 2, 3), sleep=slept.append) is None
    assert slept == []  # a 4xx is not transient: no retries


def test_existing_keys_lets_a_rerun_skip_rows_a_crashed_pass_already_wrote():
    bf = _load_script("backfill_fg_history")
    eng, k = _db()
    wave = bf.wave_ts(k)
    with Session(eng) as s:
        s.add(
            OddsSnapshot(
                game_id=1, book="draftkings", market="full_game_total", line=50.5, captured_at=wave
            )
        )
        s.add(
            OddsSnapshot(
                game_id=1, book="draftkings", market="1H_total", line=24.5, captured_at=wave
            )
        )  # other market: not a key clash
        s.commit()
        assert bf.existing_keys(s, [1, 3], wave) == {(1, "draftkings")}
        assert bf.existing_keys(s, [1], wave + timedelta(hours=1)) == set()
        assert bf.existing_keys(s, [], wave) == set()


def test_two_events_matching_one_game_keep_only_the_best_scoring_event():
    bf = _load_script("backfill_fg_history")
    eng, k = _db()
    with Session(eng) as s:
        scope = bf.games_needing_fg_close(s, 2024, rated_only="gbm_v1")
    iso = k.strftime("%Y-%m-%dT%H:%M:%SZ")
    events = [
        {
            "id": "exact",
            "home_team": "Auburn Tigers",
            "away_team": "Missouri Tigers",
            "commence_time": iso,
        },
        {"id": "fuzzy", "home_team": "Auburn", "away_team": "Missouri St", "commence_time": iso},
    ]
    out = bf.match_events_to_games(events, scope)
    assert list(out.values()).count(1) == 1  # one event per game
    assert out.get("exact") == 1
