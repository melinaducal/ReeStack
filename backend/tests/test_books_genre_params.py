from unittest.mock import patch

from app.routers.books import resolve_genres


def _labels(values):
    return [genre["label"] for genre in resolve_genres(values)]


def test_resolve_genres_accepts_spanish_and_english():
    assert _labels(["Ficción"]) == ["Ficción"]
    assert _labels(["ficcion"]) == ["Ficción"]
    assert _labels(["FICTION"]) == ["Ficción"]
    assert _labels(["Ciencia Ficción"]) == ["Ciencia Ficción"]
    assert _labels(["science fiction"]) == ["Ciencia Ficción"]
    assert _labels(["Autoayuda", "self-help"]) == ["Autoayuda"]
    assert _labels(["Fantasia"]) == ["Fantasía"]
    assert _labels(["Juvenil"]) == ["Juvenil"]
    assert _labels(["young adult"]) == ["Juvenil"]


def test_resolve_genres_splits_commas_and_dedupes():
    assert _labels(["Romance,Aventura", "romance"]) == ["Romance", "Aventura"]
    assert _labels(["Romance", "Aventura", "Terror"]) == [
        "Romance",
        "Aventura",
        "Terror",
    ]


def test_resolve_genres_keeps_unknown_genre_as_is():
    resolved = resolve_genres(["Cocina vegana"])
    assert resolved[0]["label"] == "Cocina vegana"
    assert resolved[0]["slugs"] == ["cocina_vegana"]


async def _fake_results(genres, mode):
    items = [
        {
            "title": "Un libro",
            "authors": ["Autora"],
            "cover_url": None,
            "description": None,
            "isbn": None,
            "published_date": "2020",
            "genres": [genres[0]["label"]],
            "matched_genres": [genre["label"] for genre in genres],
        }
    ]
    return items, {"google_books"}, []


async def _fake_empty(genres, mode):
    return [], set(), ["provider_empty"]


def test_search_accepts_axios_array_style_genres(client, auth_headers):
    with patch("app.routers.books._search_by_genres", new=_fake_results):
        response = client.get(
            "/books/search?genres[]=Ficción&genres[]=Fantasía&mode=or",
            headers=auth_headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["genres"] == ["Ficción", "Fantasía"]
    assert body["total"] == 1
    assert body["results"][0]["title"] == "Un libro"


def test_search_accepts_comma_separated_genres(client, auth_headers):
    with patch("app.routers.books._search_by_genres", new=_fake_results):
        response = client.get(
            "/books/search?genres=Romance,Aventura&mode=or", headers=auth_headers
        )

    assert response.status_code == 200
    assert response.json()["genres"] == ["Romance", "Aventura"]


def test_search_returns_empty_200_instead_of_503(client, auth_headers):
    with patch("app.routers.books._search_by_genres", new=_fake_empty):
        response = client.get(
            "/books/search?genres=Cocina vegana&mode=or", headers=auth_headers
        )

    assert response.status_code == 200
    body = response.json()
    assert body["results"] == []
    assert body["total"] == 0


def test_search_paginates(client, auth_headers):
    async def fake_many(genres, mode):
        items = [
            {
                "title": f"Libro {index}",
                "authors": ["Autora"],
                "genres": ["Romance"],
                "matched_genres": ["Romance"],
            }
            for index in range(5)
        ]
        return items, {"google_books"}, []

    with patch("app.routers.books._search_by_genres", new=fake_many):
        response = client.get(
            "/books/search?genres=Romance&page=2&limit=2", headers=auth_headers
        )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert body["page"] == 2
    assert [item["title"] for item in body["results"]] == ["Libro 2", "Libro 3"]


def test_search_rejects_invalid_mode(client, auth_headers):
    response = client.get(
        "/books/search?genres=Romance&mode=xor", headers=auth_headers
    )

    assert response.status_code == 400
