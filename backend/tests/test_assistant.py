"""Assistant and internal MCP permission tests."""
import asyncio
import os
import sys
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import Content, Entry, User

from .conftest import register

MUT = {"X-Reesatck-Request": "1"}


# ---------------------------------------------------------------------------
# HTTP surface: configuration is honest, never faked
# ---------------------------------------------------------------------------


def test_status_reports_unconfigured_without_key(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    resp = client.get("/api/assistant/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["configured"] is False
    assert body["model"] is None


def test_status_reports_configured_with_key(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    body = client.get("/api/assistant/status").json()
    assert body == {"configured": True, "model": "gpt-4o-mini"}


def test_chat_requires_authentication(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")

    def unexpected_issue(*_args, **_kwargs):
        raise AssertionError("Anonymous chat must not issue an MCP token")

    monkeypatch.setattr("app.auth.issue_token", unexpected_issue)
    resp = client.post("/api/assistant/chat", json={"message": "hello"}, headers=MUT)
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Not authenticated"}


def test_chat_returns_503_when_unconfigured(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    register(client)
    resp = client.post("/api/assistant/chat", json={"message": "hello"}, headers=MUT)
    assert resp.status_code == 503
    assert resp.json() == {"detail": "The assistant is not configured. Set OPENAI_API_KEY to enable it."}


def test_chat_never_calls_provider_when_unconfigured(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    register(client)

    def _explode(*_args, **_kwargs):
        raise AssertionError("Unconfigured chat must not construct a provider or issue an MCP token")

    monkeypatch.setattr("app.assistant.service._build_model", _explode)
    monkeypatch.setattr("app.auth.issue_token", _explode)
    resp = client.post("/api/assistant/chat", json={"message": "hi"}, headers=MUT)
    assert resp.status_code == 503


def test_chat_surfaces_provider_failure_as_503(client, monkeypatch):
    """A provider error must be an explicit 503, never a fake answer."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    register(client)

    class _Boom:
        def invoke(self, _messages):
            raise TimeoutError("network down")

    monkeypatch.setattr("app.assistant.service._build_model", lambda: _Boom())
    resp = client.post("/api/assistant/chat", json={"message": "hi"}, headers=MUT)
    assert resp.status_code == 503
    assert "unavailable" in resp.json()["detail"].lower()


def test_chat_returns_model_reply_without_provider_call(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    register(client)
    content = client.post(
        "/api/contents",
        json={"title": "Cosmos", "creator": "Carl Sagan", "kind": "book", "total_units": 365, "unit_label": "pages"},
        headers=MUT,
    ).json()
    entry = client.post("/api/collection", json={"content_id": content["id"]}, headers=MUT).json()
    client.patch(f"/api/collection/{entry['id']}", json={"progress": 120, "status": "in_progress"}, headers=MUT)

    seen = {}

    class _Reply:
        content = "You are 120 pages into Cosmos."

    class _Model:
        def invoke(self, messages):
            seen["context"] = " ".join(str(getattr(m, "content", "")) for m in messages)
            return _Reply()

    monkeypatch.setattr("app.assistant.service._build_model", lambda: _Model())
    resp = client.post("/api/assistant/chat", json={"message": "how am I doing?"}, headers=MUT)
    assert resp.status_code == 200, resp.text
    assert "Cosmos" in resp.json()["reply"]
    assert "Cosmos" in seen["context"]


def test_build_context_only_uses_own_data(client, session):
    register(client, username="alice")
    from app.assistant import service

    content = client.post(
        "/api/contents",
        json={"title": "Cosmos", "creator": "Carl Sagan", "kind": "book", "total_units": 365, "unit_label": "pages"},
        headers=MUT,
    ).json()
    client.post("/api/collection", json={"content_id": content["id"]}, headers=MUT)
    client.post("/api/posts", json={"body": "Only Alice should see this."}, headers=MUT)

    alice = session.exec(select(User).where(User.username == "alice")).first()
    context = service.build_context(session, alice)
    assert "Cosmos" in context
    assert "Only Alice should see this." in context

    client.post("/api/auth/logout", headers=MUT)
    register(client, username="bob")
    bob = session.exec(select(User).where(User.username == "bob")).first()
    bob_context = service.build_context(session, bob)
    assert "Cosmos" not in bob_context
    assert "Only Alice" not in bob_context


# ---------------------------------------------------------------------------
# Internal MCP: real stdio transport, token-scoped
# ---------------------------------------------------------------------------


@pytest.fixture(name="mcp_db")
def mcp_db_fixture():
    """A real file database shared with the MCP subprocess, outside the repo."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="reesatck-mcp-"))
    db_path = tmp_dir / "mcp.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    url = f"sqlite:///{db_path}"
    yield engine, url
    engine.dispose()
    # Scratch dir is retained; the parent orchestrator owns cleanup.


@asynccontextmanager
async def _mcp_session(url: str, token: str):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    env = dict(os.environ)
    env["REESATCK_MCP_TOKEN"] = token
    env["DATABASE_URL"] = url
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.assistant.mcp_server"],
        env=env,
        cwd=str(Path(__file__).resolve().parent.parent),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


def _payload(result):
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict) and "result" in structured:
        return structured["result"]
    if isinstance(structured, list):
        return structured
    content = getattr(result, "content", None) or []
    for block in content:
        text = getattr(block, "text", None)
        if text:
            import json

            parsed = json.loads(text)
            if isinstance(parsed, dict) and "result" in parsed:
                return parsed["result"]
            return parsed
    raise AssertionError(f"unexpected MCP payload: {result!r}")


def _seed_two_users(engine):
    from app.auth import issue_token

    with Session(engine) as session:
        alice = User(username="alice", display_name="Alice", password_hash="x")
        bob = User(username="bob", display_name="Bob", password_hash="x")
        cosmos = Content(title="Cosmos", creator="Carl Sagan", kind="book", total_units=365, unit_label="pages")
        milk = Content(title="Milk and Honey", creator="Rupi Kaur", kind="book")
        session.add_all([alice, bob, cosmos, milk])
        session.commit()
        for row in (alice, bob, cosmos, milk):
            session.refresh(row)
        session.add(Entry(user_id=alice.id, content_id=cosmos.id, status="in_progress", progress=120))
        session.add(Entry(user_id=bob.id, content_id=milk.id, status="planned"))
        session.commit()
        alice_token = issue_token(session, alice.id, kind="mcp", lifetime=300)
        bob_token = issue_token(session, bob.id, kind="mcp", lifetime=300)
    return alice_token, bob_token


def test_mcp_tools_respect_token_scope(mcp_db):
    engine, url = mcp_db
    alice_token, bob_token = _seed_two_users(engine)

    async def _collect(token):
        async with _mcp_session(url, token) as session:
            result = await session.call_tool("get_collection", {})
            return _payload(result)

    alice_titles = [entry["content"]["title"] for entry in asyncio.run(_collect(alice_token))]
    bob_titles = [entry["content"]["title"] for entry in asyncio.run(_collect(bob_token))]

    assert alice_titles == ["Cosmos"]
    assert bob_titles == ["Milk and Honey"]


def test_mcp_posts_are_limited_to_author(mcp_db):
    engine, url = mcp_db
    from app.auth import issue_token
    from app.models import Post

    with Session(engine) as session:
        alice = User(username="alice", display_name="Alice", password_hash="x")
        bob = User(username="bob", display_name="Bob", password_hash="x")
        session.add_all([alice, bob])
        session.commit()
        session.refresh(alice)
        session.refresh(bob)
        session.add(Post(user_id=alice.id, body="Alice thought"))
        session.add(Post(user_id=bob.id, body="Bob thought"))
        session.commit()
        alice_token = issue_token(session, alice.id, kind="mcp", lifetime=300)

    async def _posts():
        async with _mcp_session(url, alice_token) as session:
            return _payload(await session.call_tool("get_my_posts", {}))

    bodies = [post["body"] for post in asyncio.run(_posts())]
    assert bodies == ["Alice thought"]


def _error_text(result) -> str:
    """A tool error is reported as isError + a text block, not an exception."""
    assert getattr(result, "isError", False) is True, f"expected tool error, got {result!r}"
    parts = []
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return " ".join(parts)


def test_mcp_rejects_invalid_token(mcp_db):
    _, url = mcp_db
    _seed_two_users(mcp_db[0])

    async def _collect():
        async with _mcp_session(url, "not-a-real-token") as session:
            return await session.call_tool("get_collection", {})

    message = _error_text(asyncio.run(_collect()))
    assert "Access denied" in message
    # No internal detail may leak back to the model.
    assert "sqlite" not in message.lower()
    assert "auth_tokens" not in message.lower()
    assert "select" not in message.lower()


def test_mcp_rejects_session_token(mcp_db):
    """A browser session token must not unlock MCP tools."""
    engine, url = mcp_db
    from app.auth import issue_token

    with Session(engine) as session:
        user = User(username="carol", display_name="Carol", password_hash="x")
        session.add(user)
        session.commit()
        session.refresh(user)
        session_token = issue_token(session, user.id, kind="session", lifetime=300)

    async def _collect():
        async with _mcp_session(url, session_token) as session:
            return await session.call_tool("get_collection", {})

    message = _error_text(asyncio.run(_collect()))
    assert "Access denied" in message
    assert "auth_tokens" not in message.lower()


def test_mcp_rejects_missing_token(mcp_db):
    _, url = mcp_db
    _seed_two_users(mcp_db[0])

    async def _collect():
        async with _mcp_session(url, "") as session:
            return await session.call_tool("get_collection", {})

    message = _error_text(asyncio.run(_collect()))
    assert "Access denied" in message


def test_mcp_exposes_only_read_tools(mcp_db):
    """The tool surface stays read-only: no write or list-user tools exist."""
    engine, url = mcp_db
    alice_token, _ = _seed_two_users(engine)

    async def _list():
        async with _mcp_session(url, alice_token) as session:
            return await session.list_tools()

    tools = asyncio.run(_list())
    names = sorted(t.name for t in tools.tools)
    assert names == ["get_collection", "get_my_posts"]
    for tool in tools.tools:
        schema = tool.inputSchema or {}
        assert "user_id" not in schema.get("properties", {})


def test_mcp_rejects_expired_token(mcp_db):
    """The shared server factory preserves stdio expiry enforcement."""
    from app.auth import issue_token

    engine, url = mcp_db
    with Session(engine) as session:
        user = User(username="expired", display_name="Expired", password_hash="x")
        session.add(user)
        session.commit()
        token = issue_token(session, user.id, kind="mcp", lifetime=-1)

    async def _collect():
        async with _mcp_session(url, token) as session:
            return await session.call_tool("get_collection", {})

    message = _error_text(asyncio.run(_collect()))
    assert "Access denied" in message
    assert token not in message
