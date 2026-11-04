"""Direct file downloads over HTTP(S) with Range resume and checksum checks."""

import base64
import binascii
import contextlib
import hashlib
import re
from email.message import Message
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlsplit

import httpx

from anyget.core.filenames import safe_join, sanitize_filename, unique_path
from anyget.core.net import Net
from anyget.handlers.base import (
    Choice,
    DownloadResult,
    HandlerError,
    JobRef,
    Probe,
    Progress,
    ProgressCallback,
    part_path,
)

HTML_TYPES = ("text/html", "application/xhtml+xml")
_CONTENT_RANGE = re.compile(r"bytes (\d+)-(\d+)/(\d+|\*)")


def filename_from_disposition(header: str | None) -> str | None:
    """Filename from Content-Disposition, including RFC 6266 filename*=UTF-8''…"""
    if not header:
        return None
    message = Message()
    message["content-disposition"] = header
    name = message.get_filename()
    if not name:
        return None
    return PurePosixPath(name.replace("\\", "/")).name or None


def filename_from_url(url: str) -> str | None:
    path = unquote(urlsplit(url).path)
    name = PurePosixPath(path).name
    return name or None


def checksums_from_headers(headers: httpx.Headers) -> dict[str, str]:
    """md5/sha1 the server advertises (Content-MD5, Digest, x-goog-hash)."""
    found: dict[str, str] = {}

    def add_b64(algo: str, value: str) -> None:
        with contextlib.suppress(binascii.Error, ValueError):
            found[algo] = base64.b64decode(value.strip(), validate=True).hex()

    if "content-md5" in headers:
        add_b64("md5", headers["content-md5"])
    for header in ("digest", "x-goog-hash"):
        for part in headers.get(header, "").split(","):
            algo, _, value = part.strip().partition("=")
            algo = algo.lower().replace("-", "")
            if algo == "md5":
                add_b64("md5", value)
            elif algo in ("sha", "sha1"):
                add_b64("sha1", value)
    return found


def _total_from(response: httpx.Response) -> int | None:
    match = _CONTENT_RANGE.match(response.headers.get("content-range", ""))
    if match and match.group(3) != "*":
        return int(match.group(3))
    if response.status_code == 200 and "content-length" in response.headers:
        length = response.headers["content-length"]
        return int(length) if length.isdigit() else None
    return None


def _hash_file(path: Path, algo: str) -> str:
    with path.open("rb") as fh:
        return hashlib.file_digest(fh, algo).hexdigest()


class HttpGenericHandler:
    """Fallback for any http(s) link that serves a file."""

    name = "http"

    def __init__(self, net: Net) -> None:
        self.net = net

    def can_handle(self, url: str) -> bool:
        return urlsplit(url).scheme in ("http", "https")

    async def probe(self, url: str) -> Probe:
        response = await self.net.request("HEAD", url)
        if response.status_code in (403, 405, 501) or response.status_code >= 500:
            # Some servers refuse HEAD; ask for the first byte instead.
            async with self.net.stream("GET", url, headers={"Range": "bytes=0-0"}) as streamed:
                response = streamed
        if response.status_code == 404:
            raise HandlerError("not_found", "the server says this file does not exist (404)")
        if response.status_code >= 400:
            raise HandlerError("upstream", f"the server answered {response.status_code}")

        content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
        if content_type in HTML_TYPES:
            raise HandlerError(
                "unsupported",
                "this is a web page, not a direct file link. "
                "Video sites and page saving arrive in later versions.",
            )
        final_url = str(response.url)
        host = urlsplit(final_url).hostname or "download"
        raw_name = (
            filename_from_disposition(response.headers.get("content-disposition"))
            or filename_from_url(final_url)
            or host
        )
        filename = sanitize_filename(raw_name, fallback=host)
        size = _total_from(response)
        resumable = (
            response.headers.get("accept-ranges", "").lower() == "bytes"
            or response.status_code == 206
        )
        ext = filename.rpartition(".")[2].lower() if "." in filename else None
        extra: dict[str, Any] = {
            "filename": filename,
            "content_type": content_type or None,
            "resumable": resumable,
            "final_url": final_url,
            "checksums": checksums_from_headers(response.headers),
        }
        return Probe(
            url=url,
            handler=self.name,
            title=filename,
            size=size,
            choices=[
                Choice(id="file", label=filename, kind="file", size=size, ext=ext, default=True)
            ],
            extra=extra,
        )

    async def download(
        self, job: JobRef, options: dict[str, Any], progress_cb: ProgressCallback
    ) -> DownloadResult:
        probe_data = options.get("probe")
        probe = Probe.model_validate(probe_data) if probe_data else await self.probe(job.url)
        filename = sanitize_filename(str(options.get("filename") or probe.extra["filename"]))
        expected: dict[str, str] = {
            **probe.extra.get("checksums", {}),
            **{k: str(v).lower() for k, v in options.items() if k in ("md5", "sha1") and v},
        }

        job.output_dir.mkdir(parents=True, exist_ok=True)
        part = part_path(job.output_dir, job.id)
        existing = part.stat().st_size if part.exists() else 0
        total = probe.size
        if total is not None and existing > total:
            part.unlink()
            existing = 0

        if total is None or existing < total:
            existing, total = await self._fetch(job.url, part, existing, total, progress_cb)

        size = part.stat().st_size
        if total is not None and size != total:
            raise HandlerError("incomplete", f"download stopped at {size} of {total} bytes")

        checksum_ok: bool | None = None
        for algo, value in expected.items():
            actual = _hash_file(part, algo)
            if actual != value.lower():
                part.unlink()
                raise HandlerError("checksum", f"{algo} mismatch: expected {value}, got {actual}")
            checksum_ok = True

        final = unique_path(safe_join(job.output_dir, filename))
        part.rename(final)
        progress_cb(Progress(downloaded=size, total=size))
        return DownloadResult(paths=[final], checksum_ok=checksum_ok)

    async def _fetch(
        self,
        url: str,
        part: Path,
        existing: int,
        total: int | None,
        progress_cb: ProgressCallback,
    ) -> tuple[int, int | None]:
        headers = {"Range": f"bytes={existing}-"} if existing else None
        async with self.net.stream("GET", url, headers=headers) as response:
            if response.status_code == 416 and existing and total in (None, existing):
                return existing, existing  # already complete
            if response.status_code >= 400:
                raise HandlerError("upstream", f"the server answered {response.status_code}")
            if response.status_code == 206 and existing:
                match = _CONTENT_RANGE.match(response.headers.get("content-range", ""))
                if not match or int(match.group(1)) != existing:
                    raise HandlerError("upstream", "the server sent the wrong part of the file")
                mode = "ab"
            else:
                existing, mode = 0, "wb"  # server ignored Range: start over
            total = _total_from(response) or total
            downloaded = existing
            progress_cb(Progress(downloaded=downloaded, total=total))
            with part.open(mode) as fh:
                async for chunk in response.aiter_bytes():
                    fh.write(chunk)
                    downloaded += len(chunk)
                    progress_cb(Progress(downloaded=downloaded, total=total))
        return downloaded, total
