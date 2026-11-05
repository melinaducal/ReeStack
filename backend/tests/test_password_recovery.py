"""Real tests for password recovery.

Everything runs against the in-memory database from ``conftest.py``; the
production ``reestack.db`` and its users are never touched. Email delivery is
replaced by an in-memory outbox so the tests can read the link, but the
production path still uses real SMTP.
"""

import hashlib
import logging
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest

from app.models import PasswordResetToken

OLD_PASSWORD = "Password123!"
NEW_PASSWORD = "NewPassword456!"


def _register(
    client,
    *,
    username="testuser",
    email="test@example.com",
    password=OLD_PASSWORD,
):
    response = client.post(
        "/auth/register",
        json={
            "username": username,
            "first_name": "Test",
            "last_name": "User",
            "email": email,
            "birth_date": "1990-01-01",
            "password": password,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _login(client, email="test@example.com", password=OLD_PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password})


@pytest.fixture
def email_outbox(monkeypatch):
    sent = []

    def fake_send(**kwargs):
        sent.append(kwargs)

    monkeypatch.setattr("app.routers.auth.ensure_email_configured", lambda: None)
    monkeypatch.setattr("app.routers.auth.send_password_reset_email", fake_send)
    return sent


def _token_from(email):
    query = parse_qs(urlparse(email["reset_link"]).query)
    return query["token"][0]


def _forgot(client, email="test@example.com"):
    return client.post("/auth/forgot-password", json={"email": email})


def _reset(client, token, new_password=NEW_PASSWORD):
    return client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": new_password},
    )


# ---------------------------------------------------------------------------
# Requesting a recovery link
# ---------------------------------------------------------------------------


def test_registered_email_gets_generic_response_and_email(client, auth_headers, email_outbox):
    response = _forgot(client)

    assert response.status_code == 200, response.text
    assert response.json() == {
        "message": "Si el correo está registrado, vas a recibir un enlace para restablecer tu contraseña."
    }
    assert len(email_outbox) == 1
    assert "/reset-password?token=" in email_outbox[0]["reset_link"]
    assert email_outbox[0]["expires_minutes"] == 30


def test_unknown_email_gets_the_same_response_and_no_email(client, email_outbox):
    registered = _forgot(client, "missing@example.com")
    unknown = _forgot(client, "really-missing@example.com")

    assert registered.status_code == 200
    assert unknown.status_code == 200
    assert registered.json() == unknown.json()
    assert email_outbox == []


def test_only_the_hash_is_stored_and_the_raw_token_is_never_returned(
    client, auth_headers, email_outbox, db_session
):
    response = _forgot(client)
    raw_token = _token_from(email_outbox[0])
    me = client.get("/auth/me", headers=auth_headers).json()

    record = (
        db_session.query(PasswordResetToken)
        .filter(PasswordResetToken.user_id == me["id"])
        .order_by(PasswordResetToken.id.desc())
        .first()
    )
    assert record is not None
    assert record.token_hash == hashlib.sha256(raw_token.encode()).hexdigest()
    assert record.token_hash != raw_token
    assert raw_token not in response.text
    assert record.used_at is None
    assert record.expires_at > datetime.utcnow()


def test_forgot_password_requires_smtp_instead_of_faking_success(client, monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_FROM_EMAIL", raising=False)
    monkeypatch.delenv("SMTP_FROM", raising=False)

    response = _forgot(client, "someone@example.com")

    assert response.status_code == 503
    assert "correo" in response.json()["detail"].lower()


def test_forgot_password_is_rate_limited_per_ip(client, email_outbox, monkeypatch):
    monkeypatch.setenv("PASSWORD_RESET_RATE_LIMIT_FORGOT_IP", "2")
    monkeypatch.setenv("PASSWORD_RESET_RATE_LIMIT_FORGOT_IP_WINDOW", "900")
    _register(client, username="one", email="one@example.com")
    _register(client, username="two", email="two@example.com")

    assert _forgot(client, "one@example.com").status_code == 200
    assert _forgot(client, "two@example.com").status_code == 200
    limited = _forgot(client, "three@example.com")

    assert limited.status_code == 429
    assert "Retry-After" in limited.headers
    assert len(email_outbox) == 2


# ---------------------------------------------------------------------------
# Consuming the token
# ---------------------------------------------------------------------------


def test_valid_token_changes_the_password_and_rejects_the_old_one(
    client, auth_headers, email_outbox
):
    _forgot(client)
    raw_token = _token_from(email_outbox[0])

    reset = _reset(client, raw_token)
    assert reset.status_code == 200, reset.text

    assert _login(client, password=OLD_PASSWORD).status_code == 401
    new_login = _login(client, password=NEW_PASSWORD)
    assert new_login.status_code == 200, new_login.text
    assert new_login.json()["access_token"]


def test_reset_invalidates_existing_sessions(client, auth_headers, email_outbox):
    # The fixture token was minted before the reset.
    assert client.get("/auth/me", headers=auth_headers).status_code == 200

    _forgot(client)
    assert _reset(client, _token_from(email_outbox[0])).status_code == 200

    assert client.get("/auth/me", headers=auth_headers).status_code == 401


def test_token_is_single_use(client, auth_headers, email_outbox):
    _forgot(client)
    raw_token = _token_from(email_outbox[0])

    first = _reset(client, raw_token)
    second = _reset(client, raw_token, "AnotherPass789!")

    assert first.status_code == 200
    assert second.status_code == 400
    assert _login(client, password=NEW_PASSWORD).status_code == 200
    assert _login(client, password="AnotherPass789!").status_code == 401


def test_expired_token_is_rejected(client, auth_headers, email_outbox, db_session):
    _forgot(client)
    raw_token = _token_from(email_outbox[0])
    me = client.get("/auth/me", headers=auth_headers).json()

    record = (
        db_session.query(PasswordResetToken)
        .filter(PasswordResetToken.user_id == me["id"])
        .order_by(PasswordResetToken.id.desc())
        .first()
    )
    record.expires_at = datetime.utcnow() - timedelta(minutes=1)
    db_session.commit()

    response = _reset(client, raw_token)

    assert response.status_code == 400
    assert _login(client, password=OLD_PASSWORD).status_code == 200


def test_new_request_invalidates_previous_pending_tokens(client, auth_headers, email_outbox):
    _forgot(client)
    first_token = _token_from(email_outbox[0])
    _forgot(client)
    second_token = _token_from(email_outbox[1])
    assert first_token != second_token

    assert _reset(client, first_token).status_code == 400
    assert _reset(client, second_token).status_code == 200


def test_unknown_token_is_rejected(client, auth_headers):
    response = _reset(client, "x" * 32)
    assert response.status_code == 400
    assert client.get("/auth/me", headers=auth_headers).status_code == 200


def test_weak_new_password_is_rejected_without_burning_the_token(
    client, auth_headers, email_outbox
):
    _forgot(client)
    raw_token = _token_from(email_outbox[0])

    weak = _reset(client, raw_token, "weakpass")
    assert weak.status_code == 422

    assert _login(client, password=OLD_PASSWORD).status_code == 200
    assert _reset(client, raw_token, NEW_PASSWORD).status_code == 200
    assert _login(client, password=NEW_PASSWORD).status_code == 200


def test_short_or_missing_token_is_rejected(client, auth_headers):
    assert _reset(client, "short").status_code == 422
    assert client.post(
        "/auth/reset-password", json={"new_password": NEW_PASSWORD}
    ).status_code == 422


def test_reset_endpoint_is_rate_limited(client, auth_headers, email_outbox, monkeypatch):
    monkeypatch.setenv("PASSWORD_RESET_RATE_LIMIT_RESET_IP", "1")
    monkeypatch.setenv("PASSWORD_RESET_RATE_LIMIT_RESET_IP_WINDOW", "900")

    _forgot(client)
    raw_token = _token_from(email_outbox[0])

    assert _reset(client, raw_token).status_code == 200
    assert _reset(client, raw_token).status_code == 429


# ---------------------------------------------------------------------------
# No secret leakage
# ---------------------------------------------------------------------------


def test_passwords_and_tokens_are_never_logged(
    client, auth_headers, email_outbox, caplog
):
    caplog.set_level(logging.DEBUG)

    _forgot(client)
    raw_token = _token_from(email_outbox[0])
    assert _reset(client, raw_token).status_code == 200
    assert _login(client, password=NEW_PASSWORD).status_code == 200

    assert raw_token not in caplog.text
    assert OLD_PASSWORD not in caplog.text
    assert NEW_PASSWORD not in caplog.text
