"""ManualPick decision-tracking columns (shared contract with the web lane —
names are exact): verdict_at_pick, reason, gap_at_pick, ev_at_pick,
hr_line_at_pick, model_line_at_pick, model_score_at_pick. pick.py add takes them
as flags; --paper now stakes one flat unit so paper picks grade as +/-1
(is_paper keeps them out of the real ledger).

The two model_* columns were written ONLY by the website until 2026-09-13, so
every terminal and card pick left them NULL and fell out of decision-quality's
agreed/against split, which filters on model_line_at_pick != null."""

from argparse import Namespace
from contextlib import contextmanager
from datetime import datetime, timedelta

from conftest import _load_script
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from beatvegas.db.models import Base, Game, ManualPick, Prediction
from beatvegas.db.store import _MIGRATIONS, _apply_migrations

TRACKING_COLS = {
    "verdict_at_pick": "VARCHAR(8)",
    "reason": "VARCHAR(16)",
    "gap_at_pick": "FLOAT",
    "ev_at_pick": "FLOAT",
    "hr_line_at_pick": "FLOAT",
    "model_line_at_pick": "FLOAT",
    "model_score_at_pick": "INTEGER",
}


def test_model_and_migration_carry_the_tracking_columns():
    cols = ManualPick.__table__.columns
    for name in TRACKING_COLS:
        assert name in cols, name
    assert cols["verdict_at_pick"].type.length == 8
    assert cols["reason"].type.length == 16
    for name, sqltype in TRACKING_COLS.items():
        assert _MIGRATIONS["manual_picks"][name] == sqltype


def test_migration_adds_columns_to_a_legacy_table():
    eng = create_engine("sqlite:///:memory:")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE manual_picks (id INTEGER PRIMARY KEY, line FLOAT)"))
    _apply_migrations(eng)
    have = {col["name"] for col in inspect(eng).get_columns("manual_picks")}
    assert set(TRACKING_COLS) <= have


def test_data_migration_backfills_our_number_on_legacy_card_picks():
    """Week 2's 25 paper picks predate add_pick writing the model snapshot. Our
    number reconstructs EXACTLY from fields frozen at the pick: a card item only
    qualifies when Hard Rock priced it, and card.py then measures the gap against
    Hard Rock's own line, so bv_line = hr_line_at_pick - gap_at_pick. The score
    has no such reconstruction and comes from the prediction the pick was logged
    against. Both are scoped to reason='model_gap' and guarded on IS NULL, so a
    row the website (or the new writer) already filled is never touched."""
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(Prediction(game_id=1, model_version="gbm_v1", bv_line=22.15, under_score=91))
        s.add_all(
            [
                # a card paper pick: both NULL, both recoverable
                ManualPick(
                    id=1,
                    game_id=1,
                    season=2026,
                    week=2,
                    home_team="H",
                    away_team="A",
                    side="under",
                    market="1H",
                    line=28.5,
                    reason="model_gap",
                    hr_line_at_pick=28.5,
                    gap_at_pick=6.35,
                ),
                # already filled by the website — must survive untouched
                ManualPick(
                    id=2,
                    game_id=1,
                    season=2026,
                    week=2,
                    home_team="H",
                    away_team="A",
                    side="under",
                    market="1H",
                    line=28.5,
                    reason="model_gap",
                    hr_line_at_pick=28.5,
                    gap_at_pick=6.35,
                    model_line_at_pick=99.0,
                    model_score_at_pick=7,
                ),
                # a hand-logged pick with no model read behind it
                ManualPick(
                    id=3,
                    game_id=1,
                    season=2026,
                    week=2,
                    home_team="H",
                    away_team="A",
                    side="under",
                    market="1H",
                    line=28.5,
                    reason="manual",
                    hr_line_at_pick=28.5,
                    gap_at_pick=6.35,
                ),
            ]
        )
        s.commit()

    _apply_migrations(eng)
    _apply_migrations(eng)  # idempotent: a second pass must change nothing

    with Session(eng) as s:
        rows = {r.id: r for r in s.query(ManualPick).all()}
    assert (rows[1].model_line_at_pick, rows[1].model_score_at_pick) == (22.15, 91)
    assert (rows[2].model_line_at_pick, rows[2].model_score_at_pick) == (99.0, 7)
    assert rows[3].model_line_at_pick is None and rows[3].model_score_at_pick is None


def _args(**kw) -> Namespace:
    base = dict(
        home="Michigan",
        away="Ohio State",
        line=24.5,
        price=-110,
        stake=1.0,
        book=None,
        season=2026,
        week=None,
        note=None,
        market="1h",
        force=False,
        paper=False,
        reason="manual",
        verdict=None,
        gap=None,
        ev=None,
        hr_line=None,
    )
    base.update(kw)
    return Namespace(**base)


def _pick_module():
    pick = _load_script("pick")
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(
            Game(
                id=1,
                season=2026,
                week=13,
                home_team="Michigan",
                away_team="Ohio State",
                start_date=datetime.utcnow() + timedelta(days=30),
            )
        )
        s.commit()

    @contextmanager
    def scope():
        with Session(eng) as s:
            yield s
            s.commit()

    pick.session_scope = scope
    return pick, eng


def test_add_stores_the_decision_snapshot():
    """The CLI is paper-only since 2026-09-22 (real money is logged on the site,
    where the policy gates run); the decision snapshot is stored either way."""
    pick, eng = _pick_module()
    pick.cmd_add(
        _args(
            paper=True,
            reason="model_gap",
            verdict="BET",
            gap=2.25,
            ev=0.031,
            hr_line=24.5,
            stake=2.0,
        )
    )
    with Session(eng) as s:
        (row,) = s.query(ManualPick).all()
    assert row.reason == "model_gap"
    assert row.verdict_at_pick == "BET"
    assert row.gap_at_pick == 2.25
    assert row.ev_at_pick == 0.031
    assert row.hr_line_at_pick == 24.5
    assert row.stake == 1.0 and row.is_paper is True  # paper stakes one flat unit


def test_add_defaults_to_manual_reason_and_null_snapshot():
    pick, eng = _pick_module()
    pick.cmd_add(_args(paper=True))
    with Session(eng) as s:
        (row,) = s.query(ManualPick).all()
    assert row.reason == "manual"
    assert row.verdict_at_pick is None and row.gap_at_pick is None
    assert row.ev_at_pick is None and row.hr_line_at_pick is None


def test_paper_pick_stakes_one_flat_unit():
    pick, eng = _pick_module()
    pick.cmd_add(_args(paper=True, stake=3.0))
    with Session(eng) as s:
        (row,) = s.query(ManualPick).all()
    assert row.is_paper is True
    assert row.stake == 1.0  # grades as +/-1u; is_paper keeps it off the real ledger


def test_paper_pick_grades_to_plus_minus_one_unit():
    fields = _load_script("pick").graded_pick_fields(20, 24.5, -110, 1.0, 25.0, 24.0)
    assert fields["result"] == "under" and round(fields["units"], 3) == 0.909
    fields = _load_script("pick").graded_pick_fields(30, 24.5, -110, 1.0, 25.0, 24.0)
    assert fields["result"] == "over" and fields["units"] == -1.0


def test_cli_parses_the_new_flags(monkeypatch):
    import sys

    pick = _load_script("pick")
    seen = {}
    monkeypatch.setattr(pick, "try_init_db", lambda: True)
    monkeypatch.setattr(pick, "cmd_add", lambda a: seen.update(vars(a)))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pick.py",
            "add",
            "--home",
            "Michigan",
            "--away",
            "Ohio State",
            "--line",
            "24.5",
            "--reason",
            "price_edge",
            "--verdict",
            "WATCH",
            "--gap",
            "1.5",
            "--ev",
            "0.02",
            "--hr-line",
            "25",
            "--paper",
        ],
    )
    pick.main()
    assert seen["reason"] == "price_edge" and seen["verdict"] == "WATCH"
    assert seen["gap"] == 1.5 and seen["ev"] == 0.02 and seen["hr_line"] == 25.0
    assert seen["paper"] is True


# --- paper ledger vs real ledger (2026-09-07) ----------------------------------

from beatvegas.picks import add_pick, existing_pick  # noqa: E402


def test_blocker_column_and_migration():
    cols = ManualPick.__table__.columns
    assert "blocker" in cols and cols["blocker"].type.length == 16
    assert _MIGRATIONS["manual_picks"]["blocker"] == "VARCHAR(16)"


def _paper(s, gid=1, blocker="price"):
    return add_pick(
        s,
        game_id=gid,
        season=2026,
        week=13,
        home_team="Michigan",
        away_team="Ohio State",
        line=24.5,
        price=-125,
        is_paper=True,
        reason="model_gap",
        verdict="WATCH",
        gap=2.0,
        blocker=blocker,
        factors_json='{"total_band": "52–60"}',
    )


def test_null_price_persists_as_null():
    """An unpriced Hard Rock line logs price NULL — the ORM must not fall back
    to a -110 column default on INSERT (grade fills it from HR's close)."""
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        row = add_pick(
            s,
            game_id=1,
            season=2026,
            week=3,
            home_team="H",
            away_team="A",
            line=24.5,
            price=None,
            is_paper=True,
        )
        s.commit()
        rid = row.id
    with Session(eng) as s:
        assert s.get(ManualPick, rid).price is None


def test_add_pick_stores_blocker_and_chips():
    pick, eng = _pick_module()
    with Session(eng) as s:
        _paper(s)
        s.commit()
        (row,) = s.query(ManualPick).all()
    assert row.blocker == "price" and row.factors_json_at_pick == '{"total_band": "52–60"}'


def test_add_pick_freezes_our_number_and_leaves_it_null_when_unknown():
    from beatvegas.picks import add_pick

    pick, eng = _pick_module()
    with Session(eng) as s:
        add_pick(
            s,
            game_id=1,
            season=2026,
            week=3,
            home_team="H",
            away_team="A",
            line=24.5,
            model_line=22.4,
            model_score=78,
        )
        add_pick(
            s,
            game_id=2,
            season=2026,
            week=3,
            home_team="H2",
            away_team="A2",
            line=24.5,
        )
        s.commit()
        first, second = s.query(ManualPick).order_by(ManualPick.id).all()
    assert (first.model_line_at_pick, first.model_score_at_pick) == (22.4, 78)
    assert second.model_line_at_pick is None and second.model_score_at_pick is None


def test_model_read_prefers_the_model_row_over_derived_lines():
    """The same rule web/lib/picks.ts createPick uses: post_derived_lines writes
    seconds after scoring, so ordering on recency alone would freeze the
    display-only reference line as OUR number."""
    from beatvegas.picks import model_read

    pick, eng = _pick_module()
    with Session(eng) as s:
        s.add_all(
            [
                Prediction(
                    game_id=1,
                    model_version="gbm_v1",
                    bv_line=22.4,
                    under_score=78,
                    created_at=datetime(2026, 9, 11, 20, 0),
                ),
                Prediction(
                    game_id=1,
                    model_version="derived_lines",
                    line_used=24.5,
                    under_score=12,
                    created_at=datetime(2026, 9, 11, 20, 1),  # newer
                ),
            ]
        )
        s.commit()
        assert model_read(s, 1) == (22.4, 78)
        # The model is 1H-only, and an unmatched pick has no game to read.
        assert model_read(s, 1, "full") == (None, None)
        assert model_read(s, None) == (None, None)
        assert model_read(s, 999) == (None, None)


def test_pick_add_freezes_the_model_read_on_the_ticket():
    pick, eng = _pick_module()
    with Session(eng) as s:
        s.add(
            Prediction(
                game_id=1,
                model_version="gbm_v1",
                bv_line=22.4,
                under_score=78,
                created_at=datetime(2026, 9, 11, 20, 0),
            )
        )
        s.commit()
    pick.cmd_add(_args(paper=True))
    with Session(eng) as s:
        (row,) = s.query(ManualPick).all()
    assert row.model_line_at_pick == 22.4 and row.model_score_at_pick == 78


def test_existing_pick_is_scoped_per_ledger():
    pick, eng = _pick_module()
    with Session(eng) as s:
        _paper(s)
        s.commit()
        assert existing_pick(s, 1, "1H") is not None  # any ledger (legacy)
        assert existing_pick(s, 1, "1H", is_paper=True) is not None
        assert existing_pick(s, 1, "1H", is_paper=False) is None  # real ledger is clear
        # a legacy row with NULL is_paper counts as real
        s.add(
            ManualPick(
                game_id=1,
                season=2026,
                week=13,
                side="under",
                market="1H",
                line=24.5,
                price=-110,
                stake=1.0,
                is_paper=None,
            )
        )
        s.commit()
        assert existing_pick(s, 1, "1H", is_paper=False) is not None


def test_real_ticket_is_not_blocked_by_the_cards_paper_pick():
    """The ledgers are scoped apart: the card's paper pick on a game never
    blocks Tate's real ticket on it. The real ticket is written by the site
    (POST /api/picks -> picks.ts createPick) through the same per-ledger
    duplicate rule `existing_pick` implements; the CLI no longer writes real
    money, so the rule is exercised here directly."""
    pick, eng = _pick_module()
    with Session(eng) as s:
        _paper(s)
        s.commit()
        assert existing_pick(s, 1, "1H", is_paper=False) is None  # the real ledger is clear
        add_pick(
            s,
            game_id=1,
            season=2026,
            week=13,
            home_team="Michigan",
            away_team="Ohio State",
            line=24.5,
            price=-110,
            is_paper=False,
        )
        s.commit()
        rows = s.query(ManualPick).order_by(ManualPick.id).all()
    assert [r.is_paper for r in rows] == [True, False]


def test_the_cli_refuses_real_money_dup_or_not(capsys):
    """Since 2026-09-22 `pick.py add` is paper-only: it ran none of the policy
    gates and defaulted a missing price to -110. Real money is logged on the site."""
    pick, eng = _pick_module()
    pick.cmd_add(_args())
    pick.cmd_add(_args(price=-105))
    out = capsys.readouterr().out
    assert out.count("REFUSED") == 2 and "paper-only" in out
    with Session(eng) as s:
        assert s.query(ManualPick).count() == 0


def test_second_paper_pick_is_refused(capsys):
    pick, eng = _pick_module()
    pick.cmd_add(_args(paper=True))
    pick.cmd_add(_args(paper=True))
    assert "REFUSED: paper pick" in capsys.readouterr().out


def test_grade_uses_the_consensus_close_even_for_a_hard_rock_ticket():
    """CLV grades against the MARKET consensus, never one book's close.

    Grading a Hard Rock ticket at Hard Rock's own close reads like the right
    idea -- it is the only book Tate can bet. It is not: Hard Rock posts an
    off-centre rung as its main 1H total on 26 of 28 quotes inside 3 h of
    kickoff, which is the window the close polls run in. In 2026 week 2 that put
    a rung in closing_line for every paper pick and reported +1.67 points of
    line value where the market had moved +0.43.
    """
    from datetime import datetime, timedelta

    from beatvegas.db.models import Game, OddsSnapshot

    pick, eng = _pick_module()
    kick = datetime(2026, 9, 19, 19, 30)
    with Session(eng) as s:
        s.add(
            Game(
                id=2,
                season=2026,
                week=3,
                home_team="Missouri",
                away_team="Kansas",
                start_date=kick,
                home_points=30,
                away_points=10,
                first_half_total=20,
                first_half_source="pbp",
            )
        )
        for book, line, hrs in (
            ("draftkings", 24.5, 30),
            ("draftkings", 26.5, 1),
            ("hardrockbet", 24.5, 30),
            ("hardrockbet", 23.5, 1),
            ("hardrockbet", 30.0, -1),
        ):  # last one is in-game
            s.add(
                OddsSnapshot(
                    game_id=2,
                    book=book,
                    market="1H_total",
                    line=line,
                    over_price=-110,
                    under_price=-110,
                    captured_at=kick - timedelta(hours=hrs),
                )
            )
        s.add(
            ManualPick(
                game_id=2,
                season=2026,
                week=3,
                home_team="Missouri",
                away_team="Kansas",
                side="under",
                market="1H",
                line=24.5,
                price=-110,
                stake=1.0,
                is_paper=False,
                book="hardrockbet",
                graded=False,
                placed_at=kick,
            )
        )
        s.add(
            ManualPick(
                game_id=2,
                season=2026,
                week=3,
                home_team="Missouri",
                away_team="Kansas",
                side="under",
                market="1H",
                line=24.5,
                price=-110,
                stake=1.0,
                is_paper=True,
                book=None,
                graded=False,
                placed_at=kick,
            )
        )
        s.commit()
    pick.cmd_grade(_args(season=2026))
    with Session(eng) as s:
        hr, other = (
            s.query(ManualPick).filter(ManualPick.game_id == 2).order_by(ManualPick.id).all()
        )
    assert hr.graded and hr.result == "under"
    # Both grade at the consensus close: median of each book's last PRE-kick
    # line (draftkings 26.5, hardrockbet 23.5) = 25.0. `book` no longer changes it.
    assert hr.closing_line == 25.0 and hr.clv == 0.5
    assert other.closing_line == 25.0 and other.clv == 0.5


def test_graded_pick_fields_leave_units_none_when_unpriced():
    fields = _load_script("pick").graded_pick_fields(20, 24.5, None, 1.0, 25.0, 24.0)
    assert fields["result"] == "under" and fields["units"] is None
    assert fields["clv"] == -0.5  # line CLV still grades without a price (closing - line)


def test_grade_never_overwrites_the_decision_price_with_the_close(capsys):
    """A pick logged with price NULL keeps price NULL, and the book's pre-kick
    close lands in `closing_price` instead.

    This asserts the INVERSE of the behaviour that shipped until 2026-09-14, when
    the grader wrote Hard Rock's closing price into `price`. That turned the price
    at the DECISION into the price at the CLOSE, which makes any price-based CLV
    identically zero by construction -- and nothing marked the affected rows, so
    they were indistinguishable from genuinely priced tickets and would have
    diluted the metric toward zero, looking exactly like a null result. Unknown
    stays NULL: that is recoverable, a fabricated value is not.

    Units still require a decision price, so an unpriced ticket grades the result
    and the record but contributes no units or ROI."""
    from datetime import datetime, timedelta

    from beatvegas.db.models import Game, OddsSnapshot

    pick, eng = _pick_module()
    kick = datetime(2026, 9, 19, 19, 30)

    def _game(gid):
        return Game(
            id=gid,
            season=2026,
            week=3,
            home_team=f"H{gid}",
            away_team=f"A{gid}",
            start_date=kick,
            home_points=30,
            away_points=10,
            first_half_total=20,
            first_half_source="pbp",
        )

    def _snap(gid, line, under, hrs):
        return OddsSnapshot(
            game_id=gid,
            book="hardrockbet",
            market="1H_total",
            line=line,
            over_price=-110,
            under_price=under,
            captured_at=kick - timedelta(hours=hrs),
        )

    def _pick(gid):
        return ManualPick(
            game_id=gid,
            season=2026,
            week=3,
            home_team=f"H{gid}",
            away_team=f"A{gid}",
            side="under",
            market="1H",
            line=24.5,
            price=None,
            stake=1.0,
            is_paper=True,
            book="hardrockbet",
            graded=False,
            placed_at=kick - timedelta(days=1),
        )

    with Session(eng) as s:
        s.add_all([_game(2), _game(3)])
        # game 2: HR opened unpriced, then priced -108 pre-kick; -130 is in-game
        s.add_all([_snap(2, 24.5, None, 30), _snap(2, 24.5, -108, 1), _snap(2, 24.5, -130, -1)])
        # game 3: HR never priced the under before kickoff
        s.add_all([_snap(3, 24.5, None, 30), _snap(3, 24.0, None, 1)])
        s.add_all([_pick(2), _pick(3)])
        s.commit()
    pick.cmd_grade(_args(season=2026))
    out = capsys.readouterr().out
    with Session(eng) as s:
        priced = s.query(ManualPick).filter(ManualPick.game_id == 2).one()
        unpriced = s.query(ManualPick).filter(ManualPick.game_id == 3).one()
    # game 2: HR closed at -108 pre-kick. That is the CLOSE, not our entry.
    assert priced.graded and priced.result == "under"
    assert priced.price is None, "the decision price was unknown and must stay unknown"
    assert priced.closing_price == -108, "the close belongs in its own column"
    assert priced.units is None, "no decision price means no units, by design"
    # game 3: HR never priced the under pre-kick, so there is no close either.
    assert unpriced.graded and unpriced.price is None and unpriced.result == "under"
    assert unpriced.closing_price is None and unpriced.units is None
    # summary: both count for the record / hit rate; neither contributes units now
    assert "PAPER RECORD: 2-0" in out and "hit=100.0%" in out
    assert "(2 unpriced)" in out
    # list must not choke on the unpriced graded row
    pick.cmd_list(_args(season=2026))
    assert "under (unpriced," in capsys.readouterr().out


def test_data_migration_backfills_hard_rock_as_the_book_on_real_tickets():
    """Until 2026-09-20 the website never wrote `book`, and grade_pick computes
    closing_price only when it is set, so every real 2026 ticket was invisible to
    price-CLV. Every real ticket is Hard Rock's (the only Florida book), so the
    backfill states a known fact; paper rows and pre-2026 rows are untouched."""
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    common = dict(
        game_id=1, week=3, home_team="H", away_team="A", side="under", market="1H", line=28.5
    )
    with Session(eng) as s:
        s.add_all(
            [
                ManualPick(id=1, season=2026, is_paper=False, **common),  # web ticket, no book
                ManualPick(id=2, season=2026, is_paper=None, **common),  # legacy NULL flag = real
                ManualPick(
                    id=3, season=2026, is_paper=True, **common
                ),  # paper: build_card's business
                ManualPick(
                    id=4, season=2026, is_paper=False, book="draftkings", **common
                ),  # already set
                ManualPick(id=5, season=2025, is_paper=False, **common),  # out of scope
            ]
        )
        s.commit()

    _apply_migrations(eng)
    _apply_migrations(eng)  # idempotent

    with Session(eng) as s:
        books = {p.id: p.book for p in s.query(ManualPick).order_by(ManualPick.id)}
    assert books == {1: "hardrockbet", 2: "hardrockbet", 3: None, 4: "draftkings", 5: None}
