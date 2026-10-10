"""The weather arms H-ARM-WX1H / H-ARM-WXFG (docs/HYPOTHESES.md, Tate's calls of
2026-10-09): the build-time forecast capture, the 10+ mph kickoff-hour rule, and
paper unders at Hard Rock's price into challenger_picks only."""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from beatvegas import protocol as P
from beatvegas import wx_paper as W
from beatvegas.db.models import (
    BuildForecast,
    ChallengerPick,
    Game,
    ManualPick,
    OddsSnapshot,
    Venue,
)
from beatvegas.sources.weather import WeatherUnavailable
from tests.conftest import _sqlite_scope

NOW = datetime(2026, 10, 13, 20, 10)  # a Tuesday build
KICK = datetime(2026, 10, 17, 19, 30)  # Saturday


def _seed(eng, games):
    """games: [(id, venue_id, kickoff)]; venues 1 (outdoor), 2 (dome), 3 (outdoor)."""
    with Session(eng) as s:
        s.add(Venue(id=1, name="Open", latitude=40.0, longitude=-83.0, dome=False))
        s.add(Venue(id=2, name="Dome", latitude=42.3, longitude=-83.0, dome=True))
        s.add(Venue(id=3, name="Windy", latitude=41.0, longitude=-96.0, dome=False))
        for gid, vid, kick in games:
            s.add(
                Game(
                    id=gid,
                    season=2026,
                    week=8,
                    home_team=f"H{gid}",
                    away_team=f"A{gid}",
                    venue_id=vid,
                    start_date=kick,
                )
            )
        s.commit()


def _fake_fetch(winds):
    """A fetch that returns `winds[(lat, day)]` at every hour and records calls."""
    calls = []

    def fetch(lat, lon, start, end, **kw):
        calls.append((lat, start, kw.get("source"), kw.get("models")))
        w = winds[(lat, start)]
        if w is None:
            raise WeatherUnavailable("down")
        return {
            f"{start}T{h:02d}": {
                "wind_mph": w,
                "wind_gust_mph": w + 8,
                "temperature_f": 55.0,
                "precipitation": 0.0,
            }
            for h in range(24)
        }

    return fetch, calls


def test_capture_stores_one_forecast_per_game_one_call_per_venue_day_and_no_dome_call():
    eng, scope = _sqlite_scope()
    _seed(eng, [(1, 1, KICK), (2, 1, KICK + timedelta(hours=3)), (3, 2, KICK), (4, None, KICK)])
    fetch, calls = _fake_fetch({(40.0, "2026-10-17"): 12.0})
    with scope() as s:
        stats = W.capture(s, [1, 2, 3, 4], NOW, slot="tue_pm", fetch=fetch)
    assert stats == {"stored": 3, "domes": 1, "no_venue": 1, "failed": 0}
    assert calls == [(40.0, "2026-10-17", "open_meteo_forecast", "icon_seamless")]
    with Session(eng) as s:
        rows = {r.game_id: r for r in s.query(BuildForecast).all()}
    assert rows[1].wind_mph == 12.0 and rows[1].fetched_at == NOW and rows[1].slot == "tue_pm"
    assert rows[1].lead_hours == round((KICK - NOW).total_seconds() / 3600, 2)
    assert rows[3].dome is True and rows[3].wind_mph is None


def test_a_failed_fetch_is_counted_never_raised_and_a_kicked_off_game_is_skipped():
    eng, scope = _sqlite_scope()
    _seed(eng, [(1, 1, KICK), (2, 3, NOW - timedelta(hours=1))])
    fetch, _ = _fake_fetch({(40.0, "2026-10-17"): None})
    with scope() as s:
        stats = W.capture(s, [1, 2], NOW, fetch=fetch)
    assert stats["failed"] == 1 and stats["stored"] == 0  # game 2 already kicked off


def test_the_rule_is_10_mph_sustained_outdoors():
    def fc(w, dome=False):
        return BuildForecast(wind_mph=w, dome=dome)

    assert W.qualifies(fc(10.0)) and W.qualifies(fc(23.4))
    assert not W.qualifies(fc(9.99)) and not W.qualifies(fc(None))
    assert not W.qualifies(fc(30.0, dome=True)) and not W.qualifies(None)
    assert W.WIND_MIN_MPH == 10.0


def test_newest_is_the_latest_fetch_at_or_before_the_build():
    eng, scope = _sqlite_scope()
    _seed(eng, [(1, 1, KICK)])
    with Session(eng) as s:
        for at, w in [
            (NOW - timedelta(days=2), 15.0),
            (NOW, 8.0),
            (NOW + timedelta(hours=1), 20.0),
        ]:
            s.add(BuildForecast(game_id=1, fetched_at=at, wind_mph=w, dome=False))
        s.commit()
    with scope() as s:
        assert W.newest(s, [1], NOW)[1].wind_mph == 8.0  # never a later fetch


def _item(gid, **over):
    it = {
        "game_id": gid,
        "home": f"H{gid}",
        "away": f"A{gid}",
        "kick": KICK.isoformat() + "Z",
        "hr_line": 24.5,
        "hr_price": -115,
        "hr_centred": True,
    }
    it.update(over)
    return it


def test_first_half_arm_logs_windy_centred_games_once_at_hard_rocks_price():
    eng, scope = _sqlite_scope()
    _seed(eng, [(g, 1, KICK) for g in (1, 2, 3, 4)])
    fcs = {
        1: BuildForecast(game_id=1, wind_mph=14.0, dome=False, fetched_at=NOW),
        2: BuildForecast(game_id=2, wind_mph=6.0, dome=False, fetched_at=NOW),
        3: BuildForecast(game_id=3, wind_mph=18.0, dome=False, fetched_at=NOW),
    }
    card = {
        "season": 2026,
        "week": 8,
        "slot": "tue_pm",
        "items": [_item(1), _item(2), _item(3, hr_centred=False), _item(4)],
    }
    with scope() as s:
        first = W.log_first_half(s, card, NOW, fcs)
        again = W.log_first_half(s, card, NOW, fcs)
    assert first == {"windy": 1, "added": 1} and again["added"] == 0
    with Session(eng) as s:
        (r,) = s.query(ChallengerPick).all()
        assert (r.arm, r.side, r.market, r.game_id) == ("H-ARM-WX1H", "under", "1H", 1)
        assert r.line == 24.5 and r.price == -115 and r.book == "hardrockbet"
        assert '"wind_mph": 14.0' in r.factors_json_at_pick
        assert s.query(ManualPick).count() == 0


def test_first_half_arm_respects_the_paper_window():
    eng, scope = _sqlite_scope()
    _seed(eng, [(1, 1, KICK)])
    fcs = {1: BuildForecast(game_id=1, wind_mph=14.0, dome=False, fetched_at=NOW)}
    card = {"season": 2026, "week": 8, "slot": "tue_pm", "items": [_item(1)]}
    with scope() as s:
        assert W.log_first_half(s, card, NOW, fcs, window_hours=48)["added"] == 0  # 95 h out
        assert W.log_first_half(s, card, NOW, fcs, window_hours=None)["added"] == 1


def test_full_game_arm_logs_at_hard_rocks_newest_centred_total():
    eng, scope = _sqlite_scope()
    _seed(eng, [(1, 1, KICK), (2, 1, KICK), (3, 1, KICK)])
    with Session(eng) as s:
        for gid, line, over, under in [
            (1, 41.5, -110, -110),
            (2, 44.5, -110, -110),
            (3, 50.5, -170, 135),
        ]:
            s.add(
                OddsSnapshot(
                    game_id=gid,
                    book="hardrockbet",
                    market="full_game_total",
                    line=line,
                    over_price=over,
                    under_price=under,
                    captured_at=NOW - timedelta(hours=1),
                )
            )
        s.commit()
    fcs = {
        1: BuildForecast(game_id=1, wind_mph=11.0, dome=False, fetched_at=NOW),
        2: BuildForecast(game_id=2, wind_mph=4.0, dome=False, fetched_at=NOW),
        3: BuildForecast(game_id=3, wind_mph=20.0, dome=False, fetched_at=NOW),
    }
    with scope() as s:
        out = W.log_full_game(s, 2026, 8, NOW, fcs, slot="tue_pm")
    assert out == {"windy": 1, "added": 1}  # game 3's quote is an off-centre rung
    with Session(eng) as s:
        (r,) = s.query(ChallengerPick).all()
        assert (r.arm, r.market, r.side, r.line, r.price) == (
            "H-ARM-WXFG",
            "full",
            "under",
            41.5,
            -110,
        )


def test_the_weather_arms_hold_slots_6_and_7_and_run_their_own_clocks():
    assert P.ARMS[P.ARM_WX_1H] == {
        "table": "challenger_picks",
        "market": "1H",
        "side": "under",
        "slot": 6,
    }
    assert P.ARMS[P.ARM_WX_FG]["market"] == "full" and P.ARMS[P.ARM_WX_FG]["slot"] == 7
    assert P.arm_start(P.ARM_WX_1H) == P.WX_ARMS_START is not None
    assert P.arm_start(P.ARM_1H_UNDER) is None  # the model arms stay paused (p1.1)
    assert len({spec["slot"] for spec in P.ARMS.values()}) == len(P.ARMS) <= P.K_TESTS


def _hr_full_game(eng, quotes):
    """quotes: [(game_id, over_price, under_price)] -> Hard Rock full-game totals."""
    with Session(eng) as s:
        for gid, over, under in quotes:
            s.add(
                OddsSnapshot(
                    game_id=gid,
                    book="hardrockbet",
                    market="full_game_total",
                    line=47.5,
                    over_price=over,
                    under_price=under,
                    captured_at=NOW - timedelta(hours=1),
                )
            )
        s.commit()


def test_arm_game_ids_are_the_hard_rock_priced_games_either_arm_can_log():
    # 2026-10-10: the sat_am capture fetched every game of the week (254) and
    # timed the card out; only a game an arm can log is worth a forecast call.
    eng, scope = _sqlite_scope()
    _seed(eng, [(g, 1, KICK) for g in (1, 2, 3, 4, 5, 7)] + [(6, 1, NOW - timedelta(hours=1))])
    _hr_full_game(eng, [(4, -110, -110), (5, -170, 135), (6, -110, -110)])
    card = {
        "season": 2026,
        "week": 8,
        "items": [
            _item(1),  # centred, priced: the first-half arm
            _item(2, hr_centred=False),
            _item(3, hr_price=None),
        ],
    }
    with scope() as s:
        ids = W.arm_game_ids(s, card, 2026, 8, NOW)
    # 4 = a centred full-game total; 5 is an off-centre rung; 6 has kicked off;
    # 7 has no Hard Rock quote at all.
    assert ids == [1, 4]


def test_capture_starts_no_call_past_its_budget_and_counts_the_rest_failed():
    eng, scope = _sqlite_scope()
    _seed(eng, [(1, 1, KICK), (2, 3, KICK), (3, 1, KICK + timedelta(days=1))])
    calls = []

    def fetch(lat, lon, start, end, **kw):
        calls.append((lat, start, kw.get("timeout"), kw.get("attempts")))
        return {f"{start}T{h:02d}": {"wind_mph": 12.0} for h in range(24)}

    ticks = [0.0, 0.0, 100.0, 200.0]  # start, then before each new call; holds the last

    def clock():
        return ticks.pop(0) if len(ticks) > 1 else ticks[0]

    with scope() as s:
        stats = W.capture(s, [3, 2, 1], NOW, fetch=fetch, budget_seconds=150.0, clock=clock)
    # Kickoff order: games 1 and 2 (Saturday) are fetched; game 3 (Sunday) would
    # start a call after the budget, so it is counted, never fetched.
    assert [c[:2] for c in calls] == [(40.0, "2026-10-17"), (41.0, "2026-10-17")]
    assert stats == {"stored": 2, "domes": 0, "no_venue": 0, "failed": 1, "over_budget": 1}
    # Every build call carries the short limits, not the backfills' 60 s x 4.
    assert {c[2:] for c in calls} == {(W.BUILD_FETCH_TIMEOUT_S, W.BUILD_FETCH_ATTEMPTS)}
    assert (W.BUILD_FETCH_TIMEOUT_S, W.BUILD_FETCH_ATTEMPTS) == (10, 2)


def test_the_summary_names_the_games_past_the_time_cap():
    stats = {
        "capture": {"stored": 2, "domes": 0, "no_venue": 0, "failed": 1, "over_budget": 1},
        "1h": {"windy": 0, "added": 0},
        "full": {"windy": 0, "added": 0},
    }
    (line,) = W.summary_lines(stats)
    assert "failed 1, 1 past the 180 s cap" in line
    (quiet,) = W.summary_lines({"capture": {"stored": 3, "failed": 0}})
    assert "past the" not in quiet
