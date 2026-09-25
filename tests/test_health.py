"""beatvegas/health.py -- the contracts as data, one pass/fail pair per check
against an in-memory SQLite with the full schema, the verdict rule, the note,
and the generated docs block."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from beatvegas import health, ops
from beatvegas.db.models import (
    AppSetting,
    Card,
    Game,
    GameRecord,
    ManualPick,
    OddsSnapshot,
    PostMortemRun,
    Prediction,
    TeamTempo,
    Weather,
)
from tests.conftest import _sqlite_scope

SEASON, WEEK = 2026, 4
# A Thursday 4:05pm ET build: RUN_STARTED_AT is the gate step's clock, `now`
# ten minutes later (the job ran).
STARTED = datetime(2026, 9, 24, 20, 5, 0)
NOW = STARTED + timedelta(minutes=10)
KICK = datetime(2026, 9, 26, 19, 30)  # Saturday 3:30pm ET


def _iso_z(d: datetime) -> str:
    return d.isoformat(timespec="seconds") + "Z"


def _ctx(session, job, **kw):
    base = dict(
        session=session,
        now=NOW,
        job=job,
        run_started_at=STARTED,
        season=SEASON,
        week=WEEK,
        env={"GITHUB_RUN_ID": "1234", "GITHUB_EVENT_NAME": "workflow_dispatch"},
    )
    base.update(kw)
    return health.Ctx(**base)


def _check(job: str, cid: str) -> health.Check:
    return next(c for c in health.CONTRACTS[job].checks if c.id == cid)


def _game(gid, home="Missouri", away="Kansas", kick=KICK, week=WEEK, **kw):
    return Game(
        id=gid, season=SEASON, week=week, home_team=home, away_team=away, start_date=kick, **kw
    )


def _item(gid, *, qualifies=True, hr_line=24.5, kick=KICK, blocker=None, gate_blocker=None):
    return {
        "game_id": gid,
        "home": "Missouri",
        "away": "Kansas",
        "kick": _iso_z(kick),
        "qualifies": qualifies,
        "hr_line": hr_line,
        "hr_price": -110,
        "tier": "BET" if qualifies else "PASS",
        "blocker": blocker,
        "gate_blocker": gate_blocker,
        "gap": 2.1,
        "ev": -0.01,
        "bv_line": 22.4,
        "under_score": 72,
        "action": "bet",
    }


def _card(slot="thu_pm", *, status=None, degraded=(), items=None, built_at=None, week=WEEK):
    from beatvegas.ci import CARD_STATUS_BY_SLOT

    items = items if items is not None else [_item(g) for g in range(1, 13)]
    payload = {
        "season": SEASON,
        "week": week,
        "slot": slot,
        "status": status or CARD_STATUS_BY_SLOT[slot],
        "degraded": list(degraded),
        "counts": {"bet": sum(1 for it in items if it["qualifies"])},
        "items": items,
    }
    return Card(
        season=SEASON,
        week=week,
        built_at=built_at or (STARTED + timedelta(minutes=8)),
        payload=json.dumps(payload),
    )


def _paper(gid, placed_at=None):
    return ManualPick(
        game_id=gid,
        season=SEASON,
        week=WEEK,
        side="under",
        market="1H",
        line=24.5,
        is_paper=True,
        placed_at=placed_at or (STARTED + timedelta(minutes=8)),
    )


@pytest.fixture
def db():
    eng, scope = _sqlite_scope()
    return eng, scope


# --------------------------------------------------------------------------- #
# card
# --------------------------------------------------------------------------- #
class TestCard:
    def test_row_this_run_pass_and_fail(self, db):
        eng, scope = db
        with Session(eng) as s:
            s.add(_card("thu_pm"))
            s.commit()
        with scope() as s:
            ok = _check("card", "card.row_this_run").fn(_ctx(s, "card", slot="thu_pm"))
            assert ok.ok and "items=12" in ok.detail
            # Same row, different slot: not this run's card.
            miss = _check("card", "card.row_this_run").fn(_ctx(s, "card", slot="fri_pm"))
            assert not miss.ok and "slot=fri_pm" in miss.detail
            # Built BEFORE the run started: last build's card, not this one.
            late = _ctx(s, "card", slot="thu_pm", run_started_at=STARTED + timedelta(hours=1))
            assert not _check("card", "card.row_this_run").fn(late).ok

    def test_status_clean_pass_and_fail(self, db):
        eng, scope = db
        with Session(eng) as s:
            s.add(_card("thu_pm"))
            s.commit()
        with scope() as s:
            assert _check("card", "card.status_clean").fn(_ctx(s, "card", slot="thu_pm")).ok
        eng2, scope2 = _sqlite_scope()
        with Session(eng2) as s:
            s.add(
                _card(
                    "thu_pm",
                    status="degraded",
                    degraded=[{"input": "sweep", "detail": "stopped at the credit cap"}],
                )
            )
            s.commit()
        with scope2() as s:
            r = _check("card", "card.status_clean").fn(_ctx(s, "card", slot="thu_pm"))
            assert not r.ok and "status=degraded" in r.detail and "[sweep]" in r.detail

    def test_status_clean_knows_manual_is_a_preview(self, db):
        eng, scope = db
        with Session(eng) as s:
            s.add(_card("manual"))  # status "preview" is the clean state for manual
            s.commit()
        with scope() as s:
            assert _check("card", "card.status_clean").fn(_ctx(s, "card", slot="manual")).ok

    def test_hr_priced_floor_pass_and_fail(self, db):
        eng, scope = db
        with Session(eng) as s:
            s.add(_card("thu_pm", items=[_item(g) for g in range(1, 1 + health.HR_PRICED_FLOOR)]))
            s.commit()
        with scope() as s:
            assert _check("card", "card.hr_priced_floor").fn(_ctx(s, "card", slot="thu_pm")).ok
        eng2, scope2 = _sqlite_scope()
        with Session(eng2) as s:
            items = [_item(g, hr_line=None) for g in range(1, 20)] + [_item(99)]
            s.add(_card("thu_pm", items=items))
            s.commit()
        with scope2() as s:
            r = _check("card", "card.hr_priced_floor").fn(_ctx(s, "card", slot="thu_pm"))
            assert not r.ok and r.detail.startswith("1 Hard Rock-priced")

    def test_paper_logged_for_a_scheduled_slot_respects_the_window(self, db):
        """thu_pm's window is 24 h: a Saturday game is NOT expected to be logged
        by Thursday's build (Friday claims it); a Friday-afternoon game is."""
        eng, scope = db
        fri_game = STARTED + timedelta(hours=20)
        with Session(eng) as s:
            s.add(
                _card(
                    "thu_pm",
                    items=[
                        _item(1, kick=fri_game),  # in window, logged
                        _item(2, kick=KICK),  # Saturday: outside the 24 h window
                        _item(3, qualifies=False, kick=fri_game),  # does not qualify
                    ],
                )
            )
            s.add(_paper(1))
            s.commit()
        with scope() as s:
            r = _check("card", "card.paper_logged_iff_window").fn(_ctx(s, "card", slot="thu_pm"))
            assert r.ok, r.detail
            assert "1/1 qualifying items in window (24h)" in r.detail

    def test_paper_logged_misses_when_a_window_game_has_no_paper_pick(self, db):
        eng, scope = db
        with Session(eng) as s:
            s.add(_card("fri_pm", items=[_item(1), _item(2)]))  # fri_pm: rest of the week
            s.add(_paper(1))
            s.commit()
        with scope() as s:
            r = _check("card", "card.paper_logged_iff_window").fn(_ctx(s, "card", slot="fri_pm"))
            assert not r.ok
            assert "1/2 qualifying items in window (rest of week)" in r.detail
            assert "missing 2" in r.detail

    def test_paper_logged_for_manual_wants_zero_new_paper_rows(self, db):
        eng, scope = db
        with Session(eng) as s:
            s.add(_card("manual", items=[_item(1)]))
            s.add(_paper(7, placed_at=STARTED - timedelta(days=1)))  # an older pick is fine
            s.commit()
        with scope() as s:
            assert (
                _check("card", "card.paper_logged_iff_window").fn(_ctx(s, "card", slot="manual")).ok
            )
        with Session(eng) as s:
            s.add(_paper(1))  # logged by THIS manual build: the week is now frozen
            s.commit()
        with scope() as s:
            r = _check("card", "card.paper_logged_iff_window").fn(_ctx(s, "card", slot="manual"))
            assert not r.ok and "logged 1 paper picks" in r.detail

    def test_sweep_reached_slate_reads_the_status_file(self, db):
        eng, scope = db
        good = {"complete": True, "events_in_window": 80, "events_polled": 80, "credits_spent": 80}
        partial = {
            "complete": False,
            "reason": "credit_cap",
            "events_in_window": 80,
            "events_polled": 41,
            "credits_spent": 41,
        }
        with scope() as s:
            fn = _check("card", "card.sweep_reached_slate").fn
            assert fn(_ctx(s, "card", status_files={"sweep": good})).ok
            r = fn(_ctx(s, "card", status_files={"sweep": partial}))
            assert not r.ok and "polled=41/80" in r.detail and "credit_cap" in r.detail
            # No file: a miss unless the sweep step was skipped.
            assert not fn(_ctx(s, "card", outcomes={"sweep": "failure"})).ok
            assert fn(_ctx(s, "card", outcomes={"sweep": "skipped"})).ok

    def test_info_counts_early_season_holds_and_bets(self, db):
        eng, scope = db
        with Session(eng) as s:
            items = [
                _item(1, blocker="early_season"),
                _item(2, blocker="degraded", gate_blocker="early_season"),
                _item(3),
            ]
            s.add(_card("thu_pm", items=items))
            s.commit()
        with scope() as s:
            info = health.CONTRACTS["card"].info(
                _ctx(s, "card", slot="thu_pm", outcomes={"sweep": "success", "preview": "failure"})
            )
        assert info == {
            "sweep": "success",
            "preview": "failure",
            "early_season_held": "2",
            "bets": "3",
            "hr_alt_ignored": "0",
        }


# --------------------------------------------------------------------------- #
# grade
# --------------------------------------------------------------------------- #
class TestGrade:
    def test_completed_this_run_pass_and_fail(self, db):
        eng, scope = db
        fn = _check("grade", "grade.completed_this_run").fn
        with scope() as s:
            assert not fn(_ctx(s, "grade")).ok  # never written
            ops.record_gauge(ops.LAST_GRADE_COMPLETED_AT, "x", session=s)
        with Session(eng) as s:
            s.get(AppSetting, ops.LAST_GRADE_COMPLETED_AT).updated_at = STARTED - timedelta(hours=3)
            s.commit()
        with scope() as s:
            assert not fn(_ctx(s, "grade")).ok  # last run's, not this one's
        with Session(eng) as s:
            s.get(AppSetting, ops.LAST_GRADE_COMPLETED_AT).updated_at = STARTED + timedelta(
                minutes=5
            )
            s.commit()
        with scope() as s:
            assert fn(_ctx(s, "grade")).ok

    def test_finals_landed_is_the_boards_stale_predicate(self, db):
        eng, scope = db
        old_kick = NOW - timedelta(hours=health.STALE_AFTER_HOURS + 1)
        recent_kick = NOW - timedelta(hours=3)
        with Session(eng) as s:
            s.add_all(
                [
                    _game(1, kick=old_kick),  # rated, unscored, old -> the miss
                    _game(2, kick=old_kick),  # unrated (no record): FCS noise, ignored
                    _game(3, kick=recent_kick),  # rated, unscored but still in play
                    _game(4, kick=old_kick, home_points=21, away_points=10),  # scored
                ]
            )
            for gid in (1, 3, 4):
                s.add(GameRecord(game_id=gid, season=SEASON, week=WEEK, line=24.5))
            s.commit()
        fn = _check("grade", "grade.finals_landed").fn
        with scope() as s:
            r = fn(_ctx(s, "grade"))
            assert not r.ok and r.detail.startswith("1 rated games")
        with Session(eng) as s:
            g = s.get(Game, 1)
            g.home_points, g.away_points = 14, 7
            s.commit()
        with scope() as s:
            assert fn(_ctx(s, "grade")).ok

    def test_records_graded_pass_and_fail(self, db):
        eng, scope = db
        with Session(eng) as s:
            s.add_all([_game(1, first_half_total=20), _game(2)])  # 2 has no 1H yet
            s.add(GameRecord(game_id=1, season=SEASON, week=WEEK, line=24.5))
            s.add(GameRecord(game_id=2, season=SEASON, week=WEEK, line=24.5))
            s.commit()
        fn = _check("grade", "grade.records_graded").fn
        with scope() as s:
            r = fn(_ctx(s, "grade"))
            assert not r.ok and r.detail.startswith("1 game_records")
        with Session(eng) as s:
            rec = s.query(GameRecord).filter(GameRecord.game_id == 1).one()
            rec.graded_at = NOW
            s.commit()
        with scope() as s:
            assert fn(_ctx(s, "grade")).ok

    def test_picks_graded_pass_and_fail(self, db):
        eng, scope = db
        with Session(eng) as s:
            s.add_all([_game(1, first_half_total=20), _game(2)])
            s.add(_paper(1))  # graded defaults False, game played -> miss
            s.add(_paper(2))  # game not played -> nothing to grade
            s.commit()
        fn = _check("grade", "grade.picks_graded").fn
        with scope() as s:
            r = fn(_ctx(s, "grade"))
            assert not r.ok and r.detail.startswith("1 picks")
        with Session(eng) as s:
            p = s.query(ManualPick).filter(ManualPick.game_id == 1).one()
            p.graded = True
            s.commit()
        with scope() as s:
            assert fn(_ctx(s, "grade")).ok

    def test_postmortem_written_matches_the_exact_live_scope(self, db):
        eng, scope = db
        fn = _check("grade", "grade.postmortem_written").fn
        with Session(eng) as s:
            # The bug of 2026-09-22 in reverse: a row with scope 'live' is NOT the season's.
            s.add(PostMortemRun(run_id="a", computed_at=NOW, scope="live", n_games=5))
            s.add(PostMortemRun(run_id="b", computed_at=NOW, scope="hist_2023_25", n_games=5))
            s.add(
                PostMortemRun(
                    run_id="c",
                    computed_at=STARTED - timedelta(hours=5),
                    scope=f"live_{SEASON}",
                    n_games=5,
                )
            )
            s.commit()
        with scope() as s:
            r = fn(_ctx(s, "grade"))
            assert not r.ok and f"scope=live_{SEASON}" in r.detail
        with Session(eng) as s:
            s.add(PostMortemRun(run_id="d", computed_at=NOW, scope=f"live_{SEASON}", n_games=9))
            s.commit()
        with scope() as s:
            r = fn(_ctx(s, "grade"))
            assert r.ok and "n_games=9" in r.detail

    def test_reference_cache_populated_reads_the_prior_seasons_five_files(
        self, db, tmp_path, monkeypatch
    ):
        from beatvegas.sources import season_stats

        monkeypatch.setattr(season_stats, "CACHE", tmp_path)
        eng, scope = db
        fn = _check("grade", "grade.reference_cache_populated").fn
        with scope() as s:
            r = fn(_ctx(s, "grade"))
            assert not r.ok and "0/5" in r.detail and f"sp_{SEASON - 1}.json" in r.detail
            for kind in health.REFERENCE_CACHE_KINDS:
                (tmp_path / f"{kind}_{SEASON - 1}.json").write_text("x" * 2000)
            # The current season's file is reported, never required (an empty
            # payload is exactly the 2-byte bug the size floor exists for).
            (tmp_path / f"sp_{SEASON}.json").write_text("[]")
            r = fn(_ctx(s, "grade"))
            assert r.ok and f"{SEASON - 1}: 5/5" in r.detail and f"{SEASON}: 0/5" in r.detail
            # An empty payload for the prior season is a miss again.
            (tmp_path / f"adv_{SEASON - 1}.json").write_text("[]")
            assert not fn(_ctx(s, "grade")).ok

    def test_info_counts_zero_halves_graded_this_run(self, db):
        eng, scope = db
        with Session(eng) as s:
            s.add_all([_game(1), _game(2), _game(3)])
            s.add(
                GameRecord(game_id=1, season=SEASON, week=WEEK, first_half_total=0, graded_at=NOW)
            )
            s.add(
                GameRecord(game_id=2, season=SEASON, week=WEEK, first_half_total=21, graded_at=NOW)
            )
            s.add(
                GameRecord(
                    game_id=3,
                    season=SEASON,
                    week=WEEK,
                    first_half_total=0,
                    graded_at=STARTED - timedelta(days=1),  # graded by an earlier run
                )
            )
            s.commit()
        with scope() as s:
            info = health.CONTRACTS["grade"].info(_ctx(s, "grade", outcomes={"pm": "success"}))
        assert info == {"zero_halves_graded": "1", "pm": "success"}


# --------------------------------------------------------------------------- #
# sunday
# --------------------------------------------------------------------------- #
class TestSunday:
    # Sunday 2026-09-27 2:30pm ET = 18:30Z; ET midnight that day = 04:00Z.
    SUN_NOW = datetime(2026, 9, 27, 18, 30)
    SUN_STARTED = datetime(2026, 9, 27, 18, 20)
    BEFORE_MIDNIGHT = datetime(2026, 9, 27, 3, 30)  # still Saturday in ET
    AFTER_MIDNIGHT = datetime(2026, 9, 27, 12, 0)

    def _sctx(self, s, **kw):
        return _ctx(s, "sunday", now=self.SUN_NOW, run_started_at=self.SUN_STARTED, **kw)

    def test_fg_snapshot_today_is_since_ET_midnight(self, db):
        eng, scope = db
        fn = _check("sunday", "sunday.fg_snapshot_today").fn
        with Session(eng) as s:
            s.add(_game(1))
            s.add(
                OddsSnapshot(
                    game_id=1,
                    book="draftkings",
                    market="full_game_total",
                    line=50.5,
                    captured_at=self.BEFORE_MIDNIGHT,
                )
            )
            s.commit()
        with scope() as s:
            assert not fn(self._sctx(s)).ok  # yesterday's (ET) capture does not count
        with Session(eng) as s:
            s.add(
                OddsSnapshot(
                    game_id=1,
                    book="hardrockbet",
                    market="full_game_total",
                    line=50.5,
                    captured_at=self.AFTER_MIDNIGHT,
                )
            )
            s.commit()
        with scope() as s:
            r = fn(self._sctx(s))
            assert r.ok and r.detail.startswith("1 full-game snapshots")

    def test_predictions_and_derived_lines_are_told_apart(self, db):
        eng, scope = db
        model = _check("sunday", "sunday.predictions_today").fn
        derived = _check("sunday", "sunday.derived_lines_posted").fn
        with Session(eng) as s:
            s.add(_game(1))
            s.add(_game(2, week=WEEK + 1))  # next week's game: not this slate
            s.add(
                Prediction(
                    game_id=1,
                    model_version="derived_lines",
                    bv_line=24.0,
                    created_at=self.AFTER_MIDNIGHT,
                )
            )
            s.add(
                Prediction(
                    game_id=2, model_version="gbm_v2", bv_line=24.0, created_at=self.AFTER_MIDNIGHT
                )
            )
            s.add(
                Prediction(
                    game_id=1, model_version="gbm_v2", bv_line=24.0, created_at=self.BEFORE_MIDNIGHT
                )
            )
            s.commit()
        with scope() as s:
            assert derived(self._sctx(s)).ok
            r = model(self._sctx(s))
            assert not r.ok and r.detail.startswith("0 model predictions")
        with Session(eng) as s:
            s.add(
                Prediction(
                    game_id=1, model_version="gbm_v2", bv_line=24.0, created_at=self.AFTER_MIDNIGHT
                )
            )
            s.commit()
        with scope() as s:
            assert model(self._sctx(s)).ok

    def test_pace_coverage_over_the_fbs_slate(self, db, monkeypatch):
        from beatvegas.etl import fbs

        monkeypatch.setattr(
            fbs,
            "load_fbs_teams",
            lambda path=None: {SEASON: {"Missouri", "Kansas", "Iowa", "Nebraska"}},
        )
        eng, scope = db
        fn = _check("sunday", "sunday.pace_coverage").fn
        with Session(eng) as s:
            s.add(_game(1, home="Missouri", away="Kansas"))
            s.add(_game(2, home="Iowa", away="Nebraska"))
            s.add(_game(3, home="Nobody", away="Noone"))  # FCS: not on the scored slate
            for t in ("Missouri", "Kansas", "Iowa"):
                s.add(TeamTempo(season=SEASON, week=WEEK, team=t, seconds_per_play=27.0))
            s.add(TeamTempo(season=SEASON, week=WEEK, team="Nebraska", seconds_per_play=None))
            s.add(TeamTempo(season=SEASON, week=WEEK - 1, team="Nebraska", seconds_per_play=26.0))
            s.commit()
        with scope() as s:
            r = fn(self._sctx(s))
            assert not r.ok and "3/4 slate teams" in r.detail  # 75% < 80%
        with Session(eng) as s:
            # (season, week, team) is unique: the mapper fills in the pace.
            row = (
                s.query(TeamTempo)
                .filter(TeamTempo.week == WEEK, TeamTempo.team == "Nebraska")
                .one()
            )
            row.seconds_per_play = 25.0
            s.commit()
        with scope() as s:
            r = fn(self._sctx(s))
            assert r.ok and "4/4 slate teams" in r.detail

    def test_weather_coverage_over_the_fbs_slate(self, db, monkeypatch):
        from beatvegas.etl import fbs

        monkeypatch.setattr(
            fbs,
            "load_fbs_teams",
            lambda path=None: {SEASON: {"Missouri", "Kansas", "Iowa", "Nebraska"}},
        )
        eng, scope = db
        fn = _check("sunday", "sunday.weather_coverage").fn
        with Session(eng) as s:
            s.add(_game(1, home="Missouri", away="Kansas"))
            s.add(_game(2, home="Iowa", away="Nebraska"))
            s.add(_game(3, home="Nobody", away="Noone"))
            s.add(Weather(game_id=1, temperature_f=71.0, dome=False))
            s.commit()
        with scope() as s:
            r = fn(self._sctx(s))
            assert not r.ok and "1/2 FBS games" in r.detail
        with Session(eng) as s:
            s.add(Weather(game_id=2, dome=True))  # a dome row is coverage too
            s.commit()
        with scope() as s:
            assert fn(self._sctx(s)).ok

    def test_coverage_falls_back_to_every_game_when_the_fbs_snapshot_lacks_the_season(
        self, db, monkeypatch
    ):
        from beatvegas.etl import fbs

        monkeypatch.setattr(fbs, "load_fbs_teams", lambda path=None: {SEASON - 1: {"Missouri"}})
        eng, scope = db
        with Session(eng) as s:
            s.add(_game(1))
            s.add(Weather(game_id=1, dome=True))
            s.commit()
        with scope() as s:
            r = _check("sunday", "sunday.weather_coverage").fn(self._sctx(s))
            assert r.ok and "no FBS snapshot" in r.detail

    def test_info_carries_the_probe_facts_and_enrichment_outcomes(self, db):
        eng, scope = db
        with scope() as s:
            info = health.CONTRACTS["sunday"].info(
                self._sctx(
                    s,
                    env={"NEED_CAPTURE": "false", "NEED_SCORE": "true"},
                    outcomes={"pace": "success", "weather": "failure"},
                )
            )
        assert info == {
            "need_capture": "false",
            "need_score": "true",
            "pace": "success",
            "weather": "failure",
        }


# --------------------------------------------------------------------------- #
# lines_watch
# --------------------------------------------------------------------------- #
class TestLinesWatch:
    def test_close_polled_pass_and_fail(self, db):
        eng, scope = db
        fn = _check("lines_watch", "lines_watch.close_polled").fn
        with scope() as s:
            assert not fn(_ctx(s, "lines_watch")).ok  # no file
            assert fn(
                _ctx(
                    s,
                    "lines_watch",
                    status_files={
                        "close": {"events_in_window": 0, "events_polled": 0, "complete": True}
                    },
                )
            ).ok
            assert fn(
                _ctx(
                    s,
                    "lines_watch",
                    status_files={
                        "close": {"events_in_window": 3, "events_polled": 3, "complete": True}
                    },
                )
            ).ok
            r = fn(
                _ctx(
                    s,
                    "lines_watch",
                    status_files={
                        "close": {
                            "events_in_window": 3,
                            "events_polled": 0,
                            "complete": False,
                            "reason": "credit_floor",
                        }
                    },
                )
            )
            assert not r.ok and "polled=0/3" in r.detail and "credit_floor" in r.detail

    def test_hr_rows_touched_counts_new_rows_and_last_seen_stamps(self, db):
        eng, scope = db
        fn = _check("lines_watch", "lines_watch.hr_rows_touched").fn
        polled = {"close": {"events_in_window": 2, "events_polled": 2, "complete": True}}
        with Session(eng) as s:
            s.add(_game(1))
            # An HR 1H row from the Friday sweep, never re-seen: not this run's.
            s.add(
                OddsSnapshot(
                    game_id=1,
                    book="hardrockbet",
                    market="1H_total",
                    line=24.5,
                    captured_at=STARTED - timedelta(days=1),
                )
            )
            # A DK row written by this run: the wrong book.
            s.add(
                OddsSnapshot(
                    game_id=1, book="draftkings", market="1H_total", line=24.5, captured_at=NOW
                )
            )
            s.commit()
        with scope() as s:
            assert not fn(_ctx(s, "lines_watch", status_files=polled)).ok
            # Nothing polled: nothing expected.
            assert fn(
                _ctx(
                    s,
                    "lines_watch",
                    status_files={"close": {"events_in_window": 0, "events_polled": 0}},
                )
            ).ok
        with Session(eng) as s:
            row = s.query(OddsSnapshot).filter(OddsSnapshot.book == "hardrockbet").one()
            row.last_seen_at = NOW  # the unchanged-number stamp IS the close time
            s.commit()
        with scope() as s:
            r = fn(_ctx(s, "lines_watch", status_files=polled))
            assert r.ok and r.detail.startswith("1 Hard Rock 1H rows")

    def test_close_gauge_written_pass_and_fail(self, db):
        eng, scope = db
        fn = _check("lines_watch", "lines_watch.close_gauge_written").fn
        polled = {"close": {"events_in_window": 2, "events_polled": 2, "complete": True}}
        with scope() as s:
            assert not fn(_ctx(s, "lines_watch", status_files=polled)).ok
            assert fn(_ctx(s, "lines_watch", status_files={})).ok  # n/a
            ops.record_gauge(ops.LAST_CLOSE_CAPTURE_AT, NOW.isoformat(), session=s)
        with Session(eng) as s:
            # record_gauge stamps the wall clock; the fixture's run is in the future.
            s.get(AppSetting, ops.LAST_CLOSE_CAPTURE_AT).updated_at = NOW
            s.commit()
        with scope() as s:
            assert fn(_ctx(s, "lines_watch", status_files=polled)).ok


# --------------------------------------------------------------------------- #
# evaluate / verdict / note
# --------------------------------------------------------------------------- #
def _const(ok: bool):
    def fn(ctx):
        return health.Result(ok, f"d{ok}")

    return fn


def _stub_contract(*severities_ok):
    checks = tuple(
        health.Check(f"t.c{i}", sev, "fact", _const(ok))
        for i, (sev, ok) in enumerate(severities_ok)
    )
    return health.Contract("t", "t.yml", "w", (), (), checks, ())


def test_verdict_failed_beats_degraded_beats_ok(db):
    eng, scope = db
    with scope() as s:
        ctx = _ctx(s, "t")
        assert health.evaluate(_stub_contract(("failed", True), ("degraded", True)), ctx)[0] == "ok"
        assert (
            health.evaluate(_stub_contract(("failed", True), ("degraded", False)), ctx)[0]
            == "degraded"
        )
        assert (
            health.evaluate(_stub_contract(("failed", False), ("degraded", True)), ctx)[0]
            == "failed"
        )
        assert (
            health.evaluate(_stub_contract(("failed", False), ("degraded", False)), ctx)[0]
            == "failed"
        )


def test_a_check_that_raises_is_a_miss_not_a_crash(db):
    eng, scope = db

    def boom(ctx):
        raise RuntimeError("table missing")

    contract = health.Contract(
        "t", "t.yml", "w", (), (), (health.Check("t.boom", "degraded", "fact", boom),), ()
    )
    with scope() as s:
        verdict, results = health.evaluate(contract, _ctx(s, "t"))
    assert verdict == "degraded"
    assert results[0][1].detail == "check raised RuntimeError: table missing"


def test_the_note_names_the_run_the_trigger_the_slot_and_every_miss(db):
    eng, scope = db
    with Session(eng) as s:
        s.add(_card("thu_pm", items=[_item(1)]))  # 1 HR-priced item: under the floor
        s.add(_paper(1))
        s.commit()
    good = {"complete": True, "events_in_window": 80, "events_polled": 80, "credits_spent": 80}
    with scope() as s:
        ctx = _ctx(
            s,
            "card",
            slot="thu_pm",
            status_files={"sweep": good},
            outcomes={"sweep": "success", "preview": "success"},
        )
        verdict, results = health.evaluate(health.CONTRACTS["card"], ctx)
        note = health.verdict_note("card", ctx, results)
    assert verdict == "degraded"
    assert note.startswith(
        "run=1234 event=workflow_dispatch slot=thu_pm miss=card.hr_priced_floor("
    )
    assert " info=" in note and "bets=1" in note and "early_season_held=0" in note
    assert ";" not in note.split("miss=")[1].split(" info=")[0]  # one miss, no separator
    assert len(note) <= health.NOTE_MAX_CHARS


def test_the_note_is_capped_and_a_clean_run_has_no_miss(db):
    eng, scope = db
    with scope() as s:
        ctx = _ctx(s, "t", env={"GITHUB_RUN_ID": "9", "GITHUB_EVENT_NAME": "schedule"})
        checks = tuple(
            health.Check(f"t.c{i}", "degraded", "fact", lambda ctx: health.Result(False, "x" * 200))
            for i in range(6)
        )
        contract = health.Contract("t", "t.yml", "w", (), (), checks, ())
        _v, results = health.evaluate(contract, ctx)
        note = health.verdict_note("t", ctx, results)
        assert len(note) == health.NOTE_MAX_CHARS and note.endswith("...")
        clean = health.verdict_note("t", ctx, [(checks[0], health.Result(True, "fine"))])
        assert clean == "run=9 event=schedule"


def test_details_never_carry_the_note_separators(db):
    eng, scope = db
    contract = health.Contract(
        "t",
        "t.yml",
        "w",
        (),
        (),
        (health.Check("t.c", "degraded", "f", lambda ctx: health.Result(False, "a; b\nc")),),
        (),
    )
    with scope() as s:
        _v, results = health.evaluate(contract, _ctx(s, "t"))
    assert results[0][1].detail == "a, b c"


# --------------------------------------------------------------------------- #
# The contracts themselves
# --------------------------------------------------------------------------- #
def test_every_contract_is_a_gauge_job_and_every_check_id_is_prefixed_by_its_job():
    assert tuple(health.CONTRACTS) == ops.HEALTH_JOBS
    for job, c in health.CONTRACTS.items():
        assert c.job == job
        assert c.workflow.endswith(".yml")
        for ch in c.checks:
            assert ch.id.startswith(f"{job}."), ch.id
            assert ch.severity in health.SEVERITIES
    ids = health.all_check_ids()
    assert len(ids) == len(set(ids))


def test_every_failure_mode_names_a_check_that_exists():
    ids = set(health.all_check_ids())
    for c in health.CONTRACTS.values():
        for fm in c.failure_modes:
            assert set(fm.caught_by) <= ids, (c.job, fm.date, fm.caught_by)


def test_lines_watch_has_no_failed_severity_check_and_the_others_have_one():
    assert all(ch.severity == "degraded" for ch in health.CONTRACTS["lines_watch"].checks)
    for job in ("card", "grade", "sunday"):
        assert any(ch.severity == "failed" for ch in health.CONTRACTS[job].checks), job


def test_render_contracts_is_deterministic_and_names_every_check_and_parameter():
    a, b = health.render_contracts(), health.render_contracts()
    assert a == b
    assert a.startswith(health.CONTRACTS_BEGIN) and a.rstrip().endswith(health.CONTRACTS_END)
    for cid in health.all_check_ids():
        assert f"`{cid}`" in a, cid
    for name, value in health.PARAMETERS.items():
        assert f"`{name} = {value}`" in a, name
    # Each parameter is also named, with its default in brackets, in the check
    # that uses it -- so the doc reader sees the number beside the rule.
    for name, value in health.PARAMETERS.items():
        assert f"{name} [{value}]" in a, name
    for job in health.CONTRACTS:
        assert f"\n### {job}\n" in a


def test_render_into_replaces_only_the_block():
    before = "# Title\n\nprose\n\n<!-- contracts:begin -->\nold\n<!-- contracts:end -->\n\nafter\n"
    out = health.render_into(before)
    assert out.startswith("# Title\n\nprose\n\n<!-- contracts:begin -->\n")
    assert out.endswith("<!-- contracts:end -->\n\nafter\n")
    assert "old" not in out
    assert health.render_into(out) == out  # idempotent
    with pytest.raises(ValueError):
        health.render_into("no markers here")


def test_health_key_fits_app_settings_key():
    for job in ops.HEALTH_JOBS:
        assert ops.health_key(job) == f"last_health_{job}"
        assert len(ops.health_key(job)) <= 32
    assert not any(k.startswith(ops.HEALTH_PREFIX) for k in ops.GAUGE_KEYS)
