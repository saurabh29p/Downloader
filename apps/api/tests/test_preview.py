"""Previews: real file types, byte ranges, text pages, the EPUB reader, subtitles, access."""

import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from anyget.core.jobs import JobState
from anyget.library.inspect import inspect, read_text, sniff, srt_to_vtt
from anyget.main import create_app
from tests.test_owner_auth import make_client, owner, sign_in  # noqa: F401 - fixture
from tests.test_phase8 import make_epub

MP4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2" + bytes(range(256)) * 40


@pytest.fixture
def client(env_settings: Path) -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


def _scan(client: TestClient) -> dict[str, dict[str, Any]]:
    client.post("/api/library/scan")
    return {Path(i["rel_path"]).name: i for i in client.get("/api/library").json()["items"]}


@pytest.mark.parametrize(
    ("head", "name", "preview", "mime"),
    [
        (b"%PDF-1.7\n", "report.bin", "pdf", "application/pdf"),
        (MP4[:40], "clip", "video", "video/mp4"),
        (b"\x00\x00\x00\x18ftypM4A \x00\x00", "song.m4a", "audio", "audio/mp4"),
        (
            b"\x1aE\xdf\xa3\x9fB\x86\x81\x01B\xf7\x81\x01B\xf2\x81\x04B\x82\x84webm",
            "v.mkv",
            "video",
            "video/webm",
        ),
        (b"ID3\x04\x00", "a.mp3", "audio", "audio/mpeg"),
        (b"OggS\x00\x02" + b"\x00" * 22 + b"OpusHead", "a.opus", "audio", "audio/ogg"),
        (b"fLaC\x00", "a.flac", "audio", "audio/flac"),
        (b"\x89PNG\r\n\x1a\n", "p.jpg", "image", "image/png"),
        (b"\xff\xd8\xff\xe0", "photo", "image", "image/jpeg"),
        (
            b"<?xml version='1.0'?><svg xmlns='http://www.w3.org/2000/svg'/>",
            "a.svg",
            "image",
            "image/svg+xml",
        ),
        (b"II*\x00", "scan.tif", "none", "image/tiff"),
        (
            b"PK\x03\x04\x14\x00\x00\x00\x00\x00mimetypeapplication/epub+zip",
            "b.epub",
            "epub",
            "application/epub+zip",
        ),
        (
            b"PK\x03\x04[Content_Types].xml",
            "a.docx",
            "none",
            "application/vnd.openxmlformats-officedocument",
        ),
        (b"<!DOCTYPE html><html>", "page.htm", "text", "text/html"),
        ("नमस्ते दुनिया".encode(), "note", "text", "text/plain"),
        (b"\x00\x01\x02binary", "x.dat", "none", "application/octet-stream"),
    ],
)
def test_sniff_uses_bytes_before_names(head: bytes, name: str, preview: str, mime: str) -> None:
    assert sniff(head, name) == (preview, mime)


def test_inspect_reasons_and_subtitles(tmp_path: Path) -> None:
    (tmp_path / "talk.mp4").write_bytes(MP4)
    (tmp_path / "talk.en.srt").write_text("1\n00:00:01,000 --> 00:00:02,500\nHello\n")
    (tmp_path / "talk.hi.vtt").write_text("WEBVTT\n\n00:01.000 --> 00:02.000\nनमस्ते\n")
    (tmp_path / "other.en.srt").write_text("x")
    info = inspect(tmp_path / "talk.mp4")
    assert info.preview == "video" and [s.lang for s in info.subtitles] == ["en", "hi"]
    (tmp_path / "empty.pdf").write_bytes(b"")
    assert inspect(tmp_path / "empty.pdf").reason == "empty"
    assert inspect(tmp_path / "gone.pdf").reason == "missing"
    (tmp_path / "a.zip").write_bytes(b"PK\x03\x04rest")
    assert inspect(tmp_path / "a.zip").reason == "archive"
    vtt = srt_to_vtt("1\r\n00:00:01,000 --> 00:00:02,500\r\nHello\r\n")
    assert vtt.startswith("WEBVTT\n\n") and "00:00:01.000 --> 00:00:02.500" in vtt


def test_text_pages_never_split_a_character(tmp_path: Path) -> None:
    path = tmp_path / "hindi.txt"
    path.write_text("क" * 10, encoding="utf-8")  # 3 bytes each
    first, after = read_text(path, 0, 4)
    assert first == "क" and after == 3
    rest, end = read_text(path, after, 100)
    assert rest == "क" * 9 and end is None


def test_preview_api(client: TestClient, env_settings: Path) -> None:
    root = env_settings / "downloads"
    root.mkdir(parents=True, exist_ok=True)
    (root / "clip").write_bytes(MP4)  # no extension: sniffed as MP4
    (root / "clip.en.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHi\n")
    (root / "notes.txt").write_text("line one\nदूसरी पंक्ति\n" * 2000, encoding="utf-8")
    (root / "page.html").write_text("<p>Visible</p><script>steal()</script>")
    make_epub(root / "story.epub", ["Once upon a time.", "The end."])
    (root / "broken.epub").write_bytes(b"PK\x03\x04 not really a zip")
    items = _scan(client)
    clip = items["clip"]["id"]

    info = client.get(f"/api/library/{clip}/info").json()
    assert info["preview"] == "video" and info["mime"] == "video/mp4"
    assert info["subtitles"] == [{"index": 0, "label": "en", "lang": "en"}]
    full = client.get(f"/api/library/{clip}/file")
    assert full.headers["content-type"] == "video/mp4"
    assert full.headers["accept-ranges"] == "bytes"
    part = client.get(f"/api/library/{clip}/file", headers={"Range": "bytes=10-19"})
    assert part.status_code == 206 and part.content == MP4[10:20]
    assert part.headers["content-range"] == f"bytes 10-19/{len(MP4)}"
    tail = client.get(f"/api/library/{clip}/file", headers={"Range": "bytes=-5"})
    assert tail.status_code == 206 and tail.content == MP4[-5:]
    bad = client.get(f"/api/library/{clip}/file", headers={"Range": f"bytes={len(MP4) + 10}-"})
    assert bad.status_code == 416
    vtt = client.get(f"/api/library/{clip}/subtitles/0")
    assert vtt.headers["content-type"].startswith("text/vtt") and "00:00:01.000" in vtt.text
    assert client.get(f"/api/library/{clip}/subtitles/3").status_code == 404

    notes = items["notes.txt"]["id"]
    page = client.get(f"/api/library/{notes}/text", params={"limit": 4096}).json()
    assert page["offset"] == 0 and page["next_offset"] is not None and page["size"] > 4096
    more = client.get(f"/api/library/{notes}/text", params={"offset": page["next_offset"]})
    assert more.status_code == 200 and "�" not in more.json()["text"]
    assert client.get(f"/api/library/{clip}/text").status_code == 422
    html = client.get(f"/api/library/{items['page.html']['id']}/text").json()
    assert html["text"] == "Visible"  # visible text only; the script is dropped
    short = client.get(f"/api/library/{notes}/preview").json()
    assert short["text"].startswith("line one") and short["truncated"] is True

    story = items["story.epub"]["id"]
    book = client.get(f"/api/library/{story}/epub").json()
    assert book["title"] == "A Book" and len(book["chapters"]) == 2
    chapter = client.get(f"/api/library/{story}/epub/1").json()
    kinds = [(b["kind"], b["text"]) for b in chapter["blocks"]]
    assert ("h1", "Ch 1") in kinds and ("p", "The end.") in kinds
    assert not any("alert" in text or "color" in text for _, text in kinds)
    assert client.get(f"/api/library/{story}/epub/9").status_code == 404
    broken = client.get(f"/api/library/{items['broken.epub']['id']}/epub")
    assert broken.status_code == 422 and broken.json()["code"] == "unsupported"


def test_drm_epub_is_refused_but_font_obfuscation_is_fine(
    client: TestClient, env_settings: Path
) -> None:
    root = env_settings / "downloads"
    root.mkdir(parents=True, exist_ok=True)
    for name, algorithm in [
        ("drm.epub", "http://www.w3.org/2001/04/xmlenc#aes128-cbc"),
        ("fonts.epub", "http://www.idpf.org/2008/embedding"),
    ]:
        path = make_epub(root / name, ["Text"])
        with zipfile.ZipFile(path, "a") as book:
            book.writestr(
                "META-INF/encryption.xml",
                '<encryption xmlns="urn:oasis:names:tc:opendocument:xmlns:container" '
                'xmlns:enc="http://www.w3.org/2001/04/xmlenc#"><enc:EncryptedData>'
                f'<enc:EncryptionMethod Algorithm="{algorithm}"/></enc:EncryptedData></encryption>',
            )
    items = _scan(client)
    drm = client.get(f"/api/library/{items['drm.epub']['id']}/epub")
    assert drm.status_code == 422 and drm.json()["code"] == "protected"
    assert client.get(f"/api/library/{items['fonts.epub']['id']}/epub").status_code == 200


def test_downloads_preview_finds_the_library_item(client: TestClient, env_settings: Path) -> None:
    root = env_settings / "downloads"
    root.mkdir(parents=True, exist_ok=True)
    (root / "song.mp3").write_bytes(b"ID3\x04\x00" + b"\x00" * 100)
    _scan(client)
    services = client.app.state.services  # type: ignore[attr-defined]

    job = services.store.create("https://music.test/song.mp3")
    services.store.update(job.id, state=JobState.done, rel_path="song.mp3")
    found = client.get(f"/api/library/by-job/{job.id}")
    assert found.status_code == 200 and found.json()["rel_path"] == "song.mp3"
    assert client.get("/api/library/by-job/nope").status_code == 404


def test_preview_needs_sign_in(make_client: Any, env_settings: Path) -> None:  # noqa: F811
    root = env_settings / "downloads"
    root.mkdir(parents=True, exist_ok=True)
    (root / "secret.pdf").write_bytes(b"%PDF-1.4 private")
    client = owner(make_client)
    for path in (
        "/api/library",
        "/api/library/x/file",
        "/api/library/x/info",
        "/api/library/x/text",
    ):
        denied = client.get(path, headers={"Range": "bytes=0-3"})
        assert denied.status_code == 401, path
        assert b"PDF" not in denied.content
    assert sign_in(client).status_code == 200
    web = {"X-Requested-With": "anyget"}
    client.post("/api/library/scan", headers=web)
    item = client.get("/api/library").json()["items"][0]
    got = client.get(f"/api/library/{item['id']}/file", headers={"Range": "bytes=0-3"})
    assert got.status_code == 206 and got.content == b"%PDF"
