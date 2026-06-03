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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="print the message instead of sending it")
    ap.add_argument("--url", default=DEFAULT_URL)
    args = ap.parse_args()

    up = board_reachable(args.url)
    msg = (f"DK fired — this week's openers are in, board updated. {args.url}"
           if up else
           f"Sunday run complete — check the board: {args.url}")

    acfg = load_config().get("alerts", {}) or {}
    recipient = acfg.get("imessage_to", "")
    if args.dry_run or not recipient:
        print(f"[notify] {msg}" + ("" if recipient else "  (no recipient set)"))
        return
    ok, detail = send_imessage(recipient, msg)
    print(f"[notify {'sent' if ok else 'FAILED: ' + detail}] {msg}")


if __name__ == "__main__":
    main()
