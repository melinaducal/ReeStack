from fastapi.testclient import TestClient
from main import app
from app.database import get_db, Base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def _auth_headers():
    client.post("/auth/register", json={"username": "bookuser", "first_name": "B", "last_name": "U", "email": "book@test.com", "birth_date": "1990-01-01", "password": "Password123!"})
    r = client.post("/auth/login", json={"email": "book@test.com", "password": "Password123!"})
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_books_romance_or_real():
    h = _auth_headers()
    r = client.get("/books/search?genres=Romance&mode=or", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert data.get("source") in ["google_books", "open_library"]
    assert isinstance(data.get("results"), list)
    assert len(data.get("results")) > 0
    first = data["results"][0]
    assert first.get("title")
    assert isinstance(first.get("authors"), list)


def test_books_aventura_or_real():
    h = _auth_headers()
    r = client.get("/books/search?genres=Aventura&mode=or", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert data.get("source") in ["google_books", "open_library"]
    assert isinstance(data.get("results"), list)
    assert len(data.get("results")) > 0
    first = data["results"][0]
    assert first.get("title")
    assert isinstance(first.get("authors"), list)


def test_books_romance_aventura_or_real():
    h = _auth_headers()
    r = client.get("/books/search?genres=Romance,Aventura&mode=or", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert data.get("source") in ["google_books", "open_library"]
    assert isinstance(data.get("results"), list)
    assert len(data.get("results")) > 0
    first = data["results"][0]
    assert first.get("title")
    assert isinstance(first.get("authors"), list)


def test_books_romance_aventura_and_real():
    h = _auth_headers()
    r = client.get("/books/search?genres=Romance,Aventura&mode=and", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert data.get("source") in ["google_books", "open_library"]
    assert isinstance(data.get("results"), list)
    # Puede haber 0 o más, pero NO debe ser 503
    for item in data.get("results", []):
        assert item.get("title")
        assert isinstance(item.get("authors"), list)
