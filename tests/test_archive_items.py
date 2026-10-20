"""The archive items (beatvegas/archive.py; final-2026 plan PR-C10).

A fake archive answers like the feed: bulk historical totals at a time carry the
games still to kick off with a snapshot timestamp 2 minutes earlier; Hard Rock's
first-half total exists from a release time on (an earlier ask is empty and
free); its first-half team totals exist at kickoff - 30 min. The items must
write `research_snapshots` only (purpose, source historical, the snapshot's own
time), never `odds_snapshots`, skip what the ledger says was bought, stop at
their budget, and find the release time to the 5-minute grid.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from conftest import _load_script, _sqlite_scope
from sqlalchemy.orm import Session

from beatvegas import archive as A
from beatvegas.db.models import AppSetting, Game, OddsSnapshot, OddsSpend, ResearchSnapshot

SAT = datetime(2026, 9, 12, 16, 0)  # week 3, noon ET
GAMES = [
    (1, "Alabama", "Georgia", SAT),
    (2, "Texas", "Ohio State", SAT + timedelta(minutes=30)),
    (3, "Michigan", "Oregon", SAT + timedelta(hours=3, minutes=30)),
]
RELEASE = datetime(2026, 9, 7, 14, 35)  # Monday 10:35am ET


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


class FakeArchive:
    def __init__(self, release=RELEASE, tt1h=True):
        self.calls = []
        self.release = release
        self.tt1h = tt1h
        self.last_credits = None
        self.last_spend_id = None
        self.purpose = None

    def _bill(self, n):
        self.last_credits = SimpleNamespace(remaining=9000, used=11000, last_cost=n)
        self.last_spend_id = len(self.calls)

    def _event(self, gid, home, away, kick, books):
        return {
            "id": f"ev{gid}",
            "home_team": home,
            "away_team": away,
            "commence_time": iso(kick),
            "bookmakers": books,
        }

    def historical_bulk_totals(self, date_iso, regions=None, envelope=False):
        t = datetime.fromisoformat(date_iso[:-1])
        self.calls.append(("bulk", date_iso, regions))
        self._bill(10)
        book = {"eu": "pinnacle", "us": "draftkings", "us2": "hardrockbet"}[regions]
        data = [
            self._event(
                gid,
                h,
                a,
                k,
                [
                    {
                        "key": book,
                        "markets": [
                            {
                                "key": "totals",
                                "last_update": iso(t - timedelta(minutes=3)),
                                "outcomes": [
                                    {"name": "Over", "point": 50.5 + gid, "price": -110},
                                    {"name": "Under", "point": 50.5 + gid, "price": -110},
                                ],
                            }
                        ],
                    }
                ],
            )
            for gid, h, a, k in GAMES
            if k > t
        ]
        return {"timestamp": iso(t - timedelta(minutes=2)), "data": data}

    def list_historical_events(self, date_iso):
        self.calls.append(("events", date_iso))
        self._bill(1)
        return [
            {"id": f"ev{gid}", "home_team": h, "away_team": a, "commence_time": iso(k)}
            for gid, h, a, k in GAMES
        ]

    def historical_event_odds(self, event_id, date_iso, markets, bookmakers, envelope=False):
        t = datetime.fromisoformat(date_iso[:-1])
        self.calls.append(("event", event_id, date_iso, markets))
        gid = int(event_id[2:])
        _g, h, a, k = next(g for g in GAMES if g[0] == gid)
        if markets == "totals_h1":
            present = t >= self.release
            mk = {
                "key": "totals_h1",
                "outcomes": [
                    {"name": "Over", "point": 24.5, "price": -110},
                    {"name": "Under", "point": 24.5, "price": -110},
                ],
            }
        else:
            present = self.tt1h
            mk = {
                "key": "team_totals_h1",
                "outcomes": [
                    {"name": "Over", "description": h, "point": 13.5, "price": -115},
                    {"name": "Under", "description": h, "point": 13.5, "price": -105},
                    {"name": "Over", "description": a, "point": 10.5, "price": -110},
                    {"name": "Under", "description": a, "point": 10.5, "price": -110},
                    {"name": "Over", "description": a, "point": 12.5, "price": +150},
                    {"name": "Under", "description": a, "point": 12.5, "price": -190},
                ],
            }
        self._bill(10 if present else 0)
        books = [{"key": "hardrockbet", "markets": [mk]}] if present else []
        return {"timestamp": iso(t), "data": self._event(gid, h, a, k, books)}


@pytest.fixture
def db():
    eng, scope = _sqlite_scope()
    with Session(eng) as s:
        for gid, h, a, k in GAMES:
            s.add(
                Game(
                    id=gid,
                    season=2026,
                    week=3,
                    season_type="regular",
                    home_team=h,
                    away_team=a,
                    start_date=k,
                )
            )
            # Our first live capture of Hard Rock's line: Tuesday's card.
            s.add(
                OddsSnapshot(
                    game_id=gid,
                    book="hardrockbet",
                    market="1H_total",
                    line=24.5,
                    captured_at=datetime(2026, 9, 8, 20, 41, 17),
                )
            )
        s.add(
            Game(
                id=9,
                season=2026,
                week=3,
                season_type="regular",
                home_team="Alabama A&M",
                away_team="Tuskegee",
                start_date=SAT,
            )
        )
        s.commit()
    return eng, scope


def _rows(eng, purpose):
    with Session(eng) as s:
        return s.query(ResearchSnapshot).filter(ResearchSnapshot.purpose == purpose).all()


def test_close_waves_group_kickoffs_within_30_minutes():
    games = [{"id": g, "week": 3, "start_date": k} for g, _h, _a, k in GAMES]
    waves = A.close_waves(games)
    assert [(w, [g["id"] for g in m]) for w, m in waves] == [
        (SAT - timedelta(minutes=30), [1, 2]),
        (SAT + timedelta(hours=3), [3]),
    ]


def test_path_waves_run_every_4_hours_from_the_sunday_before():
    games = [{"id": g, "week": 3, "start_date": k} for g, _h, _a, k in GAMES]
    waves = A.path_waves(games)
    assert waves[0][0] == datetime(2026, 9, 6, 16, 0)  # the Sunday before, 16:00Z
    assert all((b[0] - a[0]) == timedelta(hours=4) for a, b in zip(waves, waves[1:]))
    assert waves[-1][0] == SAT and [g["id"] for g in waves[-1][1]] == [2, 3]


def test_the_release_search_finds_the_first_5_minute_snapshot():
    asked = []

    def probe(t):
        asked.append(t)
        return {"t": t} if t >= RELEASE else None

    hi = datetime(2026, 9, 8, 20, 40)
    t1, env, at_start = A.find_first_present(probe, hi - timedelta(hours=72), hi)
    assert t1 == RELEASE and not at_start and len(asked) <= 12
    # A good hint finds it in three asks (hi, lo, the hint, the step before it).
    asked.clear()
    t1, *_ = A.find_first_present(probe, hi - timedelta(hours=72), hi, hints=[RELEASE])
    assert t1 == RELEASE and len(asked) == 4
    # Present at the window's start: written there, marked "at or before".
    t1, _e, at_start = A.find_first_present(probe, RELEASE + timedelta(hours=1), hi)
    assert t1 == RELEASE + timedelta(hours=1) and at_start
    # The archive lacks it even at the end: nothing.
    assert A.find_first_present(lambda t: None, RELEASE, hi) is None


def test_team_total_rows_keep_each_teams_most_balanced_pair():
    fake = FakeArchive()
    env = fake.historical_event_odds("ev1", iso(SAT), "team_totals_h1", ["hardrockbet"])
    rows = A.team_total_rows(env["data"])
    by_team = {r["team"]: (r["line"], r["over_price"], r["under_price"]) for r in rows}
    assert by_team == {"Alabama": (13.5, -115, -105), "Georgia": (10.5, -110, -110)}
    assert all(r["market"] == "team_total_1h" and r["book"] == "hardrockbet" for r in rows)


def test_close_waves_write_research_rows_at_the_snapshot_time_and_skip_bought_waves(db):
    eng, scope = db
    with Session(eng) as s:  # the second wave was bought by an earlier run
        s.add(
            OddsSpend(
                spent_at=SAT,
                endpoint="hist_odds",
                credits=10,
                http_status=200,
                purpose="archive_pinnacle_2026",
                params_json=json.dumps({"date": iso(SAT + timedelta(hours=3))}),
            )
        )
        s.commit()
    fake = FakeArchive()
    spent = A.run_close_waves(
        fake,
        scope,
        season=2026,
        weeks=(3,),
        purpose="archive_pinnacle_2026",
        regions="eu",
        budget=A.Budget(100),
        log=lambda *_: None,
    )
    assert spent == 10 and [c[:2] for c in fake.calls] == [
        ("bulk", iso(SAT - timedelta(minutes=30)))
    ]
    rows = _rows(eng, "archive_pinnacle_2026")
    assert sorted(r.game_id for r in rows) == [1, 2], "only the wave's own games, FBS only"
    assert all(r.book == "pinnacle" and r.source == "historical" and r.region == "eu" for r in rows)
    assert all(r.captured_at == SAT - timedelta(minutes=32) for r in rows)
    with Session(eng) as s:
        assert s.query(OddsSnapshot).filter(OddsSnapshot.book == "pinnacle").count() == 0


def test_an_item_stops_at_its_budget(db):
    eng, scope = db
    fake = FakeArchive()
    with pytest.raises(A.BudgetExhausted):
        A.run_paths(
            fake,
            scope,
            season=2026,
            weeks=(3,),
            purpose="archive_fg_paths",
            regions="us",
            budget=A.Budget(25),
            log=lambda *_: None,
        )
    assert len(fake.calls) == 2, "two 10-credit waves fit in 25, the third is never asked"


def test_paths_write_on_change(db):
    eng, scope = db
    fake = FakeArchive()
    A.run_paths(
        fake,
        scope,
        season=2026,
        weeks=(3,),
        purpose="archive_fg_paths",
        regions="us",
        budget=A.Budget(10_000),
        log=lambda *_: None,
    )
    rows = _rows(eng, "archive_fg_paths")
    # The fake's line never moves: one row per game, its last sighting moved forward.
    assert sorted(r.game_id for r in rows) == [1, 2, 3]
    assert all(r.last_seen_at > r.captured_at for r in rows)


def test_the_release_item_writes_one_row_per_game_at_first_sighting(db):
    eng, scope = db
    fake = FakeArchive()
    A.run_hr_release(
        fake,
        scope,
        season=2026,
        weeks=(3,),
        purpose="archive_hr_release",
        budget=A.Budget(10_000),
        log=lambda *_: None,
    )
    rows = _rows(eng, "archive_hr_release")
    assert sorted(r.game_id for r in rows) == [1, 2, 3]
    assert {r.captured_at for r in rows} == {RELEASE}
    assert all(r.market == "1H_total" and r.line == 24.5 for r in rows)
    events = [c for c in fake.calls if c[0] == "events"]
    assert len(events) == 1, "one events list for the week"
    # The batch hint: the second and third games cost far fewer asks than the first.
    per_game = [
        sum(1 for c in fake.calls if c[0] == "event" and c[1] == f"ev{g}") for g in (1, 2, 3)
    ]
    assert per_game[1] <= 4 and per_game[2] <= 4 < per_game[0]


def test_the_team_total_item_skips_games_asked_before(db):
    eng, scope = db
    fake = FakeArchive(tt1h=False)
    A.run_hr_tt1h(
        fake,
        scope,
        season=2026,
        weeks=(3,),
        purpose="archive_hr_tt1h",
        budget=A.Budget(10_000),
        log=lambda *_: None,
    )
    assert _rows(eng, "archive_hr_tt1h") == []
    fake2 = FakeArchive(tt1h=True)
    A.run_hr_tt1h(
        fake2,
        scope,
        season=2026,
        weeks=(3,),
        purpose="archive_hr_tt1h",
        budget=A.Budget(10_000),
        log=lambda *_: None,
    )
    rows = _rows(eng, "archive_hr_tt1h")
    assert len(rows) == 6 and {r.team for r in rows} >= {"Alabama", "Georgia"}


@pytest.fixture
def mod(db, monkeypatch):
    eng, scope = db
    with Session(eng) as s:
        s.add(
            AppSetting(
                key="odds_credits_remaining", value="9000", updated_at=datetime(2026, 11, 2, 7, 0)
            )
        )
        s.add(
            AppSetting(
                key="odds_cycle_reset_at",
                value="2026-11-05T00:00:00",
                updated_at=datetime(2026, 10, 20),
            )
        )
        s.add(
            AppSetting(
                key="close_coverage_pct",
                value="1.000",
                updated_at=datetime(2026, 11, 1, 10, 0),
                note="sat=2026-10-31 games=50 covered=50",
            )
        )
        s.commit()
    m = _load_script("archive_buy")
    monkeypatch.setattr(m, "session_scope", scope)
    return m, eng


class _LiveFake(FakeArchive):
    def list_events(self):
        self.calls.append(("live_events",))
        self.last_credits = SimpleNamespace(remaining=3_000, used=17_000, last_cost=0)
        return []


def test_auto_reads_the_live_balance_and_spends_inside_the_allowance(mod, monkeypatch, tmp_path):
    m, eng = mod
    real_now = datetime(2026, 11, 2, 7, 5)
    monkeypatch.setattr(m, "datetime", SimpleNamespace(utcnow=lambda: real_now, now=datetime.now))
    ran = []

    def fake_item(name, cost):
        def run(client, scope, budget, log, purpose):
            ran.append((name, budget.cap))
            budget.check(cost, name)
            budget.spent += cost
            return cost

        return run

    q = [
        m.ArchiveItem("a", "archive_pinnacle_2026", 1500, fake_item("a", 1000)),
        m.ArchiveItem("parked", "archive_hr_ladder", 3900, None),
        m.ArchiveItem("b", "archive_fg_paths", 3000, fake_item("b", 2000)),
    ]
    monkeypatch.setattr(m, "ARCHIVE_QUEUE", q)
    status = tmp_path / "s.json"
    fake = _LiveFake()
    assert m.cmd_auto(SimpleNamespace(dry_run=False, status_file=str(status)), client=fake) == 0
    st = json.loads(status.read_text())
    # Live 3,000 (not the gauge's 9,000) - floor 1,500 - ~3 days of recurring need.
    assert st["live_balance"] == 3000 and st["allowance"] < 1500
    assert ran[0] == ("a", min(1500, st["allowance"]))
    assert [i["state"] for i in st["items"]][1] == "parked"
    assert st["spent"] <= st["allowance"]


def test_estimates_count_what_is_left_to_buy(db):
    eng, _ = db
    with Session(eng) as s:
        assert A.estimate(s, "close", season=2026, weeks=(3,), purpose="archive_pinnacle_2026") == {
            "units": 2,
            "credits": 20,
        }
        assert A.estimate(s, "release", season=2026, weeks=(3,), purpose="archive_hr_release") == {
            "units": 3,
            "credits": 3 * A.RELEASE_EST_PER_GAME + 1,
        }
        assert A.estimate(s, "tt1h", season=2026, weeks=(3,), purpose="archive_hr_tt1h") == {
            "units": 3,
            "credits": 31,
        }
