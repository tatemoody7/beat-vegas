"""The research shortlist (H-1H-SHORTLIST, website plan PR D): the pricing safeguards Tate approved
(adjustment 3), the frozen insert-only publication (adjustment 2) and its health check."""

import json
from datetime import datetime, timedelta

import pytest
from conftest import _sqlite_scope
from sqlalchemy.orm import Session

from beatvegas import pricing as PR
from beatvegas import shortlist as S

T0 = datetime(2026, 10, 15, 20, 15, 0)
NOW = datetime(2026, 10, 15, 20, 20, 0)
KICK = "2026-10-17T19:30:00Z"
MT = PR.MassTable.load()


def snap(book, line=24.5, over=-110, under=-110, at=T0, seen=None, gid=1):
    return PR.Snap(
        game_id=gid,
        book=book,
        market="1H_total",
        line=line,
        over_price=over,
        under_price=under,
        home_price=None,
        away_price=None,
        captured_at=at,
        last_seen_at=seen,
    )


def item(gid=1, line=24.5, price=-110, over=-110, centred=True, kick=KICK, as_of=T0):
    return {
        "game_id": gid,
        "away": "Away",
        "home": "Home",
        "kick": kick,
        "hr_centred": centred,
        "hr_line": line,
        "hr_price": price,
        "hr_over_price": over,
        "hr_as_of": as_of.isoformat() if as_of else None,
    }


THREE_BOOKS = [
    snap("draftkings", under=-115, over=-105),
    snap("fanduel", under=-112, over=-108),
    snap("betmgm", under=-118, over=-102),
]


# --- the pool ---------------------------------------------------------------------------------
def test_the_pool_takes_only_hard_rocks_main_line_with_a_price_before_kickoff():
    items = [
        item(1),
        item(2, centred=False),  # an alternate rung never enters
        item(3, price=None),  # a missing price is never filled in
        item(4, line=None),
        item(5, kick="2026-10-15T19:00:00Z"),  # already kicked off
    ]
    assert [it["game_id"] for it in S.pool(items, NOW)] == [1]


# --- the price safeguards ---------------------------------------------------------------------
def test_three_same_sweep_books_price_the_game():
    sn = [snap("hardrockbet")] + THREE_BOOKS
    pr = S.price_read(item(), sn, MT, NOW)
    assert pr["status"] == "priced"
    assert pr["ref_books"] == ["betmgm", "draftkings", "fanduel"]
    assert (
        pr["range_low"] <= pr["ev_point"] <= pr["range_high"] or pr["range_low"] <= pr["ev_point"]
    )
    assert S.label(pr) in (S.LABEL_POTENTIAL, S.LABEL_FAIR, S.LABEL_EXPENSIVE)


def test_fewer_than_three_books_is_insufficient_pricing():
    sn = [snap("hardrockbet")] + THREE_BOOKS[:2]
    pr = S.price_read(item(), sn, MT, NOW)
    assert pr["status"].startswith("insufficient pricing data (2 reference books")
    assert S.label(pr) == S.LABEL_INSUFFICIENT
    assert "ev_point" not in pr


def test_fliff_and_the_feed_consensus_never_count_as_reference_books():
    sn = [snap("hardrockbet"), snap("fliff"), snap("consensus")] + THREE_BOOKS[:2]
    pr = S.price_read(item(), sn, MT, NOW)
    assert "fliff" not in pr["ref_books"] and "consensus" not in pr["ref_books"]
    assert S.label(pr) == S.LABEL_INSUFFICIENT


def test_a_book_from_another_sweep_does_not_count():
    old = T0 - timedelta(hours=3)
    sn = [snap("hardrockbet")] + THREE_BOOKS[:2] + [snap("caesars", at=old)]
    pr = S.price_read(item(), sn, MT, NOW)
    assert "caesars" not in pr["ref_books"]
    assert S.label(pr) == S.LABEL_INSUFFICIENT


def test_a_book_more_than_one_and_a_half_points_away_does_not_count():
    sn = [snap("hardrockbet")] + THREE_BOOKS[:2] + [snap("caesars", line=26.5)]
    pr = S.price_read(item(), sn, MT, NOW)
    assert "caesars" not in pr["ref_books"]


def test_a_hard_rock_price_older_than_six_hours_is_not_priced():
    old = NOW - timedelta(hours=7)
    sn = [snap("hardrockbet", at=old)] + [
        snap(b.book, under=b.under_price, over=b.over_price, at=old) for b in THREE_BOOKS
    ]
    pr = S.price_read(item(as_of=old), sn, MT, NOW)
    assert pr["status"] == "insufficient pricing data (Hard Rock price 7 h old)"
    assert S.label(pr) == S.LABEL_INSUFFICIENT


def test_freshness_is_the_last_confirmation_not_the_first_capture():
    old = NOW - timedelta(hours=7)
    seen = NOW - timedelta(minutes=10)
    sn = [snap("hardrockbet", at=old, seen=seen)] + [
        snap(b.book, under=b.under_price, over=b.over_price, at=old, seen=seen) for b in THREE_BOOKS
    ]
    pr = S.price_read(item(as_of=old), sn, MT, NOW)
    assert pr["status"] == "priced"
    assert pr["hr_age_h"] == pytest.approx(10 / 60)


def test_a_card_price_with_no_matching_hard_rock_snapshot_is_not_priced():
    sn = [snap("hardrockbet", under=-120)] + THREE_BOOKS
    pr = S.price_read(item(price=-110), sn, MT, NOW)
    assert pr["status"] == "no matching Hard Rock snapshot"
    assert S.label(pr) == S.LABEL_INSUFFICIENT


def test_a_missing_over_price_leaves_the_hold_missing_never_minus_110():
    pr = S.price_read(item(over=None), [snap("hardrockbet")] + THREE_BOOKS, MT, NOW)
    assert pr["hr_over"] is None and pr["hr_hold"] is None


@pytest.mark.parametrize(
    "pr,want",
    [
        (
            {"status": "priced", "ev_point": 0.012, "range_low": 0.001, "range_high": 0.03},
            S.LABEL_POTENTIAL,
        ),
        (
            {"status": "priced", "ev_point": 0.009, "range_low": 0.001, "range_high": 0.03},
            S.LABEL_FAIR,
        ),
        (
            {"status": "priced", "ev_point": 0.02, "range_low": 0.0, "range_high": 0.04},
            S.LABEL_FAIR,
        ),
        (
            {"status": "priced", "ev_point": -0.03, "range_low": -0.05, "range_high": -0.001},
            S.LABEL_EXPENSIVE,
        ),
        (
            {"status": "insufficient pricing data (2 reference books in the same sweep)"},
            S.LABEL_INSUFFICIENT,
        ),
    ],
)
def test_labels_need_the_whole_rough_range(pr, want):
    assert S.label(pr) == want


def test_an_informational_candidate_ranks_below_every_priced_game():
    priced = {
        "price": {"status": "priced", "range_low": -0.08, "ev_point": -0.05, "ref_books": ["a"] * 3}
    }
    info = {
        "price": {"status": "insufficient pricing data (Hard Rock price 9 h old)", "ev_point": 0.2}
    }
    assert sorted([info, priced], key=S.rank_key) == [priced, info]


def test_why_rank_says_an_informational_candidate_ranks_below():
    top = [
        {
            "price": {
                "status": "priced",
                "ev_point": 0.01,
                "range_low": -0.01,
                "range_high": 0.03,
                "ref_books": ["a", "b", "c"],
            }
        },
        {"price": {"status": "insufficient pricing data (2 reference books in the same sweep)"}},
    ]
    S.why_rank(top)
    assert [e["rank"] for e in top] == [1, 2]
    assert top[0]["why_rank"].startswith("R1: estimated EV +1.0%")
    assert "ranks below every fully priced game" in top[1]["why_rank"]


# --- the analysis speaks of scoring -----------------------------------------------------------
def test_the_analysis_marks_scoring_by_percentile_and_never_the_bet():
    ref = {
        "values": {"std_fh_pf": [float(x) for x in range(100)]},
        "verdicts": {"std_fh_pf": "null"},
    }
    out = S.analysis({"std_fh_pf": 10.0}, ref, {"wind_mph": 14, "dome": False}, None)
    st = next(x for x in out["stats"] if x["key"] == "std_fh_pf")
    assert st["pct"] == pytest.approx(0.11) and st["scoring"] == "less" and st["verdict"] == "null"
    assert out["weather"]["scoring"] == "less"
    assert out["qb"]["out"] is False
    assert "under" not in json.dumps(out)


# --- the frozen publication -------------------------------------------------------------------
def _pub(card_id=30):
    return {
        "published_at": "2026-10-15T20:20:00Z",
        "card_id": card_id,
        "season": 2026,
        "week": 7,
        "slot": "thu_pm",
        "card_built": "2026-10-15T20:17:15",
        "pool": 2,
        "method": S.METHOD,
        "top10": [
            {"game_id": 1, "rank": 1, "label": S.LABEL_FAIR, "price": {"ev_point": 0.01}},
            {"game_id": 2, "rank": 2, "label": S.LABEL_INSUFFICIENT, "price": {"status": "x"}},
        ],
    }


def test_a_card_publishes_once_and_a_second_run_writes_nothing():
    from beatvegas.db.models import ShortlistEntry

    eng, _ = _sqlite_scope()
    pub = _pub()
    with Session(eng) as s:
        assert S.write_publication(s, pub) == 2
        s.commit()
    changed = _pub()
    changed["top10"][0]["label"] = S.LABEL_POTENTIAL  # a later re-rank must not land
    with Session(eng) as s:
        assert S.write_publication(s, changed) == 0
        s.commit()
        rows = s.query(ShortlistEntry).order_by(ShortlistEntry.rank).all()
        assert [r.label for r in rows] == [S.LABEL_FAIR, S.LABEL_INSUFFICIENT]
        # The stored rows rebuild the publication exactly: its sha256 re-checks.
        assert S.publication_sha(S.publication_from_rows(rows)) == S.publication_sha(pub)
        assert rows[0].publication_sha256 == S.publication_sha(pub)


def test_the_unique_key_stops_a_second_copy_of_an_entry():
    from sqlalchemy.exc import IntegrityError

    from beatvegas.db.models import ShortlistEntry

    eng, _ = _sqlite_scope()
    with Session(eng) as s:
        S.write_publication(s, _pub())
        s.commit()
        e = json.loads(s.query(ShortlistEntry).first().payload_json)
        s.add(
            ShortlistEntry(
                card_id=30,
                season=2026,
                week=7,
                slot="thu_pm",
                published_at=NOW,
                publication_sha256="x",
                game_id=e["game_id"],
                rank=9,
                label="x",
                payload_json="{}",
            )
        )
        with pytest.raises(IntegrityError):
            s.flush()


# --- the health check ------------------------------------------------------------------------
def _card_ctx(eng, slot="thu_pm", items=None):
    from beatvegas import health
    from beatvegas.db.models import Card

    with Session(eng) as s:
        s.add(
            Card(
                id=30,
                season=2026,
                week=7,
                built_at=T0,
                payload=json.dumps(
                    {"slot": slot, "items": items if items is not None else [item()]}
                ),
            )
        )
        s.commit()
    s = Session(eng)
    return health, health.Ctx(
        session=s,
        now=NOW,
        job="card",
        run_started_at=T0 - timedelta(minutes=5),
        season=2026,
        week=7,
        slot=slot,
        outcomes={"shortlist": "failure"},
    )


def test_health_flags_a_scheduled_card_with_no_publication_and_names_the_recovery():
    eng, _ = _sqlite_scope()
    health, ctx = _card_ctx(eng)
    r = health.card_shortlist_published(ctx)
    assert not r.ok
    assert "shortlist_publish.yml card_id=30" in r.detail
    check = next(c for c in health.CONTRACTS["card"].checks if c.id == "card.shortlist_published")
    assert check.severity == "degraded"


def test_health_passes_once_published_and_for_a_manual_or_empty_card():
    eng, _ = _sqlite_scope()
    health, ctx = _card_ctx(eng)
    S.write_publication(ctx.session, _pub())
    ctx.session.commit()
    assert health.card_shortlist_published(ctx).ok
    eng2, _ = _sqlite_scope()
    health, ctx2 = _card_ctx(eng2, slot="manual")
    assert health.card_shortlist_published(ctx2).ok
    eng3, _ = _sqlite_scope()
    health, ctx3 = _card_ctx(eng3, items=[item(centred=False)])
    assert health.card_shortlist_published(ctx3).ok
