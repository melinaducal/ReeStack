"""End-to-end API tests against the public HTTP interface."""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import AuthToken, Content, Entry, User

from .conftest import register

MUT = {"X-Reesatck-Request": "1"}


def _auth(client, username="reader"):
    user = register(client, username=username)
    return user


# ---------------------------------------------------------------------------
# Health and auth
# ---------------------------------------------------------------------------


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_register_sets_cookie_and_me(client):
    user = _auth(client)
    assert user["username"] == "reader"
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["id"] == user["id"]


def test_register_rejects_duplicate_username(client):
    _auth(client)
    resp = client.post(
        "/api/auth/register",
        json={"username": "reader", "display_name": "Other", "password": "correct-horse-battery"},
    )
    assert resp.status_code == 409


def test_register_rejects_short_password(client):
    resp = client.post(
        "/api/auth/register",
        json={"username": "newuser", "display_name": "New", "password": "short"},
    )
    assert resp.status_code == 422


def test_login_and_bad_credentials(client):
    _auth(client)
    client.post("/api/auth/logout", headers=MUT)
    resp = client.post("/api/auth/login", json={"username": "reader", "password": "correct-horse-battery"})
    assert resp.status_code == 200
    resp = client.post("/api/auth/login", json={"username": "reader", "password": "wrong-password"})
    assert resp.status_code == 401


def test_me_requires_auth(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_no_password_or_token_in_response(client):
    resp = client.post(
        "/api/auth/register",
        json={"username": "safeuser", "display_name": "Safe", "password": "correct-horse-battery"},
    )
    body = resp.text.lower()
    assert "password" not in body
    assert "token" not in body
    assert "correct-horse" not in body


def test_logout_revokes_token(client):
    _auth(client)
    # Capture the raw cookie value before logout.
    raw = client.cookies.get("reesatck_session")
    assert raw
    resp = client.post("/api/auth/logout", headers=MUT)
    assert resp.status_code == 204
    assert resp.content == b""
    assert 'reesatck_session=' in resp.headers["set-cookie"]
    assert 'Max-Age=0' in resp.headers["set-cookie"]
    assert client.cookies.get("reesatck_session") is None
    assert client.get("/api/auth/me").status_code == 401
    # The raw token must no longer resolve.
    client.cookies.clear()
    client.cookies.set("reesatck_session", raw)
    assert client.get("/api/auth/me").status_code == 401


# ---------------------------------------------------------------------------
# CSRF / origin guards
# ---------------------------------------------------------------------------


def test_mutation_requires_header_or_rejects_foreign_origin(client):
    _auth(client)
    # Foreign origin rejected even with header.
    resp = client.post(
        "/api/contents",
        json={"title": "T", "creator": "C", "kind": "book"},
        headers={**MUT, "Origin": "https://evil.example"},
    )
    assert resp.status_code == 403
    # Missing header with a browser-like origin is also rejected.
    client.post("/api/contents", json={"title": "T", "creator": "C", "kind": "book"}, headers={"Origin": "https://evil.example"})
    assert client.post(
        "/api/contents",
        json={"title": "T2", "creator": "C", "kind": "book"},
        headers={"Origin": "http://localhost:5173"},
    ).status_code == 403


def test_mcp_token_cannot_call_browser_api(client, session):
    _auth(client)
    user = session.exec(select(User).where(User.username == "reader")).first()
    from app.auth import issue_token

    mcp_raw = issue_token(session, user.id, kind="mcp", lifetime=300)
    client.cookies.clear()
    client.cookies.set("reesatck_session", mcp_raw)
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/collection").status_code == 401


def test_expired_token_rejected(client, session):
    _auth(client)
    user = session.exec(select(User).where(User.username == "reader")).first()
    import hashlib

    raw = "expired-token-value"
    session.add(
        AuthToken(
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            user_id=user.id,
            kind="session",
            expires_at=int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
        )
    )
    session.commit()
    client.cookies.clear()
    client.cookies.set("reesatck_session", raw)
    assert client.get("/api/auth/me").status_code == 401


# ---------------------------------------------------------------------------
# Contents catalog
# ---------------------------------------------------------------------------


def test_create_and_list_contents(client):
    _auth(client)
    resp = client.post(
        "/api/contents",
        json={"title": "Dune", "creator": "Frank Herbert", "kind": "book", "total_units": 688, "unit_label": "pages"},
        headers=MUT,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Dune"
    listed = client.get("/api/contents", params={"q": "dune", "kind": "book"}).json()
    assert len(listed) == 1
    assert listed[0]["id"] == data["id"]


def test_contents_requires_auth_to_create(client):
    resp = client.post(
        "/api/contents",
        json={"title": "X", "creator": "Y", "kind": "book"},
        headers=MUT,
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Personal collection
# ---------------------------------------------------------------------------


def _add_content(client, title="Severance", kind="series", total_units=19, unit_label="episodes"):
    resp = client.post(
        "/api/contents",
        json={"title": title, "creator": "Dan Erickson", "kind": kind, "total_units": total_units, "unit_label": unit_label},
        headers=MUT,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_save_is_idempotent_and_preserves_progress(client):
    _auth(client)
    content = _add_content(client)
    first = client.post("/api/collection", json={"content_id": content["id"]}, headers=MUT)
    assert first.status_code == 201
    entry_id = first.json()["id"]
    client.patch(f"/api/collection/{entry_id}", json={"progress": 7, "status": "in_progress"}, headers=MUT)
    second = client.post("/api/collection", json={"content_id": content["id"]}, headers=MUT)
    assert second.status_code == 200
    assert second.json()["id"] == entry_id
    assert second.json()["progress"] == 7


def test_progress_rating_review_roundtrip(client):
    _auth(client)
    content = _add_content(client, title="Kind of Blue", kind="music", total_units=5, unit_label="tracks")
    entry = client.post("/api/collection", json={"content_id": content["id"]}, headers=MUT).json()
    patched = client.patch(
        f"/api/collection/{entry['id']}",
        json={"progress": 3, "rating": 5, "review": "Spacious and warm.", "status": "in_progress"},
        headers=MUT,
    ).json()
    assert patched["progress"] == 3
    assert patched["rating"] == 5
    assert patched["review"] == "Spacious and warm."
    # Clearing rating with null works.
    cleared = client.patch(f"/api/collection/{entry['id']}", json={"rating": None}, headers=MUT).json()
    assert cleared["rating"] is None
    assert cleared["review"] == "Spacious and warm."


def test_collection_status_query_filters_without_changing_stored_entries(client):
    _auth(client)
    book = _add_content(client, title="A book", kind="book")
    series = _add_content(client)
    planned = client.post("/api/collection", json={"content_id": book["id"]}, headers=MUT).json()
    active = client.post("/api/collection", json={"content_id": series["id"]}, headers=MUT).json()
    client.patch(f"/api/collection/{active['id']}", json={"status": "in_progress"}, headers=MUT)
    before = client.get("/api/collection").json()

    filtered = client.get("/api/collection", params={"status": "planned"})
    assert filtered.status_code == 200
    assert [entry["id"] for entry in filtered.json()] == [planned["id"]]
    assert client.get("/api/collection", params={"status": "planned", "kind": "series"}).json() == []
    assert [entry["id"] for entry in client.get("/api/collection", params={"kind": "series"}).json()] == [active["id"]]
    assert client.get("/api/collection", params={"status_filter": "planned"}).json() == filtered.json()
    assert client.get("/api/collection").json() == before


def test_progress_over_total_rejected_and_data_unchanged(client):
    _auth(client)
    content = _add_content(client, total_units=10)
    entry = client.post("/api/collection", json={"content_id": content["id"]}, headers=MUT).json()
    client.patch(f"/api/collection/{entry['id']}", json={"progress": 4}, headers=MUT)
    resp = client.patch(f"/api/collection/{entry['id']}", json={"progress": 99}, headers=MUT)
    assert resp.status_code == 422
    after = client.get("/api/collection").json()[0]
    assert after["progress"] == 4


def test_invalid_rating_rejected(client):
    _auth(client)
    content = _add_content(client)
    entry = client.post("/api/collection", json={"content_id": content["id"]}, headers=MUT).json()
    resp = client.patch(f"/api/collection/{entry['id']}", json={"rating": 9}, headers=MUT)
    assert resp.status_code == 422


def test_collection_is_isolated_between_users(client):
    _auth(client, username="alice")
    content = _add_content(client)
    client.post("/api/collection", json={"content_id": content["id"]}, headers=MUT)
    entry_id = client.get("/api/collection").json()[0]["id"]

    client.post("/api/auth/logout", headers=MUT)
    register(client, username="bob")
    assert client.get("/api/collection").json() == []
    # Bob cannot see or modify Alice's entry.
    assert client.patch(f"/api/collection/{entry_id}", json={"rating": 1}, headers=MUT).status_code == 404
    assert client.delete(f"/api/collection/{entry_id}", headers=MUT).status_code == 404


def test_delete_entry(client):
    _auth(client)
    content = _add_content(client)
    entry = client.post("/api/collection", json={"content_id": content["id"]}, headers=MUT).json()
    resp = client.delete(f"/api/collection/{entry['id']}", headers=MUT)
    assert resp.status_code == 204
    assert client.get("/api/collection").json() == []


def test_all_five_kinds_supported(client):
    _auth(client)
    for kind in ("book", "movie", "series", "music", "paper"):
        resp = client.post(
            "/api/contents",
            json={"title": f"Item {kind}", "creator": "Someone", "kind": kind},
            headers=MUT,
        )
        assert resp.status_code == 201, resp.text
        assert client.post("/api/collection", json={"content_id": resp.json()["id"]}, headers=MUT).status_code == 201
    assert len(client.get("/api/collection").json()) == 5


# ---------------------------------------------------------------------------
# Posts / feed
# ---------------------------------------------------------------------------


def test_post_without_completing_content(client):
    _auth(client)
    content = _add_content(client)
    # Save but do not finish: still allowed to reflect publicly.
    client.post("/api/collection", json={"content_id": content["id"]}, headers=MUT)
    resp = client.post(
        "/api/posts",
        json={"body": "Two episodes in and already uneasy.", "content_id": content["id"]},
        headers=MUT,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["body"].startswith("Two episodes")
    assert data["content"]["title"] == "Severance"
    assert data["like_count"] == 0


def test_blank_post_rejected(client):
    _auth(client)
    resp = client.post("/api/posts", json={"body": "   "}, headers=MUT)
    assert resp.status_code == 422


def test_feed_is_public_and_personalized(client):
    _auth(client, username="alice")
    resp = client.post("/api/posts", json={"body": "Reading Dune slowly."}, headers=MUT)
    post_id = resp.json()["id"]

    client.post("/api/auth/logout", headers=MUT)
    client.cookies.clear()
    anonymous = client.get("/api/posts").json()
    assert any(p["id"] == post_id for p in anonymous)
    assert all(p["liked"] is False for p in anonymous)

    register(client, username="bob")
    liked = client.put(f"/api/posts/{post_id}/like", headers=MUT).json()
    assert liked == {"liked": True, "like_count": 1}
    feed = client.get("/api/posts").json()
    target = next(p for p in feed if p["id"] == post_id)
    assert target["liked"] is True
    assert target["like_count"] == 1


def test_like_is_idempotent(client):
    _auth(client)
    post_id = client.post("/api/posts", json={"body": "A thought."}, headers=MUT).json()["id"]
    for _ in range(3):
        result = client.put(f"/api/posts/{post_id}/like", headers=MUT).json()
    assert result == {"liked": True, "like_count": 1}
    unliked = client.delete(f"/api/posts/{post_id}/like", headers=MUT).json()
    assert unliked == {"liked": False, "like_count": 0}
    again = client.delete(f"/api/posts/{post_id}/like", headers=MUT).json()
    assert again == {"liked": False, "like_count": 0}


def test_comments_flow(client):
    _auth(client)
    post_id = client.post("/api/posts", json={"body": "Discuss this."}, headers=MUT).json()["id"]
    resp = client.post(f"/api/posts/{post_id}/comments", json={"body": "Agreed."}, headers=MUT)
    assert resp.status_code == 201
    comments = client.get(f"/api/posts/{post_id}/comments").json()
    assert len(comments) == 1
    assert comments[0]["body"] == "Agreed."
    assert comments[0]["author"]["username"] == "reader"
    assert "password" not in comments[0]["author"]


def test_unknown_ids_return_404(client):
    _auth(client)
    assert client.get("/api/posts/9999/comments").status_code == 404
    assert client.put("/api/posts/9999/like", headers=MUT).status_code == 404
    assert client.post("/api/collection", json={"content_id": 9999}, headers=MUT).status_code == 404
    assert client.delete("/api/collection/9999", headers=MUT).status_code == 404


def test_feed_filter_and_sort(client):
    _auth(client)
    book = _add_content(client, title="Cosmos", kind="book")
    movie = _add_content(client, title="Interstellar", kind="movie", total_units=169, unit_label="minutes")
    p1 = client.post("/api/posts", json={"body": "Stargazing with Sagan.", "content_id": book["id"]}, headers=MUT).json()
    p2 = client.post("/api/posts", json={"body": "Wormholes on screen.", "content_id": movie["id"]}, headers=MUT).json()

    books = client.get("/api/posts", params={"kind": "book"}).json()
    assert [p["id"] for p in books] == [p1["id"]]
    hits = client.get("/api/posts", params={"q": "wormholes"}).json()
    assert [p["id"] for p in hits] == [p2["id"]]
    client.put(f"/api/posts/{p1['id']}/like", headers=MUT)
    popular = client.get("/api/posts", params={"sort": "popular"}).json()
    assert popular[0]["id"] == p1["id"]


# ---------------------------------------------------------------------------
# Demo seed
# ---------------------------------------------------------------------------


def test_demo_seed_is_idempotent_and_marked(client, session):
    _auth(client)
    from app.seed import seed_demo

    seed_demo(session)
    seed_demo(session)
    contents = client.get("/api/contents").json()
    titles = [c["title"] for c in contents]
    assert titles.count("Cosmos") == 1
    posts = client.get("/api/posts").json()
    demo_posts = [p for p in posts if p["is_demo"]]
    assert demo_posts
    assert all(p["author"]["username"].startswith("demo_") for p in demo_posts)


def test_demo_users_cannot_log_in(client, session):
    from app.seed import seed_demo

    seed_demo(session)
    client.cookies.clear()
    resp = client.post("/api/auth/login", json={"username": "demo_mara", "password": "anything-at-all"})
    assert resp.status_code == 401
