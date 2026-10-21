"""Authentication: Argon2 passwords, opaque server-side session tokens.

Session tokens are random strings. Only a SHA-256 hash is stored, so a
database leak does not yield usable tokens. Tokens carry a `kind`
(`session` for the browser cookie, `mcp` for short-lived assistant
access) and an absolute expiry.
"""
import hashlib
import secrets
import time
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Cookie, Depends, HTTPException, Request, Response, status
from sqlmodel import Session, select

from .db import get_session
from .models import AuthToken, User

SESSION_COOKIE = "reesatck_session"
SESSION_LIFETIME = 7 * 24 * 3600  # 7 days

_hasher = PasswordHasher(time_cost=2, memory_cost=64 * 1024, parallelism=2)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def issue_token(session: Session, user_id: int, kind: str = "session", lifetime: int = SESSION_LIFETIME) -> str:
    raw = secrets.token_urlsafe(32)
    record = AuthToken(token_hash=_hash_token(raw), user_id=user_id, kind=kind, expires_at=int(time.time()) + lifetime)
    session.add(record)
    session.commit()
    return raw


def resolve_token(session: Session, raw: str, kind: str = "session") -> Optional[User]:
    if not raw:
        return None
    record = session.get(AuthToken, _hash_token(raw))
    if record is None or record.kind != kind or record.expires_at < time.time():
        return None
    return session.get(User, record.user_id)


def revoke_token(session: Session, raw: str) -> None:
    record = session.get(AuthToken, _hash_token(raw))
    if record is not None:
        session.delete(record)
        session.commit()


def get_current_user(
    session: Session = Depends(get_session),
    reesatck_session: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
) -> User:
    if not reesatck_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user = resolve_token(session, reesatck_session, kind="session")
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def get_optional_user(
    session: Session = Depends(get_session),
    reesatck_session: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
) -> Optional[User]:
    if not reesatck_session:
        return None
    return resolve_token(session, reesatck_session, kind="session")


def set_session_cookie(response: Response, raw: str) -> None:
    import os

    secure = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    response.set_cookie(
        key=SESSION_COOKIE,
        value=raw,
        httponly=True,
        samesite="lax",
        secure=secure,
        max_age=SESSION_LIFETIME,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE, path="/")


def check_mutation_origin(request: Request) -> None:
    """Reject unsafe cross-origin mutations (CSRF mitigation).

    Browsers attach an `Origin` header to POST/PUT/PATCH/DELETE. When one
    is present we require both an allow-listed origin and the
    `X-Reesatck-Request: 1` custom header, which a third-party page cannot
    set without CORS approval. Non-browser clients (no Origin) are allowed
    so curl and scripts keep working.
    """
    import os

    method = request.method.upper()
    if method in ("GET", "HEAD", "OPTIONS"):
        return
    origin = request.headers.get("origin")
    if not origin:
        return
    allowed = {
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://testserver",
    }
    extra = os.getenv("ALLOWED_ORIGINS", "")
    for item in extra.split(","):
        item = item.strip()
        if item:
            allowed.add(item)
    if origin not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origin not allowed")
    if request.headers.get("x-reesatck-request") != "1":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing request header")
