"""The champion-read allow-list (2026-10-06): every "the model's line" read sees
only `CHAMPION_READ_VERSIONS`, so a shadow engine writing into `predictions` /
`game_records` (`bv_fg_v1` for H-FG-P, the PR6 shadows) is never read as the
champion. Each reader below is handed a NEWER shadow row and must ignore it.
The two web readers (board.ts universeWhere, picks.ts createPick) are covered by
the e2e fixture's bv_fg_v1 rows; their constant is pinned here."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from conftest import _load_script
from sqlalchemy.orm import Session

from beatvegas import card, health
from beatvegas.db.models import Game, GameRecord, Prediction
from beatvegas.model import score
from beatvegas.model.bv_line import BV_FEATURE_COLS
from beatvegas.picks import model_read, model_refit_id
from tests.conftest import _sqlite_scope

SHADOW = "bv_fg_v1"
_MODEL_TS = Path(__file__).resolve().parent.parent / "web" / "lib" / "model.ts"


def test_the_allow_list_is_the_champion_then_derived_lines():
    assert score.CHAMPION_READ_VERSIONS == (score.MODEL_VERSION, "derived_lines")
    assert SHADOW not in score.CHAMPION_READ_VERSIONS
    # One string, three names: the card's reference version and health's.
    assert card.REFERENCE_MODEL_VERSION == score.CHAMPION_READ_VERSIONS[1]
    assert health.DERIVED_LINES_MODEL_VERSION == score.CHAMPION_READ_VERSIONS[1]


def test_web_model_ts_mirrors_the_allow_list():
    src = _MODEL_TS.read_text()
    consts = dict(re.findall(r'export\s+const\s+([A-Z_]+)\s*=\s*"([^"]+)"\s*;', src))
    assert consts["MODEL_VERSION"] == score.MODEL_VERSION
    assert consts["DERIVED_LINES_MODEL_VERSION"] == score.CHAMPION_READ_VERSIONS[1]
    m = re.search(
        r"export\s+const\s+CHAMPION_READ_VERSIONS\s*=\s*\[(.*?)\]\s*as\s+const", src, re.S
    )
    assert m, "web/lib/model.ts must export CHAMPION_READ_VERSIONS"
    names = [n.strip() for n in m.group(1).split(",") if n.strip()]
    assert [consts[n] for n in names] == list(score.CHAMPION_READ_VERSIONS)


def _seed_predictions(s: Session) -> None:
    s.add_all(
        [
            Prediction(
                game_id=1,
                model_version=score.MODEL_VERSION,
                bv_line=22.4,
                refit_id=7,
                created_at=datetime(2026, 10, 4, 20, 0),
            ),
            Prediction(
                game_id=1,
                model_version=SHADOW,
                bv_line=51.5,
                refit_id=99,
                created_at=datetime(2026, 10, 4, 20, 30),  # newer
            ),
        ]
    )
    s.commit()


def test_model_read_and_refit_ignore_a_newer_shadow_row():
    eng, _scope = _sqlite_scope()
    with Session(eng) as s:
        _seed_predictions(s)
        assert model_read(s, 1) == 22.4
        assert model_refit_id(s, 1) == 7


def test_a_shadow_only_game_has_no_model_read():
    eng, _scope = _sqlite_scope()
    with Session(eng) as s:
        s.add(Prediction(game_id=2, model_version=SHADOW, bv_line=48.0, refit_id=99))
        s.commit()
        assert model_read(s, 2) is None
        assert model_refit_id(s, 2) is None


def test_sunday_predictions_today_does_not_count_shadow_rows():
    eng, _scope = _sqlite_scope()
    now = datetime(2026, 10, 11, 22, 0)  # Sunday 6pm ET
    with Session(eng) as s:
        s.add(Game(id=1, season=2026, week=7, home_team="A", away_team="B"))
        s.add(
            Prediction(
                game_id=1, model_version=SHADOW, bv_line=51.5, created_at=now - timedelta(hours=1)
            )
        )
        s.commit()
        ctx = health.Ctx(
            session=s,
            now=now,
            job="sunday",
            run_started_at=now - timedelta(minutes=30),
            season=2026,
            week=7,
            env={},
        )
        assert health.sunday_predictions_today(ctx).ok is False
        s.add(
            Prediction(
                game_id=1,
                model_version=score.MODEL_VERSION,
                bv_line=22.4,
                created_at=now - timedelta(minutes=50),
            )
        )
        s.commit()
        assert health.sunday_predictions_today(ctx).ok is True


def test_frozen_features_ignore_a_newer_shadow_record():
    bc = _load_script("build_card")
    eng, _scope = _sqlite_scope()
    col = BV_FEATURE_COLS[0]
    with Session(eng) as s:
        s.add_all(
            [
                GameRecord(
                    game_id=1,
                    model_version=score.MODEL_VERSION,
                    captured_at=datetime(2026, 10, 4, 20, 0),
                    features_json=json.dumps({col: 1.0}),
                ),
                GameRecord(
                    game_id=1,
                    model_version=SHADOW,
                    captured_at=datetime(2026, 10, 4, 21, 0),  # newer
                    features_json=json.dumps({col: 999.0}),
                ),
            ]
        )
        s.commit()
        out = bc.frozen_features(s, [1])
        assert out[1][col] == 1.0
