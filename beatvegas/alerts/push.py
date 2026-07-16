"""Send a phone push from a standalone script — cloud-friendly, no Mac required.

Unlike alerts/imessage.py (AppleScript -> Messages.app, Mac-only), this is a plain
HTTPS POST, so it works from GitHub Actions where the Sunday/mid-week line-drop
jobs run (the Mac can't reach Neon from the campus network). Default provider is
**Pushover** (reliable, ~$5 one-time); **ntfy.sh** is a free fallback. Fail-silent
(returns (ok, detail), never raises) so a polling job never crashes on a send error.

Secrets come from config.yaml `push:` OR env vars (so CI can inject them):
  PUSHOVER_TOKEN, PUSHOVER_USER, NTFY_TOPIC

    push:
      provider: pushover        # or: ntfy
      pushover: {token: "...", user: "..."}
      ntfy:     {topic: "beatvegas-xxxx", server: "https://ntfy.sh"}
"""

from __future__ import annotations

import os
from typing import Dict, Optional, Tuple

import requests

from ..config import load_config

_PUSHOVER_URL = "https://api.pushover.net/1/messages.json"


def _push_cfg() -> Dict:
    """Merge config.yaml `push:` with env-var secret overrides (env wins)."""
    cfg = dict(load_config().get("push", {}) or {})
    po = dict(cfg.get("pushover", {}) or {})
    if os.environ.get("PUSHOVER_TOKEN"):
        po["token"] = os.environ["PUSHOVER_TOKEN"]
    if os.environ.get("PUSHOVER_USER"):
        po["user"] = os.environ["PUSHOVER_USER"]
    cfg["pushover"] = po
    nt = dict(cfg.get("ntfy", {}) or {})
    if os.environ.get("NTFY_TOPIC"):
        nt["topic"] = os.environ["NTFY_TOPIC"]
    cfg["ntfy"] = nt
    return cfg


def push_configured() -> bool:
    """True when the configured provider has the credentials it needs to send.

    Pollers run this BEFORE spending API credits: a `--push` run with no
    Pushover token/user would otherwise capture snapshots (consuming the
    first-appearance alert state) and then silently fail to notify."""
    cfg = _push_cfg()
    provider = (cfg.get("provider") or "pushover").lower()
    if provider == "pushover":
        po = cfg.get("pushover", {})
        return bool(po.get("token") and po.get("user"))
    if provider == "ntfy":
        return bool(cfg.get("ntfy", {}).get("topic"))
    return False


def send_push(
    title: str, body: str, url: Optional[str] = None, timeout: int = 15
) -> Tuple[bool, str]:
    """Send one push notification via the configured provider. Returns (ok, detail);
    never raises. `url` becomes a tap-through link (the board) when supported."""
    cfg = _push_cfg()
    provider = (cfg.get("provider") or "pushover").lower()
    try:
        if provider == "pushover":
            po = cfg.get("pushover", {})
            token, user = po.get("token"), po.get("user")
            if not token or not user:
                return False, "pushover token/user not configured"
            data = {"token": token, "user": user, "title": title, "message": body}
            if url:
                data["url"] = url
            r = requests.post(_PUSHOVER_URL, data=data, timeout=timeout)
            ok = r.status_code == 200
            return ok, ("sent" if ok else f"pushover {r.status_code}: {r.text[:120]}")
        if provider == "ntfy":
            nt = cfg.get("ntfy", {})
            topic = nt.get("topic")
            if not topic:
                return False, "ntfy topic not configured"
            server = (nt.get("server") or "https://ntfy.sh").rstrip("/")
            headers = {"Title": title}
            if url:
                headers["Click"] = url
            r = requests.post(
                f"{server}/{topic}", data=body.encode("utf-8"), headers=headers, timeout=timeout
            )
            return r.ok, ("sent" if r.ok else f"ntfy {r.status_code}")
        return False, f"unknown push provider '{provider}'"
    except Exception as e:  # fail-silent, like imessage.py
        return False, f"push error: {type(e).__name__}: {e}"
