"""Chat must cross the real MCP protocol and release its delegated credentials."""
from types import SimpleNamespace

import pytest
from mcp import ClientSession

from app import auth
from app.assistant import mcp_server, service

from .conftest import register

MUT = {"X-Reesatck-Request": "1"}
PROVIDER_KEY = "sk-test-mcp-context-not-real"
CONTEXT_ERROR = {"detail": "The assistant context is unavailable."}
PROVIDER_ERROR = {"detail": "The assistant provider is unavailable."}


@pytest.fixture
def accounts(client):
    users = {}
    for name in ("alice", "bob"):
        users[name] = register(client, username=name)
        content = client.post(
            "/api/contents",
            json={"title": f"{name}'s book", "creator": name, "kind": "book"},
            headers=MUT,
        )
        assert content.status_code == 201
        entry = client.post(
            "/api/collection", json={"content_id": content.json()["id"]}, headers=MUT,
        )
        assert entry.status_code == 201
        assert client.patch(
            f"/api/collection/{entry.json()['id']}",
            json={"review": f"{name}'s private review", "rating": 4}, headers=MUT,
        ).status_code == 200
        assert client.post(
            "/api/posts", json={"body": f"{name}'s reflection"}, headers=MUT,
        ).status_code == 201
        assert client.post("/api/auth/logout", headers=MUT).status_code == 204
    _login(client, "alice")
    return users


def _login(client, name):
    response = client.post(
        "/api/auth/login",
        json={"username": name, "password": "correct-horse-battery"}, headers=MUT,
    )
    assert response.status_code == 200


def _data(client):
    """Observe collection rows and public post counters through HTTP, not tables."""
    collection = client.get("/api/collection")
    posts = client.get("/api/posts")
    assert collection.status_code == posts.status_code == 200
    return collection.json(), posts.json()


@pytest.fixture
def observed(monkeypatch, session):
    state = SimpleNamespace(tokens=[], revoked=[], calls=[], messages=[], before_tool=None)
    issue = auth.issue_token
    revoke = auth.revoke_token
    call_tool = ClientSession.call_tool

    def issue_spy(db, user_id, kind="session", lifetime=auth.SESSION_LIFETIME):
        raw = issue(db, user_id, kind=kind, lifetime=lifetime)
        if kind == "mcp":
            assert auth.resolve_token(db, raw, kind="mcp").id == user_id
            assert auth.resolve_token(db, raw, kind="session") is None
            state.tokens.append((raw, user_id, lifetime))
        return raw

    def revoke_spy(db, raw):
        revoke(db, raw)
        state.revoked.append(raw)

    async def call_spy(client_session, name, arguments=None, *args, **kwargs):
        state.calls.append((name, arguments))
        if state.before_tool:
            state.before_tool(name)
        return await call_tool(client_session, name, arguments, *args, **kwargs)

    class Model:
        def invoke(self, messages):
            state.messages.append("\n".join(str(message.content) for message in messages))
            # Delegated database access is no longer needed during provider work.
            for raw, _, _ in state.tokens:
                assert auth.resolve_token(session, raw, kind="mcp") is None
            return SimpleNamespace(content="A scoped response.")

    monkeypatch.setenv("OPENAI_API_KEY", PROVIDER_KEY)
    monkeypatch.setenv("REESATCK_MCP_TOKEN", "unrelated-process-token")
    monkeypatch.setattr(auth, "issue_token", issue_spy)
    monkeypatch.setattr(auth, "revoke_token", revoke_spy)
    monkeypatch.setattr(ClientSession, "call_tool", call_spy)
    monkeypatch.setattr(service, "_build_model", Model)
    return state


def _assert_released(observed, session, owner_id):
    assert len(observed.tokens) == 1, "Chat must issue one temporary MCP token"
    raw, user_id, lifetime = observed.tokens[0]
    assert user_id == owner_id
    assert 0 < lifetime <= 300
    assert raw in observed.revoked
    assert auth.resolve_token(session, raw, kind="mcp") is None
    return raw


@pytest.mark.parametrize("owner,other", [("alice", "bob"), ("bob", "alice")])
def test_chat_reads_real_protocol_scoped_to_authenticated_owner(
    client, session, accounts, observed, monkeypatch, caplog, owner, other,
):
    _login(client, owner)
    before = _data(client)
    reader = mcp_server.collection_for

    def marked_tool_output(db, user_id):
        rows = reader(db, user_id)
        rows[0]["review"] += " (delivered through MCP)"
        return rows

    monkeypatch.setattr(mcp_server, "collection_for", marked_tool_output)
    response = client.post(
        "/api/assistant/chat",
        json={"message": "Summarize my library.", "user_id": accounts[other]["id"]},
        headers=MUT,
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"reply": "A scoped response."}
    assert observed.calls == [("get_collection", {}), ("get_my_posts", {})]
    raw = _assert_released(observed, session, accounts[owner]["id"])
    assert len(observed.messages) == 1
    context = observed.messages[0]
    for text in (f"{owner}'s book", f"{owner}'s private review", f"{owner}'s reflection"):
        assert text in context
    assert "(delivered through MCP)" in context
    assert other not in context
    for secret in (raw, PROVIDER_KEY, "unrelated-process-token"):
        assert secret not in context + response.text + caplog.text
    assert _data(client) == before
    assert client.get("/api/auth/me").json() == accounts[owner]


@pytest.mark.parametrize("failure_stage", ["construction", "invocation"])
def test_chat_releases_token_and_hides_provider_failure(
    client, session, accounts, observed, monkeypatch, caplog, failure_stage,
):
    before = _data(client)

    def fail():
        raw = observed.tokens[0][0] if observed.tokens else "token-not-issued"
        raise RuntimeError(f"Provider failure: {PROVIDER_KEY} {raw}")

    class BrokenModel:
        def invoke(self, _messages):
            fail()

    monkeypatch.setattr(service, "_build_model", fail if failure_stage == "construction" else BrokenModel)
    response = client.post("/api/assistant/chat", json={"message": "hello"}, headers=MUT)
    assert response.status_code == 503
    assert response.json() == PROVIDER_ERROR
    assert observed.calls == [("get_collection", {}), ("get_my_posts", {})]
    raw = _assert_released(observed, session, accounts["alice"]["id"])
    assert raw not in response.text + caplog.text
    assert PROVIDER_KEY not in response.text + caplog.text
    assert _data(client) == before
    assert client.get("/api/auth/me").json() == accounts["alice"]


@pytest.mark.parametrize("failed_tool,reader_name", [
    ("get_collection", "collection_for"), ("get_my_posts", "posts_for"),
])
def test_chat_tool_failure_is_closed_and_releases_token(
    client, session, accounts, observed, monkeypatch, caplog, failed_tool, reader_name,
):
    before = _data(client)

    def fail(_db, _user_id):
        raw = observed.tokens[0][0]
        raise RuntimeError(f"sqlite internal details {raw} {PROVIDER_KEY}")

    monkeypatch.setattr(mcp_server, reader_name, fail)
    response = client.post("/api/assistant/chat", json={"message": "hello"}, headers=MUT)
    assert response.status_code == 503
    assert response.json() == CONTEXT_ERROR
    expected = [("get_collection", {})]
    if failed_tool == "get_my_posts":
        expected.append(("get_my_posts", {}))
    assert observed.calls == expected
    assert observed.messages == [], "No model call or direct-data fallback after a tool error"
    raw = _assert_released(observed, session, accounts["alice"]["id"])
    for secret in (raw, PROVIDER_KEY, "sqlite internal details"):
        assert secret not in response.text + caplog.text
    assert _data(client) == before
    assert client.get("/api/auth/me").json() == accounts["alice"]


def test_chat_revalidates_token_on_second_tool_call(client, session, accounts, observed):
    before = _data(client)

    def revoke_before_posts(name):
        if name == "get_my_posts":
            auth.revoke_token(session, observed.tokens[0][0])

    observed.before_tool = revoke_before_posts
    response = client.post("/api/assistant/chat", json={"message": "hello"}, headers=MUT)
    assert response.status_code == 503
    assert response.json() == CONTEXT_ERROR
    assert observed.calls == [("get_collection", {}), ("get_my_posts", {})]
    assert observed.messages == []
    _assert_released(observed, session, accounts["alice"]["id"])
    assert _data(client) == before
    assert client.get("/api/auth/me").json() == accounts["alice"]


def test_chat_releases_token_when_protocol_initialization_fails(
    client, session, accounts, observed, monkeypatch, caplog,
):
    before = _data(client)

    async def fail(_client_session):
        raise ConnectionError(f"Transport failed {observed.tokens[0][0]} {PROVIDER_KEY}")

    monkeypatch.setattr(ClientSession, "initialize", fail)
    response = client.post("/api/assistant/chat", json={"message": "hello"}, headers=MUT)
    assert response.status_code == 503
    assert response.json() == CONTEXT_ERROR
    assert observed.calls == observed.messages == []
    raw = _assert_released(observed, session, accounts["alice"]["id"])
    assert raw not in response.text + caplog.text
    assert PROVIDER_KEY not in response.text + caplog.text
    assert _data(client) == before
    assert client.get("/api/auth/me").json() == accounts["alice"]


@pytest.mark.parametrize("invalid_result", ["error_flag", "invalid_structure"])
def test_chat_rejects_unsuccessful_protocol_results(
    client, session, accounts, observed, monkeypatch, invalid_result,
):
    before = _data(client)
    call_tool = ClientSession.call_tool

    async def corrupt(client_session, *args, **kwargs):
        result = await call_tool(client_session, *args, **kwargs)
        if invalid_result == "error_flag":
            result.isError = True
        else:
            result.structuredContent = {"result": "not a list of rows"}
        return result

    monkeypatch.setattr(ClientSession, "call_tool", corrupt)
    response = client.post("/api/assistant/chat", json={"message": "hello"}, headers=MUT)
    assert response.status_code == 503
    assert response.json() == CONTEXT_ERROR
    assert observed.calls == [("get_collection", {})]
    assert observed.messages == []
    _assert_released(observed, session, accounts["alice"]["id"])
    assert _data(client) == before
    assert client.get("/api/auth/me").json() == accounts["alice"]
