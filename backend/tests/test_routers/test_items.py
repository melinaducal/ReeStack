def test_get_items_empty(client, auth_headers):
    response = client.get("/items/", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_create_item(client, auth_headers):
    response = client.post(
        "/items/",
        headers=auth_headers,
        json={
            "title": "El Quijote",
            "creator": "Miguel de Cervantes",
            "type": "book",
            "cover_url": "https://example.com/cover.jpg",
            "pages": 863,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "El Quijote"
    assert data["type"] == "book"
    assert "id" in data


def test_get_item(client, auth_headers):
    # Create item first
    create_response = client.post(
        "/items/",
        headers=auth_headers,
        json={
            "title": "El Quijote",
            "creator": "Miguel de Cervantes",
            "type": "book",
            "pages": 863,
        },
    )
    item_id = create_response.json()["id"]

    response = client.get(f"/items/{item_id}")
    assert response.status_code == 200
    assert response.json()["title"] == "El Quijote"


def test_get_item_not_found(client, auth_headers):
    response = client.get("/items/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Item not found"


def test_get_items_filter_by_type(client, auth_headers):
    # Create items
    client.post(
        "/items/",
        headers=auth_headers,
        json={"title": "Book1", "creator": "Author1", "type": "book", "pages": 100},
    )
    client.post(
        "/items/",
        headers=auth_headers,
        json={"title": "Movie1", "creator": "Director1", "type": "movie"},
    )

    response = client.get("/items/?type=book", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["type"] == "book"


def test_update_progress(client, auth_headers):
    # Create book
    create_response = client.post(
        "/items/",
        headers=auth_headers,
        json={
            "title": "El Quijote",
            "creator": "Miguel de Cervantes",
            "type": "book",
            "pages": 863,
        },
    )
    item_id = create_response.json()["id"]

    response = client.put(
        f"/items/{item_id}/progress",
        headers=auth_headers,
        json={"current_page": 100},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["current_page"] == 100
    assert data["reading_progress"] == 11  # int(100/863*100)


def test_update_progress_no_pages_defined(client, auth_headers):
    # Create book without pages
    create_response = client.post(
        "/items/",
        headers=auth_headers,
        json={
            "title": "Book Without Pages",
            "creator": "Author",
            "type": "book",
        },
    )
    item_id = create_response.json()["id"]

    response = client.put(
        f"/items/{item_id}/progress",
        headers=auth_headers,
        json={"current_page": 50},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "El libro no tiene total de páginas definido"


def test_update_progress_invalid_page(client, auth_headers):
    # Create book
    create_response = client.post(
        "/items/",
        headers=auth_headers,
        json={
            "title": "El Quijote",
            "creator": "Miguel de Cervantes",
            "type": "book",
            "pages": 863,
        },
    )
    item_id = create_response.json()["id"]

    response = client.put(
        f"/items/{item_id}/progress",
        headers=auth_headers,
        json={"current_page": 1000},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "La página debe estar entre 0 y el total de páginas"


def test_update_progress_negative_page(client, auth_headers):
    # Create book
    create_response = client.post(
        "/items/",
        headers=auth_headers,
        json={
            "title": "El Quijote",
            "creator": "Miguel de Cervantes",
            "type": "book",
            "pages": 863,
        },
    )
    item_id = create_response.json()["id"]

    response = client.put(
        f"/items/{item_id}/progress",
        headers=auth_headers,
        json={"current_page": -1},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "La página debe estar entre 0 y el total de páginas"


def test_delete_item(client, auth_headers):
    # Create item first
    create_response = client.post(
        "/items/",
        headers=auth_headers,
        json={
            "title": "To Delete",
            "creator": "Author",
            "type": "book",
        },
    )
    item_id = create_response.json()["id"]

    response = client.delete(f"/items/{item_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["message"] == "Item deleted successfully"

    # Verify it's deleted
    get_response = client.get(f"/items/{item_id}")
    assert get_response.status_code == 404
