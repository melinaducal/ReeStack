"""Shared pytest fixtures: isolated in-memory database + test client."""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool


@pytest.fixture(name="engine")
def engine_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture(name="session")
def session_fixture(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(engine):
    from app.main import create_app
    from app.db import get_session

    app = create_app()
    app.router.lifespan_context = _noop_lifespan

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


from contextlib import asynccontextmanager


@asynccontextmanager
async def _noop_lifespan(app):
    yield


def register(client: TestClient, username="reader", password="correct-horse-battery"):
    resp = client.post(
        "/api/auth/register",
        json={"username": username, "display_name": username.title(), "password": password},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()
