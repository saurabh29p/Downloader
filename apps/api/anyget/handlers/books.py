"""Book pages: Project Gutenberg, Standard Ebooks, Open Library and Wikisource links.

The probe lists the formats the book exists in (best first) and the download
saves the chosen one. Open Library scans come from archive.org; borrow-only
editions are refused with a clear reason, never borrowed for you.
"""

import re
from typing import Any
from urllib.parse import quote, unquote, urlsplit

from anyget.books import gutendex, standard_ebooks
from anyget.books.base import Access, BookFormat, BookHit, SearchContext
from anyget.books.http import get_json
from anyget.books.ranker import sort_formats
from anyget.core.filenames import sanitize_filename
from anyget.core.net import Net
from anyget.core.settings import Settings
from anyget.handlers.archive_org import ArchiveOrgHandler
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

_GUTENBERG = re.compile(r"^/ebooks/(\d+)/?$")
_STANDARD = re.compile(r"^/ebooks/[^/]+/[^/]+(?:/[^/]+)?/?$")
_OPENLIB = re.compile(r"^/(works|books)/(OL\d+[WM])")
EXT = {"epub": "epub", "pdf_text": "pdf", "pdf_scan": "pdf", "txt": "txt", "html": "html"}


def book_kind(url: str) -> str | None:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower().removeprefix("www.")
    path = parts.path
    if host == "gutenberg.org" and _GUTENBERG.match(path):
        return "gutenberg"
    if host == "standardebooks.org" and _STANDARD.match(path) and "/downloads/" not in path:
        return "standard_ebooks"
    if host == "openlibrary.org" and _OPENLIB.match(path):
        return "open_library"
    if host.endswith(".wikisource.org") and path.startswith("/wiki/"):
        return "wikisource"
    return None


class BooksHandler:
    name = "books"

    def __init__(self, net: Net, settings: Settings, archive: ArchiveOrgHandler) -> None:
        self.net = net
        self.settings = settings
        self.http = HttpGenericHandler(net)
        self.archive = archive

    def can_handle(self, url: str) -> bool:
        return book_kind(url) is not None

    def _ctx(self) -> SearchContext:
        return SearchContext(net=self.net, settings=self.settings)

    async def book(self, url: str) -> BookHit:
        kind = book_kind(url)
        parts = urlsplit(url)
        if kind == "gutenberg":
            match = _GUTENBERG.match(parts.path)
            if match is None:
                raise HandlerError("unsupported", "not a Gutenberg book link")
            base = self.settings.gutendex_url.rstrip("/")
            return gutendex.to_hit(await get_json(self._ctx(), f"{base}/books/{match.group(1)}"))
        if kind == "standard_ebooks":
            path = parts.path.rstrip("/")
            name = path.rsplit("/", 1)[-1].replace("-", " ").title()
            return BookHit(
                source="standard_ebooks",
                id=path,
                title=name,
                access=Access.full_view,
                formats=[BookFormat(kind="epub", url=standard_ebooks.epub_url(path), label="EPUB")],
                details_url=url,
            )
        if kind == "open_library":
            return await self._open_library(parts.path)
        if kind == "wikisource":
            lang = (parts.hostname or "en.").split(".")[0]
            page = parts.path.removeprefix("/wiki/")
            return BookHit(
                source="wikisource",
                id=f"{lang}:{page}",
                title=unquote(page).replace("_", " "),
                language=lang,
                access=Access.full_view,
                formats=[
                    BookFormat(
                        kind="epub",
                        url=f"https://ws-export.wmcloud.org/?format=epub&lang={lang}&page={page}",
                        label="EPUB",
                    )
                ],
                details_url=url,
            )
        raise HandlerError("unsupported", "not a book page this handler knows")

    async def _open_library(self, path: str) -> BookHit:
        match = _OPENLIB.match(path)
        if match is None:
            raise HandlerError("unsupported", "not an Open Library book link")
        key = f"/{match.group(1)}/{match.group(2)}"
        field = "key" if match.group(1) == "works" else "edition_key"
        value = key if field == "key" else match.group(2)
        data = await get_json(
            self._ctx(),
            "https://openlibrary.org/search.json?fields=key,title,author_name,ia,ebook_access"
            f"&q={quote(f'{field}:{value}')}",
        )
        docs = data.get("docs") or []
        if not docs:
            raise HandlerError("not_found", "Open Library has no book like this")
        doc = docs[0]
        access = str(doc.get("ebook_access") or "")
        ia = doc.get("ia") or []
        if access in ("borrowable", "printdisabled"):
            raise HandlerError(
                "borrow_only",
                "this book can only be borrowed from Open Library's lending library",
            )
        if access != "public" or not ia:
            raise HandlerError("in_copyright", "no legal download of this book is available")
        return BookHit(
            source="open_library",
            id=key,
            title=str(doc.get("title") or key),
            authors=[str(a) for a in doc.get("author_name") or []][:3],
            access=Access.full_view,
            formats=[
                BookFormat(kind="pdf_scan", url=f"https://archive.org/details/{ia[0]}", label="PDF")
            ],
            details_url=f"https://openlibrary.org{key}",
        )

    async def probe(self, url: str, options: dict[str, Any] | None = None) -> Probe:
        hit = sort_formats(await self.book(url))
        if not hit.downloadable:
            raise HandlerError("in_copyright", "this book is not legally downloadable")
        return Probe(
            url=url,
            handler=self.name,
            title=hit.title,
            thumbnail=hit.thumbnail,
            choices=[
                Choice(
                    id=f.kind,
                    label=f.label or f.kind,
                    kind="file",
                    ext=EXT.get(f.kind),
                    size=f.size,
                    default=i == 0,
                )
                for i, f in enumerate(hit.formats)
            ],
            extra={"kind": "book", "book": hit.model_dump(mode="json")},
        )

    async def download(
        self, job: JobRef, options: dict[str, Any], progress_cb: ProgressCallback
    ) -> DownloadResult:
        hit = sort_formats(await self.book(job.url))
        if not hit.downloadable:
            raise HandlerError("in_copyright", "this book is not legally downloadable")
        wanted = options.get("files")
        chosen = [hit.formats[0]]
        if isinstance(wanted, list) and wanted:
            kinds = {str(w) for w in wanted}
            chosen = [f for f in hit.formats if f.kind in kinds]
            if not chosen:
                raise HandlerError("not_found", "this book is not available in that format")
        paths = []
        authors = f" - {hit.authors[0]}" if hit.authors else ""
        for index, fmt in enumerate(chosen):
            inner = JobContext(
                id=job.id if index == 0 else f"{job.id}-{index}",
                url=fmt.url,
                output_dir=job.output_dir,
            )
            if urlsplit(fmt.url).hostname in ("archive.org", "www.archive.org"):
                result = await self.archive.download(inner, {}, progress_cb)
            else:
                filename = sanitize_filename(f"{hit.title}{authors}.{EXT.get(fmt.kind, 'bin')}")
                result = await self.http.download(inner, {"filename": filename}, progress_cb)
            paths.extend(result.paths)
        return DownloadResult(paths=paths)
