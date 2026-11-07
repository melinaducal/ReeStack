"""Integration tests for friendships and notifications.

The suite runs against the in-memory SQLite database from ``conftest.py``;
the production ``reestack.db`` is never touched.
"""

import pytest
from sqlalchemy.exc import IntegrityError

import app.routers.friends as friends_router
from app.models import Friendship


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
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _me(client, headers):
    response = client.get("/auth/me", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _create_post(client, headers, title="Mi publicación"):
    response = client.post(
        "/items/",
        headers=headers,
        json={"title": title, "type": "post", "thoughts": "<p>Contenido</p>"},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _send_request(client, headers, user_id):
    return client.post(f"/friends/requests/{user_id}", headers=headers)


def _notifications(client, headers):
    response = client.get("/notifications", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Friendships
# ---------------------------------------------------------------------------


def test_send_friend_request_creates_pending_state_and_notification(
    client, auth_headers
):
    alice = _me(client, auth_headers)
    bob_headers = _register(client, "bob", "bob@example.com")
    bob = _me(client, bob_headers)

    sent = _send_request(client, auth_headers, bob["id"])
    assert sent.status_code == 200, sent.text
    payload = sent.json()
    assert payload["status"] == "pending_outgoing"
    assert payload["friendship_id"] is not None

    incoming = client.get("/friends/requests", headers=bob_headers).json()
    assert len(incoming) == 1
    assert incoming[0]["direction"] == "incoming"
    assert incoming[0]["user"]["id"] == alice["id"]

    outgoing = client.get("/friends/requests/sent", headers=auth_headers).json()
    assert len(outgoing) == 1
    assert outgoing[0]["user"]["id"] == bob["id"]

    bob_notifications = _notifications(client, bob_headers)
    assert [n["type"] for n in bob_notifications] == ["friend_request"]
    assert bob_notifications[0]["actor"]["id"] == alice["id"]

    assert _notifications(client, auth_headers) == []

    assert (
        client.get(f"/friends/status/{bob['id']}", headers=auth_headers).json()[
            "status"
        ]
        == "pending_outgoing"
    )
    assert (
        client.get(f"/friends/status/{alice['id']}", headers=bob_headers).json()[
            "status"
        ]
        == "pending_incoming"
    )


def test_self_request_is_rejected(client, auth_headers):
    alice = _me(client, auth_headers)
    response = _send_request(client, auth_headers, alice["id"])
    assert response.status_code == 400
    assert _notifications(client, auth_headers) == []


def test_request_to_unknown_user_returns_404(client, auth_headers):
    response = _send_request(client, auth_headers, 999999)
    assert response.status_code == 404


def test_duplicate_request_is_rejected(client, auth_headers):
    bob_headers = _register(client, "bob", "bob@example.com")
    bob = _me(client, bob_headers)

    assert _send_request(client, auth_headers, bob["id"]).status_code == 200
    duplicate = _send_request(client, auth_headers, bob["id"])
    assert duplicate.status_code == 400
    assert len(_notifications(client, bob_headers)) == 1


def test_accept_request_creates_friendship_and_notifies_requester(
    client, auth_headers
):
    alice = _me(client, auth_headers)
    bob_headers = _register(client, "bob", "bob@example.com")
    bob = _me(client, bob_headers)
    request_id = _send_request(client, auth_headers, bob["id"]).json()[
        "friendship_id"
    ]

    accepted = client.post(
        f"/friends/requests/{request_id}/accept", headers=bob_headers
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "friends"

    alice_friends = client.get("/friends", headers=auth_headers).json()
    bob_friends = client.get("/friends", headers=bob_headers).json()
    assert [friend["user"]["id"] for friend in alice_friends] == [bob["id"]]
    assert [friend["user"]["id"] for friend in bob_friends] == [alice["id"]]

    assert (
        client.get(f"/friends/status/{bob['id']}", headers=auth_headers).json()[
            "status"
        ]
        == "friends"
    )

    alice_notifications = _notifications(client, auth_headers)
    assert [n["type"] for n in alice_notifications] == ["friend_accepted"]
    assert alice_notifications[0]["actor"]["id"] == bob["id"]

    assert client.get("/friends/requests", headers=bob_headers).json() == []


def test_reverse_request_auto_accepts_instead_of_creating_a_second_row(
    client, auth_headers
):
    alice = _me(client, auth_headers)
    bob_headers = _register(client, "bob", "bob@example.com")
    bob = _me(client, bob_headers)

    assert _send_request(client, auth_headers, bob["id"]).status_code == 200
    reverse = client.post(f"/friends/requests/{alice['id']}", headers=bob_headers)

    assert reverse.status_code == 200, reverse.text
    assert reverse.json()["status"] == "friends"

    assert len(client.get("/friends", headers=auth_headers).json()) == 1
    assert len(client.get("/friends", headers=bob_headers).json()) == 1
    assert client.get("/friends/requests", headers=bob_headers).json() == []
    assert client.get("/friends/requests/sent", headers=auth_headers).json() == []

    alice_notifications = _notifications(client, auth_headers)
    assert [n["type"] for n in alice_notifications] == ["friend_accepted"]
    assert alice_notifications[0]["actor"]["id"] == bob["id"]


def test_only_the_addressee_can_accept_or_reject(client, auth_headers):
    bob_headers = _register(client, "bob", "bob@example.com")
    bob = _me(client, bob_headers)
    charlie_headers = _register(client, "charlie", "charlie@example.com")
    request_id = _send_request(client, auth_headers, bob["id"]).json()[
        "friendship_id"
    ]

    assert (
        client.post(
            f"/friends/requests/{request_id}/accept", headers=auth_headers
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/friends/requests/{request_id}/reject", headers=charlie_headers
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/friends/requests/{request_id}/accept", headers=charlie_headers
        ).status_code
        == 403
    )

    still_pending = client.get("/friends/requests", headers=bob_headers).json()
    assert len(still_pending) == 1


def test_reject_allows_sending_the_request_again(client, auth_headers):
    bob_headers = _register(client, "bob", "bob@example.com")
    bob = _me(client, bob_headers)
    request_id = _send_request(client, auth_headers, bob["id"]).json()[
        "friendship_id"
    ]

    rejected = client.post(
        f"/friends/requests/{request_id}/reject", headers=bob_headers
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"

    resent = _send_request(client, auth_headers, bob["id"])
    assert resent.status_code == 200, resent.text
    assert resent.json()["status"] == "pending_outgoing"

    requests = client.get("/friends/requests", headers=bob_headers).json()
    assert len(requests) == 1


def test_unfriend_removes_the_relationship_for_both_users(client, auth_headers):
    bob_headers = _register(client, "bob", "bob@example.com")
    bob = _me(client, bob_headers)
    request_id = _send_request(client, auth_headers, bob["id"]).json()[
        "friendship_id"
    ]
    client.post(f"/friends/requests/{request_id}/accept", headers=bob_headers)

    removed = client.delete(f"/friends/{bob['id']}", headers=auth_headers)
    assert removed.status_code == 200, removed.text

    assert client.get("/friends", headers=auth_headers).json() == []
    assert client.get("/friends", headers=bob_headers).json() == []
    assert (
        client.get(f"/friends/status/{bob['id']}", headers=auth_headers).json()[
            "status"
        ]
        == "none"
    )


def test_friend_endpoints_require_authentication(client, auth_headers):
    bob_headers = _register(client, "bob", "bob@example.com")
    bob = _me(client, bob_headers)

    assert client.get("/friends").status_code == 401
    assert client.get("/friends/requests").status_code == 401
    assert client.get("/friends/requests/sent").status_code == 401
    assert client.get(f"/friends/status/{bob['id']}").status_code == 401
    assert client.post(f"/friends/requests/{bob['id']}").status_code == 401


# ---------------------------------------------------------------------------
# Notifications from likes and comments
# ---------------------------------------------------------------------------


def test_like_notifies_the_owner_once_per_actor_and_post(client, auth_headers):
    alice = _me(client, auth_headers)
    bob_headers = _register(client, "bob", "bob@example.com")
    bob = _me(client, bob_headers)
    item_id = _create_post(client, auth_headers)

    assert client.post(f"/likes/item/{item_id}", headers=bob_headers).status_code == 200

    notifications = _notifications(client, auth_headers)
    assert [n["type"] for n in notifications] == ["like"]
    assert notifications[0]["actor"]["id"] == bob["id"]
    assert notifications[0]["actor"]["id"] != alice["id"]
    assert notifications[0]["item"]["id"] == item_id

    # Unlike and like again while the notification is unread: no duplicate.
    assert (
        client.delete(f"/likes/item/{item_id}", headers=bob_headers).status_code
        == 200
    )
    assert client.post(f"/likes/item/{item_id}", headers=bob_headers).status_code == 200
    assert len(_notifications(client, auth_headers)) == 1

    # Liking your own post never notifies yourself.
    assert client.post(f"/likes/item/{item_id}", headers=auth_headers).status_code == 200
    assert len(_notifications(client, auth_headers)) == 1


def test_comment_notifies_owner_with_a_preview(client, auth_headers):
    bob_headers = _register(client, "bob", "bob@example.com")
    item_id = _create_post(client, auth_headers)

    assert (
        client.post(
            f"/comments/item/{item_id}",
            headers=bob_headers,
            json={"content": "Muy buena publicación"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/comments/item/{item_id}",
            headers=bob_headers,
            json={"content": "Segundo comentario"},
        ).status_code
        == 200
    )

    notifications = _notifications(client, auth_headers)
    assert [n["type"] for n in notifications] == ["comment", "comment"]
    assert notifications[0]["comment_preview"] == "Segundo comentario"
    assert notifications[1]["comment_preview"] == "Muy buena publicación"
    assert all(n["item"]["id"] == item_id for n in notifications)

    # Commenting on your own post never notifies yourself.
    assert (
        client.post(
            f"/comments/item/{item_id}",
            headers=auth_headers,
            json={"content": "Comentario propio"},
        ).status_code
        == 200
    )
    assert len(_notifications(client, auth_headers)) == 2


def test_notifications_are_private_and_require_authentication(client, auth_headers):
    bob_headers = _register(client, "bob", "bob@example.com")
    bob = _me(client, bob_headers)
    item_id = _create_post(client, auth_headers)
    client.post(f"/likes/item/{item_id}", headers=bob_headers)

    notification_id = _notifications(client, auth_headers)[0]["id"]

    assert client.get("/notifications").status_code == 401
    assert client.get("/notifications", headers=bob_headers).json() == []
    assert (
        client.post(
            f"/notifications/{notification_id}/read", headers=bob_headers
        ).status_code
        == 404
    )
    assert (
        client.get("/notifications/unread-count", headers=bob_headers).json()["count"]
        == 0
    )


def test_mark_one_and_all_notifications_as_read(client, auth_headers):
    bob_headers = _register(client, "bob", "bob@example.com")
    item_id = _create_post(client, auth_headers)

    client.post(f"/likes/item/{item_id}", headers=bob_headers)
    client.post(
        f"/comments/item/{item_id}",
        headers=bob_headers,
        json={"content": "Comentario"},
    )

    assert (
        client.get("/notifications/unread-count", headers=auth_headers).json()["count"]
        == 2
    )

    notification_id = _notifications(client, auth_headers)[0]["id"]
    marked = client.post(
        f"/notifications/{notification_id}/read", headers=auth_headers
    )
    assert marked.status_code == 200, marked.text
    assert marked.json()["is_read"] is True
    assert (
        client.get("/notifications/unread-count", headers=auth_headers).json()["count"]
        == 1
    )

    read_all = client.post("/notifications/read-all", headers=auth_headers)
    assert read_all.status_code == 200, read_all.text
    assert read_all.json()["updated"] == 1
    assert (
        client.get("/notifications/unread-count", headers=auth_headers).json()["count"]
        == 0
    )


def test_notification_list_can_filter_unread_only(client, auth_headers):
    bob_headers = _register(client, "bob", "bob@example.com")
    item_id = _create_post(client, auth_headers)
    client.post(f"/likes/item/{item_id}", headers=bob_headers)

    notification_id = _notifications(client, auth_headers)[0]["id"]
    client.post(f"/notifications/{notification_id}/read", headers=auth_headers)

    assert client.get("/notifications?unread_only=true", headers=auth_headers).json() == []
    assert len(_notifications(client, auth_headers)) == 1


# ---------------------------------------------------------------------------
# Database-level uniqueness and concurrency
# ---------------------------------------------------------------------------


def test_database_rejects_duplicate_rows_in_the_same_direction(
    client, auth_headers, db_session
):
    alice = _me(client, auth_headers)
    bob_headers = _register(client, "bob", "bob@example.com")
    bob = _me(client, bob_headers)

    db_session.add(
        Friendship(requester_id=alice["id"], addressee_id=bob["id"])
    )
    db_session.commit()

    db_session.add(
        Friendship(requester_id=alice["id"], addressee_id=bob["id"])
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    assert db_session.query(Friendship).count() == 1


def test_database_rejects_mirrored_rows_for_the_same_pair(
    client, auth_headers, db_session
):
    alice = _me(client, auth_headers)
    bob_headers = _register(client, "bob", "bob@example.com")
    bob = _me(client, bob_headers)

    db_session.add(
        Friendship(requester_id=alice["id"], addressee_id=bob["id"])
    )
    db_session.commit()

    # B -> A must fail even though (requester, addressee) is a different pair:
    # the canonical index on min()/max() enforces one row per unordered pair.
    db_session.add(
        Friendship(requester_id=bob["id"], addressee_id=alice["id"])
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    assert db_session.query(Friendship).count() == 1


def test_database_rejects_self_friendship(client, auth_headers, db_session):
    alice = _me(client, auth_headers)

    db_session.add(
        Friendship(requester_id=alice["id"], addressee_id=alice["id"])
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def _hide_pair_once(monkeypatch):
    """Simulate a race where the pair row is not visible on the first SELECT."""
    original = friends_router._find_pair
    calls = {"total": 0}

    def flaky(db, first_id, second_id):
        calls["total"] += 1
        if calls["total"] == 1:
            return None
        return original(db, first_id, second_id)

    monkeypatch.setattr(friends_router, "_find_pair", flaky)


def test_duplicate_request_race_returns_controlled_error(
    client, auth_headers, db_session, monkeypatch
):
    bob_headers = _register(client, "bob", "bob@example.com")
    bob = _me(client, bob_headers)

    assert _send_request(client, auth_headers, bob["id"]).status_code == 200
    assert db_session.query(Friendship).count() == 1

    # The first lookup misses the existing row, so the handler tries to insert
    # again and hits the unique index. It must answer 400, never 500.
    _hide_pair_once(monkeypatch)
    raced = _send_request(client, auth_headers, bob["id"])

    assert raced.status_code == 400, raced.text
    assert raced.json()["detail"] == friends_router.ALREADY_REQUESTED
    assert db_session.query(Friendship).count() == 1
    assert len(_notifications(client, bob_headers)) == 1


def test_crossed_request_race_auto_accepts_without_duplicate_rows(
    client, auth_headers, db_session, monkeypatch
):
    alice = _me(client, auth_headers)
    bob_headers = _register(client, "bob", "bob@example.com")
    bob = _me(client, bob_headers)

    assert _send_request(client, auth_headers, bob["id"]).status_code == 200

    # B does not see A's pending request on the first lookup and tries to
    # insert B -> A. The canonical index rejects it; the handler must recover
    # by accepting the existing row instead of returning 500.
    _hide_pair_once(monkeypatch)
    raced = _send_request(client, bob_headers, alice["id"])

    assert raced.status_code == 200, raced.text
    assert raced.json()["status"] == "friends"
    assert db_session.query(Friendship).count() == 1

    assert [friend["user"]["id"] for friend in client.get("/friends", headers=auth_headers).json()] == [bob["id"]]
    assert [friend["user"]["id"] for friend in client.get("/friends", headers=bob_headers).json()] == [alice["id"]]

    alice_notifications = _notifications(client, auth_headers)
    assert [n["type"] for n in alice_notifications] == ["friend_accepted"]
    assert alice_notifications[0]["actor"]["id"] == bob["id"]


def test_accept_cannot_be_replayed_and_notifies_once(client, auth_headers):
    bob_headers = _register(client, "bob", "bob@example.com")
    bob = _me(client, bob_headers)
    request_id = _send_request(client, auth_headers, bob["id"]).json()[
        "friendship_id"
    ]

    first = client.post(
        f"/friends/requests/{request_id}/accept", headers=bob_headers
    )
    second = client.post(
        f"/friends/requests/{request_id}/accept", headers=bob_headers
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 400, second.text
    assert second.json()["detail"] == friends_router.ALREADY_ANSWERED

    acceptances = [
        n for n in _notifications(client, auth_headers)
        if n["type"] == "friend_accepted"
    ]
    assert len(acceptances) == 1


def test_reject_after_accept_is_rejected(client, auth_headers):
    bob_headers = _register(client, "bob", "bob@example.com")
    bob = _me(client, bob_headers)
    request_id = _send_request(client, auth_headers, bob["id"]).json()[
        "friendship_id"
    ]

    client.post(f"/friends/requests/{request_id}/accept", headers=bob_headers)
    rejected = client.post(
        f"/friends/requests/{request_id}/reject", headers=bob_headers
    )

    assert rejected.status_code == 400
    assert rejected.json()["detail"] == friends_router.ALREADY_ANSWERED
    assert [friend["user"]["id"] for friend in client.get("/friends", headers=auth_headers).json()] == [bob["id"]]
