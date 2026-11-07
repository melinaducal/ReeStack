RICH_HTML = (
    '<p><span style="font-size: 18px; font-family: Lora, Georgia, serif;">'
    "<strong>Hola</strong> <em>mundo</em> <u>subrayado</u> <s>tachado</s>"
    '</span></p><p>Segundo párrafo con <a href="https://example.com">enlace</a>.</p>'
)


def _create(client, headers, **payload):
    body = {"title": "Contenido", "type": "book"}
    body.update(payload)
    return client.post("/items/", headers=headers, json=body)


def test_post_is_created_as_post_not_book(client, auth_headers):
    response = _create(
        client,
        auth_headers,
        title="Una reflexión",
        type="post",
        thoughts=RICH_HTML,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "post"
    assert data["kind"] == "post"


def test_backend_preserves_rich_content_exactly(client, auth_headers):
    response = _create(
        client,
        auth_headers,
        type="post",
        thoughts=RICH_HTML,
    )

    assert response.status_code == 200
    assert response.json()["thoughts"] == RICH_HTML

    item_id = response.json()["id"]
    fetched = client.get(f"/items/{item_id}", headers=auth_headers).json()
    assert fetched["thoughts"] == RICH_HTML


def test_update_post_keeps_rich_content_and_type(client, auth_headers):
    created = _create(client, auth_headers, type="post", thoughts=RICH_HTML)
    item_id = created.json()["id"]

    updated_html = RICH_HTML + '<p><span style="font-size: 24px;">Más texto</span></p>'
    response = client.put(
        f"/items/{item_id}",
        headers=auth_headers,
        json={"thoughts": updated_html},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "post"
    assert data["kind"] == "post"
    assert data["thoughts"] == updated_html


def test_cultural_item_keeps_its_type(client, auth_headers):
    response = _create(
        client,
        auth_headers,
        title="El Quijote",
        type="book",
        creator="Miguel de Cervantes",
        thoughts="Una novela fundamental.",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "book"
    assert data["kind"] == "work"
    assert data["thoughts"] == "Una novela fundamental."


def test_unknown_type_is_rejected(client, auth_headers):
    response = _create(client, auth_headers, type="article")

    assert response.status_code == 422


def test_library_views_can_exclude_posts(client, auth_headers):
    post = _create(client, auth_headers, type="post", title="Post")
    book = _create(client, auth_headers, type="book", title="Libro")
    assert post.status_code == 200
    assert book.status_code == 200

    library = client.get(
        "/items/", headers=auth_headers, params={"mine": True, "include_posts": False}
    ).json()
    assert [item["type"] for item in library] == ["book"]

    posts = client.get(
        "/items/", headers=auth_headers, params={"mine": True, "type": "post"}
    ).json()
    assert [item["id"] for item in posts] == [post.json()["id"]]

    # Default keeps the previous behaviour for existing clients.
    everything = client.get(
        "/items/", headers=auth_headers, params={"mine": True}
    ).json()
    assert {item["type"] for item in everything} == {"book", "post"}


def test_feed_keeps_posts_and_works(client, auth_headers):
    post = _create(client, auth_headers, type="post", title="Post")
    book = _create(client, auth_headers, type="book", title="Libro")
    assert post.status_code == 200
    assert book.status_code == 200

    feed = client.get("/items/feed", headers=auth_headers).json()
    assert {item["id"] for item in feed} == {post.json()["id"], book.json()["id"]}


def test_public_profile_counts_posts_separately(client, auth_headers):
    user_id = client.get("/auth/me", headers=auth_headers).json()["id"]
    _create(client, auth_headers, type="book", title="Libro")
    _create(client, auth_headers, type="post", title="Post")

    profile = client.get(f"/users/{user_id}/public").json()

    assert profile["stats"]["items_count"] == 1
    assert profile["stats"]["books"] == 1
    assert profile["stats"]["posts_count"] == 1


def test_public_collection_excludes_posts_by_default(client, auth_headers):
    user_id = client.get("/auth/me", headers=auth_headers).json()["id"]
    _create(client, auth_headers, type="book", title="Libro")
    _create(client, auth_headers, type="post", title="Post")

    collection = client.get(
        f"/users/{user_id}/collection", headers=auth_headers
    ).json()
    assert [item["type"] for item in collection["items"]] == ["book"]

    with_posts = client.get(
        f"/users/{user_id}/collection",
        headers=auth_headers,
        params={"include_posts": True},
    ).json()
    assert {item["type"] for item in with_posts["items"]} == {"book", "post"}


def test_legacy_plain_items_are_returned_unchanged(client, auth_headers):
    created = _create(
        client,
        auth_headers,
        type="movie",
        title="Película antigua",
        thoughts="Texto plano con\nsaltos de línea.",
    )
    assert created.status_code == 200

    item_id = created.json()["id"]
    fetched = client.get(f"/items/{item_id}", headers=auth_headers).json()
    assert fetched["type"] == "movie"
    assert fetched["kind"] == "work"
    assert fetched["thoughts"] == "Texto plano con\nsaltos de línea."
