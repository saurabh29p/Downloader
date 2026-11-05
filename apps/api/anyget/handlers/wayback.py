"""Wayback Machine: list snapshots (CDX) and download the original bytes (`id_`)."""

import re
from typing import Any
from urllib.parse import quote, urlsplit

from pydantic import BaseModel

from anyget.core.filenames import sanitize_filename
from anyget.core.net import Net
from anyget.handlers.base import (
    DownloadResult,
    HandlerError,
    JobContext,
    JobRef,
    Probe,
    ProgressCallback,
)
from anyget.handlers.http_generic import HttpGenericHandler

WAYBACK_HOST = "web.archive.org"
# /web/<14-digit timestamp, optionally with a modifier like id_ or im_>/<original url>
_SNAPSHOT = re.compile(r"^/web/(\d{4,14})(?:[a-z]{2}_)?/(.+)$")


class Snapshot(BaseModel):
    timestamp: str
    original: str
    mimetype: str | None = None
    status: str | None = None
    length: int | None = None
    raw_url: str
    view_url: str


class SnapshotList(BaseModel):
    url: str
    total: int
    years: dict[str, int]
    snapshots: list[Snapshot]


def raw_url(timestamp: str, original: str) -> str:
    """The archived bytes exactly as captured, without the Wayback toolbar."""
    return f"https://{WAYBACK_HOST}/web/{timestamp}id_/{original}"


def parse_snapshot_url(url: str) -> tuple[str, str]:
    parts = urlsplit(url)
    path = parts.path + (f"?{parts.query}" if parts.query else "")
    match = _SNAPSHOT.match(path)
    if not match:
        raise HandlerError("unsupported", "not a Wayback Machine snapshot link")
    timestamp, original = match.group(1), match.group(2)
    if not original.startswith(("http://", "https://")):
        original = "http://" + original.lstrip("/")
    return timestamp, original


async def list_snapshots(
    net: Net,
    url: str,
    *,
    year_from: int | None = None,
    year_to: int | None = None,
    limit: int = 500,
) -> SnapshotList:
    """CDX index for a URL, one row per distinct capture (collapse=digest)."""
    query = (
        f"url={quote(url, safe='')}&output=json&collapse=digest"
        "&fl=timestamp,original,mimetype,statuscode,length"
        f"&limit={min(max(limit, 1), 5000)}"
    )
    if year_from:
        query += f"&from={year_from}"
    if year_to:
        query += f"&to={year_to}"
    response = await net.request("GET", f"https://{WAYBACK_HOST}/cdx/search/cdx?{query}")
    if response.status_code >= 400:
        raise HandlerError("upstream", f"the Wayback Machine answered {response.status_code}")
    rows: list[list[str]] = response.json() if response.content.strip() else []
    snapshots: list[Snapshot] = []
    years: dict[str, int] = {}
    for row in rows[1:]:  # first row is the header
        if len(row) < 5:
            continue
        timestamp, original, mimetype, status, length = row[:5]
        years[timestamp[:4]] = years.get(timestamp[:4], 0) + 1
        snapshots.append(
            Snapshot(
                timestamp=timestamp,
                original=original,
                mimetype=mimetype or None,
                status=status if status != "-" else None,
                length=int(length) if length.isdigit() else None,
                raw_url=raw_url(timestamp, original),
                view_url=f"https://{WAYBACK_HOST}/web/{timestamp}/{original}",
            )
        )
    return SnapshotList(url=url, total=len(snapshots), years=years, snapshots=snapshots)


class WaybackHandler:
    name = "wayback"

    def __init__(self, net: Net) -> None:
        self.http = HttpGenericHandler(net)

    def can_handle(self, url: str) -> bool:
        parts = urlsplit(url)
        return (parts.hostname or "").lower() == WAYBACK_HOST and bool(_SNAPSHOT.match(parts.path))

    @staticmethod
    def _filename(timestamp: str, original: str, base: str) -> str:
        host = urlsplit(original).hostname or "snapshot"
        stem, dot, ext = base.rpartition(".")
        if not dot or base == host:
            stem, ext = base, ""
        stamp = (
            f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}"
            if len(timestamp) >= 8
            else timestamp
        )
        name = f"{host} {stem} {stamp}" if stem and stem != host else f"{host} {stamp}"
        return sanitize_filename(f"{name}.{ext}" if ext else name)

    async def probe(self, url: str, options: dict[str, Any] | None = None) -> Probe:
        timestamp, original = parse_snapshot_url(url)
        raw = raw_url(timestamp, original)
        probe = await self.http.probe(raw, {"allow_html": True})
        filename = self._filename(timestamp, original, str(probe.extra["filename"]))
        extra = {
            **probe.extra,
            "filename": filename,
            "kind": "wayback_snapshot",
            "timestamp": timestamp,
            "original": original,
            "raw_url": raw,
        }
        return Probe(
            url=url,
            handler=self.name,
            title=filename,
            size=probe.size,
            choices=probe.choices,
            extra=extra,
        )

    async def download(
        self, job: JobRef, options: dict[str, Any], progress_cb: ProgressCallback
    ) -> DownloadResult:
        timestamp, original = parse_snapshot_url(job.url)
        probe_data = options.get("probe")
        if not probe_data:
            probe_data = (await self.probe(job.url)).model_dump(mode="json")
        raw = raw_url(timestamp, original)
        # The HTTP handler fetches the raw capture; keep our filename.
        inner = JobContext(id=job.id, url=raw, output_dir=job.output_dir)
        options = {
            "probe": {**probe_data, "url": raw},
            "filename": probe_data["extra"]["filename"],
            "allow_html": True,
        }
        return await self.http.download(inner, options, progress_cb)
