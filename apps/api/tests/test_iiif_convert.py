"""IIIF libraries, conversions (images → PDF, OCR, ffmpeg) and the books/search APIs."""

import io
import json
import os
import shutil
import stat
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from PIL import Image

from anyget.convert.pdf import images_to_pdf
from anyget.core.db import Database
from anyget.core.jobs import JobState, JobStore
from anyget.core.net import Net
from anyget.core.services import build_registry
from anyget.core.settings import Settings
from anyget.handlers.base import HandlerError, JobContext
from anyget.handlers.convert import ConvertHandler, convert_url, parse
from anyget.handlers.iiif_library import IiifLibraryHandler, manifest_url_for, parse_manifest
from anyget.libraries.registry import LIBRARIES, REGIONS, library_for_host
from anyget.main import create_app

FIX = Path(__file__).parent / "fixtures" / "iiif"


def manifest(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIX / name).read_text(encoding="utf-8"))
    return data


def jpeg(color: str = "red", size: tuple[int, int] = (40, 60)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, "JPEG")
    return buffer.getvalue()


@pytest.fixture
async def net(settings: Settings) -> AsyncIterator[Net]:
    n = Net(settings)
    yield n
    await n.aclose()


# ----- registry ------------------------------------------------------------------


def test_registry_covers_every_region() -> None:
    assert {lib.region for lib in LIBRARIES} == set(REGIONS)
    assert len({lib.id for lib in LIBRARIES}) == len(LIBRARIES)
    lib = library_for_host("gallica.bnf.fr")
    assert lib is not None and lib.name.startswith("Gallica")
    assert library_for_host("example.org") is None


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://gallica.bnf.fr/ark:/12148/bpt6k5545437j/f1.item",
            "https://gallica.bnf.fr/iiif/ark:/12148/bpt6k5545437j/manifest.json",
        ),
        (
            "https://www.loc.gov/item/2021667404/",
            "https://www.loc.gov/item/2021667404/manifest.json",
        ),
        (
            "https://dl.ndl.go.jp/pid/2567680",
            "https://www.dl.ndl.go.jp/api/iiif/2567680/manifest.json",
        ),
        (
            "https://dl.ndl.go.jp/info:ndljp/pid/2567680",
            "https://www.dl.ndl.go.jp/api/iiif/2567680/manifest.json",
        ),
        (
            "https://www.europeana.eu/en/item/9200365/BibliographicResource_3000",
            "https://iiif.europeana.eu/presentation/9200365/BibliographicResource_3000/manifest",
        ),
        (
            "https://www.qdl.qa/en/archive/81055/vdc_100000000833.0x000001",
            "https://www.qdl.qa/en/iiif/81055/vdc_100000000833.0x000001/manifest",
        ),
        (
            "https://iiif.example.org/books/42/manifest.json",
            "https://iiif.example.org/books/42/manifest.json",
        ),
        ("https://gallica.bnf.fr/services/engine/search", None),
        ("https://example.org/page.html", None),
    ],
)
def test_manifest_urls(url: str, expected: str | None) -> None:
    assert manifest_url_for(url) == expected


def test_parse_v2_and_v3() -> None:
    v2 = parse_manifest(manifest("v2.json"))
    assert v2.title == "Les misérables" and len(v2.pages) == 2
    assert v2.pages[0].url == (
        "https://gallica.bnf.fr/iiif/ark:/12148/bpt6k5545437j/f1/full/full/0/default.jpg"
    )
    assert v2.attribution == "Bibliothèque nationale de France"
    v3 = parse_manifest(manifest("v3.json"))
    assert v3.title == "源氏物語" and len(v3.pages) == 2  # the empty canvas is skipped
    assert v3.pages[1].url.endswith("/R0000002/full/max/0/default.jpg")
    assert v3.attribution == "National Diet Library"


@respx.mock
async def test_iiif_probe_download_and_pdf(net: Net, settings: Settings) -> None:
    respx.get("https://www.dl.ndl.go.jp/api/iiif/2567680/manifest.json").mock(
        return_value=httpx.Response(200, json=manifest("v3.json"))
    )
    for n, color in ((1, "red"), (2, "blue")):
        url = f"https://dl.ndl.go.jp/api/iiif/2567680/R000000{n}/full/max/0/default.jpg"
        data = jpeg(color)
        respx.head(url).mock(
            return_value=httpx.Response(200, headers={"Content-Length": str(len(data))})
        )
        respx.get(url).mock(return_value=httpx.Response(200, content=data))
    handler = IiifLibraryHandler(net, settings)
    item = "https://dl.ndl.go.jp/pid/2567680"
    assert handler.can_handle(item)
    probe = await handler.probe(item)
    assert probe.extra["count"] == 2 and probe.extra["library"] == "National Diet Library"
    assert probe.extra["items"][0]["url"].endswith("/full/240,/0/default.jpg")
    job = JobContext(id="i1", url=item, output_dir=settings.downloads_dir)
    result = await handler.download(job, {"pdf": True}, lambda _p: None)
    pdf, *pages = result.paths
    assert pdf.name == "源氏物語.pdf" and pdf.read_bytes().startswith(b"%PDF")
    assert [p.name for p in pages] == ["0001.jpg", "0002.jpg"]
    only_second = await handler.download(
        JobContext(id="i2", url=item, output_dir=settings.downloads_dir / "b"),
        {"files": ["2"]},
        lambda _p: None,
    )
    assert [p.name for p in only_second.paths] == ["0002.jpg"]


@respx.mock
async def test_iiif_refuses_in_copyright_and_restricted(net: Net, settings: Settings) -> None:
    respx.get("https://iiif.example.org/a/manifest.json").mock(
        return_value=httpx.Response(200, json=manifest("v3_in_copyright.json"))
    )
    respx.get("https://iiif.example.org/b/manifest.json").mock(return_value=httpx.Response(403))
    handler = IiifLibraryHandler(net, settings)
    for url, code in (
        ("https://iiif.example.org/a/manifest.json", "in_copyright"),
        ("https://iiif.example.org/b/manifest.json", "restricted"),
    ):
        with pytest.raises(HandlerError) as info:
            await handler.probe(url)
        assert info.value.code == code


def test_registry_routes_library_and_book_links(settings: Settings) -> None:
    registry = build_registry(Net(settings), settings)
    assert registry.find("https://gallica.bnf.fr/ark:/12148/bpt6k5545437j").name == "iiif_library"  # type: ignore[union-attr]
    assert registry.find("https://www.gutenberg.org/ebooks/1342").name == "books"  # type: ignore[union-attr]


# ----- conversions -----------------------------------------------------------------


def test_images_to_pdf_handles_png_with_alpha(tmp_path: Path) -> None:
    a = tmp_path / "a.png"
    Image.new("RGBA", (30, 30), (255, 0, 0, 128)).save(a)
    b = tmp_path / "b.jpg"
    b.write_bytes(jpeg())
    out = images_to_pdf([a, b], tmp_path / "out.pdf")
    assert out.read_bytes().startswith(b"%PDF") and not (tmp_path / ".out.tmp").exists()


@pytest.fixture
def store(settings: Settings) -> JobStore:
    settings.downloads_dir.mkdir(parents=True, exist_ok=True)
    db = Database(settings)
    db.create_all()
    return JobStore(db)


def done_job(store: JobStore, settings: Settings, files: list[str]) -> str:
    job = store.create("https://example.org/x")
    for rel in files:
        path = settings.downloads_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(jpeg() if rel.endswith(".jpg") else b"%PDF-1.4 x")
    store.update(job.id, state=JobState.done, rel_path=files[0], files=files[1:] or None)
    return job.id


def test_convert_links_round_trip() -> None:
    url = convert_url("abc", "ocr", "eng+hin")
    assert parse(url) == ("abc", "ocr", "eng+hin")
    with pytest.raises(HandlerError):
        parse("anyget:convert?job=abc&to=exe")


async def test_pages_become_a_pdf_next_to_their_folder(settings: Settings, store: JobStore) -> None:
    job_id = done_job(store, settings, ["Book/0001.jpg", "Book/0002.jpg"])
    handler = ConvertHandler(settings, store)
    url = convert_url(job_id, "pdf")
    probe = await handler.probe(url)
    assert probe.extra["inputs"] == 2
    result = await handler.download(
        JobContext(id="c1", url=url, output_dir=settings.downloads_dir), {}, lambda _p: None
    )
    assert result.paths[0] == (settings.downloads_dir / "Book.pdf").resolve()


async def test_convert_refuses_files_outside_downloads(
    settings: Settings, store: JobStore, tmp_path: Path
) -> None:
    job = store.create("https://example.org/x")
    store.update(job.id, state=JobState.done, rel_path="../outside.pdf")
    (tmp_path / "outside.pdf").write_bytes(b"%PDF")
    with pytest.raises(HandlerError) as info:
        await ConvertHandler(settings, store).probe(convert_url(job.id, "ocr"))
    assert info.value.code == "unsafe_path"


def fake_tool(folder: Path, name: str, script: str) -> None:
    path = folder / name
    path.write_text("#!/bin/sh\n" + script, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


async def test_ocr_runs_ocrmypdf_with_languages(
    settings: Settings, store: JobStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "args.txt"
    # Fake ocrmypdf: record args, copy input to output, write the sidecar text.
    fake_tool(
        bin_dir,
        "ocrmypdf",
        f'echo "$@" > {log}\n'
        'while [ $# -gt 2 ]; do case "$1" in --sidecar) side="$2"; shift;; esac; shift; done\n'
        'echo "hello world" > "$side"; cp "$1" "$2"\n',
    )
    fake_tool(bin_dir, "tesseract", 'printf "List of available languages (2):\\neng\\nhin\\n"\n')
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    from anyget.convert import ocr

    ocr.languages.cache_clear()
    job_id = done_job(store, settings, ["scan.pdf"])
    url = convert_url(job_id, "ocr", "eng+hin+xyz")
    result = await ConvertHandler(settings, store).download(
        JobContext(id="c2", url=url, output_dir=settings.downloads_dir), {}, lambda _p: None
    )
    assert result.paths[0].name == "scan (OCR).pdf"
    assert result.paths[1].read_text().strip() == "hello world"
    assert "-l eng+hin " in log.read_text()  # unknown language dropped
    ocr.languages.cache_clear()


async def test_ocr_without_tools_says_so(
    settings: Settings, store: JobStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("anyget.convert.ocr.which", lambda _name: None)
    job_id = done_job(store, settings, ["scan.pdf"])
    with pytest.raises(HandlerError) as info:
        await ConvertHandler(settings, store).probe(convert_url(job_id, "ocr"))
    assert info.value.code == "tool_missing"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
async def test_ffmpeg_audio_conversion(settings: Settings, store: JobStore) -> None:
    import subprocess

    source = settings.downloads_dir / "tone.wav"
    settings.downloads_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(  # noqa: S603, ASYNC221
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=duration=0.5", str(source)],  # noqa: S607
        check=True,
    )
    job_id = done_job(store, settings, ["tone.wav"])
    url = convert_url(job_id, "m4a")
    result = await ConvertHandler(settings, store).download(
        JobContext(id="c3", url=url, output_dir=settings.downloads_dir), {}, lambda _p: None
    )
    assert result.paths[0].name == "tone.m4a" and result.paths[0].stat().st_size > 0


# ----- API ---------------------------------------------------------------------------


@pytest.fixture
def client(env_settings: Path) -> Any:
    with TestClient(create_app()) as test_client:
        yield test_client


def test_libraries_api(client: TestClient) -> None:
    body = client.get("/api/libraries").json()
    assert body["regions"][0] == "global"
    gallica = next(lib for lib in body["libraries"] if lib["id"] == "gallica")
    assert gallica["searchable"] is True and gallica["key_configured"] is None
    trove = next(lib for lib in body["libraries"] if lib["id"] == "trove")
    assert trove["key_configured"] is False


def test_key_status_never_shows_values(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    body = client.get("/api/settings/keys").json()
    assert {k["name"] for k in body} >= {"europeana_key", "dpla_key", "github_token"}
    assert all(set(k) == {"name", "env", "configured"} for k in body)


@respx.mock(assert_all_called=False)
def test_universal_search_books_tab(client: TestClient, respx_mock: respx.MockRouter) -> None:
    respx_mock.route(host="testserver").pass_through()
    respx_mock.get(url__startswith="https://gutendex.com/books").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": 11,
                        "title": "Alice's Adventures in Wonderland",
                        "authors": [{"name": "Carroll, Lewis"}],
                        "formats": {
                            "application/epub+zip": "https://www.gutenberg.org/ebooks/11.epub3.images"
                        },
                    }
                ]
            },
        )
    )
    respx_mock.get(url__regex=r"https://(?!gutendex).*").mock(return_value=httpx.Response(503))
    body = client.get("/api/search", params={"q": "alice wonderland", "types": ["books"]}).json()
    assert body["archive"] is None and body["videos"] is None
    assert body["books"]["best"]["source"] == "gutendex"
    assert {s["name"]: s["status"] for s in body["books"]["sources"]}["dpla"] == "needs_key"


def test_convert_api_needs_a_known_job(client: TestClient) -> None:
    response = client.post("/api/convert", json={"job_id": "nope", "to": "pdf"})
    assert response.status_code == 404
    bad = client.post("/api/convert", json={"job_id": "x", "to": "exe"})
    assert bad.status_code == 422


@respx.mock
async def test_loc_falls_back_to_item_json(net: Net, settings: Settings) -> None:
    respx.get("https://www.loc.gov/item/16014724/manifest.json").mock(
        return_value=httpx.Response(403)
    )
    respx.get("https://www.loc.gov/item/16014724/?fo=json").mock(
        return_value=httpx.Response(
            200,
            json={
                "item": {"title": "Alice's adventures in Wonderland", "access_restricted": False},
                "resources": [
                    {
                        "files": [
                            [
                                {
                                    "mimetype": "image/jpeg",
                                    "url": "https://tile.loc.gov/p1-150.jpg",
                                    "width": 150,
                                },
                                {
                                    "mimetype": "image/jpeg",
                                    "url": "https://tile.loc.gov/p1-full.jpg",
                                    "width": 2400,
                                },
                                {
                                    "mimetype": "image/tiff",
                                    "url": "https://tile.loc.gov/p1.tif",
                                    "width": 2400,
                                },
                            ],
                            [
                                {
                                    "mimetype": "image/jpeg",
                                    "url": "https://tile.loc.gov/p2.jpg",
                                    "width": 800,
                                }
                            ],
                        ]
                    }
                ],
            },
        )
    )
    probe = await IiifLibraryHandler(net, settings).probe("https://www.loc.gov/item/16014724/")
    assert probe.title == "Alice's adventures in Wonderland" and probe.extra["count"] == 2
    assert probe.extra["items"][0]["url"] == "https://tile.loc.gov/p1-150.jpg"
    respx.get("https://www.loc.gov/item/2/manifest.json").mock(return_value=httpx.Response(403))
    respx.get("https://www.loc.gov/item/2/?fo=json").mock(
        return_value=httpx.Response(200, json={"item": {"access_restricted": True}})
    )
    with pytest.raises(HandlerError) as info:
        await IiifLibraryHandler(net, settings).probe("https://www.loc.gov/item/2/")
    assert info.value.code == "restricted"
