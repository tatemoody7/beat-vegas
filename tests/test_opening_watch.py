"""scripts/opening_watch.py and its workflow (temporary research, 2026-10-15): pure logic only,
no network. The watch must never touch the database, must ask each market only of books that
have not posted it (so credits are spent only at an opening), and must keep the verified window."""

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "opening_watch", ROOT / "scripts" / "opening_watch.py"
)
W = importlib.util.module_from_spec(spec)
spec.loader.exec_module(W)
WF = ROOT / ".github" / "workflows" / "opening_watch.yml"


def test_the_script_never_touches_the_database_or_the_engine():
    src = (ROOT / "scripts" / "opening_watch.py").read_text()
    for banned in ("beatvegas", "DATABASE_URL", "sqlalchemy", "psycopg", "neon"):
        assert banned not in src.replace("never imports `beatvegas`", ""), banned


def test_book_groups_never_exceed_one_region():
    assert W.MAX_BOOKS_PER_CALL == 10
    gs = W.groups(W.BOOKS)
    assert all(len(g) <= 10 for g in gs) and sum(len(g) for g in gs) == len(W.BOOKS)
    assert "hardrockbet" in W.BOOKS and "pinnacle" in W.BOOKS and "kalshi" in W.BOOKS


def test_detection_asks_each_market_only_of_books_that_have_not_posted_it():
    st = W.new_state()
    full = W.plan_detection(st, ["e1"])
    assert {m for _, m, _ in full} == set(W.MARKETS)
    assert all(len(b) <= 10 for _, _, b in full)
    st["seen"] = {"e1": {"totals_h1": {b: "t" for b in W.BOOKS if b != "hardrockbet"}}}
    h1 = [b for _, m, b in W.plan_detection(st, ["e1"]) if m == "totals_h1"]
    assert h1 == [["hardrockbet"]]  # the only book still waiting
    st["seen"]["e1"]["totals_h1"]["hardrockbet"] = "t"
    assert not [1 for _, m, _ in W.plan_detection(st, ["e1"]) if m == "totals_h1"]


def _rows(books):
    return [{"book": b, "market": "totals_h1", "name": "Under", "point": 27.5, "price": -110,
             "description": None, "last_update": "2026-10-19T13:02:11Z"} for b in books]  # fmt: skip


def test_a_first_sighting_carries_its_verified_window():
    st = W.new_state()
    # First ask: DraftKings is already up -> no earlier miss exists.
    h = W.record_hits(
        st, "e1", "totals_h1", ["hardrockbet", "draftkings"], _rows(["draftkings"]), "T1"
    )
    assert [x["book"] for x in h] == ["draftkings"] and h[0][
        "window_from"
    ] == "already-open-at-first-ask"
    # Second ask: nothing new.
    assert W.record_hits(st, "e1", "totals_h1", ["hardrockbet"], [], "T2") == []
    # Third ask: Hard Rock appears; its window opens at T2, the last miss.
    h = W.record_hits(st, "e1", "totals_h1", ["hardrockbet"], _rows(["hardrockbet"]), "T3")
    assert (
        h[0]["book"] == "hardrockbet"
        and h[0]["window_from"] == "T2"
        and h[0]["captured_at"] == "T3"
    )
    assert h[0]["rows"][0]["last_update"] == "2026-10-19T13:02:11Z"
    # A book outside the request is never recorded from someone else's answer.
    assert W.record_hits(st, "e1", "totals_h1", ["fanduel"], _rows(["betmgm"]), "T4") == []


def test_team_totals_keep_the_team_name():
    ev = {"bookmakers": [{"key": "hardrockbet", "markets": [{"key": "team_totals", "last_update": "x",
          "outcomes": [{"name": "Over", "description": "Iowa", "point": 20.5, "price": -110}]}]}]}  # fmt: skip
    r = W.market_rows(ev, "team_totals")[0]
    assert r["description"] == "Iowa" and r["point"] == 20.5 and r["book"] == "hardrockbet"


def test_the_window_targets_and_budget():
    assert W.in_window(datetime(2026, 10, 19, 13, 0, tzinfo=timezone.utc))
    assert not W.in_window(datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc))
    assert not W.in_window(datetime(2026, 10, 21, 0, 0, tzinfo=timezone.utc))
    assert W.is_target("2026-10-24T19:30:00Z") and W.is_target("2026-10-20T23:00:00Z")
    assert not W.is_target("2026-10-17T19:30:00Z")  # this weekend's games are not "next week"
    assert W.BUDGET == 5500 and W.budget_left({"spent": 5500}) == 0


def test_the_workflow_is_read_only_and_isolated():
    data = yaml.safe_load(WF.read_text())
    text = yaml.safe_dump(data)  # the parsed workflow, not its explanatory comments
    assert "DATABASE_URL" not in text and "setup-python" not in text and "pip install" not in text
    assert data["concurrency"]["group"] == "opening-watch"
    on = data.get("on") or data.get(True)
    crons = [c["cron"] for c in on["schedule"]]
    assert crons == ["*/20 * * * *", "10,30,50 10-16 * * 1"]
    job = data["jobs"]["tick"]
    assert job["env"]["ODDS_API_KEY"] == "${{ secrets.ODDS_API_KEY }}"
    for step in job["steps"]:
        assert "${{" not in str(step.get("run", "")), step.get("name")
