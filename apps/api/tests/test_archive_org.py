"""archive.org handler and API: offline, with recorded metadata/search/CDX responses."""

import hashlib
import json
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from anyget.core.net import Net
from anyget.core.settings import Settings
from anyget.handlers.archive_org import (
    ArchiveOrgHandler,
    build_query,
    default_files,
    parse_item_url,
    parse_metadata,
)
from anyget.handlers.base import HandlerError, JobContext
from anyget.handlers.wayback import WaybackHandler, parse_snapshot_url, raw_url
from anyget.main import create_app

FIX = Path(__file__).parent / "fixtures" / "archive"
ID = "alicesadventures00gut"


def load(name: str) -> Any:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


CONTENT = {k: v.encode("latin1") for k, v in load("contents.json").items()}
FILES = {
    "alice.pdf": CONTENT["pdf"],
    "alice.epub": CONTENT["epub"],
    "alice_djvu.txt": CONTENT["txt"],
}


def mock_archive(mock: respx.MockRouter) -> None:
    mock.get(f"https://archive.org/metadata/{ID}").mock(
        return_value=httpx.Response(200, json=load("metadata_alice.json"))
    )
    mock.get("https://archive.org/metadata/lentbook00").mock(
        return_value=httpx.Response(200, json=load("metadata_lending.json"))
    )
    mock.get("https://archive.org/metadata/nothing00").mock(
        return_value=httpx.Response(200, json={})
    )
    for name, data in FILES.items():
        url = f"https://archive.org/download/{ID}/{name}"
        mock.head(url).mock(
            return_value=httpx.Response(
                200, headers={"Content-Length": str(len(data)), "Accept-Ranges": "bytes"}
            )
        )
        mock.get(url).mock(return_value=httpx.Response(200, content=data))


@pytest.fixture
async def handler(settings: Settings) -> AsyncIterator[ArchiveOrgHandler]:
    net = Net(settings)
    yield ArchiveOrgHandler(net)
    await net.aclose()


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (f"https://archive.org/details/{ID}", (ID, None)),
        (f"https://archive.org/details/{ID}/page/n5/mode/2up", (ID, None)),
        (f"https://archive.org/download/{ID}/alice.pdf", (ID, "alice.pdf")),
        (f"https://archive.org/download/{ID}/sub%20dir/a%20b.mp3", (ID, "sub dir/a b.mp3")),
    ],
)
def test_parse_item_url(url: str, expected: tuple[str, str | None]) -> None:
    assert parse_item_url(url) == expected


def test_can_handle(handler: ArchiveOrgHandler) -> None:
    assert handler.can_handle(f"https://archive.org/details/{ID}")
    assert handler.can_handle(f"https://www.archive.org/download/{ID}/alice.pdf")
    assert not handler.can_handle("https://web.archive.org/web/2005/http://example.com/")
    assert not handler.can_handle("https://archive.org/search?query=alice")


def test_metadata_parsing_and_defaults() -> None:
    item = parse_metadata(load("metadata_alice.json"))
    assert item.title == "Alice's Adventures in Wonderland" and item.restricted is None
    assert item.collections == ["gutenberg", "opensource"]
    assert [f.name for f in default_files(item)] == ["alice.pdf"]  # texts → Text PDF first
    lending = parse_metadata(load("metadata_lending.json"))
    assert lending.restricted == "borrow_only"


def test_build_query() -> None:
    q = build_query(
        "alice",
        mediatype="texts",
        collection="gutenberg",
        year_from=1860,
        year_to=1870,
        creator='Carroll "Lewis"',
    )
    assert q == (
        '(alice) AND mediatype:"texts" AND collection:"gutenberg" AND creator:"Carroll \\"Lewis\\""'
        " AND year:[1860 TO 1870]"
    )
    assert build_query("") == "*:*"


@respx.mock
async def test_probe_item(handler: ArchiveOrgHandler) -> None:
    mock_archive(respx.mock)
    probe = await handler.probe(f"https://archive.org/details/{ID}")
    names = [c.id for c in probe.choices]
    assert names == ["alice.pdf", "alice.epub", "alice_djvu.txt"]  # no metadata, tiles, private
    assert probe.extra["selected"] == ["alice.pdf"]
    assert {f["format"] for f in probe.extra["formats"]} == {"Text PDF", "EPUB", "DjVuTXT"}
    assert probe.thumbnail == f"https://archive.org/services/img/{ID}"


@respx.mock
async def test_metadata_is_cached(handler: ArchiveOrgHandler) -> None:
    mock_archive(respx.mock)
    await handler.item(ID)
    await handler.item(ID)
    assert respx.mock.routes[0].call_count == 1


@respx.mock
async def test_lending_and_missing_items(handler: ArchiveOrgHandler) -> None:
    mock_archive(respx.mock)
    with pytest.raises(HandlerError) as lent:
        await handler.probe("https://archive.org/details/lentbook00")
    assert lent.value.code == "borrow_only"
    with pytest.raises(HandlerError) as missing:
        await handler.probe("https://archive.org/details/nothing00")
    assert missing.value.code == "not_found"


@respx.mock
async def test_download_selected_files_with_md5(
    handler: ArchiveOrgHandler, settings: Settings
) -> None:
    mock_archive(respx.mock)
    job = JobContext(
        id="a1", url=f"https://archive.org/details/{ID}", output_dir=settings.downloads_dir
    )
    seen: list[int] = []
    result = await handler.download(
        job, {"files": ["alice.pdf", "alice.epub"]}, lambda p: seen.append(p.downloaded)
    )
    assert [p.name for p in result.paths] == ["alice.pdf", "alice.epub"]
    assert result.paths[0].parent.name == ID
    assert result.paths[0].read_bytes() == CONTENT["pdf"]
    assert result.checksum_ok is True
    assert seen[-1] == len(CONTENT["pdf"]) + len(CONTENT["epub"])


@respx.mock
async def test_download_all_of_a_format(handler: ArchiveOrgHandler, settings: Settings) -> None:
    mock_archive(respx.mock)
    job = JobContext(
        id="a2", url=f"https://archive.org/details/{ID}", output_dir=settings.downloads_dir
    )
    result = await handler.download(job, {"format": "EPUB"}, lambda _p: None)
    assert [p.name for p in result.paths] == ["alice.epub"]
    with pytest.raises(HandlerError):
        await handler.download(job, {"format": "Flac"}, lambda _p: None)


@respx.mock
async def test_single_file_link_and_bad_md5(handler: ArchiveOrgHandler, settings: Settings) -> None:
    mock_archive(respx.mock)
    url = f"https://archive.org/download/{ID}/alice_djvu.txt"
    job = JobContext(id="a3", url=url, output_dir=settings.downloads_dir)
    result = await handler.download(job, {}, lambda _p: None)
    assert [p.name for p in result.paths] == ["alice_djvu.txt"]

    respx.mock.get(f"https://archive.org/download/{ID}/alice.pdf").mock(
        return_value=httpx.Response(200, content=b"corrupted" * 10)
    )
    respx.mock.head(f"https://archive.org/download/{ID}/alice.pdf").mock(
        return_value=httpx.Response(200, headers={"Content-Length": "90"})
    )
    job = JobContext(
        id="a4", url=f"https://archive.org/details/{ID}", output_dir=settings.downloads_dir
    )
    with pytest.raises(HandlerError) as bad:
        await handler.download(job, {"files": ["alice.pdf"]}, lambda _p: None)
    assert bad.value.code == "checksum"


# ----- Wayback -----------------------------------------------------------------


def test_snapshot_urls() -> None:
    assert parse_snapshot_url("https://web.archive.org/web/20050105083000/http://example.com/") == (
        "20050105083000",
        "http://example.com/",
    )
    assert parse_snapshot_url("https://web.archive.org/web/2005id_/example.com/a.pdf") == (
        "2005",
        "http://example.com/a.pdf",
    )
    assert raw_url("20050105083000", "http://example.com/") == (
        "https://web.archive.org/web/20050105083000id_/http://example.com/"
    )


@respx.mock
async def test_wayback_raw_html_download(settings: Settings) -> None:
    raw = "https://web.archive.org/web/20050105083000id_/http://example.com/"
    html = b"<html><body>Example Web Page</body></html>"
    respx.mock.head(raw).mock(
        return_value=httpx.Response(
            200, headers={"Content-Type": "text/html", "Content-Length": str(len(html))}
        )
    )
    respx.mock.get(raw).mock(return_value=httpx.Response(200, content=html))
    net = Net(settings)
    handler = WaybackHandler(net)
    url = "https://web.archive.org/web/20050105083000/http://example.com/"
    assert handler.can_handle(url)
    probe = await handler.probe(url)
    assert probe.extra["raw_url"] == raw
    job = JobContext(id="w1", url=url, output_dir=settings.downloads_dir)
    result = await handler.download(job, {"probe": probe.model_dump(mode="json")}, lambda _p: None)
    assert result.paths[0].name == "example.com 2005-01-05.html"
    assert result.paths[0].read_bytes() == html
    await net.aclose()


# ----- API -----------------------------------------------------------------------


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with respx.mock(assert_all_called=False) as mock:
        mock_archive(mock)
        mock.get(url__startswith="https://archive.org/advancedsearch.php").mock(
            return_value=httpx.Response(200, json=load("search.json"))
        )
        mock.get(url__startswith="https://archive.org/services/search/v1/scrape").mock(
            return_value=httpx.Response(200, json=load("scrape.json"))
        )
        mock.get(url__startswith="https://web.archive.org/cdx/search/cdx").mock(
            return_value=httpx.Response(200, json=load("cdx_example.json"))
        )
        with TestClient(create_app(settings)) as test_client:
            test_client.mock = mock
            yield test_client


def test_search_endpoint(client: TestClient) -> None:
    body = client.get(
        "/api/archive/search", params={"q": "alice", "mediatype": "texts", "year_from": 1860}
    ).json()
    assert body["total"] == 2
    assert body["items"][0]["creator"] == "Carroll, Lewis"
    assert body["items"][1]["year"] == "1871"
    sent = client.mock.calls.last.request.url
    assert sent.params["q"] == '(alice) AND mediatype:"texts" AND year:[1860 TO 9999]'
    assert "identifier" in sent.params.get_list("fl[]")


def test_deep_search_returns_cursor(client: TestClient) -> None:
    body = client.get(
        "/api/archive/search", params={"q": "collection:gutenberg", "deep": True}
    ).json()
    assert body["cursor"] and body["total"] == 5000 and len(body["items"]) == 2


def test_item_endpoint(client: TestClient) -> None:
    body = client.get(f"/api/archive/items/{ID}").json()
    assert body["title"].startswith("Alice")
    assert [f["name"] for f in body["files"]] == ["alice.pdf", "alice.epub", "alice_djvu.txt"]
    assert client.get("/api/archive/items/lentbook00").json()["restricted"] == "borrow_only"


def test_probe_lending_item_is_403(client: TestClient) -> None:
    response = client.post("/api/probe", json={"url": "https://archive.org/details/lentbook00"})
    assert response.status_code == 403 and response.json()["code"] == "borrow_only"


def test_snapshots_endpoint(client: TestClient) -> None:
    body = client.get("/api/wayback/snapshots", params={"url": "example.com"}).json()
    assert body["total"] == 4
    assert body["years"] == {"2005": 2, "2012": 1, "2019": 1}
    first = body["snapshots"][0]
    assert first["raw_url"] == "https://web.archive.org/web/20050105083000id_/http://example.com/"
    assert body["snapshots"][2]["length"] is None


def test_snapshots_blocks_private_targets(client: TestClient) -> None:
    response = client.get("/api/wayback/snapshots", params={"url": "http://127.0.0.1/"})
    assert response.status_code == 400


def test_md5_fixture_is_consistent() -> None:
    files = {f["name"]: f for f in load("metadata_alice.json")["files"]}
    assert files["alice.pdf"]["md5"] == hashlib.md5(CONTENT["pdf"]).hexdigest()
