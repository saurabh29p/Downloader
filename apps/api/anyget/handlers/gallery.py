"""Image galleries (Imgur, Flickr, Reddit, DeviantArt, Pixiv, Danbooru, …) via gallery-dl.

gallery-dl is GPL, so it only ever runs as a separate process, and only to list
the images (`-J`). The images themselves are fetched by our own HTTP path, so
resume, checksums and the SSRF guard apply. Known limit: gallery-dl's own page
requests happen in its process; we vet the gallery URL before starting it and
only route hosts gallery-dl has an extractor for.
"""

import asyncio
import json
import re
import subprocess
import sys
from functools import lru_cache
from typing import Any
from urllib.parse import urlsplit

from anyget.core.filenames import safe_join, sanitize_filename
from anyget.core.net import Net
from anyget.handlers.base import (
    Choice,
    DownloadResult,
    HandlerError,
    JobRef,
    Probe,
    ProgressCallback,
)
from anyget.handlers.http_generic import HttpGenericHandler
from anyget.handlers.multi import RemoteFile, download_many

MAX_ITEMS = 500
PROBE_TIMEOUT = 90.0
_EXAMPLE = re.compile(r"^Example\s*:\s*(\S+)", re.MULTILINE)
GALLERY_DL = [sys.executable, "-m", "gallery_dl", "--config-ignore", "--no-input"]


@lru_cache(maxsize=1)
def gallery_hosts() -> frozenset[str]:
    """Hosts gallery-dl has extractors for (from its own example URLs)."""
    try:
        out = subprocess.run(  # noqa: S603 (fixed command)
            [*GALLERY_DL, "--list-extractors"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return frozenset()
    hosts = set()
    for url in _EXAMPLE.findall(out):
        host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
        if host and host not in ("example.com", "example.org"):
            hosts.add(host)
    return frozenset(hosts)


def parse_dump(text: str) -> tuple[str, list[dict[str, Any]]]:
    """gallery-dl -J output → (title, items)."""
    try:
        messages = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HandlerError("upstream", "gallery-dl returned something unexpected") from exc
    title = ""
    items: list[dict[str, Any]] = []
    for message in messages if isinstance(messages, list) else []:
        if not isinstance(message, list) or not message:
            continue
        if message[0] == -1 and len(message) > 1:  # error message
            error = message[1] if isinstance(message[1], dict) else {}
            raise HandlerError(
                "upstream", str(error.get("message") or "gallery-dl could not read this")
            )
        if message[0] == 2 and len(message) > 1 and isinstance(message[1], dict) and not title:
            meta = message[1]
            title = str(
                meta.get("title")
                or meta.get("album")
                or meta.get("gallery")
                or meta.get("category")
                or ""
            )
        if message[0] == 3 and len(message) > 2 and isinstance(message[2], dict):
            meta = message[2]
            name = str(meta.get("filename") or meta.get("id") or len(items) + 1)
            ext = str(meta.get("extension") or "jpg")
            items.append(
                {
                    "index": len(items) + 1,
                    "url": str(message[1]),
                    "name": f"{name}.{ext}",
                    "width": meta.get("width"),
                    "height": meta.get("height"),
                }
            )
            if not title:
                title = str(meta.get("title") or meta.get("album") or meta.get("category") or "")
    return title, items[:MAX_ITEMS]


class GalleryHandler:
    name = "gallery"

    def __init__(self, net: Net) -> None:
        self.net = net
        self.http = HttpGenericHandler(net)

    def can_handle(self, url: str) -> bool:
        host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
        hosts = gallery_hosts()
        return any(host == h or host.endswith("." + h) for h in hosts)

    async def _list(self, url: str) -> tuple[str, list[dict[str, Any]]]:
        await self.net.check(url)
        process = await asyncio.create_subprocess_exec(
            *GALLERY_DL,
            "-J",
            "--range",
            f"1-{MAX_ITEMS}",
            url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), PROBE_TIMEOUT)
        except TimeoutError as exc:
            process.kill()
            raise HandlerError("upstream", "gallery-dl took too long") from exc
        if not stdout.strip():
            message = stderr.decode(errors="replace").strip().splitlines()[-1:] or ["no output"]
            raise HandlerError("upstream", message[0][:300])
        return parse_dump(stdout.decode(errors="replace"))

    async def probe(self, url: str, options: dict[str, Any] | None = None) -> Probe:
        title, items = await self._list(url)
        if not items:
            raise HandlerError("not_found", "no images found in this gallery")
        return Probe(
            url=url,
            handler=self.name,
            title=title or urlsplit(url).hostname or "gallery",
            thumbnail=items[0]["url"],
            choices=[
                Choice(id=str(i["index"]), label=i["name"], kind="image", default=True)
                for i in items
            ],
            extra={"kind": "gallery", "items": items, "count": len(items)},
        )

    async def download(
        self, job: JobRef, options: dict[str, Any], progress_cb: ProgressCallback
    ) -> DownloadResult:
        probe = options.get("probe") or {}
        items = (probe.get("extra") or {}).get("items")
        title = str(probe.get("title") or "")
        if not items:
            title, items = await self._list(job.url)
        wanted = options.get("files")
        if isinstance(wanted, list) and wanted:
            ids = {str(w) for w in wanted}
            items = [i for i in items if str(i["index"]) in ids]
        if not items:
            raise HandlerError("not_found", "none of the chosen images are in this gallery")
        files = [
            RemoteFile(
                url=str(i["url"]),
                name=f"{int(i['index']):03d} {i['name']}",
                headers={"Referer": job.url},
            )
            for i in items
        ]
        folder = safe_join(job.output_dir, sanitize_filename(title or "gallery"))
        folder.mkdir(parents=True, exist_ok=True)
        return await download_many(self.http, job, files, folder, progress_cb)
