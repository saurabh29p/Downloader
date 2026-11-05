"""Sections (v2 Phase 4): presets, TMDB where-to-watch, Commons photos, legal rules."""

from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from anyget.core.net import Net
from anyget.core.settings import Settings, get_settings
from anyget.handlers.base import HandlerError
from anyget.main import create_app
from anyget.universal.commons import licence_of, search_photos
from anyget.universal.keyword_router import plan
from anyget.universal.sections import SECTIONS, preset_of
from anyget.universal.tmdb import search_movies

TMDB = "https://api.themoviedb.org/3"


def test_every_preset_plans_and_no_piracy_sources() -> None:
    banned = ("torrent", "pirate", "1337x", "yts", "rarbg", "fmovies", "123movies", "libgen")
    for section in SECTIONS:
        for link in section.links:
            assert link.url.startswith("https://") and "{q}" in link.url
            assert not any(word in link.url.lower() for word in banned), link.url
        for preset in section.presets:
            planned = plan("", section.id, preset.id)
            assert planned.kind == "search" and planned.queries, (section.id, preset.id)
            assert all(q.q == preset.query for q in planned.queries)


def test_presets_carry_their_filters() -> None:
    noir = plan("", "movies", "film-noir")
    assert [q.source for q in noir.queries] == ["archive"]
    assert noir.queries[0].filters == {"mediatype": "movies", "collection": "Film_Noir"}
    oscars = plan("", "movies", "oscar-winners")
    assert [q.source for q in oscars.queries] == ["tmdb", "archive", "videos"]
    assert preset_of("movies", "nope") is None and preset_of("nope", "film-noir") is None
    photos = plan("Bombay", "photos")
    assert photos.media == ["photo"] and photos.queries[0].source == "commons"
    declassified = plan("MKUltra", "declassified")
    assert [q.source for q in declassified.queries] == ["archive"]


@pytest.fixture
async def net(settings: Settings) -> AsyncIterator[Net]:
    n = Net(settings)
    yield n
    await n.aclose()


def details(movie_id: int) -> dict[str, Any]:
    return {
        "id": movie_id,
        "overview": "A woman leaves her husband for a mill worker.",
        "vote_average": 7.84,
        "credits": {"cast": [{"name": "Nargis"}, {"name": "Raj Kapoor"}]},
        "videos": {"results": [{"site": "YouTube", "type": "Trailer", "key": "abc123"}]},
        "watch/providers": {
            "results": {
                "IN": {
                    "link": "https://www.themoviedb.org/movie/1/watch?locale=IN",
                    "flatrate": [
                        {"provider_name": "Netflix", "logo_path": "/n.png", "display_priority": 2},
                        {"provider_name": "JioHotstar", "display_priority": 1},
                    ],
                    "ads": [{"provider_name": "YouTube (free)"}],
                    "rent": [{"provider_name": "Apple TV"}],
                },
                "US": {"flatrate": [{"provider_name": "Hulu"}]},
            }
        },
    }


@respx.mock
async def test_tmdb_where_to_watch_in_india(net: Net) -> None:
    search = respx.get(url__startswith=f"{TMDB}/search/movie").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": 1,
                        "title": "Awaara",
                        "release_date": "1951-12-14",
                        "poster_path": "/p.jpg",
                    },
                    {"id": 2, "title": "Awaara Paagal"},
                ]
            },
        )
    )
    respx.get(url__regex=rf"{TMDB}/movie/1\?.*").mock(
        return_value=httpx.Response(200, json=details(1))
    )
    respx.get(url__regex=rf"{TMDB}/movie/2\?.*").mock(return_value=httpx.Response(404))
    cards = await search_movies(net, "v3key", "Awaara")
    assert "api_key=v3key" in str(search.calls[0].request.url)
    first = cards[0]
    assert first.download is None and first.licence == "rights_reserved"  # never a download
    assert first.year == "1951" and first.thumbnail == "https://image.tmdb.org/t/p/w342/p.jpg"
    movie = first.movie
    assert movie is not None and movie.rating == 7.8 and movie.cast == ["Nargis", "Raj Kapoor"]
    assert [p.name for p in movie.stream] == ["JioHotstar", "Netflix"]  # display order
    assert [p.name for p in movie.free] == ["YouTube (free)"]
    assert movie.trailer == "https://www.youtube.com/watch?v=abc123"
    assert cards[1].movie is None  # details failed: the card still shows


@respx.mock
async def test_tmdb_v4_token_and_bad_key(net: Net) -> None:
    route = respx.get(url__startswith=f"{TMDB}/search/movie").mock(return_value=httpx.Response(401))
    with pytest.raises(HandlerError) as caught:
        await search_movies(net, "eyJhbGciOi.token", "x")
    assert caught.value.code == "needs_key"
    assert route.calls[0].request.headers["authorization"] == "Bearer eyJhbGciOi.token"
    with pytest.raises(HandlerError):
        await search_movies(net, "", "x")


@respx.mock
async def test_commons_photos_with_licences(net: Net) -> None:
    respx.get(url__startswith="https://commons.wikimedia.org/w/api.php").mock(
        return_value=httpx.Response(
            200,
            json={
                "query": {
                    "pages": [
                        {
                            "pageid": 7,
                            "index": 2,
                            "title": "File:Bombay street 1890.jpg",
                            "imageinfo": [
                                {
                                    "descriptionurl": "https://commons.wikimedia.org/wiki/File:B.jpg",
                                    "thumburl": "https://upload.wikimedia.org/t.jpg",
                                    "extmetadata": {
                                        "LicenseShortName": {"value": "Public domain"},
                                        "Artist": {"value": "<a href='x'>Unknown</a> photographer"},
                                        "DateTimeOriginal": {"value": "1890"},
                                    },
                                }
                            ],
                        },
                        {
                            "pageid": 8,
                            "index": 1,
                            "title": "File:Gateway.png",
                            "imageinfo": [
                                {
                                    "descriptionurl": "https://commons.wikimedia.org/wiki/File:G.png",
                                    "extmetadata": {"LicenseShortName": {"value": "CC BY-SA 4.0"}},
                                }
                            ],
                        },
                    ]
                }
            },
        )
    )
    cards = await search_photos(net, "Bombay street")
    assert [c.title for c in cards] == ["Gateway", "Bombay street 1890"]  # API order
    street = cards[1]
    assert street.licence == "public_domain" and street.year == "1890"
    assert street.creator == "Unknown photographer"
    assert cards[0].licence == "cc" and street.download and street.media == "photo"
    assert licence_of({"LicenseShortName": {"value": "Copyrighted"}}) == "unknown"


@pytest.fixture
def client(env_settings: Path) -> Iterator[TestClient]:
    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_sections_api(client: TestClient) -> None:
    sections = client.get("/api/sections").json()
    ids = [s["id"] for s in sections]
    assert ids[:6] == ["movies", "books", "music", "video", "declassified", "more"]
    movies = sections[0]
    assert movies["needs_key"] == ["tmdb"] and len(movies["presets"]) >= 6
    declassified = client.get("/api/sections/declassified", params={"q": "MK Ultra"}).json()
    cia = next(link for link in declassified["links"] if "cia.gov" in link["url"])
    assert cia["url"].endswith("/MK%20Ultra")
    assert client.get("/api/sections/nope").status_code == 404
    more = next(s for s in sections if s["id"] == "more")
    assert "wayback" in more["pages"]
    assert {s["parent"] for s in sections if s["id"] in ("maps", "photos")} == {"more"}


@respx.mock(assert_all_called=False)
def test_universal_runs_a_preset(client: TestClient, respx_mock: respx.MockRouter) -> None:
    respx_mock.route(host="testserver").pass_through()
    archive = respx_mock.get(url__startswith="https://archive.org/advancedsearch.php").mock(
        return_value=httpx.Response(200, json={"response": {"numFound": 0, "docs": []}})
    )
    response = client.get("/api/universal", params={"section": "declassified", "preset": "jfk"})
    assert response.status_code == 200 and "JFK assassination records" in response.text
    assert "JFK" in str(archive.calls[0].request.url)
    assert client.get("/api/universal", params={"section": "books"}).status_code == 422
