"""Manual smoke check for the profile endpoints.

This file used to execute HTTP requests at import time, so a bare ``pytest``
collection crashed before any test ran (the in-memory test database has no
tables yet at import time).

The flow now lives inside ``main()`` and only runs when the file is executed
directly::

    python test_profiles.py

Automated coverage for the same endpoints lives in ``tests/test_profiles.py``
and runs against the isolated in-memory database.
"""


def main():
    from fastapi.testclient import TestClient

    from app.auth.utils import get_password_hash
    from app.database import SessionLocal
    from app.models import User
    from main import app

    client = TestClient(app)

    # Create the smoke-test user if it does not exist.
    db = SessionLocal()
    user = db.query(User).filter(User.email == "testprofile@example.com").first()
    if not user:
        user = User(
            username="testprofile",
            first_name="Test",
            last_name="Profile",
            email="testprofile@example.com",
            birth_date="1995-01-01",
            hashed_password=get_password_hash("Passw0rd!"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    db.close()

    # Login.
    response = client.post(
        "/auth/login",
        json={"email": "testprofile@example.com", "password": "Passw0rd!"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Get me.
    response = client.get("/users/me", headers=headers)
    assert response.status_code == 200
    me = response.json()
    assert "hashed_password" not in me
    assert "password" not in me

    # Update me.
    response = client.put(
        "/users/me",
        headers=headers,
        json={"display_name": "Test P", "bio": "Hola", "username": "testprofile2"},
    )
    if response.status_code == 400:
        # The username is already taken; retry without it.
        response = client.put(
            "/users/me",
            headers=headers,
            json={"display_name": "Test P", "bio": "Hola"},
        )
    assert response.status_code == 200

    # Search.
    response = client.get("/users/search?q=test&page=1&limit=10")
    assert response.status_code == 200

    # Public profile by id.
    response = client.get(f'/users/{me["id"]}/public')
    assert response.status_code == 200
    public = response.json()
    assert "email" not in public
    assert "hashed_password" not in public
    assert "password" not in public
    assert "stats" in public

    print("all tests passed")


if __name__ == "__main__":
    main()
