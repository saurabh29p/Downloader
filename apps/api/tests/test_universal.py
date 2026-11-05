"""Universal search (v2 Phase 3): classify, plan, fan out, stream result cards."""

import asyncio
import json
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from anyget.core.net import Net
from anyget.core.settings import Settings, get_settings
from anyget.handlers.archive_org import SearchHit
from anyget.main import create_app
from anyget.universal.classify import classify, language_of
from anyget.universal.engine import Engine, archive_licence
from anyget.universal.keyword_router import clean_query, plan
from anyget.universal.models import ResultCard, SourceDone, UniversalDone

ARCHIVE = "https://archive.org/advancedsearch.php"


def docs(*items: dict[str, Any]) -> dict[str, Any]:
    return {"response": {"numFound": len(items), "docs": list(items)}}


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("https://www.youtube.com/watch?v=abc", "url"),
        ("look https://a.example/x.pdf https://b.example/y", "url"),
        ("magnet:?xt=urn:btih:abc", "url"),
        ("Taj Mahal", "search"),
        ("pride and prejudice epub", "search"),
        ("who built the Taj Mahal", "question"),
        ("old maps of Delhi?", "question"),
        ("ताज महल किसने बनवाया?", "question"),
        ("kya hai taj mahal ka itihas", "question"),
        ("من بنى تاج محل؟", "question"),
        ("what", "search"),  # one word is a search
    ],
)
def test_classify(text: str, kind: str) -> None:
    assert classify(text)[0] == kind


def test_links_and_languages() -> None:
    _, links = classify("see (https://a.example/x.pdf), and https://a.example/x.pdf.")
    assert links == ["https://a.example/x.pdf"]
    assert language_of("ताज महल") == "hi"
    assert language_of("تاج محل") == "ar"
    assert language_of("taj mahal ka gaana") == "hinglish"
    assert language_of("Taj Mahal") == "en"


def test_plans() -> None:
    open_plan = plan("Taj Mahal")
    assert open_plan.kind == "search" and open_plan.media == []
    assert [q.source for q in open_plan.queries] == ["archive", "books", "videos", "libraries"]

    film = plan("download taj mahal film")
    assert film.media == ["movie"] and film.intent == "download"
    assert [q.source for q in film.queries] == ["tmdb", "archive", "videos"]
    assert film.queries[1].q == "taj mahal" and film.queries[1].filters == {"mediatype": "movies"}

    books = plan("Godaan", section="books")
    assert books.media == ["book"] and books.queries[0].source == "books"

    question = plan("who built the Taj Mahal?")
    assert question.answer_needed and question.intent == "explore"
    assert question.queries[0].q == "who built Taj Mahal"

    hindi = plan("ताज महल फिल्म")
    assert hindi.media == ["movie"] and hindi.language == "hi"
    assert hindi.queries[0].q == "ताज महल"

    links = plan("https://example.org/a.pdf")
    assert links.kind == "url" and links.urls == ["https://example.org/a.pdf"]
    assert links.queries == []
    assert clean_query("free hd") == "free hd"  # nothing left: keep what was typed


def test_archive_licences() -> None:
    def hit(url: str | None) -> SearchHit:
        return SearchHit(identifier="x", title="x", thumbnail="t", licenseurl=url)

    assert archive_licence(hit("http://creativecommons.org/publicdomain/mark/1.0/")) == (
        "public_domain"
    )
    assert archive_licence(hit("https://creativecommons.org/licenses/by/4.0/")) == "cc"
    assert archive_licence(hit(None)) == "unknown"


@pytest.fixture
async def net(settings: Settings) -> AsyncIterator[Net]:
    n = Net(settings)
    yield n
    await n.aclose()


@respx.mock
async def test_engine_streams_each_source_then_done(net: Net, settings: Settings) -> None:
    settings.book_sources = ["gutendex"]
    respx.get(url__startswith=ARCHIVE).mock(
        return_value=httpx.Response(
            200,
            json=docs(
                {
                    "identifier": "band",
                    "title": "Taj Mahal Live",
                    "mediatype": "etree",
                    "creator": "Taj Mahal",
                    "collection": ["etree"],
                    "downloads": 90000,
                },
                {
                    "identifier": "agra",
                    "title": "The Taj Mahal, Agra",
                    "mediatype": "image",
                    "subject": ["Taj Mahal"],
                    "downloads": 10,
                    "licenseurl": "https://creativecommons.org/licenses/by/4.0/",
                },
            ),
        )
    )
    respx.get(url__startswith="https://gutendex.com/books").mock(
        return_value=httpx.Response(200, json={"results": []})
    )

    async def slow_videos(query: str, limit: int) -> list[dict[str, Any]]:
        await asyncio.sleep(0.05)
        return [{"id": "v1", "title": "Taj Mahal tour", "url": "https://youtu.be/v1"}]

    engine = Engine(net, settings, slow_videos)
    parts = [p async for p in engine.stream(plan("Taj Mahal"))]
    sources = [p for p in parts if isinstance(p, SourceDone)]
    done = parts[-1]
    assert isinstance(done, UniversalDone) and len(sources) == 4
    archive = next(s for s in sources if s.source == "archive")
    assert [c.id for c in archive.results] == ["archive:agra", "archive:band"]  # place first
    agra = archive.results[0]
    assert agra.media == "photo" and agra.licence == "cc"
    assert agra.download == "https://archive.org/details/agra"
    videos = next(s for s in sources if s.source == "videos")
    assert videos.results[0].media == "video" and videos.results[0].licence == "unknown"
    assert done.counts == {"photo": 1, "music": 1, "video": 1} and done.total == 3


async def test_a_failing_or_slow_source_does_not_stop_the_rest(
    net: Net, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from anyget.universal import engine as engine_mod

    async def broken(query: str, limit: int) -> list[dict[str, Any]]:
        raise RuntimeError("down")

    monkeypatch.setitem(engine_mod.TIME_LIMIT, "archive", 0.01)

    async def never(*args: Any, **kwargs: Any) -> Any:
        await asyncio.sleep(5)

    monkeypatch.setattr(engine_mod, "archive_search", never)
    engine = Engine(net, settings, broken)
    film = plan("taj mahal film")
    statuses = {p.source: p.status async for p in engine.stream(film) if isinstance(p, SourceDone)}
    assert statuses == {"tmdb": "needs_key", "archive": "timeout", "videos": "error"}


@pytest.fixture
def client(env_settings: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("ANYGET_BOOK_SOURCES", "gutendex")
    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def events(text: str) -> list[tuple[str, Any]]:
    out = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if "event" in lines:
            out.append((lines["event"], json.loads(lines["data"])))
    return out


@respx.mock(assert_all_called=False)
def test_universal_endpoint(client: TestClient, respx_mock: respx.MockRouter) -> None:
    respx_mock.route(host="testserver").pass_through()
    respx_mock.get(url__startswith=ARCHIVE).mock(
        return_value=httpx.Response(
            200,
            json=docs(
                {"identifier": "m", "title": "Metropolis", "mediatype": "movies", "year": "1927"}
            ),
        )
    )
    response = client.get("/api/universal", params={"q": "Metropolis", "section": "movies"})
    assert response.headers["content-type"].startswith("text/event-stream")
    got = events(response.text)
    assert got[0][0] == "plan" and got[0][1]["media"] == ["movie"]
    archive = next(data for name, data in got if name == "source" and data["source"] == "archive")
    card = ResultCard.model_validate(archive["results"][0])
    assert card.title == "Metropolis" and card.year == "1927" and card.media == "movie"
    assert got[-1][0] == "done"

    posted = client.post("/api/universal", json={"text": "https://example.org/a.pdf"})
    got = events(posted.text)
    assert [name for name, _ in got] == ["plan", "done"]
    assert got[0][1]["kind"] == "url" and got[0][1]["urls"] == ["https://example.org/a.pdf"]
    assert client.get("/api/universal", params={"q": "x", "section": "nope"}).status_code == 422


def test_saved_from_search_gets_library_tags(client: TestClient, env_settings: Path) -> None:
    services = client.app.state.services  # type: ignore[attr-defined]
    root = env_settings / "downloads"
    root.mkdir(parents=True, exist_ok=True)
    (root / "film.mp4").write_bytes(b"x")
    job = services.store.create("https://example.org/film.mp4", {"tags": ["saved", " "]})
    job = services.store.update(job.id, rel_path="film.mp4")
    items = services.library.add_job_sync(job)
    assert items[0].tags == ["saved"]
