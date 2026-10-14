"""The stored arm positions (`arm_positions`, 2026-10-14, programme step 10).

One row per registered hypothesis per read date. The six paper arms are written
by `scripts/protocol_position.py --write` from the protocol reader's line; the
pricing study by `scripts/pricing_check.py --write` from its verdict. The site
(`web/lib/armPositions.ts`), the Monday read and the January review all read the
newest row per hypothesis, so one number reaches every reader. `--write` runs only
inside `pricing_monday.yml`; a `study.yml` dispatch never writes.
"""

from __future__ import annotations

import json
import math
import statistics
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from . import protocol as P
from .db.models import ArmPosition

STANDARD_SPRT = "sprt"
STANDARD_PRICING = "pricing"
PRICING_ID = "H-PRICE-HR"
HYPOTHESES: Tuple[str, ...] = tuple(P.ARMS) + (PRICING_ID,)
OUTDATED_AFTER_DAYS = 8  # a Monday read older than this is "outdated" on the site


def read_date(now: datetime) -> str:
    return now.strftime("%Y-%m-%d")


def next_monday(now: datetime) -> str:
    """The next Monday after `now` (UTC), the day the reads happen."""
    d = now.date()
    ahead = (7 - d.weekday()) % 7 or 7
    return (d + timedelta(days=ahead)).isoformat()


def mean_ci(values: Iterable[float]) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """(mean, lo, hi) at 95% (normal); (mean, None, None) below two values."""
    v = [float(x) for x in values]
    if not v:
        return None, None, None
    m = sum(v) / len(v)
    if len(v) < 2:
        return m, None, None
    h = 1.96 * statistics.stdev(v) / math.sqrt(len(v))
    return m, m - h, m + h


def arm_position(arm: str, line: Mapping[str, Any], now: datetime, run_id: str) -> Dict[str, Any]:
    """The row for one arm from `protocol_position.read_arm`'s line."""
    return {
        "hypothesis": arm,
        "standard": STANDARD_SPRT,
        "read_date": read_date(now),
        "read_at": now,
        "run_id": run_id,
        "state": line.get("state"),
        "label": line.get("label"),
        "logged": int(line.get("logged") or 0),
        "readings": int(line.get("readings") or 0),
        "weeks": int(line.get("weeks") or 0),
        "excluded": int(line.get("excluded") or 0),
        "pending": int(line.get("pending") or 0),
        "needed": P.MIN_OBS,
        "llr": line.get("llr"),
        "mean_ev": line.get("mean_ev"),
        "ev_lo": line.get("ev_lo"),
        "ev_hi": line.get("ev_hi"),
        "next_read": next_monday(now),
        "payload_json": json.dumps(dict(line), default=str),
    }


def pricing_position(
    verdict: Mapping[str, Any],
    forward_by_market: Mapping[str, Mapping[str, Any]],
    now: datetime,
    run_id: str,
) -> Dict[str, Any]:
    """The row for H-PRICE-HR from `pricing.verdict` and the forward summaries."""
    close = verdict.get("ev_close") or {}
    ci = close.get("ci")
    return {
        "hypothesis": PRICING_ID,
        "standard": STANDARD_PRICING,
        "read_date": read_date(now),
        "read_at": now,
        "run_id": run_id,
        "state": verdict.get("verdict"),
        "label": str(verdict.get("verdict") or "").upper(),
        "logged": sum(int(m.get("states_compared") or 0) for m in forward_by_market.values()),
        "readings": int(verdict.get("opportunities") or 0),
        "weeks": None,
        "excluded": sum(
            sum(int(n) for n in (m.get("drops") or {}).values()) for m in forward_by_market.values()
        ),
        "pending": 0,
        "needed": int(verdict.get("min_required") or 0),
        "llr": None,
        "mean_ev": close.get("mean"),
        "ev_lo": ci[0] if ci else None,
        "ev_hi": ci[1] if ci else None,
        "next_read": next_monday(now),
        "payload_json": json.dumps(dict(verdict), default=str),
    }


def upsert_position(session, row: Mapping[str, Any]) -> ArmPosition:
    """Insert, or rewrite the same (hypothesis, read_date) row."""
    existing = (
        session.query(ArmPosition)
        .filter(
            ArmPosition.hypothesis == row["hypothesis"],
            ArmPosition.read_date == row["read_date"],
        )
        .one_or_none()
    )
    if existing is None:
        existing = ArmPosition(**row)
        session.add(existing)
    else:
        for k, v in row.items():
            setattr(existing, k, v)
    session.flush()
    return existing


def newest_positions(session, hypotheses: Sequence[str] = HYPOTHESES) -> Dict[str, ArmPosition]:
    """The newest row per hypothesis (by read_at, then id)."""
    rows: List[ArmPosition] = (
        session.query(ArmPosition)
        .filter(ArmPosition.hypothesis.in_(list(hypotheses)))
        .order_by(ArmPosition.read_at.asc(), ArmPosition.id.asc())
        .all()
    )
    out: Dict[str, ArmPosition] = {}
    for r in rows:
        out[r.hypothesis] = r
    return out


def freshness(read_at: Optional[datetime], now: datetime) -> str:
    """'outdated' past OUTDATED_AFTER_DAYS, 'missing' with no row, else 'current'."""
    if read_at is None:
        return "missing"
    return "outdated" if now - read_at > timedelta(days=OUTDATED_AFTER_DAYS) else "current"
