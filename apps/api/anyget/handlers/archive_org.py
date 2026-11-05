"""archive.org items: metadata, file picker, "all of format X", search and deep paging.

Uses the public HTTP APIs only (the AGPL `ia` tool is not imported). Every request
goes through core.net.Net, so the SSRF guard, the contact User-Agent and 429/503
backoff apply; the queue limits archive.org to 2 parallel downloads.
Access-restricted, lending (borrow-only) and dark items are reported, never bypassed.
"""

import re
import time
from typing import Any
from urllib.parse import quote, unquote, urlsplit

from pydantic import BaseModel, Field

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

ARCHIVE_HOSTS = {"archive.org", "www.archive.org"}
METADATA_TTL = 600.0
_ID = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
SEARCH_FIELDS = ("identifier", "title", "mediatype", "creator", "year", "date", "downloads")

# Preferred formats when the user does not pick files, per media type.
DEFAULT_FORMATS: dict[str, tuple[str, ...]] = {
    "texts": ("Text PDF", "EPUB", "PDF", "DjVu"),
    "audio": ("VBR MP3", "MP3", "Ogg Vorbis", "Flac"),
    "etree": ("VBR MP3", "MP3", "Flac"),
    "movies": ("h.264", "MPEG4", "h.264 IA", "512Kb MPEG4", "Ogg Video"),
    "image": ("JPEG", "PNG"),
}
# Housekeeping files every item has; never offered by default.
SKIP_FORMATS = {
    "Metadata",
    "Item Tile",
    "Archive BitTorrent",
    "JSON",
    "Thumbnail",
    "Columbia Peaks",
    "Spectrogram",
    "PNG Thumbnail",
}


class ArchiveFile(BaseModel):
    name: str
    format: str
    size: int | None = None
    md5: str | None = None
    source: str | None = None
    private: bool = False


class ArchiveItem(BaseModel):
    identifier: str
    title: str
    mediatype: str | None = None
    creator: str | None = None
    date: str | None = None
    language: str | None = None
    collections: list[str] = Field(default_factory=list)
    description: str | None = None
    restricted: str | None = None  # None, "borrow_only", "restricted", "dark"
    item_size: int | None = None
    files: list[ArchiveFile] = Field(default_factory=list)
    # Storage servers holding the item (d2 first: /download/ usually sends us to d1).
    servers: list[str] = Field(default_factory=list)
    dir: str | None = None

    @property
    def thumbnail(self) -> str:
        return f"https://archive.org/services/img/{self.identifier}"


class SearchHit(BaseModel):
    identifier: str
    title: str
    mediatype: str | None = None
    creator: str | None = None
    year: str | None = None
    downloads: int | None = None
    thumbnail: str


class SearchPage(BaseModel):
    total: int
    items: list[SearchHit]
    page: int | None = None
    cursor: str | None = None


def _first(value: Any) -> str | None:
    if isinstance(value, list):
        return str(value[0]) if value else None
    return str(value) if value not in (None, "") else None


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)] if value else []


def parse_item_url(url: str) -> tuple[str, str | None]:
    """https://archive.org/details/<id>[/...] or /download/<id>[/<file>] → (id, file)."""
    parts = urlsplit(url)
    segments = [unquote(s) for s in parts.path.split("/") if s]
    if len(segments) < 2 or segments[0] not in ("details", "download"):
        raise HandlerError("unsupported", "not an archive.org item link")
    identifier = segments[1]
    if not _ID.match(identifier):
        raise HandlerError("unsupported", "not a valid archive.org identifier")
    file_name = "/".join(segments[2:]) if segments[0] == "download" and len(segments) > 2 else None
    return identifier, file_name


def parse_metadata(data: dict[str, Any]) -> ArchiveItem:
    if not data or "metadata" not in data:
        raise HandlerError("not_found", "archive.org has no item with this identifier")
    meta = data["metadata"]
    restricted: str | None = None
    if data.get("is_dark"):
        restricted = "dark"
    elif str(meta.get("access-restricted-item", "")).lower() == "true":
        collections = {c.lower() for c in _as_list(meta.get("collection"))}
        lending = {"inlibrary", "printdisabled", "lendinglibrary"}
        restricted = "borrow_only" if collections & lending else "restricted"
    files = [
        ArchiveFile(
            name=str(f["name"]),
            format=str(f.get("format") or ""),
            size=int(f["size"]) if str(f.get("size", "")).isdigit() else None,
            md5=f.get("md5"),
            source=f.get("source"),
            private=str(f.get("private", "")).lower() == "true",
        )
        for f in data.get("files") or []
        if f.get("name")
    ]
    return ArchiveItem(
        identifier=str(meta.get("identifier") or ""),
        title=_first(meta.get("title")) or str(meta.get("identifier") or ""),
        mediatype=_first(meta.get("mediatype")),
        creator=_first(meta.get("creator")),
        date=_first(meta.get("date")),
        language=_first(meta.get("language")),
        collections=_as_list(meta.get("collection")),
        description=(_first(meta.get("description")) or "")[:2000] or None,
        restricted=restricted,
        item_size=data.get("item_size"),
        files=files,
        servers=list(
            dict.fromkeys(
                str(s)
                for s in [data.get("d2"), data.get("d1"), *(data.get("workable_servers") or [])]
                if s and str(s).endswith(".archive.org")
            )
        ),
        dir=str(data["dir"]) if data.get("dir") else None,
    )


def downloadable(item: ArchiveItem) -> list[ArchiveFile]:
    return [f for f in item.files if not f.private and f.format not in SKIP_FORMATS]


def default_files(item: ArchiveItem) -> list[ArchiveFile]:
    """The files to fetch when the user did not choose: best format for the media type."""
    files = downloadable(item)
    for fmt in DEFAULT_FORMATS.get(item.mediatype or "", ()):
        chosen = [f for f in files if f.format == fmt]
        if chosen:
            return chosen
    originals = [f for f in files if f.source == "original"]
    if originals:
        return [max(originals, key=lambda f: f.size or 0)]
    return files[:1]


def format_summary(files: list[ArchiveFile]) -> list[dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for f in files:
        entry = summary.setdefault(f.format, {"format": f.format, "count": 0, "size": 0})
        entry["count"] += 1
        entry["size"] += f.size or 0
    return sorted(summary.values(), key=lambda e: (-e["count"], e["format"]))


def _escape(term: str) -> str:
    return term.replace("\\", "\\\\").replace('"', '\\"')


def build_query(
    q: str,
    *,
    mediatype: str | None = None,
    collection: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    language: str | None = None,
    creator: str | None = None,
) -> str:
    """advancedsearch/scrape query with the page's filters (values are quoted)."""
    parts = [f"({q.strip()})"] if q.strip() else []
    if mediatype:
        parts.append(f'mediatype:"{_escape(mediatype)}"')
    if collection:
        parts.append(f'collection:"{_escape(collection)}"')
    if language:
        parts.append(f'language:"{_escape(language)}"')
    if creator:
        parts.append(f'creator:"{_escape(creator)}"')
    if year_from or year_to:
        parts.append(f"year:[{year_from or 0} TO {year_to or 9999}]")
    return " AND ".join(parts) or "*:*"


def _hit(doc: dict[str, Any]) -> SearchHit:
    identifier = str(doc.get("identifier"))
    downloads = doc.get("downloads")
    return SearchHit(
        identifier=identifier,
        title=_first(doc.get("title")) or identifier,
        mediatype=_first(doc.get("mediatype")),
        creator=_first(doc.get("creator")),
        year=_first(doc.get("year")) or (_first(doc.get("date")) or "")[:4] or None,
        downloads=int(downloads) if isinstance(downloads, int | float) else None,
        thumbnail=f"https://archive.org/services/img/{identifier}",
    )


async def search(net: Net, query: str, *, page: int = 1, rows: int = 50) -> SearchPage:
    """One page of advancedsearch results (for the first pages of a search)."""
    params = "&".join(
        [
            f"q={quote(query)}",
            *(f"fl[]={f}" for f in SEARCH_FIELDS),
            f"rows={rows}",
            f"page={page}",
            "output=json",
            "sort[]=downloads+desc",
        ]
    )
    response = await net.request("GET", f"https://archive.org/advancedsearch.php?{params}")
    if response.status_code >= 400:
        raise HandlerError("upstream", f"archive.org search answered {response.status_code}")
    body = response.json().get("response", {})
    return SearchPage(
        total=int(body.get("numFound") or 0),
        page=page,
        items=[_hit(d) for d in body.get("docs") or [] if d.get("identifier")],
    )


async def scrape(
    net: Net, query: str, *, cursor: str | None = None, count: int = 100
) -> SearchPage:
    """Cursor paging (the scrape API) for walking big collections."""
    url = (
        "https://archive.org/services/search/v1/scrape?"
        f"q={quote(query)}&fields={','.join(SEARCH_FIELDS)}&count={max(100, count)}"
    )
    if cursor:
        url += f"&cursor={quote(cursor)}"
    response = await net.request("GET", url)
    if response.status_code >= 400:
        raise HandlerError("upstream", f"archive.org search answered {response.status_code}")
    body = response.json()
    return SearchPage(
        total=int(body.get("total") or 0),
        cursor=body.get("cursor"),
        items=[_hit(d) for d in body.get("items") or [] if d.get("identifier")],
    )


class ArchiveOrgHandler:
    name = "archive_org"

    def __init__(self, net: Net) -> None:
        self.net = net
        self.http = HttpGenericHandler(net)
        self._cache: dict[str, tuple[float, ArchiveItem]] = {}

    def can_handle(self, url: str) -> bool:
        parts = urlsplit(url)
        if (parts.hostname or "").lower() not in ARCHIVE_HOSTS:
            return False
        return parts.path.startswith(("/details/", "/download/"))

    async def item(self, identifier: str) -> ArchiveItem:
        """Item metadata, cached for 10 minutes (archive.org asks clients to cache)."""
        if not _ID.match(identifier):
            raise HandlerError("unsupported", "not a valid archive.org identifier")
        cached = self._cache.get(identifier)
        if cached and time.monotonic() - cached[0] < METADATA_TTL:
            return cached[1]
        response = await self.net.request("GET", f"https://archive.org/metadata/{identifier}")
        if response.status_code == 404:
            raise HandlerError("not_found", "archive.org has no item with this identifier")
        if response.status_code >= 400:
            raise HandlerError("upstream", f"archive.org answered {response.status_code}")
        item = parse_metadata(response.json())
        self._cache[identifier] = (time.monotonic(), item)
        if len(self._cache) > 256:
            self._cache.pop(next(iter(self._cache)))
        return item

    @staticmethod
    def _check_access(item: ArchiveItem) -> None:
        if item.restricted == "borrow_only":
            raise HandlerError(
                "borrow_only",
                "this item can only be borrowed from the archive.org lending library",
            )
        if item.restricted == "restricted":
            raise HandlerError("restricted", "archive.org restricts access to this item")
        if item.restricted == "dark":
            raise HandlerError("unavailable", "this item is not publicly available")

    async def probe(self, url: str, options: dict[str, Any] | None = None) -> Probe:
        identifier, file_name = parse_item_url(url)
        item = await self.item(identifier)
        self._check_access(item)
        files = downloadable(item)
        if not files:
            raise HandlerError("unavailable", "this item has no downloadable files")
        selected = [f.name for f in default_files(item)]
        if file_name:
            match = next((f for f in files if f.name == file_name), None)
            if match is None:
                raise HandlerError("not_found", "this file is not part of the item")
            selected = [match.name]
        size = sum(f.size or 0 for f in files if f.name in selected) or None
        return Probe(
            url=url,
            handler=self.name,
            title=item.title,
            size=size,
            thumbnail=item.thumbnail,
            choices=[
                Choice(
                    id=f.name,
                    label=f.name,
                    kind=f.format or "file",
                    size=f.size,
                    ext=f.name.rpartition(".")[2].lower() if "." in f.name else None,
                    default=f.name in selected,
                )
                for f in files
            ],
            extra={
                "kind": "archive_item",
                "identifier": item.identifier,
                "mediatype": item.mediatype,
                "creator": item.creator,
                "date": item.date,
                "language": item.language,
                "collections": item.collections,
                "description": item.description,
                "files": [f.model_dump() for f in files],
                "formats": format_summary(files),
                "selected": selected,
            },
        )

    def _pick(
        self, item: ArchiveItem, options: dict[str, Any], url_file: str | None
    ) -> list[ArchiveFile]:
        files = downloadable(item)
        names = options.get("files")
        if isinstance(names, list) and names:
            wanted = {str(n) for n in names}
            chosen = [f for f in files if f.name in wanted]
            if not chosen:
                raise HandlerError("not_found", "none of the chosen files are in this item")
            return chosen
        fmt = options.get("format")
        if isinstance(fmt, str) and fmt:
            chosen = [f for f in files if f.format == fmt]
            if not chosen:
                raise HandlerError("not_found", f"this item has no {fmt} files")
            return chosen
        if url_file:
            return [f for f in files if f.name == url_file]
        return default_files(item)

    async def download(
        self, job: JobRef, options: dict[str, Any], progress_cb: ProgressCallback
    ) -> DownloadResult:
        identifier, url_file = parse_item_url(job.url)
        item = await self.item(identifier)
        self._check_access(item)
        files = self._pick(item, options, url_file)
        folder = safe_join(job.output_dir, sanitize_filename(item.identifier))
        folder.mkdir(parents=True, exist_ok=True)

        remote = [
            RemoteFile(
                url=f"https://archive.org/download/{quote(item.identifier)}/{quote(f.name)}",
                name=f.name.replace("/", " - "),
                size=f.size,
                md5=f.md5,
                mirrors=tuple(
                    f"https://{server}{quote(item.dir)}/{quote(f.name)}" for server in item.servers
                )
                if item.dir
                else (),
            )
            for f in files
        ]
        return await download_many(self.http, job, remote, folder, progress_cb)
