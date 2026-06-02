"""Send iMessages from a standalone script via AppleScript → Messages.app.

A plain Python script can't reach MCP tools, so unattended alerts go through
`osascript`. Requires Messages.app signed in to iMessage; the first run may
trigger a macOS Automation permission prompt. Returns False (with reason) on
failure rather than raising, so polling never crashes on a send error.
"""
from __future__ import annotations

import platform
import subprocess
from typing import List, Tuple

_SCRIPT = """
on run {targetBuddy, targetMessage}
    tell application "Messages"
        set targetService to 1st service whose service type = iMessage
        send targetMessage to buddy targetBuddy of targetService
    end tell
end run
"""


def send_imessage(to: str, body: str, timeout: int = 20) -> Tuple[bool, str]:
    """Send one iMessage. Returns (ok, detail)."""
    if platform.system() != "Darwin":
        return False, "iMessage sending requires macOS"
    if not to:
        return False, "no recipient configured"
    try:
        p = subprocess.run(
            ["osascript", "-", to, body],
            input=_SCRIPT, text=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "osascript timed out"
    if p.returncode == 0:
        return True, "sent"
    return False, (p.stderr or "osascript failed").strip()


def send_many(to: str, bodies: List[str]) -> int:
    """Send several messages; return how many succeeded."""
    return sum(1 for b in bodies if send_imessage(to, b)[0])
