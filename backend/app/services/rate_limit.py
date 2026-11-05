"""Small in-process rate limiter for authentication endpoints.

This protects a single API process. If Reestack runs several workers or
instances, move the counters to Redis (or another shared store) so the limit is
global. The interface is intentionally tiny to keep that swap simple.
"""

import os
import threading
import time

from fastapi import HTTPException, status

_attempts: dict[str, list[float]] = {}
_lock = threading.Lock()


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def enforce_rate_limit(
    key: str,
    *,
    limit_env: str,
    default_limit: int,
    window_env: str,
    default_window_seconds: int,
) -> None:
    """Record an attempt or raise ``429`` when the bucket is exhausted."""
    limit = _env_int(limit_env, default_limit)
    window = _env_int(window_env, default_window_seconds)
    now = time.monotonic()
    cutoff = now - window

    with _lock:
        bucket = _attempts.setdefault(key, [])
        while bucket and bucket[0] <= cutoff:
            bucket.pop(0)
        if len(bucket) >= limit:
            retry_after = max(1, int(bucket[0] + window - now) + 1)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Demasiadas solicitudes. Esperá unos minutos antes de volver a intentar.",
                headers={"Retry-After": str(retry_after)},
            )
        bucket.append(now)


def reset_rate_limits() -> None:
    """Clear all counters. Used by tests to keep cases independent."""
    with _lock:
        _attempts.clear()
