"""H-MKT-PROBE's pure pieces (the ET slate, reading any market's quotes, the
per-market summary) and its run discipline against a fake client: the dry run
spends nothing, the credit cap stops before a call that could pass it, and a 422
on the combined call is retried one market at a time with the key dropped."""

from __future__ import annotations

from datetime import date

import pytest

from beatvegas.sources.odds import Credits


def _event(eid, books, commence="2026-10-10T16:00:00Z", home="LSU", away="Clemson"):
    return {
        "id": eid,
        "commence_time": commence,
        "home_team": home,
        "away_team": away,
        "bookmakers": [
            {"key": k, "last_update": "2026-10-10T12:00:00Z", "markets": mkts} for k, mkts in books
        ],
    }


def _tt(team, pt, over=-115, under=-105):
    return {
        "key": "team_totals",
        "outcomes": [
            {"name": "Over", "description": team, "point": pt, "price": over},
            {"name": "Under", "description": team, "point": pt, "price": under},
        ],
    }


def test_coming_saturday(load_script):
    P = load_script("market_probe")
    assert P.coming_saturday(date(2026, 10, 7)) == date(2026, 10, 10)  # Wednesday
    assert P.coming_saturday(date(2026, 10, 10)) == date(2026, 10, 10)  # Saturday itself
    assert P.coming_saturday(date(2026, 10, 11)) == date(2026, 10, 17)  # Sunday


def test_slate_is_the_et_date_in_kickoff_order(load_script):
    P = load_script("market_probe")
    evs = [
        _event("late", [], commence="2026-10-11T03:30:00Z"),  # Sat 23:30 ET
        _event("noon", [], commence="2026-10-10T16:00:00Z", home="Auburn"),  # Sat 12:00 ET
        _event("noon2", [], commence="2026-10-10T16:00:00Z", home="Alabama"),
        _event("fri", [], commence="2026-10-10T00:00:00Z"),  # Fri 20:00 ET
        _event("none", [], commence=None),
    ]
    slate = P.slate_for_date(evs, date(2026, 10, 10))
    assert [e["id"] for e in slate] == ["noon2", "noon", "late"]
    assert slate[-1]["kickoff_et"].strftime("%H:%M") == "23:30"


def test_market_quotes_reads_one_market_and_folds_the_hard_rock_key(load_script):
    P = load_script("market_probe")
    ev = _event(
        "e1",
        [
            ("hardrockbet_fl", [_tt("LSU", 30.5), {"key": "h2h_h1", "outcomes": []}]),
            ("draftkings", [{"key": "spreads_h1", "outcomes": []}]),
        ],
    )
    q = P.market_quotes(ev, "team_totals")
    assert len(q) == 1 and q[0]["book"] == "hardrockbet"
    assert q[0]["outcomes"][0] == {
        "name": "Over",
        "description": "LSU",
        "point": 30.5,
        "price": -115,
    }
    assert [r["book"] for r in P.market_quotes(ev, "spreads_h1")] == ["draftkings"]
    assert P.market_quotes(ev, "alternate_team_totals") == []


def test_summarize_counts_events_books_and_hard_rock(load_script):
    P = load_script("market_probe")
    r1 = _event("e1", [("hardrockbet", [_tt("LSU", 30.5)]), ("fanduel", [_tt("LSU", 31.5)])])
    r2 = _event("e2", [("fanduel", [_tt("Ohio State", 28.5)])], home="Ohio State")
    r3 = _event("e3", [])
    s = P.summarize([r1, r2, r3], ["team_totals", "h2h_h1"])
    tt = s["markets"]["team_totals"]
    assert s["events"] == 3
    assert (tt["events_posted"], tt["hr_posted"]) == (2, 1)
    assert tt["books"] == {"fanduel": 2, "hardrockbet": 1}
    assert [e["n_books"] for e in tt["per_event"]] == [2, 1, 0]
    assert s["markets"]["h2h_h1"]["events_posted"] == 0


class _Resp:
    def __init__(self, status, payload=None, text=""):
        self.status_code, self._payload, self.text = status, payload, text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError(f"unexpected {self.status_code}")


class _Client:
    """Bills (markets x regions) per accepted call; rejects `bad_market` with 422."""

    def __init__(self, events, bad_market=None):
        self.base_url, self.sport, self.api_key, self.odds_format = "u", "s", "k", "american"
        self.events, self.bad = events, bad_market
        self.used = 100
        self.calls = []
        self.last_credits = None

    def list_events(self):
        self.last_credits = Credits(remaining=19900, used=self.used, last_cost=0)
        return [{k: v for k, v in e.items() if k != "bookmakers"} for e in self.events]

    def _get(self, url, params):
        self.calls.append(dict(params))
        mk = params["markets"].split(",")
        if self.bad and self.bad in mk:
            self.last_credits = Credits(remaining=19900, used=self.used, last_cost=0)
            return _Resp(422, text="INVALID_MARKET")
        self.used += len(mk) * len(params["regions"].split(","))
        self.last_credits = Credits(remaining=20000 - self.used, used=self.used, last_cost=0)
        eid = url.split("/events/")[1].split("/")[0]
        ev = next(e for e in self.events if e["id"] == eid)
        return _Resp(200, ev)


def _run(load_script, monkeypatch, tmp_path, client, argv):
    P = load_script("market_probe")
    monkeypatch.setattr(P, "OddsAPIClient", lambda: client)
    rc = P.main(argv + ["--out", str(tmp_path / "market_probe")])
    return P, rc


def test_dry_run_spends_nothing_and_lists_the_slate(load_script, monkeypatch, tmp_path):
    client = _Client([_event("e1", []), _event("e2", [], commence="2026-10-11T19:00:00Z")])
    _, rc = _run(load_script, monkeypatch, tmp_path, client, ["--slate-date", "2026-10-10"])
    assert rc == 0 and client.calls == []
    md = next(tmp_path.glob("market_probe_*.md")).read_text()
    assert "`e1`" in md and "`e2`" not in md


def test_live_run_stops_before_the_cap(load_script, monkeypatch, tmp_path):
    evs = [_event(f"e{i}", [("hardrockbet", [_tt("LSU", 30.5)])]) for i in range(1, 7)]
    client = _Client(evs)
    _run(
        load_script,
        monkeypatch,
        tmp_path,
        client,
        ["--live", "--event-ids", "e1,e2,e3,e4,e5,e6", "--max-credits", "50"],
    )
    # 5 markets x 2 regions = 10 a call: five calls reach 50, the sixth is never made
    assert len(client.calls) == 5 and client.used - 100 == 50
    assert all(c["regions"] == "us,us2" and "bookmakers" not in c for c in client.calls)
    md = next(tmp_path.glob("market_probe_*.md")).read_text()
    assert "| `team_totals` | 5 | 5 |" in md


def test_a_rejected_market_key_is_found_and_dropped(load_script, monkeypatch, tmp_path):
    evs = [_event(f"e{i}", [("fanduel", [_tt("LSU", 30.5)])]) for i in (1, 2)]
    client = _Client(evs, bad_market="team_totals_h1")
    P, _ = _run(load_script, monkeypatch, tmp_path, client, ["--live", "--event-ids", "e1,e2"])
    markets_sent = [c["markets"] for c in client.calls]
    # e1: the combined call (422), then one call per market; e2: one call without the bad key
    assert markets_sent[0].count(",") == 4
    assert markets_sent[1:6] == list(P.PROBE_MARKETS)
    assert "team_totals_h1" not in markets_sent[-1] and markets_sent[-1].count(",") == 3
    md = next(tmp_path.glob("market_probe_*.md")).read_text()
    assert "rejected (422): team_totals_h1" in md
    assert "| `team_totals` | 2 | 0 | fanduel (2) |" in md


def test_live_without_ids_refuses(load_script, monkeypatch, tmp_path):
    client = _Client([_event("e1", [])])
    _, rc = _run(load_script, monkeypatch, tmp_path, client, ["--live"])
    assert rc == 2 and client.calls == []


@pytest.mark.parametrize("market", ["team_totals", "spreads_h1"])
def test_probe_markets_are_the_registered_five(load_script, market):
    P = load_script("market_probe")
    assert P.PROBE_MARKETS == (
        "team_totals",
        "team_totals_h1",
        "spreads_h1",
        "h2h_h1",
        "alternate_team_totals",
    )
    assert market in P.PROBE_MARKETS and P.PROBE_REGIONS == "us,us2"
