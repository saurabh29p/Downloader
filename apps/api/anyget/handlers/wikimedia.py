"""Wikimedia Commons and Wikipedia file pages (".../wiki/File:Name.jpg").

The page is asked for its original file through the MediaWiki API (url, size, mime,
sha1, licence), and that file is saved as it is: a JPEG stays a JPEG, an SVG an SVG.
yt-dlp's "Wikimedia" extractor would otherwise take these pages and save them as video.
"""

from typing import Any
from urllib.parse import unquote, urlencode, urlsplit

from anyget.core.filenames import sanitize_filename
from anyget.core.net import Net
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

FILE_PREFIXES = ("File:", "Image:", "Media:")
THUMB_WIDTH = 640


def file_title(url: str) -> str | None:
    """'File:Name.jpg' for a Wikimedia or Wikipedia file page, else None."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if not (host.endswith(".wikimedia.org") or host.endswith(".wikipedia.org")):
        return None
    if host == "upload.wikimedia.org":
        return None  # already the file itself
    if not parts.path.startswith("/wiki/"):
        return None
    title = unquote(parts.path[len("/wiki/") :]).replace("_", " ")
    for prefix in FILE_PREFIXES:
        if title.startswith(prefix):
            return "File:" + title[len(prefix) :]
    return None


def kind_of(mime: str) -> str:
    major = mime.split("/", 1)[0]
    return major if major in ("image", "video", "audio") else "file"


class WikimediaHandler:
    name = "wikimedia"

    def __init__(self, net: Net) -> None:
        self.net = net
        self.http = HttpGenericHandler(net)

    def can_handle(self, url: str) -> bool:
        return file_title(url) is not None

    async def _info(self, url: str) -> dict[str, Any]:
        title = file_title(url)
        if title is None:
            raise HandlerError("unsupported", "not a Wikimedia file page")
        host = urlsplit(url).hostname
        query = urlencode(
            {
                "action": "query",
                "format": "json",
                "formatversion": "2",
                "titles": title,
                "prop": "imageinfo",
                "iiprop": "url|size|mime|sha1|extmetadata",
                "iiurlwidth": str(THUMB_WIDTH),
            }
        )
        response = await self.net.request("GET", f"https://{host}/w/api.php?{query}")
        if response.status_code >= 400:
            raise HandlerError("upstream", f"Wikimedia answered {response.status_code}")
        pages = response.json().get("query", {}).get("pages") or []
        page = pages[0] if pages else {}
        infos = page.get("imageinfo") or []
        if page.get("missing") or not infos:
            raise HandlerError("not_found", "this file is not on Wikimedia")
        info: dict[str, Any] = infos[0]
        return info

    async def probe(self, url: str, options: dict[str, Any] | None = None) -> Probe:
        info = await self._info(url)
        original = str(info["url"])
        await self.net.check(original)
        mime = str(info.get("mime") or "application/octet-stream")
        name = unquote(urlsplit(original).path.rsplit("/", 1)[-1])
        filename = sanitize_filename(name, fallback="wikimedia-file")
        ext = filename.rpartition(".")[2].lower() if "." in filename else None
        size = int(info["size"]) if info.get("size") else None
        meta = info.get("extmetadata") or {}
        licence = (meta.get("LicenseShortName") or {}).get("value")
        kind = kind_of(mime)
        return Probe(
            url=url,
            handler=self.name,
            title=filename.rsplit(".", 1)[0],
            size=size,
            thumbnail=info.get("thumburl") if kind in ("image", "video") else None,
            choices=[
                Choice(id="file", label=filename, kind="file", size=size, ext=ext, default=True)
            ],
            extra={
                "kind": kind,
                "filename": filename,
                "content_type": mime,
                "final_url": original,
                "resumable": True,
                "checksums": {"sha1": str(info["sha1"]).lower()} if info.get("sha1") else {},
                "license": licence,
                "width": info.get("width"),
                "height": info.get("height"),
            },
        )

    async def download(
        self, job: JobRef, options: dict[str, Any], progress_cb: ProgressCallback
    ) -> DownloadResult:
        probe_data = options.get("probe")
        probe = (
            Probe.model_validate(probe_data) if probe_data else await self.probe(job.url, options)
        )
        original = str(probe.extra["final_url"])
        await self.net.check(original)
        inner = JobContext(id=job.id, url=original, output_dir=job.output_dir)
        inner_probe = probe.model_copy(update={"url": original, "handler": "http"})
        return await self.http.download(
            inner, {"probe": inner_probe.model_dump(mode="json")}, progress_cb
        )
