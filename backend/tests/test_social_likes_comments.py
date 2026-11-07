"""Real integration tests for likes and comments on social posts.

Every test runs against the in-memory SQLite database configured in
``conftest.py``; the production ``reestack.db`` is never touched.
"""

from fastapi.testclient import TestClient

from main import app


def _register(client, username, email):
    register = client.post(
        "/auth/register",
        json={
            "username": username,
            "first_name": username.title(),
            "last_name": "Tester",
            "email": email,
            "birth_date": "1990-01-01",
            "password": "Password123!",
        },
    )
    assert register.status_code == 200, register.text
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_post(client, headers, title="Reflexión", thoughts="<p>Hola</p>"):
    response = client.post(
        "/items/",
        headers=headers,
        json={"title": title, "type": "post", "thoughts": thoughts},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _second_user(client):
    return _register(client, "otheruser", "other@example.com")


# ---------------------------------------------------------------------------
# Likes
# ---------------------------------------------------------------------------


def test_like_and_unlike_update_the_real_counter(client, auth_headers):
    item_id = _create_post(client, auth_headers)

    created = client.post(f"/likes/item/{item_id}", headers=auth_headers)
    assert created.status_code == 200, created.text
    assert created.json() == {"item_id": item_id, "liked": True, "likes_count": 1}

    state = client.get(f"/likes/item/{item_id}", headers=auth_headers)
    assert state.json() == {"item_id": item_id, "liked": True, "likes_count": 1}

    removed = client.delete(f"/likes/item/{item_id}", headers=auth_headers)
    assert removed.status_code == 200, removed.text
    assert removed.json() == {"item_id": item_id, "liked": False, "likes_count": 0}


def test_duplicate_like_is_rejected_and_only_one_stays_active(client, auth_headers):
    item_id = _create_post(client, auth_headers)

    first = client.post(f"/likes/item/{item_id}", headers=auth_headers)
    second = client.post(f"/likes/item/{item_id}", headers=auth_headers)

    assert first.status_code == 200
    assert second.status_code == 400
    assert client.get(f"/likes/item/{item_id}", headers=auth_headers).json()[
        "likes_count"
    ] == 1


def test_like_state_is_per_user_and_the_count_is_shared(client, auth_headers):
    item_id = _create_post(client, auth_headers)
    other = _second_user(client)

    client.post(f"/likes/item/{item_id}", headers=auth_headers)

    mine = client.get(f"/likes/item/{item_id}", headers=auth_headers).json()
    theirs = client.get(f"/likes/item/{item_id}", headers=other).json()

    assert mine == {"item_id": item_id, "liked": True, "likes_count": 1}
    assert theirs == {"item_id": item_id, "liked": False, "likes_count": 1}

    client.post(f"/likes/item/{item_id}", headers=other)
    assert client.get(f"/likes/item/{item_id}", headers=other).json()[
        "likes_count"
    ] == 2


def test_like_endpoints_require_authentication(client, auth_headers):
    item_id = _create_post(client, auth_headers)

    assert client.post(f"/likes/item/{item_id}").status_code == 401
    assert client.get(f"/likes/item/{item_id}").status_code == 401
    assert client.delete(f"/likes/item/{item_id}").status_code == 401


def test_like_on_missing_item_returns_404(client, auth_headers):
    assert client.post("/likes/item/999999", headers=auth_headers).status_code == 404
    assert client.get("/likes/item/999999", headers=auth_headers).status_code == 404
    assert client.delete("/likes/item/999999", headers=auth_headers).status_code == 404


def test_unlike_without_previous_like_returns_400(client, auth_headers):
    item_id = _create_post(client, auth_headers)
    response = client.delete(f"/likes/item/{item_id}", headers=auth_headers)
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------


def test_comment_returns_author_avatar_date_and_content(client, auth_headers):
    item_id = _create_post(client, auth_headers)
    client.put(
        "/users/me",
        headers=auth_headers,
        json={"display_name": "Autora Real", "avatar_url": "/uploads/avatars/a.png"},
    )

    response = client.post(
        f"/comments/item/{item_id}",
        headers=auth_headers,
        json={"content": "  Un comentario con contenido  ", "has_spoiler": False},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["content"] == "Un comentario con contenido"
    assert data["username"] == "testuser"
    assert data["display_name"] == "Autora Real"
    assert data["avatar_url"] == "/uploads/avatars/a.png"
    assert data["created_at"], "created_at must be present for new comments"
    assert data["is_owner"] is True


def test_comment_author_comes_from_jwt_not_from_the_body(client, auth_headers):
    item_id = _create_post(client, auth_headers)
    me = client.get("/auth/me", headers=auth_headers).json()

    response = client.post(
        f"/comments/item/{item_id}",
        headers=auth_headers,
        json={
            "content": "Intento de suplantación",
            "user_id": 999999,
            "username": "hacker",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["user_id"] == me["id"]
    assert response.json()["username"] == me["username"]


def test_empty_and_whitespace_comments_are_rejected(client, auth_headers):
    item_id = _create_post(client, auth_headers)

    for content in ("", "   ", "\n\t"):
        response = client.post(
            f"/comments/item/{item_id}",
            headers=auth_headers,
            json={"content": content},
        )
        assert response.status_code == 422, (content, response.text)


def test_comment_requires_authentication(client, auth_headers):
    item_id = _create_post(client, auth_headers)
    response = client.post(
        f"/comments/item/{item_id}",
        json={"content": "Sin token"},
    )
    assert response.status_code == 401


def test_comment_on_missing_item_returns_404(client, auth_headers):
    response = client.post(
        "/comments/item/999999",
        headers=auth_headers,
        json={"content": "Comentario huérfano"},
    )
    assert response.status_code == 404


def test_comments_are_listed_and_persist_after_reload(client, auth_headers):
    item_id = _create_post(client, auth_headers)
    created = client.post(
        f"/comments/item/{item_id}",
        headers=auth_headers,
        json={"content": "Persistente"},
    )
    assert created.status_code == 200

    reloaded_client = TestClient(app)
    listed = reloaded_client.get(
        f"/comments/item/{item_id}", headers=auth_headers
    )

    assert listed.status_code == 200, listed.text
    assert [comment["content"] for comment in listed.json()] == ["Persistente"]
    assert listed.json()[0]["is_owner"] is True


def test_other_user_cannot_edit_or_delete_a_comment(client, auth_headers):
    item_id = _create_post(client, auth_headers)
    other = _second_user(client)
    comment_id = client.post(
        f"/comments/item/{item_id}",
        headers=auth_headers,
        json={"content": "Solo mía"},
    ).json()["id"]

    edit = client.put(
        f"/comments/{comment_id}",
        headers=other,
        json={"content": "Editado por otro"},
    )
    delete = client.delete(f"/comments/{comment_id}", headers=other)

    assert edit.status_code == 403, edit.text
    assert delete.status_code == 403, delete.text
    assert client.get(f"/comments/item/{item_id}", headers=auth_headers).json()[0][
        "content"
    ] == "Solo mía"


def test_author_can_edit_and_delete_own_comment(client, auth_headers):
    item_id = _create_post(client, auth_headers)
    comment_id = client.post(
        f"/comments/item/{item_id}",
        headers=auth_headers,
        json={"content": "Original"},
    ).json()["id"]

    edited = client.put(
        f"/comments/{comment_id}",
        headers=auth_headers,
        json={"content": "  Editado  "},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["content"] == "Editado"
    assert edited.json()["is_owner"] is True

    blank = client.put(
        f"/comments/{comment_id}",
        headers=auth_headers,
        json={"content": "   "},
    )
    assert blank.status_code == 422

    deleted = client.delete(f"/comments/{comment_id}", headers=auth_headers)
    assert deleted.status_code == 200
    assert client.get(f"/comments/item/{item_id}", headers=auth_headers).json() == []


def test_edit_or_delete_unknown_comment_returns_404(client, auth_headers):
    assert (
        client.put(
            "/comments/999999", headers=auth_headers, json={"content": "x"}
        ).status_code
        == 404
    )
    assert client.delete("/comments/999999", headers=auth_headers).status_code == 404


def test_private_post_comments_are_hidden_from_others(client, auth_headers):
    item_id = _create_post(client, auth_headers)
    other = _second_user(client)
    client.post(
        f"/comments/item/{item_id}",
        headers=auth_headers,
        json={"content": "Comentario privado"},
    )

    visibility = client.patch(
        f"/items/{item_id}/visibility",
        headers=auth_headers,
        json={"is_public": False},
    )
    assert visibility.status_code == 200

    assert client.get(f"/comments/item/{item_id}", headers=other).status_code == 404
    assert client.get(f"/comments/item/{item_id}").status_code == 404
    assert client.get(f"/comments/item/{item_id}", headers=auth_headers).status_code == 200


def test_feed_and_detail_expose_real_counters(client, auth_headers):
    item_id = _create_post(client, auth_headers)
    other = _second_user(client)

    client.post(f"/likes/item/{item_id}", headers=auth_headers)
    client.post(f"/likes/item/{item_id}", headers=other)
    client.post(
        f"/comments/item/{item_id}",
        headers=auth_headers,
        json={"content": "Uno"},
    )
    client.post(
        f"/comments/item/{item_id}",
        headers=other,
        json={"content": "Dos"},
    )

    detail = client.get(f"/items/{item_id}", headers=auth_headers).json()
    assert detail["likes_count"] == 2
    assert detail["comments_count"] == 2

    feed = client.get("/items/feed", headers=auth_headers).json()
    post = next(item for item in feed if item["id"] == item_id)
    assert post["likes_count"] == 2
    assert post["comments_count"] == 2
