def test_register_user(client):
    response = client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "first_name": "Test",
            "last_name": "User",
            "email": "test@example.com",
            "birth_date": "1990-01-01",
            "password": "Password123!"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"
    assert "id" in data
    assert "hashed_password" not in data


def test_register_duplicate_email(client):
    # Register first user
    client.post(
        "/auth/register",
        json={
            "username": "testuser1",
            "first_name": "Test",
            "last_name": "User",
            "email": "test@example.com",
            "birth_date": "1990-01-01",
            "password": "Password123!"
        }
    )
    # Try to register with same email
    response = client.post(
        "/auth/register",
        json={
            "username": "testuser2",
            "first_name": "Test2",
            "last_name": "User2",
            "email": "test@example.com",
            "birth_date": "1990-01-01",
            "password": "Password123!"
        }
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "El correo ya está registrado"


def test_register_duplicate_username(client):
    # Register first user
    client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "first_name": "Test",
            "last_name": "User",
            "email": "test1@example.com",
            "birth_date": "1990-01-01",
            "password": "Password123!"
        }
    )
    # Try to register with same username
    response = client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "first_name": "Test2",
            "last_name": "User2",
            "email": "test2@example.com",
            "birth_date": "1990-01-01",
            "password": "Password123!"
        }
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "El nombre de usuario ya está en uso"


def test_register_weak_password_no_uppercase(client):
    response = client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "first_name": "Test",
            "last_name": "User",
            "email": "test@example.com",
            "birth_date": "1990-01-01",
            "password": "password123!"
        }
    )
    assert response.status_code == 422


def test_register_weak_password_no_special_char(client):
    response = client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "first_name": "Test",
            "last_name": "User",
            "email": "test@example.com",
            "birth_date": "1990-01-01",
            "password": "Password123"
        }
    )
    assert response.status_code == 422


def test_register_underage(client):
    response = client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "first_name": "Test",
            "last_name": "User",
            "email": "test@example.com",
            "birth_date": "2015-01-01",
            "password": "Password123!"
        }
    )
    assert response.status_code == 422


def test_login_success(client):
    # Register user first
    client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "first_name": "Test",
            "last_name": "User",
            "email": "test@example.com",
            "birth_date": "1990-01-01",
            "password": "Password123!"
        }
    )
    # Login
    response = client.post(
        "/auth/login",
        json={
            "email": "test@example.com",
            "password": "Password123!"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client):
    # Register user first
    client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "first_name": "Test",
            "last_name": "User",
            "email": "test@example.com",
            "birth_date": "1990-01-01",
            "password": "Password123!"
        }
    )
    # Login with wrong password
    response = client.post(
        "/auth/login",
        json={
            "email": "test@example.com",
            "password": "WrongPassword123!"
        }
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Correo o contraseña incorrectos"


def test_login_nonexistent_user(client):
    response = client.post(
        "/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": "Password123!"
        }
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Correo o contraseña incorrectos"


def test_forgot_password(client):
    response = client.post(
        "/auth/forgot-password",
        json={"email": "test@example.com"}
    )
    assert response.status_code == 200
    assert "message" in response.json()
