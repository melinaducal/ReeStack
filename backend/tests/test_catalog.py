import asyncio

import pytest

from app.routers import catalog


@pytest.fixture(autouse=True)
def _clear_catalog_cache():
    catalog._cache.clear()
    yield
    catalog._cache.clear()


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    async def get(self, url, params=None, **kwargs):
        self.calls.append((url, params or {}))
        result = self.responses.get(url)
        if result is None:
            raise AssertionError(f"URL inesperada: {url}")
        if isinstance(result, list):
            return result.pop(0)
        return result


def test_catalog_requires_authentication(client):
    response = client.get("/catalog/search", params={"type": "music", "q": "abbey"})

    assert response.status_code == 401


def test_catalog_rejects_unsupported_type(client, auth_headers):
    response = client.get(
        "/catalog/search", params={"type": "game", "q": "zelda"}, headers=auth_headers
    )

    assert response.status_code == 400


def test_catalog_rejects_short_query(client, auth_headers):
    response = client.get(
        "/catalog/search", params={"type": "music", "q": "a"}, headers=auth_headers
    )

    assert response.status_code == 400


def test_catalog_returns_empty_200_instead_of_error(client, auth_headers, monkeypatch):
    async def fake_provider(client_, query, errors):
        errors.append("provider_empty")
        return [], None

    monkeypatch.setitem(catalog._PROVIDERS, "music", fake_provider)

    response = client.get(
        "/catalog/search", params={"type": "music", "q": "zzzz"}, headers=auth_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["results"] == []
    assert body["total"] == 0
    assert body["source"] is None
    assert body["errors"] == ["provider_empty"]


def test_catalog_paginates_and_dedupes(client, auth_headers, monkeypatch):
    async def fake_provider(client_, query, errors):
        items = [
            {
                "external_id": str(index % 3),
                "title": f"Disco {index % 3}",
                "creator": "Artista",
                "year": 2020,
                "cover_url": None,
                "description": None,
                "source": "itunes",
            }
            for index in range(9)
        ]
        return items, "itunes"

    monkeypatch.setitem(catalog._PROVIDERS, "music", fake_provider)

    response = client.get(
        "/catalog/search",
        params={"type": "music", "q": "disco", "page": 2, "limit": 2},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["page"] == 2
    assert [item["title"] for item in body["results"]] == ["Disco 2"]


def test_itunes_normalization_uses_large_artwork():
    item = catalog._normalize_itunes_album(
        {
            "collectionId": 123,
            "collectionName": "Abbey Road",
            "artistName": "The Beatles",
            "releaseDate": "1969-09-26T07:00:00Z",
            "artworkUrl100": "https://is1.mzstatic.com/art/100x100bb.jpg",
            "primaryGenreName": "Rock",
        }
    )

    assert item["title"] == "Abbey Road"
    assert item["creator"] == "The Beatles"
    assert item["year"] == 1969
    assert item["cover_url"].endswith("600x600bb.jpg")
    assert item["source"] == "itunes"


def test_music_falls_back_to_musicbrainz_when_itunes_is_empty():
    client = FakeClient(
        {
            catalog.ITUNES_SEARCH_URL: FakeResponse(200, {"results": []}),
            catalog.MUSICBRAINZ_RELEASE_URL: FakeResponse(
                200,
                {
                    "releases": [
                        {
                            "id": "mbid-1",
                            "title": "Abbey Road",
                            "date": "1969-09-26",
                            "artist-credit": [{"name": "The Beatles"}],
                        }
                    ]
                },
            ),
        }
    )

    results, source = asyncio.run(catalog._search_music(client, "abbey road", []))

    assert source == "musicbrainz"
    assert results[0]["title"] == "Abbey Road"
    assert results[0]["cover_url"] == "https://coverartarchive.org/release/mbid-1/front-500"


def test_tvmaze_normalization_includes_poster_and_year():
    show = catalog._normalize_tvmaze_show(
        {
            "id": 169,
            "name": "Breaking Bad",
            "premiered": "2008-01-20",
            "image": {"medium": "https://static.tvmaze.com/medium.jpg"},
            "genres": ["Drama", "Crime"],
        }
    )

    assert show["year"] == 2008
    assert show["cover_url"].endswith("medium.jpg")
    assert show["description"] == "Drama, Crime"


def test_tmdb_normalization_builds_poster_url():
    movie = catalog._normalize_tmdb_movie(
        {
            "id": 27205,
            "title": "Origen",
            "release_date": "2010-07-15",
            "poster_path": "/poster.jpg",
        }
    )

    assert movie["year"] == 2010
    assert movie["cover_url"] == "https://image.tmdb.org/t/p/w500/poster.jpg"


def test_crossref_normalization_strips_html_from_title():
    paper = catalog._normalize_crossref_item(
        {
            "DOI": "10.1000/xyz",
            "title": ["<i>Machine learning</i> for everyone"],
            "author": [{"given": "Ada", "family": "Lovelace"}],
            "issued": {"date-parts": [[2021, 5]]},
            "container-title": ["Journal of Tests"],
        }
    )

    assert paper["title"] == "Machine learning for everyone"
    assert paper["creator"] == "Ada Lovelace"
    assert paper["year"] == 2021


def test_wikipedia_film_parser_reads_infobox():
    wikitext = """
{{Infobox film
| name = Inception
| image = Inception (2010) theatrical poster.jpg
| director = [[Christopher Nolan]]
| released = {{Film date|2010|7|16}}
}}
"""

    film = catalog._normalize_wikipedia_film(
        "Inception", wikitext, "https://upload.wikimedia.org/poster.jpg"
    )

    assert film["creator"] == "Christopher Nolan"
    assert film["year"] == 2010
    assert film["cover_url"].endswith("poster.jpg")


def test_wikipedia_parser_rejects_non_film_pages():
    assert catalog._normalize_wikipedia_film("Inception", "{{Infobox album}}", None) is None
    assert (
        catalog._normalize_wikipedia_film(
            "83rd Academy Awards",
            "{{Infobox award\n| director = Someone\n}}",
            None,
        )
        is None
    )


def test_wikipedia_parser_handles_multiline_director():
    wikitext = """
{{Infobox film
| director = {{Plainlist|
* [[Nathan Greno]]
* [[Byron Howard]]
}}
| released = {{Film date|2010|11|24}}
}}
"""

    film = catalog._normalize_wikipedia_film("Tangled", wikitext, None)

    assert film["creator"] == "Nathan Greno, Byron Howard"
    assert film["year"] == 2010


def test_movies_use_tmdb_when_key_is_configured(monkeypatch):
    monkeypatch.setenv("TMDB_API_KEY", "test-key")
    client = FakeClient(
        {
            catalog.TMDB_SEARCH_URL: FakeResponse(
                200,
                {
                    "results": [
                        {
                            "id": 27205,
                            "title": "Origen",
                            "release_date": "2010-07-15",
                            "poster_path": "/poster.jpg",
                        }
                    ]
                },
            )
        }
    )

    results, source = asyncio.run(catalog._search_movies(client, "origen", []))

    assert source == "tmdb"
    assert results[0]["title"] == "Origen"


def test_movies_fall_back_to_wikipedia_without_key(monkeypatch):
    monkeypatch.delenv("TMDB_API_KEY", raising=False)
    client = FakeClient({catalog.WIKIPEDIA_API_URL: FakeResponse(200, {"query": {"search": []}})})

    results, source = asyncio.run(catalog._search_movies(client, "origen", []))

    assert results == []
    assert source is None
    assert client.calls[0][1]["srsearch"] == "origen film"
