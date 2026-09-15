"""The retry ladder shared by every outbound HTTP source.

Extracted from `cfbd.py`, which had the only real one. A rate limit is a window,
not a blip, so the waits are minutes-adjacent rather than the seconds a transient
blip would need; the server's own `Retry-After` wins when it sends one.

The alternative -- each source inventing its own -- is what left
`sources/weather.py` with no retries at all, where a 429 and a network error both
returned an empty dict. That silent failure capped the 2023-25 weather backfill
at 21% coverage (647 venues came back "empty" in `data/backfill_weather_full.log`,
Soldier Field and Stanford Stadium among them) and went unnoticed for months.
"""

from __future__ import annotations

from typing import Optional

import requests

# Transient failures worth a second look. requests.Timeout covers both
# ConnectTimeout and ReadTimeout (the Aug 30 2026 Sunday run died on ONE
# ReadTimeout); ConnectionError covers resets and DNS blips.
RETRY_EXC = (requests.Timeout, requests.ConnectionError)

# Between attempts 1->2, 2->3, 3->4. The old (2, 4) ladder gave a rate limit six
# seconds to clear, which it never does: CFBD 429'd every grading run on
# 2026-09-12/13 across four attempts spread over two days. A 429 is a quota
# window, not a blip, so wait in minutes-adjacent steps. Timeouts and connection
# errors ride the same ladder -- they are rare enough that the extra wait costs
# nothing, and these jobs have no deadline.
BACKOFF_SECONDS = (5, 20, 60)

MAX_RETRY_AFTER = 120  # honour the server's Retry-After, but never stall a job on it


def retry_after(resp: requests.Response) -> Optional[float]:
    """Seconds the server asked us to wait, or None if it did not say.

    Only the delta-seconds form is honoured; the HTTP-date form is rare here and
    a bad parse should fall back to our own ladder rather than raise.
    """
    raw = resp.headers.get("Retry-After")
    if not raw:
        return None
    try:
        secs = float(raw.strip())
    except ValueError:
        return None
    if secs <= 0:
        return None
    return min(secs, MAX_RETRY_AFTER)


def backoff_seconds(attempt: int) -> float:
    """Wait before the next attempt, clamped to the last rung of the ladder."""
    return BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)]
