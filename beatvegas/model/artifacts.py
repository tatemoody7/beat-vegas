"""Persist a fitted model with the fingerprint of what it was trained on.

score_slate refits per call and hands the fitted regressor back on
`frame.attrs["engine_artifact"]` (residual engine only). weekly_update stores
it here — one `model_artifacts` row per refit — so a scoring run is
reproducible (load_model(row.blob) predicts exactly what the job did) and a
mid-season change to the training history is visible: `fingerprint_changed`
names which of n_rows / max_game_date / feature_hash moved since the previous
fit, and the job log prints it.

joblib ships with scikit-learn; the blob is a few hundred KB.

Cross-version blob caveat. Blobs are written by the cloud job (GitHub Actions,
Python 3.11, whatever scikit-learn pip resolves that day) and would be loaded
locally (Python 3.9, scikit-learn 1.6.x). scikit-learn pickles are only
guaranteed within one version: loading across minor versions warns
(InconsistentVersionWarning) and may fail outright. Before load_model on a
row, install the `sklearn_version` that row records (the column exists;
`scripts/model_artifacts.py list` prints it). The fingerprint columns are
plain SQL and read fine from anywhere.

Reads never pull the blob unless asked: latest_artifact / newest_artifacts
defer it (fingerprint comparison needs three scalars, not 300 KB per row).
"""

from __future__ import annotations

import io
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import joblib
from sqlalchemy.orm import Session, defer

from ..db.models import ModelArtifact
from ..etl.context import json_safe

# The fingerprint fields whose movement means "the model did not see the same
# history as last time": more/fewer rows, a later last game, a different
# feature list. target_mean/std move with any of these and are not reported
# separately.
CHANGE_FIELDS = ("n_rows", "max_game_date", "feature_hash")


def dump_model(model) -> bytes:
    """joblib dump of a fitted estimator, in memory."""
    buf = io.BytesIO()
    joblib.dump(model, buf)
    return buf.getvalue()


def load_model(blob: bytes):
    """Inverse of dump_model."""
    return joblib.load(io.BytesIO(blob))


def _opt_int(v: Any) -> Optional[int]:
    return None if v is None else int(v)


def persist_artifact(
    session: Session,
    *,
    engine: str,
    model,
    fingerprint: Dict,
    season: int,
    week: Optional[int],
    metrics: Optional[Dict],
    now: datetime,
) -> int:
    """Insert one model_artifacts row (single insert, no bulk path) and return
    its id. `fingerprint` is residual.fingerprint's dict; `metrics` is whatever
    the caller wants to keep beside it (sigma, row split, fallback)."""
    fp = json_safe(fingerprint or {})
    row = ModelArtifact(
        engine=engine,
        model_version=fp.get("model_version"),
        season=_opt_int(season),
        week=_opt_int(week),
        fitted_at=now,
        n_rows=_opt_int(fp.get("n_rows")),
        min_game_date=fp.get("min_game_date"),
        max_game_date=fp.get("max_game_date"),
        feature_hash=fp.get("feature_hash"),
        n_features=_opt_int(fp.get("n_features")),
        fingerprint_json=json.dumps(fp),
        metrics_json=json.dumps(json_safe(metrics or {})),
        sklearn_version=fp.get("sklearn_version"),
        blob=dump_model(model),
    )
    session.add(row)
    session.flush()  # assigns the id
    return int(row.id)


def newest_artifacts(session: Session, engine: str, limit: int) -> List[ModelArtifact]:
    """The `limit` newest fits for `engine` (fitted_at desc, then id desc) with
    the joblib blob DEFERRED — it loads lazily only if a caller touches
    `.blob`. Comparing fingerprints and listing rows never do."""
    return (
        session.query(ModelArtifact)
        .options(defer(ModelArtifact.blob))
        .filter(ModelArtifact.engine == engine)
        .order_by(ModelArtifact.fitted_at.desc(), ModelArtifact.id.desc())
        .limit(limit)
        .all()
    )


def latest_artifact(session: Session, engine: str) -> Optional[ModelArtifact]:
    """The newest fit for `engine` (by fitted_at, then id), or None. Blob
    deferred (see newest_artifacts)."""
    rows = newest_artifacts(session, engine, limit=1)
    return rows[0] if rows else None


def fingerprint_changed(prev: Optional[ModelArtifact], fp: Dict) -> List[str]:
    """Which of CHANGE_FIELDS differ between the previous artifact row and the
    new fingerprint, in CHANGE_FIELDS order. No previous row -> [] (nothing to
    compare against). A date present on one side and missing on the other
    counts as a move."""
    if prev is None:
        return []
    fp = json_safe(fp or {})
    moved: List[str] = []
    for field in CHANGE_FIELDS:
        if getattr(prev, field) != fp.get(field):
            moved.append(field)
    return moved
