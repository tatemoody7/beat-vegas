"""The archive queue framework and its probe (scripts/archive_buy.py; final-2026 plan PR-C6).

The queue is Tate's order (C-D9, C-D17) with his caps; `spent` is read from the
credit ledger so a rerun never pays twice; the probe spends nothing past its cap
or the controller's allowance, finds the event in the archive's event list, asks
Hard Rock's ladder and team totals as of kickoff - 30 min, and writes a report.
"""

from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from conftest import _load_script, _sqlite_scope
from sqlalchemy.orm import Session

from beatvegas.db.models import AppSetting, Game, OddsSnapshot, OddsSpend

KICK = datetime(2026, 10, 3, 16, 0)
GAME = 401858250


class _FakeClient:
    """Answers like the feed; bills like the feed (10 per market returned, 1 for
    the events list, 3 for a live four-book call)."""

    def __init__(self, archive_markets=("alternate_totals_h1", "team_totals"), live_markets=()):
        self.calls = []
        self.last_credits = None
        self.archive_markets = archive_markets
        self.live_markets = live_markets

    def _bill(self, n):
        self.last_credits = SimpleNamespace(remaining=11000 - n, used=9000 + n, last_cost=n)

    def list_historical_events(self, date_iso):
        self.calls.append(("hist_events", date_iso))
        self._bill(1)
        return [
            {
                "id": "ev-nd-unc",
                "home_team": "North Carolina",
                "away_team": "Notre Dame",
                "commence_time": "2026-10-03T16:00:00Z",
            },
            {
                "id": "ev-other",
                "home_team": "Iowa State",
                "away_team": "West Virginia",
                "commence_time": "2026-10-03T16:00:00Z",
            },
        ]

    def _payload(self, markets, books):
        return {
            "id": "x",
            "bookmakers": [
                {
                    "key": b,
                    "markets": [
                        {
                            "key": m,
                            "outcomes": [
                                {"name": "Over", "point": 26.5 + i, "price": -150 + 20 * i}
                                for i in range(3)
                            ],
                        }
                        for m in markets
                    ],
                }
                for b in books
            ],
        }

    def historical_event_odds(self, event_id, date_iso, markets, bookmakers):
        self.calls.append(("hist_event_odds", event_id, date_iso, markets, tuple(bookmakers)))
        self._bill(10 * len(self.archive_markets))
        return self._payload(self.archive_markets, bookmakers) if self.archive_markets else {}

    def event_odds_raw(self, event_id, markets, bookmakers):
        self.calls.append(("live_event_odds", event_id, markets, tuple(bookmakers)))
        self._bill(len(self.live_markets))
        return self._payload(self.live_markets, bookmakers[:2]) if self.live_markets else {}


@pytest.fixture
def mod(monkeypatch):
    eng, scope = _sqlite_scope()
    with Session(eng) as s:
        s.add(
            Game(
                id=GAME,
                season=2026,
                week=5,
                home_team="North Carolina",
                away_team="Notre Dame",
                start_date=KICK,
            )
        )
        s.add(
            AppSetting(
                key="odds_credits_remaining",
                value="11000",
                updated_at=datetime(2026, 10, 18, 20, 0),
            )
        )
        s.add(
            AppSetting(
                key="odds_cycle_reset_at",
                value="2026-11-05T00:00:00",
                updated_at=datetime(2026, 10, 18),
            )
        )
        s.commit()
    m = _load_script("archive_buy")
    monkeypatch.setattr(m, "session_scope", scope)
    monkeypatch.setattr(m, "try_init_db", lambda: True)
    return m, eng


def test_the_queue_is_tates_order_with_his_caps(mod):
    m, _ = mod
    names = [it.name for it in m.ARCHIVE_QUEUE]
    assert names == [
        "pinnacle_2026_closes",
        "hr_ladder_close_2026",
        "fg_paths_2026",
        "hr_release_2026",
        "hr_team_totals_h1_2026",
        "pinnacle_2025_closes",
        "hr_ladder_close_2025",
        "fg_paths_2026_us2",
        "pinnacle_2024_closes",
    ]
    assert [it.cap for it in m.ARCHIVE_QUEUE] == [
        1500, 3900, 3000, 6000, 3300, 2100, 4500, 2500, 2600
    ]
    assert all(it.purpose.startswith("archive_") for it in m.ARCHIVE_QUEUE)
    parked = [it.name for it in m.ARCHIVE_QUEUE if it.run is None]
    assert parked == ["hr_ladder_close_2026", "hr_ladder_close_2025"], "C-D20"
    from beatvegas.research_capture import PURPOSES

    assert all(it.purpose in PURPOSES for it in m.ARCHIVE_QUEUE)


def test_spent_reads_the_ledger_by_purpose(mod):
    m, eng = mod
    with Session(eng) as s:
        s.add(
            OddsSpend(
                spent_at=KICK, endpoint="hist_odds", credits=10, purpose="archive_pinnacle_2026"
            )
        )
        s.add(
            OddsSpend(
                spent_at=KICK, endpoint="hist_odds", credits=20, purpose="archive_pinnacle_2026"
            )
        )
        s.add(
            OddsSpend(spent_at=KICK, endpoint="hist_odds", credits=7, purpose="archive_hr_ladder")
        )
        s.commit()
        assert m.spent(s, "archive_pinnacle_2026") == 30
        assert m.spent(s, "archive_hr_ladder") == 7
        assert m.spent(s, "archive_fg_paths") == 0


def test_the_probe_finds_the_event_asks_the_three_markets_and_reports(mod, tmp_path):
    m, _ = mod
    fake = _FakeClient()
    args = SimpleNamespace(
        game_id=GAME, live=False, live_event_id=None, max_credits=40, out=str(tmp_path)
    )
    assert m.cmd_probe(args, client=fake) == 0
    kinds = [c[0] for c in fake.calls]
    assert kinds == ["hist_events", "hist_event_odds"]
    _, ev, date_iso, markets, books = fake.calls[1]
    assert ev == "ev-nd-unc" and date_iso == "2026-10-03T15:30:00Z"
    assert markets == m.PROBE_MARKETS and books == ("hardrockbet",)
    report = json.loads(next(tmp_path.glob("archive_probe_*.json")).read_text())
    assert report["historical"]["event_id"] == "ev-nd-unc"
    assert sorted(report["historical"]["markets"]) == ["alternate_totals_h1", "team_totals"]
    assert report["historical"]["markets"]["alternate_totals_h1"]["outcomes"]["hardrockbet"] == 3
    assert report["credits"] == {"hist_events": 1, "hist_event_odds": 20, "total": 21}


def test_the_probe_refuses_to_pass_its_cap(mod, tmp_path):
    m, _ = mod
    fake = _FakeClient()
    args = SimpleNamespace(
        game_id=GAME, live=False, live_event_id=None, max_credits=20, out=str(tmp_path)
    )
    with pytest.raises(SystemExit) as e:
        m.cmd_probe(args, client=fake)
    assert "cap 20" in str(e.value)
    assert [c[0] for c in fake.calls] == ["hist_events"], (
        "the events list was paid, the odds call was not"
    )


def test_the_probe_refuses_past_the_controllers_allowance(mod, tmp_path, monkeypatch):
    m, _ = mod
    monkeypatch.setattr(
        m,
        "allowance_now",
        lambda s, now: {
            "allowance": 5,
            "balance": 1600,
            "floor": 1500,
            "reset_at": None,
            "recurring_per_week": 0,
            "recurring_source": "x",
            "window_open": False,
        },
    )
    fake = _FakeClient()
    args = SimpleNamespace(
        game_id=GAME, live=False, live_event_id=None, max_credits=40, out=str(tmp_path)
    )
    with pytest.raises(SystemExit) as e:
        m.cmd_probe(args, client=fake)
    assert "allowance" in str(e.value)
    assert fake.calls == [("hist_events", "2026-10-03T15:30:00Z")] or fake.calls == []


def test_an_empty_archive_answer_is_free_and_reported(mod, tmp_path):
    m, _ = mod
    fake = _FakeClient(archive_markets=())
    args = SimpleNamespace(
        game_id=GAME, live=False, live_event_id=None, max_credits=40, out=str(tmp_path)
    )
    assert m.cmd_probe(args, client=fake) == 0
    report = json.loads(next(tmp_path.glob("archive_probe_*.json")).read_text())
    assert report["historical"]["finding"] == "nothing returned"
    assert report["credits"]["hist_event_odds"] == 0


def test_the_live_half_uses_the_next_hard_rock_event(mod, tmp_path):
    m, eng = mod
    with Session(eng) as s:
        s.add(
            Game(
                id=7,
                season=2026,
                week=8,
                home_team="A",
                away_team="B",
                start_date=datetime(2099, 1, 1),
            )
        )
        s.add(
            OddsSnapshot(
                game_id=7,
                book="hardrockbet",
                market="full_game_total",
                line=50.5,
                event_id="ev-next",
                captured_at=datetime(2026, 10, 18),
            )
        )
        s.commit()
    fake = _FakeClient(live_markets=("team_totals",))
    args = SimpleNamespace(
        game_id=GAME, live=True, live_event_id=None, max_credits=40, out=str(tmp_path)
    )
    assert m.cmd_probe(args, client=fake) == 0
    live = [c for c in fake.calls if c[0] == "live_event_odds"]
    assert live == [("live_event_odds", "ev-next", m.PROBE_MARKETS, tuple(m.PROBE_LIVE_BOOKS))]
    report = json.loads(next(tmp_path.glob("archive_probe_*.json")).read_text())
    assert report["live"]["markets"]["team_totals"]["books"] == ["hardrockbet", "draftkings"]


def test_auto_runs_nothing_without_a_reset_date_or_outside_the_window(mod, capsys):
    m, eng = mod
    with Session(eng) as s:
        s.query(AppSetting).filter(AppSetting.key == "odds_cycle_reset_at").delete()
        s.commit()
    assert m.cmd_auto(SimpleNamespace(dry_run=False)) == 0
    assert "reset date unset" in capsys.readouterr().out
    with Session(eng) as s:
        s.add(
            AppSetting(
                key="odds_cycle_reset_at",
                value="2099-01-01T00:00:00",
                updated_at=datetime(2026, 10, 18),
            )
        )
        s.commit()
    assert m.cmd_auto(SimpleNamespace(dry_run=False)) == 0
    assert "window closed" in capsys.readouterr().out


def test_status_lists_the_queue(mod, capsys):
    m, _ = mod
    assert m.cmd_status(SimpleNamespace()) == 0
    out = capsys.readouterr().out
    assert "pinnacle_2026_closes" in out and "parked (C-D20)" in out
    assert "| 9 | pinnacle_2024_closes" in out


def test_the_default_probe_game_is_a_week_five_hard_rock_game(mod):
    m, _ = mod
    assert m.DEFAULT_PROBE_GAME == GAME and m.PROBE_LEAD_MIN == 30
    assert "alternate_totals_h1" in m.PROBE_MARKETS and "team_totals_h1" in m.PROBE_MARKETS
