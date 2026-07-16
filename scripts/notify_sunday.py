#!/usr/bin/env python
"""Local 'board updated' iMessage heads-up — the one piece that must stay on the
Mac (iMessage needs a macOS Messages session; the cloud job can't send it).

The Sunday capture + scoring now runs in GitHub Actions (it writes Neon, which the
campus network can't reach). This fires a few minutes after the cloud run. The Mac
CAN reach Vercel over HTTPS, so we optionally confirm the board is up before
texting; otherwise we send a schedule-based heads-up.

    python scripts/notify_sunday.py            # send
    python scripts/notify_sunday.py --dry-run  # print only
"""

from __future__ import annotations

import argparse

from beatvegas.alerts.imessage import send_imessage
from beatvegas.config import load_config

DEFAULT_URL = "https://beat-vegas.vercel.app"


def board_reachable(url: str, timeout: int = 15) -> bool:
    """True if Vercel answers (any non-5xx; the board is password-gated so a 200/
    redirect both mean it's up). Fail-silent."""
    try:
        import requests

        return requests.get(url, timeout=timeout).status_code < 500
    except Exception:  # noqa: BLE001 — best-effort check, never raise
        return False


def fresh_capture_count(url: str, timeout: int = 15):
    """Full-game snapshots captured in the last 24h, via the board's ungated
    /api/health (Neon itself is unreachable from the campus network). Returns
    None when the check can't run — the message must then hedge, never assert
    'board updated' on faith."""
    try:
        import requests

        r = requests.get(f"{url.rstrip('/')}/api/health", timeout=timeout)
        if r.status_code != 200:
            return None
        data = r.json()
        if not data.get("ok"):
            return None
        return int(data.get("fullGameSnapshotsLast24h", 0))
    except Exception:  # noqa: BLE001 — best-effort check, never raise
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--dry-run", action="store_true", help="print the message instead of sending it"
    )
    ap.add_argument("--url", default=DEFAULT_URL)
    args = ap.parse_args()

    fresh = fresh_capture_count(args.url)
    if fresh:
        msg = (
            f"Openers are in — {fresh} full-game lines captured in the last 24h. "
            f"Board updated: {args.url}"
        )
    elif fresh == 0:
        msg = (
            "⚠️ Sunday check: NO full-game lines captured in the last 24h — the "
            f"cloud job may have failed. Don't bet off the board until you check: {args.url}"
        )
    else:  # health check unavailable — hedge, never assert success on faith
        up = board_reachable(args.url)
        msg = (
            f"Sunday run finished but capture freshness is UNVERIFIED — check the "
            f"board before betting: {args.url}"
            if up
            else f"Sunday check: the board itself is unreachable — investigate: {args.url}"
        )

    acfg = load_config().get("alerts", {}) or {}
    recipient = acfg.get("imessage_to", "")
    if args.dry_run or not recipient:
        print(f"[notify] {msg}" + ("" if recipient else "  (no recipient set)"))
        return
    ok, detail = send_imessage(recipient, msg)
    print(f"[notify {'sent' if ok else 'FAILED: ' + detail}] {msg}")


if __name__ == "__main__":
    main()
