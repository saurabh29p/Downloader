"""An example AnyGet plugin: xkcd comics.

Paste https://xkcd.com/353/ and AnyGet saves the comic image with its title, using
xkcd's public JSON API (https://xkcd.com/json.html). xkcd is licensed CC BY-NC 2.5.

A plugin is one handler, exactly like the built-in ones (see anyget.handlers.base):
`name`, `can_handle`, `probe`, `download`, and optionally `priority`. Every request
goes through AnyGet's `Net`, so the SSRF guard and limits still apply.
"""

import re
from typing import Any
from urllib.parse import urlsplit

from anyget.core.filenames import sanitize_filename
from anyget.core.net import Net
from anyget.core.settings import Settings
from anyget.handlers.base import (
    Choice,
    DownloadResult,
    HandlerError,
    JobContext,
    JobRef,
    Probe,
    ProgressCallback,
)
from anyget.handlers.http_generic import HttpGenericHandler

_COMIC = re.compile(r"^/(\d+)/?$")


class XkcdHandler:
    name = "xkcd"
    priority = 75  # before yt-dlp's generic extractor

    def __init__(self, net: Net) -> None:
        self.net = net
        self.http = HttpGenericHandler(net)

    def can_handle(self, url: str) -> bool:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower().removeprefix("www.")
        return host == "xkcd.com" and (parts.path in ("", "/") or bool(_COMIC.match(parts.path)))

    async def _comic(self, url: str) -> dict[str, Any]:
        match = _COMIC.match(urlsplit(url).path)
        api = (
            f"https://xkcd.com/{match.group(1)}/info.0.json"
            if match
            else "https://xkcd.com/info.0.json"
        )
        response = await self.net.request("GET", api)
        if response.status_code == 404:
            raise HandlerError("not_found", "xkcd has no comic with that number")
        if response.status_code >= 400:
            raise HandlerError("upstream", f"xkcd answered {response.status_code}")
        comic: dict[str, Any] = response.json()
        return comic

    async def probe(self, url: str, options: dict[str, Any] | None = None) -> Probe:
        comic = await self._comic(url)
        ext = str(comic["img"]).rsplit(".", 1)[-1]
        return Probe(
            url=url,
            handler=self.name,
            title=f"xkcd {comic['num']}: {comic['safe_title']}",
            thumbnail=str(comic["img"]),
            choices=[
                Choice(
                    id="image",
                    label=f"{comic['safe_title']}.{ext}",
                    kind="image",
                    ext=ext,
                    default=True,
                )
            ],
            extra={"kind": "file", "alt": comic.get("alt"), "license": "CC BY-NC 2.5"},
        )

    async def download(
        self, job: JobRef, options: dict[str, Any], progress_cb: ProgressCallback
    ) -> DownloadResult:
        comic = await self._comic(job.url)
        img = str(comic["img"])
        ext = img.rsplit(".", 1)[-1]
        filename = sanitize_filename(f"xkcd {comic['num']} - {comic['safe_title']}.{ext}")
        inner = JobContext(id=job.id, url=img, output_dir=job.output_dir)
        return await self.http.download(inner, {"filename": filename}, progress_cb)


def make(net: Net, settings: Settings) -> XkcdHandler:
    """The entry point AnyGet calls (see pyproject.toml)."""
    return XkcdHandler(net)
