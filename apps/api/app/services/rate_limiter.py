"""
In-memory rate limiter for public widget endpoints.

IMPORTANT: This implementation is suitable for single-process development only.
In a multi-worker or multi-instance production deployment, use Redis or another
shared store (e.g. slowapi + Redis backend).

Algorithm: sliding window via deque of timestamps per key.
"""

import time
from collections import defaultdict, deque

from fastapi import HTTPException, status

# ── Store ─────────────────────────────────────────────────────────────────────

# { key: deque of float timestamps }
_store: dict[str, deque] = defaultdict(deque)


# ── Core ──────────────────────────────────────────────────────────────────────

def _check(key: str, limit: int, window_seconds: int) -> None:
    """
    Raise HTTP 429 if the key has exceeded *limit* requests in *window_seconds*.
    Prunes expired timestamps on each call.
    """
    now = time.monotonic()
    cutoff = now - window_seconds
    dq = _store[key]

    # Drop timestamps outside the window.
    while dq and dq[0] < cutoff:
        dq.popleft()

    if len(dq) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitas requisições. Aguarde um momento e tente novamente.",
            headers={"Retry-After": str(window_seconds)},
        )

    dq.append(now)


# ── Public helpers ─────────────────────────────────────────────────────────────

def check_session_rate(ip: str) -> None:
    """5 session-creation attempts per IP per 60 seconds."""
    _check(f"session:{ip}", limit=5, window_seconds=60)


def check_message_rate(session_token: str) -> None:
    """10 messages per session_token per 60 seconds."""
    _check(f"msg:{session_token}", limit=10, window_seconds=60)
