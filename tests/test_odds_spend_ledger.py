"""The credit ledger (beatvegas/sources/odds.py::_record_spend; final-2026 plan C11).

Every priced response the client gets back becomes one `odds_spend` row with
what was asked (endpoint, markets, regions or bookmakers), what the provider
billed (`x-requests-last`), the balance after, and the job / purpose context.
The ledger is written from inside the client so no script can spend unlogged;
a failed insert is a warning, never a failed pull. These tests fake
`requests.get` and point `session_scope` at an in-memory SQLite.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from conftest import _sqlite_scope
from sqlalchemy.orm import Session

from beatvegas.db.models import OddsSpend
from beatvegas.sources import odds as odds_mod
from beatvegas.sources.odds import OddsAPIClient, endpoint_of

ROOT = Path(__file__).resolve().parent.parent


class _Resp:
    def __init__(self, body, status=200, last="1", remaining="19000", used="1000"):
        self._body = body
        self.status_code = status
        self.headers = {
            "x-requests-remaining": remaining,
            "x-requests-used": used,
            "x-requests-last": last,
        }
        self.request = None

    def json(self):
        return self._body

    def raise_for_status(self):
        return None


@pytest.fixture
def ledger(monkeypatch):
    eng, scope = _sqlite_scope()
    import beatvegas.db.store as store
    import beatvegas.ops as ops

    monkeypatch.setattr(store, "session_scope", scope)
    monkeypatch.setattr(ops, "gauges_enabled", lambda: True)
    monkeypatch.setattr(ops, "record_gauge", lambda *a, **k: True)
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    monkeypatch.delenv("BV_ODDS_JOB", raising=False)
    monkeypatch.delenv("BV_ODDS_PURPOSE", raising=False)
    return eng


def _client(monkeypatch, resp, **kw):
    sent = {}

    def fake_get(url, params=None, timeout=None):
        sent["url"], sent["params"] = url, params
        return resp

    monkeypatch.setattr(odds_mod.requests, "get", fake_get)
    monkeypatch.setattr(odds_mod, "load_config", lambda: {"odds_api": {"bookmakers_1h": []}})
    c = OddsAPIClient(api_key="k", **kw)
    return c, sent


def test_endpoint_words():
    base = "https://api.the-odds-api.com/v4/sports/americanfootball_ncaaf"
    assert endpoint_of(f"{base}/events") == "events"
    assert endpoint_of(f"{base}/odds") == "odds"
    assert endpoint_of(f"{base}/events/abc123/odds") == "event_odds"
    assert (
        endpoint_of("https://api.the-odds-api.com/v4/historical/sports/x/events") == "hist_events"
    )
    assert endpoint_of("https://api.the-odds-api.com/v4/historical/sports/x/odds") == "hist_odds"
    assert (
        endpoint_of("https://api.the-odds-api.com/v4/historical/sports/x/events/e1/odds")
        == "hist_event_odds"
    )


def test_a_per_event_call_writes_one_row_with_the_billed_credits(ledger, monkeypatch):
    c, sent = _client(monkeypatch, _Resp({"id": "e1", "bookmakers": []}, last="1"), job="card")
    c.bookmakers = ["hardrockbet", "draftkings"]
    c.event_first_half_totals("e1")
    with Session(ledger) as s:
        rows = s.query(OddsSpend).all()
        assert len(rows) == 1
        r = rows[0]
        assert (r.job, r.endpoint, r.credits, r.remaining_after, r.used_after) == (
            "card",
            "event_odds",
            1,
            19000,
            1000,
        )
        assert r.markets == "totals_h1"
        assert r.bookmakers == "hardrockbet,draftkings"
        assert r.regions is None
        assert r.events == 1
        assert json.loads(r.params_json)["event_id"] == "e1"
        assert r.run_id == "-"
        assert "apiKey" not in (r.params_json or "")
    assert c.last_spend_id == rows[0].id


def test_a_bulk_call_records_regions_markets_and_event_count(ledger, monkeypatch):
    body = [{"id": "e1", "bookmakers": []}, {"id": "e2", "bookmakers": []}]
    c, _ = _client(monkeypatch, _Resp(body, last="9"))
    c.list_full_game_odds(regions="us,us2,us_ex")
    with Session(ledger) as s:
        r = s.query(OddsSpend).one()
        assert (r.endpoint, r.regions, r.markets, r.events, r.credits) == (
            "odds",
            "us,us2,us_ex",
            "totals,spreads,h2h",
            2,
            9,
        )


def test_the_free_events_list_is_recorded_at_zero(ledger, monkeypatch):
    c, _ = _client(monkeypatch, _Resp([{"id": "e1"}], last="0"))
    c.list_events()
    with Session(ledger) as s:
        r = s.query(OddsSpend).one()
        assert (r.endpoint, r.credits, r.events) == ("events", 0, 1)


def test_a_404_is_recorded_as_a_free_empty_answer(ledger, monkeypatch):
    c, _ = _client(monkeypatch, _Resp({}, status=404, last="0"))
    assert c.event_first_half_totals("gone") == {}
    with Session(ledger) as s:
        r = s.query(OddsSpend).one()
        assert (r.http_status, r.credits) == (404, 0)


def test_job_and_purpose_come_from_the_environment(ledger, monkeypatch):
    monkeypatch.setenv("BV_ODDS_JOB", "research")
    monkeypatch.setenv("BV_ODDS_PURPOSE", "sharp_eu")
    monkeypatch.setenv("GITHUB_RUN_ID", "4242")
    c, _ = _client(monkeypatch, _Resp([], last="1"))
    c.list_full_game_odds(regions="eu", markets="totals")
    with Session(ledger) as s:
        r = s.query(OddsSpend).one()
        assert (r.job, r.purpose, r.run_id) == ("research", "sharp_eu", "4242")


def test_a_historical_call_keeps_the_date(ledger, monkeypatch):
    c, _ = _client(monkeypatch, _Resp({"data": []}, last="10"))
    c.historical_bulk_totals("2026-10-10T19:00:00Z", regions="eu")
    with Session(ledger) as s:
        r = s.query(OddsSpend).one()
        assert (r.endpoint, r.credits, r.regions) == ("hist_odds", 10, "eu")
        assert json.loads(r.params_json)["date"] == "2026-10-10T19:00:00Z"


def test_no_database_means_no_ledger_and_no_error(monkeypatch):
    import beatvegas.ops as ops

    monkeypatch.setattr(ops, "gauges_enabled", lambda: False)
    monkeypatch.setattr(ops, "record_gauge", lambda *a, **k: True)
    c, _ = _client(monkeypatch, _Resp([], last="1"))
    c.list_events()
    assert c.last_spend_id is None


def test_a_failing_insert_warns_and_the_pull_survives(ledger, monkeypatch, capsys):
    import beatvegas.db.store as store

    def boom():
        raise RuntimeError("pooler down")

    monkeypatch.setattr(store, "session_scope", boom)
    c, _ = _client(monkeypatch, _Resp([{"id": "e1"}], last="0"))
    assert c.list_events() == [{"id": "e1"}]
    assert "spend ledger not written" in capsys.readouterr().out
    assert c.last_spend_id is None


def test_only_the_client_talks_to_the_provider():
    """Every credit must pass through the ledger: no other Python under
    beatvegas/ or scripts/ may name the provider's host. (The workflows' free
    `curl` pre-check is the one exception, outside Python.)"""
    host = re.compile(r"api\.the-odds-api\.com")
    # scripts/opening_watch.py is the stdlib-only temporary watch (ends
    # 2026-10-20, removed by final-2026 plan PR-08); its spend is capped in the
    # script and read from its artifacts, not the ledger. Drop this line with it.
    exempt = {"scripts/opening_watch.py"}
    offenders = []
    for folder in ("beatvegas", "scripts"):
        for p in (ROOT / folder).rglob("*.py"):
            if p.name == "odds.py" and p.parent.name == "sources":
                continue
            if str(p.relative_to(ROOT)) in exempt:
                continue
            if host.search(p.read_text(errors="ignore")):
                offenders.append(str(p.relative_to(ROOT)))
    assert offenders == [], offenders
