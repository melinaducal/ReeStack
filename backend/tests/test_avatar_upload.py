from urllib.parse import urlparse

from app.models import User
from app.routers.users import MAX_AVATAR_BYTES
from app.storage import AVATAR_DIR

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def _avatar_path(avatar_url):
    return urlparse(avatar_url).path


def _remove_uploaded(avatar_url):
    path = _avatar_path(avatar_url)
    name = path.rsplit("/uploads/avatars/", 1)[-1]
    if name:
        candidate = AVATAR_DIR / name
        if candidate.is_file():
            candidate.unlink()


def test_avatar_upload_requires_authentication(client):
    response = client.post(
        "/users/me/avatar", files={"file": ("a.png", PNG_BYTES, "image/png")}
    )

    assert response.status_code == 401


def test_owner_can_upload_and_serve_avatar(client, auth_headers, db_session):
    response = client.post(
        "/users/me/avatar",
        headers=auth_headers,
        files={"file": ("foto.png", PNG_BYTES, "image/png")},
    )

    assert response.status_code == 200, response.text
    avatar_url = response.json()["avatar_url"]
    try:
        assert "/uploads/avatars/" in avatar_url
        assert avatar_url.endswith(".png")

        served = client.get(_avatar_path(avatar_url))
        assert served.status_code == 200
        assert served.content == PNG_BYTES

        me = client.get("/users/me", headers=auth_headers).json()
        assert me["avatar_url"] == avatar_url

        stored = db_session.query(User).filter(User.id == me["id"]).first()
        db_session.refresh(stored)
        assert stored.avatar_url == avatar_url
    finally:
        _remove_uploaded(avatar_url)


def test_avatar_upload_replaces_previous_file(client, auth_headers):
    first = client.post(
        "/users/me/avatar",
        headers=auth_headers,
        files={"file": ("uno.png", PNG_BYTES, "image/png")},
    ).json()["avatar_url"]
    second = client.post(
        "/users/me/avatar",
        headers=auth_headers,
        files={"file": ("dos.png", PNG_BYTES + b"1", "image/png")},
    ).json()["avatar_url"]

    try:
        assert first != second
        assert not (AVATAR_DIR / _avatar_path(first).rsplit("/", 1)[-1]).exists()
    finally:
        _remove_uploaded(second)


def test_avatar_rejects_unsupported_content_type(client, auth_headers):
    response = client.post(
        "/users/me/avatar",
        headers=auth_headers,
        files={"file": ("nota.txt", b"hola", "text/plain")},
    )

    assert response.status_code == 400


def test_avatar_rejects_fake_image_bytes(client, auth_headers):
    response = client.post(
        "/users/me/avatar",
        headers=auth_headers,
        files={"file": ("falsa.png", b"esto no es una imagen", "image/png")},
    )

    assert response.status_code == 400


def test_avatar_rejects_images_over_limit(client, auth_headers):
    oversized = b"\x89PNG\r\n\x1a\n" + b"0" * MAX_AVATAR_BYTES

    response = client.post(
        "/users/me/avatar",
        headers=auth_headers,
        files={"file": ("grande.png", oversized, "image/png")},
    )

    assert response.status_code == 413


def test_owner_can_remove_avatar(client, auth_headers):
    avatar_url = client.post(
        "/users/me/avatar",
        headers=auth_headers,
        files={"file": ("foto.png", PNG_BYTES, "image/png")},
    ).json()["avatar_url"]
    filename = _avatar_path(avatar_url).rsplit("/", 1)[-1]

    response = client.delete("/users/me/avatar", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["avatar_url"] is None
    assert not (AVATAR_DIR / filename).exists()
