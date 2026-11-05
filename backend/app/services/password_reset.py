"""Password reset token primitives.

The raw token is generated with ``secrets`` (CSPRNG), delivered only inside the
recovery link, and never persisted. The database stores its SHA-256 hash.
"""

import hashlib
import os
import secrets
from urllib.parse import urlencode

DEFAULT_TOKEN_TTL_MINUTES = 30
DEFAULT_FRONTEND_URL = "http://localhost:5173"


def token_ttl_minutes() -> int:
    raw = os.getenv("PASSWORD_RESET_TOKEN_MINUTES")
    if not raw:
        return DEFAULT_TOKEN_TTL_MINUTES
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_TOKEN_TTL_MINUTES
    return value if value > 0 else DEFAULT_TOKEN_TTL_MINUTES


def generate_reset_token() -> str:
    # 32 random bytes -> 43 URL-safe characters, cryptographically secure.
    return secrets.token_urlsafe(32)


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def build_reset_link(token: str, frontend_url: str | None = None) -> str:
    base = (
        frontend_url
        or os.getenv("PASSWORD_RESET_FRONTEND_URL")
        or os.getenv("FRONTEND_URL")
        or DEFAULT_FRONTEND_URL
    ).rstrip("/")
    return f"{base}/reset-password?{urlencode({'token': token})}"
