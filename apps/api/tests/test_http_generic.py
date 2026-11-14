import hashlib
from base64 import b64encode
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import respx

from anyget.core.net import Net
from anyget.core.settings import Settings
from anyget.handlers.base import HandlerError, JobContext, Progress, part_path
from anyget.handlers.http_generic import (
    HttpGenericHandler,
    checksums_from_headers,
    filename_from_disposition,
)

DATA = bytes(range(256)) * 400  # 102,400 bytes
MD5 = hashlib.md5(DATA).hexdigest()
URL = "https://files.test/dir/archive.bin"


@pytest.fixture
async def handler(settings: Settings) -> AsyncIterator[HttpGenericHandler]:
    net = Net(settings)
    yield HttpGenericHandler(net)
    await net.aclose()


def job(tmp_path: Path, job_id: str = "job1") -> JobContext:
    return JobContext(id=job_id, url=URL, output_dir=tmp_path / "out")


def head_ok(**headers: str) -> httpx.Response:
    return httpx.Response(
        200,
        headers={"Content-Length": str(len(DATA)), "Accept-Ranges": "bytes", **headers},
    )


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ('attachment; filename="report.pdf"', "report.pdf"),
        (
            "attachment; filename*=UTF-8''"
            "%E0%A4%AA%E0%A5%81%E0%A4%B8%E0%A5%8D%E0%A4%A4%E0%A4%95.epub",
            "पुस्तक.epub",
        ),
        ('attachment; filename="../../evil.sh"', "evil.sh"),
        ("inline", None),
        (None, None),
    ],
)
def test_content_disposition(header: str | None, expected: str | None) -> None:
    assert filename_from_disposition(header) == expected


def test_checksum_headers() -> None:
    digest = b64encode(hashlib.md5(b"x").digest()).decode()
    headers = httpx.Headers({"Content-MD5": digest})
    assert checksums_from_headers(headers) == {"md5": hashlib.md5(b"x").hexdigest()}
    goog = httpx.Headers({"x-goog-hash": f"crc32c=AAAA, md5={digest}"})
    assert checksums_from_headers(goog)["md5"] == hashlib.md5(b"x").hexdigest()


@respx.mock
async def test_probe(handler: HttpGenericHandler) -> None:
    respx.head(URL).mock(
        return_value=head_ok(
            **{
                "Content-Type": "application/octet-stream",
                "Content-Disposition": 'attachment; filename="nice name.bin"',
            }
        )
    )
    probe = await handler.probe(URL)
    assert probe.title == "nice name.bin"
    assert probe.size == len(DATA)
    assert probe.extra["resumable"] is True
    assert probe.choices[0].ext == "bin"


@respx.mock
async def test_probe_falls_back_to_range_get(handler: HttpGenericHandler) -> None:
    respx.head(URL).mock(return_value=httpx.Response(405))
    respx.get(URL).mock(
        return_value=httpx.Response(
            206, headers={"Content-Range": f"bytes 0-0/{len(DATA)}"}, content=DATA[:1]
        )
    )
    probe = await handler.probe(URL)
    assert probe.size == len(DATA)
    assert probe.extra["resumable"] is True


@respx.mock
async def test_html_becomes_a_web_page_probe(handler: HttpGenericHandler) -> None:
    respx.head(URL).mock(return_value=httpx.Response(200, headers={"Content-Type": "text/html"}))
    respx.get(URL).mock(
        return_value=httpx.Response(
            200, headers={"Content-Type": "text/html"}, text="<title>T</title>"
        )
    )
    probe = await handler.probe(URL)
    assert probe.extra["kind"] == "webpage"
    allowed = await handler.probe(URL, {"allow_html": True})  # Wayback keeps raw HTML
    assert allowed.extra.get("kind") is None and allowed.extra["filename"].endswith(".html")


@respx.mock
async def test_probe_404(handler: HttpGenericHandler) -> None:
    respx.head(URL).mock(return_value=httpx.Response(404))
    with pytest.raises(HandlerError) as info:
        await handler.probe(URL)
    assert info.value.code == "not_found"


@respx.mock
async def test_download_with_md5(handler: HttpGenericHandler, tmp_path: Path) -> None:
    respx.head(URL).mock(
        return_value=head_ok(**{"Content-MD5": b64encode(bytes.fromhex(MD5)).decode()})
    )
    respx.get(URL).mock(return_value=httpx.Response(200, content=DATA))
    seen: list[Progress] = []
    result = await handler.download(job(tmp_path), {}, seen.append)
    assert result.paths[0].name == "archive.bin"
    assert result.paths[0].read_bytes() == DATA
    assert result.checksum_ok is True
    assert seen[-1].downloaded == len(DATA)
    assert not part_path(tmp_path / "out", "job1").exists()


@respx.mock
async def test_resume_after_interruption(handler: HttpGenericHandler, tmp_path: Path) -> None:
    half = len(DATA) // 2

    async def broken_body() -> AsyncIterator[bytes]:
        yield DATA[:half]
        raise httpx.ReadError("connection reset")

    def serve(request: httpx.Request) -> httpx.Response:
        range_header = request.headers.get("range")
        if range_header is None:
            return httpx.Response(
                200, headers={"Content-Length": str(len(DATA))}, content=broken_body()
            )
        start = int(range_header.removeprefix("bytes=").rstrip("-"))
        return httpx.Response(
            206,
            headers={"Content-Range": f"bytes {start}-{len(DATA) - 1}/{len(DATA)}"},
            content=DATA[start:],
        )

    respx.head(URL).mock(return_value=head_ok())
    get = respx.get(URL).mock(side_effect=serve)

    with pytest.raises(httpx.ReadError):
        await handler.download(job(tmp_path), {"md5": MD5}, lambda _p: None)
    part = part_path(tmp_path / "out", "job1")
    assert part.stat().st_size == half

    result = await handler.download(job(tmp_path), {"md5": MD5}, lambda _p: None)
    assert get.calls[-1].request.headers["range"] == f"bytes={half}-"
    assert result.paths[0].read_bytes() == DATA
    assert result.checksum_ok is True


@respx.mock
async def test_server_ignoring_range_restarts(handler: HttpGenericHandler, tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    part_path(out, "job1").write_bytes(b"garbage")
    respx.head(URL).mock(return_value=head_ok())
    respx.get(URL).mock(return_value=httpx.Response(200, content=DATA))
    result = await handler.download(job(tmp_path), {}, lambda _p: None)
    assert result.paths[0].read_bytes() == DATA


@respx.mock
async def test_md5_mismatch_fails(handler: HttpGenericHandler, tmp_path: Path) -> None:
    respx.head(URL).mock(return_value=head_ok())
    respx.get(URL).mock(return_value=httpx.Response(200, content=DATA))
    with pytest.raises(HandlerError) as info:
        await handler.download(job(tmp_path), {"md5": "0" * 32}, lambda _p: None)
    assert info.value.code == "checksum"
    assert not part_path(tmp_path / "out", "job1").exists()


@respx.mock
async def test_short_body_is_incomplete(handler: HttpGenericHandler, tmp_path: Path) -> None:
    respx.head(URL).mock(return_value=head_ok())
    respx.get(URL).mock(
        return_value=httpx.Response(
            200, headers={"Content-Length": str(len(DATA))}, content=DATA[:10]
        )
    )
    with pytest.raises((HandlerError, httpx.HTTPError)):
        await handler.download(job(tmp_path), {}, lambda _p: None)


@respx.mock
async def test_empty_file_is_saved(handler: HttpGenericHandler, tmp_path: Path) -> None:
    # A 0-byte file is a real file (an empty .keep, a placeholder): save it, don't crash.
    respx.head(URL).mock(return_value=httpx.Response(200, headers={"Content-Length": "0"}))
    get = respx.get(URL).mock(return_value=httpx.Response(200, content=b""))
    result = await handler.download(job(tmp_path), {}, lambda _p: None)
    assert get.called
    assert result.paths[0].name == "archive.bin"
    assert result.paths[0].read_bytes() == b""
    assert not part_path(tmp_path / "out", "job1").exists()


@respx.mock
async def test_existing_file_gets_new_name(handler: HttpGenericHandler, tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    (out / "archive.bin").write_bytes(b"old")
    respx.head(URL).mock(return_value=head_ok())
    respx.get(URL).mock(return_value=httpx.Response(200, content=DATA))
    result = await handler.download(job(tmp_path), {}, lambda _p: None)
    assert result.paths[0].name == "archive (1).bin"
    assert (out / "archive.bin").read_bytes() == b"old"


@respx.mock
async def test_compressed_response_is_saved_decoded(
    handler: HttpGenericHandler, tmp_path: Path
) -> None:
    import gzip

    text = b"Hello World!\n"
    packed = gzip.compress(text)
    encoded = {"Content-Encoding": "gzip", "Content-Length": str(len(packed))}
    head = respx.head(URL).mock(return_value=httpx.Response(200, headers=encoded))
    get = respx.get(URL).mock(return_value=httpx.Response(200, headers=encoded, content=packed))
    probe = await handler.probe(URL)
    assert probe.size is None  # a compressed length is not the file size
    result = await handler.download(job(tmp_path), {}, lambda _p: None)
    assert result.paths[0].read_bytes() == text
    assert head.calls[0].request.headers["accept-encoding"] == "identity"
    assert get.calls[-1].request.headers["accept-encoding"] == "identity"
