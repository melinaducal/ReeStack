import pytest


def _create_item(client, headers, rating):
    return client.post(
        "/items",
        json={"title": "Disco fraccionado", "type": "music", "rating": rating},
        headers=headers,
    )


@pytest.mark.parametrize("rating", [1, 4 + 1 / 3, 4 + 1 / 2, 4 + 1 / 6, 1.5, 5])
def test_item_accepts_fractional_stars(client, auth_headers, rating):
    response = _create_item(client, auth_headers, rating)

    assert response.status_code == 200, response.text
    assert response.json()["rating"] == pytest.approx(rating)


@pytest.mark.parametrize("rating", [0, 0.99, 5.01, 8, -1])
def test_item_rejects_ratings_outside_one_to_five(client, auth_headers, rating):
    response = _create_item(client, auth_headers, rating)

    assert response.status_code == 422


def test_item_rating_can_be_updated_with_fractions(client, auth_headers):
    item_id = _create_item(client, auth_headers, 4).json()["id"]

    response = client.put(
        f"/items/{item_id}", json={"rating": 4 + 1 / 6}, headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["rating"] == pytest.approx(4.1666666667)


def test_comment_accepts_fractional_stars(client, auth_headers):
    item_id = _create_item(client, auth_headers, 5).json()["id"]

    response = client.post(
        f"/comments/item/{item_id}",
        json={"content": "Muy bueno", "rating": 4 + 1 / 3},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["rating"] == pytest.approx(4.3333333333)


def test_rating_summary_averages_fractional_stars(client, auth_headers):
    item_id = _create_item(client, auth_headers, 5).json()["id"]
    for rating in (4 + 1 / 3, 4 + 1 / 2):
        client.post(
            f"/comments/item/{item_id}",
            json={"content": "Comentario", "rating": rating},
            headers=auth_headers,
        )

    response = client.get(f"/comments/item/{item_id}/rating")

    assert response.status_code == 200
    assert response.json()["count"] == 2
    assert response.json()["average"] == pytest.approx(4.417)


def test_unrated_comment_is_not_counted_in_summary(client, auth_headers):
    item_id = _create_item(client, auth_headers, 5).json()["id"]
    client.post(
        f"/comments/item/{item_id}",
        json={"content": "Sin nota", "rating": None},
        headers=auth_headers,
    )

    response = client.get(f"/comments/item/{item_id}/rating")

    assert response.status_code == 200
    assert response.json() == {"average": 0, "count": 0}
