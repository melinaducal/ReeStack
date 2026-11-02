from fastapi.testclient import TestClient
from app.models import User, Item
from app.auth.utils import get_password_hash


def test_get_me_excludes_sensitive_fields(client, auth_headers):
    response = client.get("/users/me", headers=auth_headers)
    assert response.status_code == 200
    me = response.json()
    assert "hashed_password" not in me
    assert "password" not in me
    assert me["username"] == "testuser"
    assert me["email"] == "test@example.com"


def test_update_me_changes_profile_fields(client, auth_headers):
    response = client.put(
        "/users/me",
        headers=auth_headers,
        json={"display_name": "Test Display", "bio": "Hola mundo", "username": "testuser2"},
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["username"] == "testuser2"
    assert updated["display_name"] == "Test Display"
    assert updated["bio"] == "Hola mundo"


def test_update_me_rejects_duplicate_username(client, auth_headers):
    # Create second user
    client.post(
        "/auth/register",
        json={
            "username": "otheruser",
            "first_name": "Other",
            "last_name": "User",
            "email": "other@example.com",
            "birth_date": "1990-01-01",
            "password": "Password123!",
        },
    )
    response = client.put(
        "/users/me",
        headers=auth_headers,
        json={"username": "otheruser"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "El nombre de usuario ya está en uso"


def test_search_users_returns_public_fields(client, auth_headers):
    response = client.get("/users/search?q=testuser&page=1&limit=10")
    assert response.status_code == 200
    results = response.json()
    assert isinstance(results, list)
    for user in results:
        assert "email" not in user
        assert "hashed_password" not in user
        assert "password" not in user


def test_get_user_public_by_id_includes_stats(client, auth_headers, db_session):
    # Get current user
    me_response = client.get("/users/me", headers=auth_headers)
    assert me_response.status_code == 200
    me = me_response.json()

    # Create public items for stats
    user = db_session.query(User).filter(User.email == "test@example.com").first()
    assert user is not None
    item1 = Item(
        title="Libro Test",
        type="book",
        user_id=user.id,
        is_public=True,
        reading_progress=50,
    )
    item2 = Item(
        title="Peli Test",
        type="movie",
        user_id=user.id,
        is_public=True,
        reading_progress=0,
    )
    item3 = Item(
        title="Privado",
        type="book",
        user_id=user.id,
        is_public=False,
        reading_progress=0,
    )
    db_session.add_all([item1, item2, item3])
    db_session.commit()

    response = client.get(f"/users/{me['id']}/public")
    assert response.status_code == 200
    pub = response.json()
    assert "email" not in pub
    assert "hashed_password" not in pub
    assert "password" not in pub
    assert "stats" in pub
    assert pub["stats"]["items_count"] == 2
    assert pub["stats"]["books"] == 1
    assert pub["stats"]["movies"] == 1
    assert pub["stats"]["series"] == 0
    assert pub["stats"]["music"] == 0
    assert pub["stats"]["papers"] == 0
    assert pub["username"] == me["username"]
