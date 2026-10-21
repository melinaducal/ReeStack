"""Independent probes for the assistant/MCP credential lifecycle.

These assert the security invariants directly instead of trusting the
implementation's own tests: context must travel only through the real MCP
protocol, the delegated credential is request-local and dead before any
provider work, the request body can never choose the account, failures stay
sanitized, and no chat path mutates stored data.
"""
import asyncio
import hashlib
import json
import time
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from app import auth, services
from app.assistant import mcp_server, service
from app.models import AuthToken, Content, Entry, Post, User
from app.schemas import AssistantChat

from .conftest import register

MUT = {"X-Reesatck-Request": "1"}
PROVIDER_KEY = "sk-probe-key-not-real-123"
RAW_SECRET = "RAW-TOKEN-MATERIAL-XYZ"


class _Reply:
    content = "probe reply"


class _Model:
    def invoke(self, messages):
        return _Reply()


@asynccontextmanager
async def _noop_lifespan(app):
    yield


def _seed(client, name, title):
    content = client.post(
        "/api/contents",
        json={"title": title, "creator": name, "kind": "book"},
        headers=MUT,
    ).json()
    client.post("/api/collection", json={"content_id": content["id"]}, headers=MUT)
    client.post("/api/posts", json={"body": f"{title} reflection"}, headers=MUT)


def _flat_text(exc):
    """Flatten an ExceptionGroup into the messages of its leaves."""
    parts = []
    stack = [exc]
    while stack:
        item = stack.pop()
        if isinstance(item, BaseExceptionGroup):
            stack.extend(item.exceptions)
        else:
            parts.append(f"{type(item).__name__}: {item}")
    return " | ".join(parts)


# ---------------------------------------------------------------- context path


def test_context_reads_only_through_the_mcp_server(client, monkeypatch):
    """The assistant must reach collection/posts only through the MCP tools."""
    register(client, username="alice")
    calls = []

    def direct_reader(session, user_id):
        calls.append("DIRECT")
        return []

    def mcp_reader(session, user_id):
        calls.append("MCP")
        return []

    monkeypatch.setattr(services, "collection_for", direct_reader)
    monkeypatch.setattr(services, "posts_for", direct_reader)
    monkeypatch.setattr(mcp_server, "collection_for", mcp_reader)
    monkeypatch.setattr(mcp_server, "posts_for", mcp_reader)
    monkeypatch.setenv("OPENAI_API_KEY", PROVIDER_KEY)
    monkeypatch.setattr(service, "_build_model", lambda: _Model())

    resp = client.post("/api/assistant/chat", json={"message": "hi"}, headers=MUT)
    assert resp.status_code == 200, resp.text
    assert calls == ["MCP", "MCP"], f"unexpected read path: {calls}"


def test_service_module_has_no_direct_data_reader():
    """Static half: service.py must not bind the data readers or models."""
    for name in ("collection_for", "posts_for", "serialize_posts", "entry_to_dict"):
        assert not hasattr(service, name), f"service.py exposes {name}"
    assert not hasattr(service, "select"), "service.py imports a query builder"
    assert not hasattr(service, "Entry"), "service.py imports the data model"


def test_no_fallback_when_the_mcp_path_fails(client, monkeypatch):
    """A broken MCP path must fail closed; there is no direct-DB fallback."""
    register(client, username="alice")

    def boom(*_a, **_k):
        raise RuntimeError("mcp transport down")

    monkeypatch.setattr(service, "read_context", boom)
    monkeypatch.setenv("OPENAI_API_KEY", PROVIDER_KEY)

    def explode():
        raise AssertionError("provider must not be built without context")

    monkeypatch.setattr(service, "_build_model", explode)
    resp = client.post("/api/assistant/chat", json={"message": "hi"}, headers=MUT)
    assert resp.status_code == 503, resp.text
    assert resp.json() == {"detail": "The assistant context is unavailable."}


# ---------------------------------------------------------------- credential scope


def test_token_kind_isolation_and_lifetime(engine):
    with Session(engine) as s:
        user = User(username="kindprobe", display_name="Kind", password_hash="x")
        s.add(user)
        s.commit()
        s.refresh(user)
        mcp_raw = auth.issue_token(s, user.id, kind="mcp", lifetime=service.MCP_TOKEN_LIFETIME)
        session_raw = auth.issue_token(s, user.id, kind="session", lifetime=300)

        assert auth.resolve_token(s, mcp_raw, kind="mcp").id == user.id
        assert auth.resolve_token(s, mcp_raw, kind="session") is None
        assert auth.resolve_token(s, session_raw, kind="session").id == user.id
        assert auth.resolve_token(s, session_raw, kind="mcp") is None

        record = s.get(AuthToken, auth._hash_token(mcp_raw))
        ttl = record.expires_at - time.time()
        assert 0 < ttl <= 300, f"mcp token ttl={ttl}"
        assert service.MCP_TOKEN_LIFETIME <= 300


def test_expired_token_is_rejected(engine):
    with Session(engine) as s:
        user = User(username="expiredprobe", display_name="E", password_hash="x")
        s.add(user)
        s.commit()
        s.refresh(user)
        raw = auth.issue_token(s, user.id, kind="mcp", lifetime=-1)
        assert auth.resolve_token(s, raw, kind="mcp") is None


def test_mcp_token_cannot_act_as_a_browser_session(engine, client):
    with Session(engine) as s:
        user = User(username="cookieprobe", display_name="Cookie", password_hash="x")
        s.add(user)
        s.commit()
        s.refresh(user)
        mcp_raw = auth.issue_token(s, user.id, kind="mcp", lifetime=300)
    client.cookies.clear()
    client.cookies.set("reesatck_session", mcp_raw)
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401, resp.text
    assert resp.json() == {"detail": "Not authenticated"}


def test_browser_session_token_cannot_drive_the_mcp_tools(engine):
    with Session(engine) as s:
        user = User(username="sesstoken", display_name="S", password_hash="x")
        s.add(user)
        s.commit()
        s.refresh(user)
        raw = auth.issue_token(s, user.id, kind="session", lifetime=300)
    with pytest.raises(BaseException) as excinfo:
        service.read_context(engine, raw)
    flat = _flat_text(excinfo.value)
    assert "MCP tool failed" in flat, flat
    assert raw not in flat


def test_mcp_tool_rejects_a_session_token_at_the_protocol_level(engine):
    """Direct protocol check: a session-kind token gets a generic refusal."""
    from mcp.shared.memory import create_connected_server_and_client_session

    with Session(engine) as s:
        user = User(username="proto", display_name="P", password_hash="x")
        s.add(user)
        s.commit()
        s.refresh(user)
        raw = auth.issue_token(s, user.id, kind="session", lifetime=300)

    async def call():
        server = mcp_server.create_server(engine, lambda: raw)
        async with create_connected_server_and_client_session(
            server, read_timeout_seconds=timedelta(seconds=15)
        ) as client:
            return await client.call_tool("get_collection", {})

    result = asyncio.run(call())
    assert result.isError is True, f"expected refusal, got {result!r}"
    text = " ".join(b.text for b in (result.content or []) if getattr(b, "text", None))
    assert "Access denied" in text, text
    for secret in ("sqlite", "auth_tokens", "select", raw):
        assert secret not in text.lower(), f"leaked {secret!r}: {text}"


def test_chat_leaves_no_delegated_credential_behind(client, engine, monkeypatch):
    register(client, username="alice")
    monkeypatch.setenv("OPENAI_API_KEY", PROVIDER_KEY)
    monkeypatch.setattr(service, "_build_model", lambda: _Model())
    resp = client.post("/api/assistant/chat", json={"message": "hi"}, headers=MUT)
    assert resp.status_code == 200, resp.text
    with Session(engine) as s:
        mcp_rows = s.exec(select(AuthToken).where(AuthToken.kind == "mcp")).all()
        session_rows = s.exec(select(AuthToken).where(AuthToken.kind == "session")).all()
    assert mcp_rows == [], "a delegated MCP token survived the request"
    assert len(session_rows) == 1, "the browser session token was revoked by the chat"


def test_each_request_issues_its_own_credential(client, monkeypatch):
    """Request-local: two chats must not share one delegated credential."""
    register(client, username="alice")
    monkeypatch.setenv("OPENAI_API_KEY", PROVIDER_KEY)
    issued = []
    original_issue = auth.issue_token

    def issue_spy(db, user_id, kind="session", lifetime=auth.SESSION_LIFETIME):
        raw = original_issue(db, user_id, kind=kind, lifetime=lifetime)
        if kind == "mcp":
            issued.append(raw)
        return raw

    monkeypatch.setattr(auth, "issue_token", issue_spy)
    monkeypatch.setattr(service, "_build_model", lambda: _Model())
    assert client.post("/api/assistant/chat", json={"message": "1"}, headers=MUT).status_code == 200
    assert client.post("/api/assistant/chat", json={"message": "2"}, headers=MUT).status_code == 200
    assert len(issued) == 2
    assert issued[0] != issued[1]


def test_delegated_credential_is_bound_to_the_authenticated_user(client, monkeypatch):
    """The delegated credential must carry the cookie-authenticated user id."""
    alice = register(client, username="alice")
    client.post("/api/auth/logout", headers=MUT)
    bob = register(client, username="bob")
    _seed(client, "bob", "Bob Book")
    client.post("/api/auth/logout", headers=MUT)
    client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "correct-horse-battery"},
        headers=MUT,
    )
    monkeypatch.setenv("OPENAI_API_KEY", PROVIDER_KEY)
    issued = []
    original_issue = auth.issue_token

    def issue_spy(db, user_id, kind="session", lifetime=auth.SESSION_LIFETIME):
        raw = original_issue(db, user_id, kind=kind, lifetime=lifetime)
        if kind == "mcp":
            issued.append((raw, user_id))
        return raw

    monkeypatch.setattr(auth, "issue_token", issue_spy)
    monkeypatch.setattr(service, "_build_model", lambda: _Model())
    resp = client.post("/api/assistant/chat", json={"message": "hi"}, headers=MUT)
    assert resp.status_code == 200, resp.text
    assert len(issued) == 1
    raw, user_id = issued[0]
    assert user_id == alice["id"], f"token bound to {user_id}, authenticated user is {alice['id']}"
    assert user_id != bob["id"]


# ---------------------------------------------------------------- revocation ordering


def test_credential_is_dead_before_the_provider_is_built(client, engine, monkeypatch):
    register(client, username="alice")
    monkeypatch.setenv("OPENAI_API_KEY", PROVIDER_KEY)
    state = {}
    original_issue = auth.issue_token

    def issue_spy(db, user_id, kind="session", lifetime=auth.SESSION_LIFETIME):
        raw = original_issue(db, user_id, kind=kind, lifetime=lifetime)
        if kind == "mcp":
            state["raw"] = raw
            state["lifetime"] = lifetime
        return raw

    monkeypatch.setattr(auth, "issue_token", issue_spy)

    def alive(kind="mcp"):
        with Session(engine) as s:
            return auth.resolve_token(s, state["raw"], kind=kind)

    class _Watching(_Model):
        def invoke(self, messages):
            state["alive_at_invoke"] = alive()
            return _Reply()

    def build():
        state["alive_at_build"] = alive()
        return _Watching()

    monkeypatch.setattr(service, "_build_model", build)
    resp = client.post("/api/assistant/chat", json={"message": "hi"}, headers=MUT)
    assert resp.status_code == 200, resp.text
    assert state["alive_at_build"] is None, "token still alive at provider construction"
    assert state["alive_at_invoke"] is None, "token still alive at provider invocation"
    assert 0 < state["lifetime"] <= 300


def test_credential_is_revoked_when_the_tool_fails(client, engine, monkeypatch):
    register(client, username="alice")
    monkeypatch.setenv("OPENAI_API_KEY", PROVIDER_KEY)
    state = {}
    original_issue = auth.issue_token

    def issue_spy(db, user_id, kind="session", lifetime=auth.SESSION_LIFETIME):
        raw = original_issue(db, user_id, kind=kind, lifetime=lifetime)
        if kind == "mcp":
            state["raw"] = raw
        return raw

    monkeypatch.setattr(auth, "issue_token", issue_spy)

    def boom(_db, _user_id):
        raise RuntimeError("sqlite3.OperationalError: no such table: entries")

    monkeypatch.setattr(mcp_server, "collection_for", boom)

    def explode():
        raise AssertionError("provider must not be built after a context failure")

    monkeypatch.setattr(service, "_build_model", explode)
    resp = client.post("/api/assistant/chat", json={"message": "hi"}, headers=MUT)
    assert resp.status_code == 503, resp.text
    with Session(engine) as s:
        assert auth.resolve_token(s, state["raw"], kind="mcp") is None


# ---------------------------------------------------------------- body cannot choose account


@pytest.mark.parametrize(
    "extra",
    [
        {"user_id": 999},
        {"user_id": "999"},
        {"userId": 999},
        {"owner_id": 999},
        {"account_id": 999},
        {"user": 999},
    ],
)
def test_request_body_cannot_select_the_account(client, monkeypatch, extra):
    alice = register(client, username="alice")
    client.post("/api/auth/logout", headers=MUT)
    bob = register(client, username="bob")
    _seed(client, "bob", "Bob Book")
    client.post("/api/auth/logout", headers=MUT)
    client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "correct-horse-battery"},
        headers=MUT,
    )
    monkeypatch.setenv("OPENAI_API_KEY", PROVIDER_KEY)
    seen = {}

    class _Spy(_Model):
        def invoke(self, messages):
            seen["context"] = "\n".join(str(m.content) for m in messages)
            return _Reply()

    monkeypatch.setattr(service, "_build_model", lambda: _Spy())
    payload = {"message": "hi"}
    payload.update(extra)
    resp = client.post("/api/assistant/chat", json=payload, headers=MUT)
    assert resp.status_code == 200, resp.text
    assert "Bob Book" not in seen["context"]
    assert "Bob Book reflection" not in seen["context"]
    me = client.get("/api/auth/me")
    assert me.status_code == 200, me.text
    assert me.json()["id"] == alice["id"]
    assert me.json()["id"] != bob["id"]


def test_chat_schema_exposes_only_message():
    assert set(AssistantChat.model_fields) == {"message"}
    parsed = AssistantChat(message="hi", user_id=7)
    assert not hasattr(parsed, "user_id")
    assert not parsed.model_extra


# ---------------------------------------------------------------- sanitized failures


def test_tool_failure_is_sanitized(client, caplog, monkeypatch):
    register(client, username="alice")
    monkeypatch.setenv("OPENAI_API_KEY", PROVIDER_KEY)

    def boom(_db, _user_id):
        raise RuntimeError(
            "sqlite3.OperationalError: no such table: auth_tokens "
            "SELECT * FROM auth_tokens WHERE token_hash = " + RAW_SECRET
        )

    monkeypatch.setattr(mcp_server, "collection_for", boom)
    with caplog.at_level("DEBUG"):
        resp = client.post("/api/assistant/chat", json={"message": "hi"}, headers=MUT)
    assert resp.status_code == 503, resp.text
    assert resp.json() == {"detail": "The assistant context is unavailable."}
    haystack = resp.text + caplog.text + repr(resp.headers)
    for secret in ("sqlite", "SELECT", "auth_tokens", RAW_SECRET, PROVIDER_KEY):
        assert secret not in haystack, f"leaked {secret!r}"


def test_provider_failure_is_sanitized(client, caplog, monkeypatch):
    register(client, username="alice")
    monkeypatch.setenv("OPENAI_API_KEY", PROVIDER_KEY)

    def boom():
        raise RuntimeError(f"openai.AuthenticationError: bad key {PROVIDER_KEY} {RAW_SECRET}")

    monkeypatch.setattr(service, "_build_model", boom)
    with caplog.at_level("DEBUG"):
        resp = client.post("/api/assistant/chat", json={"message": "hi"}, headers=MUT)
    assert resp.status_code == 503, resp.text
    assert resp.json() == {"detail": "The assistant provider is unavailable."}
    haystack = resp.text + caplog.text + repr(resp.headers)
    for secret in ("openai", "AuthenticationError", RAW_SECRET, PROVIDER_KEY):
        assert secret not in haystack, f"leaked {secret!r}"


def test_successful_context_carries_no_credentials(client, monkeypatch, caplog):
    """The prompt handed to the model must not embed the token or the key."""
    register(client, username="alice")
    _seed(client, "alice", "Alice Book")
    monkeypatch.setenv("OPENAI_API_KEY", PROVIDER_KEY)
    state = {}
    original_issue = auth.issue_token

    def issue_spy(db, user_id, kind="session", lifetime=auth.SESSION_LIFETIME):
        raw = original_issue(db, user_id, kind=kind, lifetime=lifetime)
        if kind == "mcp":
            state["raw"] = raw
        return raw

    monkeypatch.setattr(auth, "issue_token", issue_spy)
    seen = {}

    class _Spy(_Model):
        def invoke(self, messages):
            seen["context"] = "\n".join(str(m.content) for m in messages)
            return _Reply()

    monkeypatch.setattr(service, "_build_model", lambda: _Spy())
    resp = client.post("/api/assistant/chat", json={"message": "hi"}, headers=MUT)
    assert resp.status_code == 200, resp.text
    haystack = seen["context"] + resp.text + caplog.text
    for secret in (state["raw"], PROVIDER_KEY, "auth_tokens"):
        assert secret not in haystack, f"leaked {secret!r}"


def test_unconfigured_chat_never_builds_a_provider(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    register(client, username="alice")

    def explode(*_a, **_k):
        raise AssertionError("no provider may be built without credentials")

    monkeypatch.setattr(service, "_build_model", explode)
    monkeypatch.setattr(auth, "issue_token", explode)
    resp = client.post("/api/assistant/chat", json={"message": "hi"}, headers=MUT)
    assert resp.status_code == 503, resp.text
    assert resp.json() == {
        "detail": "The assistant is not configured. Set OPENAI_API_KEY to enable it."
    }


# ---------------------------------------------------------------- data integrity


def _row_digest(engine, tables):
    parts = []
    with Session(engine) as s:
        for table in tables:
            rows = s.exec(select(table)).all()
            for row in rows:
                parts.append(
                    table.__name__ + ":" + json.dumps(
                        {k: str(v) for k, v in row.model_dump().items()}, sort_keys=True
                    )
                )
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


@pytest.fixture(name="file_app")
def file_app_fixture(tmp_path):
    db_path = Path(tmp_path) / "probe.db"
    file_engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(file_engine)
    from app.db import get_session
    from app.main import create_app

    app = create_app()
    app.router.lifespan_context = _noop_lifespan

    def override_get_session():
        with Session(file_engine) as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as client:
        yield client, file_engine, db_path
    app.dependency_overrides.clear()
    file_engine.dispose()


def test_unauthenticated_command_leaves_the_data_file_byte_identical(file_app):
    client, file_engine, db_path = file_app
    register(client, username="alice")
    client.cookies.clear()
    before = hashlib.sha256(db_path.read_bytes()).hexdigest()
    resp = client.post("/api/assistant/chat", json={"message": "hi"}, headers=MUT)
    assert resp.status_code == 401, resp.text
    after = hashlib.sha256(db_path.read_bytes()).hexdigest()
    assert before == after, "an unauthenticated chat mutated the data file"


def test_unconfigured_command_leaves_the_data_file_byte_identical(file_app, monkeypatch):
    client, file_engine, db_path = file_app
    register(client, username="alice")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    before = hashlib.sha256(db_path.read_bytes()).hexdigest()
    resp = client.post("/api/assistant/chat", json={"message": "hi"}, headers=MUT)
    assert resp.status_code == 503, resp.text
    after = hashlib.sha256(db_path.read_bytes()).hexdigest()
    assert before == after, "an unconfigured chat mutated the data file"


def test_failing_command_keeps_user_data_byte_identical(file_app, monkeypatch):
    client, file_engine, db_path = file_app
    register(client, username="alice")
    _seed(client, "alice", "Alice Book")
    monkeypatch.setenv("OPENAI_API_KEY", PROVIDER_KEY)

    def boom(_db, _user_id):
        raise RuntimeError("sqlite3.OperationalError: no such table: entries")

    monkeypatch.setattr(mcp_server, "collection_for", boom)
    data_before = _row_digest(file_engine, [User, Content, Entry, Post])
    tokens_before = _row_digest(file_engine, [AuthToken])
    resp = client.post("/api/assistant/chat", json={"message": "hi"}, headers=MUT)
    assert resp.status_code == 503, resp.text
    assert _row_digest(file_engine, [User, Content, Entry, Post]) == data_before
    assert _row_digest(file_engine, [AuthToken]) == tokens_before


def test_successful_command_keeps_user_data_byte_identical(file_app, monkeypatch):
    client, file_engine, db_path = file_app
    register(client, username="alice")
    _seed(client, "alice", "Alice Book")
    monkeypatch.setenv("OPENAI_API_KEY", PROVIDER_KEY)
    monkeypatch.setattr(service, "_build_model", lambda: _Model())
    data_before = _row_digest(file_engine, [User, Content, Entry, Post])
    tokens_before = _row_digest(file_engine, [AuthToken])
    resp = client.post("/api/assistant/chat", json={"message": "hi"}, headers=MUT)
    assert resp.status_code == 200, resp.text
    assert _row_digest(file_engine, [User, Content, Entry, Post]) == data_before
    assert _row_digest(file_engine, [AuthToken]) == tokens_before
