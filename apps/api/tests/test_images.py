"""Direct images and Wikimedia file pages keep their format (never saved as video)."""

import hashlib
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import respx

from anyget.core.net import Net
from anyget.core.router import Router, is_image_link
from anyget.core.services import build_registry
from anyget.core.settings import Settings
from anyget.handlers.base import HandlerError, JobContext
from anyget.handlers.http_generic import HttpGenericHandler, with_extension
from anyget.handlers.wikimedia import WikimediaHandler, file_title

JPEG = b"\xff\xd8\xff\xe0" + b"fake jpeg body" * 10
ORIGINAL = "https://upload.wikimedia.org/wikipedia/commons/a/a7/Taj_Mahal_(Edited).jpeg"
COMMONS = "https://commons.wikimedia.org"
API = f"{COMMONS}/w/api.php"


@pytest.fixture
async def net(settings: Settings) -> AsyncIterator[Net]:
    n = Net(settings)
    yield n
    await n.aclose()


def imageinfo(sha1: str = hashlib.sha1(JPEG).hexdigest()) -> dict[str, object]:
    return {
        "query": {
            "pages": [
                {
                    "title": "File:Taj Mahal (Edited).jpeg",
                    "imageinfo": [
                        {
                            "url": ORIGINAL,
                            "size": len(JPEG),
                            "mime": "image/jpeg",
                            "sha1": sha1,
                            "width": 4000,
                            "height": 2700,
                            "thumburl": "https://upload.wikimedia.org/thumb/640px-Taj.jpeg",
                            "extmetadata": {"LicenseShortName": {"value": "CC BY-SA 4.0"}},
                        }
                    ],
                }
            ]
        }
    }


@pytest.mark.parametrize(
    ("url", "title"),
    [
        (f"{COMMONS}/wiki/File:Taj_Mahal_(Edited).jpeg", "File:Taj Mahal (Edited).jpeg"),
        ("https://en.wikipedia.org/wiki/File:Logo.svg", "File:Logo.svg"),
        ("https://commons.wikimedia.org/wiki/Image:Old%20name.png", "File:Old name.png"),
        ("https://commons.wikimedia.org/wiki/Main_Page", None),
        (ORIGINAL, None),
        ("https://example.org/wiki/File:x.jpg", None),
    ],
)
def test_file_title(url: str, title: str | None) -> None:
    assert file_title(url) == title


def test_image_links_and_extensions() -> None:
    assert is_image_link("https://example.org/a/b.WEBP?x=1")
    assert not is_image_link("https://example.org/watch?v=1")
    assert with_extension("photo", "image/png") == "photo.png"
    assert with_extension("photo.jpg", "image/png") == "photo.jpg"
    assert with_extension("notes", "text/plain") == "notes"


@respx.mock
async def test_commons_page_downloads_the_original(net: Net, settings: Settings) -> None:
    respx.get(url__startswith=API).mock(return_value=httpx.Response(200, json=imageinfo()))
    respx.get(ORIGINAL).mock(
        return_value=httpx.Response(200, content=JPEG, headers={"Content-Type": "image/jpeg"})
    )
    handler = WikimediaHandler(net)
    page = "https://commons.wikimedia.org/wiki/File:Taj_Mahal_(Edited).jpeg"
    probe = await handler.probe(page)
    assert probe.extra["kind"] == "image" and probe.extra["license"] == "CC BY-SA 4.0"
    assert probe.choices[0].ext == "jpeg" and probe.size == len(JPEG)
    assert probe.thumbnail and probe.thumbnail.endswith("640px-Taj.jpeg")

    job = JobContext(id="j1", url=page, output_dir=settings.downloads_dir)
    result = await handler.download(job, {"probe": probe.model_dump(mode="json")}, lambda _: None)
    assert [p.name for p in result.paths] == ["Taj_Mahal_(Edited).jpeg"]
    assert result.paths[0].read_bytes() == JPEG and result.checksum_ok is True


@respx.mock
async def test_commons_sha1_mismatch_is_refused(net: Net, settings: Settings) -> None:
    respx.get(url__startswith=API).mock(
        return_value=httpx.Response(200, json=imageinfo(sha1="0" * 40))
    )
    respx.get(ORIGINAL).mock(return_value=httpx.Response(200, content=JPEG))
    handler = WikimediaHandler(net)
    page = "https://commons.wikimedia.org/wiki/File:Taj_Mahal_(Edited).jpeg"
    job = JobContext(id="j2", url=page, output_dir=settings.downloads_dir)
    with pytest.raises(HandlerError) as caught:
        await handler.download(job, {}, lambda _: None)
    assert caught.value.code == "checksum"


@respx.mock
async def test_missing_commons_file(net: Net) -> None:
    respx.get(url__startswith=API).mock(
        return_value=httpx.Response(200, json={"query": {"pages": [{"missing": True}]}})
    )
    with pytest.raises(HandlerError) as caught:
        await WikimediaHandler(net).probe("https://commons.wikimedia.org/wiki/File:Nope.jpg")
    assert caught.value.code == "not_found"


@respx.mock
async def test_direct_image_probe_is_an_image(net: Net) -> None:
    url = "https://example.org/pictures/photo"
    respx.head(url).mock(
        return_value=httpx.Response(
            200, headers={"Content-Type": "image/webp", "Content-Length": "10"}
        )
    )
    probe = await HttpGenericHandler(net).probe(url)
    assert probe.extra["kind"] == "image" and probe.extra["filename"] == "photo.webp"
    assert probe.thumbnail == url


async def test_router_sends_images_to_the_file_handler(
    net: Net, settings: Settings, tmp_path: Path
) -> None:
    router = Router(build_registry(net, settings), net)
    _, page = await router.resolve("https://commons.wikimedia.org/wiki/File:Taj_Mahal.jpg")
    assert page.name == "wikimedia"
    _, direct = await router.resolve(ORIGINAL)
    assert direct.name == "http"


@respx.mock
async def test_html_instead_of_a_book_is_never_saved(net: Net, settings: Settings) -> None:
    page = b"<html><title>Your Download Has Started</title></html>"
    url = "https://standardebooks.org/ebooks/a/b/downloads/a_b.epub"
    respx.head(url).mock(
        return_value=httpx.Response(200, headers={"Content-Type": "text/html; charset=utf-8"})
    )
    http = HttpGenericHandler(net)
    with pytest.raises(HandlerError) as caught:
        await http.probe(url)
    assert caught.value.code == "not_a_file"

    # HEAD says EPUB, but the download itself answers with a web page.
    tricky = "https://example.org/files/book"
    respx.head(tricky).mock(
        return_value=httpx.Response(
            200, headers={"Content-Type": "application/epub+zip", "Content-Length": "100"}
        )
    )
    respx.get(tricky).mock(
        return_value=httpx.Response(200, content=page, headers={"Content-Type": "text/html"})
    )
    job = JobContext(id="b1", url=tricky, output_dir=settings.downloads_dir)
    with pytest.raises(HandlerError) as caught:
        await http.download(job, {}, lambda _: None)
    assert caught.value.code == "not_a_file"
    assert not any(settings.downloads_dir.glob("*.epub"))


def test_failed_jobs_name_the_site_to_connect() -> None:
    from anyget.core.sites import connect_site

    def site(code: str, url: str) -> str | None:
        found = connect_site(code, url)
        return found.id if found else None

    assert site("bot_check", "https://www.youtube.com/watch?v=x") == "youtube"
    assert site("login_required", "https://mobile.x.com/a/status/1") == "x"
    assert site("forbidden", "https://old.reddit.com/r/a") == "reddit"
    assert site("login_required", "https://www.example.org/v") is None
    assert site("geo_blocked", "https://www.youtube.com/watch?v=x") is None
    assert site("members_only", "https://www.youtube.com/watch?v=x") is None
